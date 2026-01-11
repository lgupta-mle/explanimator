"""
Smart document chunking for Manim documentation.

Chunks documents into semantically meaningful pieces optimized for retrieval,
while preserving code examples and maintaining context.
"""

import re
import json
from typing import List, Dict, Any
from pathlib import Path
import tiktoken
from research_viz.schemas.manim_docs_schemas import (
    DocPage, DocChunk, CodeExample, MethodSignature
)


class ManimDocsChunker:
    """Smart chunking for Manim documentation."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        preserve_code_blocks: bool = True,
        encoding_name: str = "cl100k_base"
    ):
        """
        Args:
            chunk_size: Target size in tokens
            chunk_overlap: Overlap between chunks in tokens
            preserve_code_blocks: Never split code examples
            encoding_name: Tiktoken encoding to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.preserve_code_blocks = preserve_code_blocks
        self.encoder = tiktoken.get_encoding(encoding_name)

    def chunk_all(self, docs: Dict[str, List[DocPage]]) -> List[DocChunk]:
        """
        Chunk all documentation pages.

        Args:
            docs: Dictionary mapping section names to DocPage lists

        Returns:
            List of DocChunk objects
        """
        all_chunks = []

        for section_name, pages in docs.items():
            for page in pages:
                chunks = self.chunk_document(page)
                all_chunks.extend(chunks)

        return all_chunks

    def chunk_document(self, doc: DocPage) -> List[DocChunk]:
        """
        Chunk a single documentation page.

        Strategy:
        1. Create chunks for each code example (highest priority)
        2. Chunk remaining text content semantically
        3. Add metadata for filtering
        """
        chunks = []

        # Priority 1: Code examples as standalone chunks
        for i, code_example in enumerate(doc.code_examples):
            chunk = self._create_code_example_chunk(doc, code_example, i)
            if chunk:
                chunks.append(chunk)

        # Priority 2: API documentation (method signatures)
        for i, method_sig in enumerate(doc.method_signatures):
            chunk = self._create_api_doc_chunk(doc, method_sig, i)
            if chunk:
                chunks.append(chunk)

        # Priority 3: Chunk remaining content
        content_chunks = self._chunk_text_content(doc)
        chunks.extend(content_chunks)

        return chunks

    def _create_code_example_chunk(
        self,
        doc: DocPage,
        code_example: CodeExample,
        index: int
    ) -> DocChunk:
        """Create a chunk from a code example with context."""
        content_parts = []

        if code_example.context:
            content_parts.append(f"Context: {code_example.context}")

        content_parts.append(f"\nCode Example ({code_example.language}):")
        content_parts.append(f"```{code_example.language}")
        content_parts.append(code_example.code)
        content_parts.append("```")

        if code_example.output_description:
            content_parts.append(f"\nOutput: {code_example.output_description}")

        content = "\n".join(content_parts)

        manim_classes = self._extract_manim_classes_from_code(code_example.code)
        animation_types = self._extract_animation_types(code_example.code)

        # Use hash of URL to ensure uniqueness
        url_hash = str(hash(doc.url))[-8:]
        chunk_id = f"{doc.section}_{self._sanitize_for_id(doc.title)}_{url_hash}_code_{index}"

        return DocChunk(
            chunk_id=chunk_id,
            source_url=doc.url,
            source_title=doc.title,
            section=doc.section,
            breadcrumb=doc.breadcrumb,
            content=content,
            chunk_type="code_example",
            manim_classes=manim_classes,
            animation_types=animation_types,
            concept_tags=doc.tags,
            code_example=code_example
        )

    def _create_api_doc_chunk(
        self,
        doc: DocPage,
        method_sig: MethodSignature,
        index: int
    ) -> DocChunk:
        """Create a chunk from an API method signature."""
        content_parts = []

        if method_sig.class_name:
            content_parts.append(f"Class: {method_sig.class_name}")

        sig = f"{method_sig.name}({', '.join(method_sig.parameters)})"
        if method_sig.return_type:
            sig += f" → {method_sig.return_type}"

        content_parts.append(f"\nMethod Signature: {sig}")
        content_parts.append(f"\nDescription: {method_sig.description}")

        content = "\n".join(content_parts)

        manim_classes = []
        if method_sig.class_name:
            manim_classes.append(method_sig.class_name)

        # Use hash of URL to ensure uniqueness
        url_hash = str(hash(doc.url))[-8:]
        chunk_id = f"{doc.section}_{self._sanitize_for_id(doc.title)}_{url_hash}_api_{index}"

        return DocChunk(
            chunk_id=chunk_id,
            source_url=doc.url,
            source_title=doc.title,
            section=doc.section,
            breadcrumb=doc.breadcrumb,
            content=content,
            chunk_type="api_doc",
            manim_classes=manim_classes,
            animation_types=[],
            concept_tags=doc.tags,
            method_signature=method_sig
        )

    def _chunk_text_content(self, doc: DocPage) -> List[DocChunk]:
        """Chunk the text content of a document."""
        chunks = []

        paragraphs = doc.content.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(self.encoder.encode(para))

            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                chunk_content = '\n\n'.join(current_chunk)
                chunk = self._create_text_chunk(doc, chunk_content, len(chunks))
                chunks.append(chunk)

                if self.chunk_overlap > 0 and current_chunk:
                    current_chunk = [current_chunk[-1]]
                    current_tokens = len(self.encoder.encode(current_chunk[0]))
                else:
                    current_chunk = []
                    current_tokens = 0

            current_chunk.append(para)
            current_tokens += para_tokens

        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunk = self._create_text_chunk(doc, chunk_content, len(chunks))
            chunks.append(chunk)

        return chunks

    def _create_text_chunk(
        self,
        doc: DocPage,
        content: str,
        index: int
    ) -> DocChunk:
        """Create a chunk from text content."""
        chunk_type = "tutorial" if doc.section == "tutorials" else "concept"

        manim_classes = self._extract_manim_classes_from_text(content)
        animation_types = self._extract_animation_types(content)

        # Use hash of URL to ensure uniqueness
        url_hash = str(hash(doc.url))[-8:]
        chunk_id = f"{doc.section}_{self._sanitize_for_id(doc.title)}_{url_hash}_text_{index}"

        return DocChunk(
            chunk_id=chunk_id,
            source_url=doc.url,
            source_title=doc.title,
            section=doc.section,
            breadcrumb=doc.breadcrumb,
            content=content,
            chunk_type=chunk_type,
            manim_classes=manim_classes,
            animation_types=animation_types,
            concept_tags=doc.tags
        )

    def _extract_manim_classes_from_code(self, code: str) -> List[str]:
        """Extract Manim class names from code."""
        classes = set()

        class_patterns = [
            r'\b(Circle|Square|Rectangle|Triangle|Polygon)\(',
            r'\b(Text|MathTex|Tex|Paragraph)\(',
            r'\b(Arrow|Line|Dot|Vector)\(',
            r'\b(VGroup|VMobject|Mobject)\(',
            r'\b(Create|Write|FadeIn|FadeOut|Transform|ReplacementTransform)\(',
            r'\b(Indicate|Flash|Circumscribe|ShowPassingFlash)\(',
            r'\b(ScaleInPlace|GrowFromCenter|ShrinkToCenter)\(',
            r'\b(Rotate|Shift|MoveTo)\(',
            r'\b(Matrix|Axes|NumberPlane|Graph)\(',
            r'\b(Scene|ThreeDScene|MovingCameraScene)\b'
        ]

        for pattern in class_patterns:
            matches = re.findall(pattern, code)
            classes.update(matches)

        return list(classes)

    def _extract_manim_classes_from_text(self, text: str) -> List[str]:
        """Extract Manim class names from text content."""
        classes = set()

        common_classes = [
            'Circle', 'Square', 'Rectangle', 'Text', 'MathTex', 'Tex',
            'Arrow', 'Line', 'Dot', 'VGroup', 'Create', 'Write',
            'FadeIn', 'FadeOut', 'Transform', 'Scene', 'Matrix', 'Axes'
        ]

        for cls in common_classes:
            if cls in text:
                classes.add(cls)

        return list(classes)

    def _extract_animation_types(self, text: str) -> List[str]:
        """Extract animation type keywords."""
        types = set()

        type_keywords = {
            'creation': ['create', 'draw', 'grow', 'appear'],
            'fade': ['fade', 'fadein', 'fadeout'],
            'transform': ['transform', 'morph', 'replacementtransform'],
            'move': ['move', 'shift', 'translate'],
            'scale': ['scale', 'grow', 'shrink'],
            'rotate': ['rotate', 'spin'],
            'highlight': ['indicate', 'flash', 'circumscribe', 'highlight'],
            'write': ['write', 'addtext']
        }

        text_lower = text.lower()
        for anim_type, keywords in type_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                types.add(anim_type)

        return list(types)

    def _sanitize_for_id(self, text: str) -> str:
        """Sanitize text for use in IDs."""
        sanitized = re.sub(r'[^a-zA-Z0-9]+', '_', text)
        sanitized = sanitized.strip('_').lower()
        return sanitized[:50]

    def save(self, chunks: List[DocChunk], output_path: str) -> None:
        """Save chunks to JSON file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        data = [chunk.model_dump() for chunk in chunks]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load(self, input_path: str) -> List[DocChunk]:
        """Load chunks from JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return [DocChunk.model_validate(chunk) for chunk in data]
