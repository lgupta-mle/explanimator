"""
Pydantic schemas for Manim documentation RAG system.

These schemas define the structure for scraped documentation pages,
chunked documents, and retrieval results.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any


class CodeExample(BaseModel):
    """A code example extracted from documentation."""
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="The code snippet")
    language: str = Field(default="python", description="Programming language")
    context: str = Field(..., description="Surrounding explanation or description")
    output_description: Optional[str] = Field(None, description="Description of what the code produces")


class MethodSignature(BaseModel):
    """Method or function signature from API documentation."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Method/function name")
    class_name: Optional[str] = Field(None, description="Parent class name if applicable")
    parameters: List[str] = Field(default_factory=list, description="Parameter names")
    return_type: Optional[str] = Field(None, description="Return type")
    description: str = Field(..., description="Method description")


class DocPage(BaseModel):
    """A single documentation page from Manim docs."""
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., description="Full URL of the page")
    title: str = Field(..., description="Page title")
    section: str = Field(..., description="Documentation section (api_reference, tutorials, guides, reference_manual)")
    breadcrumb: List[str] = Field(default_factory=list, description="Hierarchical navigation path")

    content: str = Field(..., description="Full page content in markdown/text")

    code_examples: List[CodeExample] = Field(default_factory=list, description="Code examples on this page")
    method_signatures: List[MethodSignature] = Field(default_factory=list, description="API signatures if applicable")

    related_classes: List[str] = Field(default_factory=list, description="Manim classes mentioned on this page")
    tags: List[str] = Field(default_factory=list, description="Topic tags (e.g., animation, geometry, text, math)")


class DocChunk(BaseModel):
    """A chunk of documentation optimized for embedding and retrieval."""
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Unique identifier for this chunk")
    source_url: str = Field(..., description="URL of the source page")
    source_title: str = Field(..., description="Title of the source page")
    section: str = Field(..., description="Documentation section")
    breadcrumb: List[str] = Field(default_factory=list, description="Navigation path")

    content: str = Field(..., description="The actual text content to embed")
    chunk_type: str = Field(..., description="Type of chunk: code_example, api_doc, tutorial, concept")

    # Metadata for filtering and ranking
    manim_classes: List[str] = Field(default_factory=list, description="Manim classes featured in this chunk")
    animation_types: List[str] = Field(default_factory=list, description="Animation types featured (creation, transform, fade, etc.)")
    concept_tags: List[str] = Field(default_factory=list, description="Concept tags for categorization")

    # Optional structured data
    code_example: Optional[CodeExample] = Field(None, description="If chunk_type is code_example, the structured code")
    method_signature: Optional[MethodSignature] = Field(None, description="If chunk_type is api_doc, the method signature")


class RetrievalResult(BaseModel):
    """A single retrieval result from the RAG system."""
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="ID of the retrieved chunk")
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., description="Relevance score (0-1, higher is better)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    source_url: str = Field(..., description="URL of the source documentation page")
