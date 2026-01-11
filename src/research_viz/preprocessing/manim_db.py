"""
RAG retrieval interface for Manim documentation.

This module provides the ManimDocRetriever class which retrieves relevant
Manim documentation for code generation based on animation scene specifications.
"""

from typing import List, Dict, Any
import os
import chromadb
from openai import OpenAI
from research_viz.schemas.animation_schemas import AnimationScene
from research_viz.schemas.manim_docs_schemas import RetrievalResult


class ManimDocRetriever:
    """Retrieve relevant Manim documentation for code generation."""

    def __init__(
        self,
        chroma_path: str = "data/manim_docs/vector_db/chroma_db",
        embedding_model: str = "text-embedding-3-large"
    ):
        """
        Args:
            chroma_path: Path to ChromaDB persistent storage
            embedding_model: OpenAI embedding model to use
        """
        self.chroma_path = chroma_path
        self.embedding_model = embedding_model

        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma_client.get_collection(name="manim_docs")

    def retrieve_for_scene(
        self,
        scene: AnimationScene,
        top_k: int = 20,
        rerank_top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant documentation for an animation scene.

        Strategy:
        1. Build rich semantic query from scene specification
        2. Retrieve top_k candidates via semantic search
        3. Rerank based on chunk type and quality signals
        4. Return rerank_top_k best results

        Args:
            scene: AnimationScene specification
            top_k: Number of candidates to retrieve initially
            rerank_top_k: Number of results to return after reranking

        Returns:
            List of RetrievalResult objects
        """
        # Build rich query from scene description
        query = self._build_query(scene)

        # Semantic search
        candidates = self._semantic_search(query, top_k)

        # Rerank based on quality signals
        reranked = self._rerank(candidates, rerank_top_k)

        return reranked

    def _build_query(self, scene: AnimationScene) -> str:
        """
        Build rich query text for semantic search.

        The query describes what we want to create and animate in natural language.
        The RAG system will find relevant documentation through semantic similarity.

        Args:
            scene: AnimationScene specification

        Returns:
            Query string optimized for semantic search
        """
        query_parts = []

        # Scene purpose and context
        query_parts.append(f"Scene Purpose: {scene.scene_purpose}")
        query_parts.append(f"\nNarration: {scene.narration_snippet[:300]}")

        # Describe shapes to create
        if scene.shapes:
            shapes_desc = []
            for shape in scene.shapes:
                desc = f"{shape.shape_type}"
                if shape.content:
                    desc += f" with content '{shape.content[:50]}'"
                if shape.color:
                    desc += f", color {shape.color}"
                desc += f" (represents: {shape.represents})"
                shapes_desc.append(desc)

            query_parts.append(f"\nShapes to Create:")
            query_parts.append("\n".join(f"- {s}" for s in shapes_desc))

        # Describe animations
        if scene.animations:
            anims_desc = []
            for anim in scene.animations:
                desc = f"{anim.animation_type} animation"
                if anim.sync_with_narration:
                    desc += f" synced with '{anim.sync_with_narration[:50]}'"
                desc += f" (duration: {anim.duration}s)"
                desc += f" - {anim.description}"
                anims_desc.append(desc)

            query_parts.append(f"\nAnimations Needed:")
            query_parts.append("\n".join(f"- {a}" for a in anims_desc))

        # Describe mathematical operations
        if scene.math_animations:
            math_desc = []
            for math_anim in scene.math_animations:
                desc = f"{math_anim.operation_type}: {math_anim.description}"
                if math_anim.input_formulas:
                    desc += f" | Inputs: {', '.join(math_anim.input_formulas[:3])}"
                desc += f" | Output: {math_anim.output_formula}"
                desc += f" | Style: {math_anim.visualization_style}"
                math_desc.append(desc)

            query_parts.append(f"\nMathematical Operations:")
            query_parts.append("\n".join(f"- {m}" for m in math_desc))

        # Add layout and conceptual information
        query_parts.append(f"\nLayout Strategy: {scene.layout_strategy}")

        if scene.concepts_visualized:
            query_parts.append(f"Concepts: {', '.join(scene.concepts_visualized)}")

        return "\n".join(query_parts)

    def _semantic_search(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Perform semantic search against documentation.

        Args:
            query: Rich query text
            top_k: Number of results to retrieve

        Returns:
            List of RetrievalResult objects
        """
        # Get embedding
        query_embedding = self._get_embedding(query)

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        # Convert to RetrievalResult
        retrieval_results = []
        for i in range(len(results['ids'][0])):
            retrieval_results.append(RetrievalResult(
                chunk_id=results['ids'][0][i],
                content=results['documents'][0][i],
                score=1.0 - results['distances'][0][i],  # Convert distance to similarity
                metadata=results['metadatas'][0][i],
                source_url=results['metadatas'][0][i].get('source_url', '')
            ))

        return retrieval_results

    def _rerank(
        self,
        candidates: List[RetrievalResult],
        top_k: int
    ) -> List[RetrievalResult]:
        """
        Rerank candidates based on quality signals.

        Scoring factors:
        1. Semantic similarity score (from ChromaDB)
        2. Chunk type preference (code examples are more useful than concepts)
        3. Documentation section (tutorials with examples vs reference manual)
        4. Content richness (chunks with multiple elements)

        Args:
            candidates: Initial retrieval results
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        for result in candidates:
            # Start with semantic similarity score
            score = result.score

            # Boost code examples significantly (they show concrete usage)
            chunk_type = result.metadata.get('chunk_type', '')
            if chunk_type == 'code_example':
                score += 0.4
            elif chunk_type == 'api_doc':
                score += 0.2
            elif chunk_type == 'tutorial':
                score += 0.25
            # 'concept' chunks get no boost (they're more abstract)

            # Boost tutorial and API reference sections
            section = result.metadata.get('section', '')
            if section == 'tutorials':
                score += 0.15
            elif section == 'api_reference':
                score += 0.1
            elif section == 'guides':
                score += 0.05

            # Boost chunks with richer metadata (more classes/concepts mentioned)
            manim_classes = result.metadata.get('manim_classes', '')
            if manim_classes:
                num_classes = len([c for c in manim_classes.split(',') if c.strip()])
                score += min(0.1, num_classes * 0.02)

            animation_types = result.metadata.get('animation_types', '')
            if animation_types:
                num_types = len([t for t in animation_types.split(',') if t.strip()])
                score += min(0.1, num_types * 0.02)

            # Update final score
            result.score = score

        # Sort by score and return top_k
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_k]

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI."""
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    def assemble_context(
        self,
        retrieval_results: List[RetrievalResult],
        max_tokens: int = 10000
    ) -> str:
        """
        Assemble retrieved chunks into formatted context for LLM.

        Strategy:
        1. Format each chunk with source attribution
        2. Stay within token budget
        3. Prioritize by relevance score

        Args:
            retrieval_results: List of retrieval results (should be pre-sorted by score)
            max_tokens: Maximum tokens to include

        Returns:
            Formatted context string ready for LLM
        """
        context_parts = []
        total_tokens = 0

        for i, result in enumerate(retrieval_results, 1):
            # Estimate tokens (rough: 1 token ≈ 4 chars)
            chunk_tokens = len(result.content) // 4

            if total_tokens + chunk_tokens > max_tokens:
                break

            # Format chunk with metadata
            chunk_type = result.metadata.get('chunk_type', 'unknown')
            section = result.metadata.get('section', 'unknown')

            chunk_text = f"""
{'='*80}
EXAMPLE #{i} | Relevance Score: {result.score:.3f} | Type: {chunk_type}
Source: {result.source_url}
Section: {section}
{'='*80}

{result.content}

"""
            context_parts.append(chunk_text)
            total_tokens += chunk_tokens

        header = f"""
# MANIM DOCUMENTATION EXAMPLES

Below are {len(context_parts)} relevant examples retrieved from Manim documentation.
Use these as reference for understanding how to implement the animation scene.

IMPORTANT:
- Study the code examples to learn Manim class names and API usage
- Follow the patterns shown in these examples
- Use the actual Manim classes and methods demonstrated here
- Do NOT invent class names - only use what you see in these examples

"""

        return header + "\n".join(context_parts)
