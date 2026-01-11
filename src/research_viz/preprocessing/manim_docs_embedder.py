"""
Generate embeddings for Manim documentation chunks and store in ChromaDB.
"""

import os
from typing import List
import chromadb
from openai import OpenAI
import tiktoken
from research_viz.schemas.manim_docs_schemas import DocChunk
from tqdm import tqdm


class ManimDocsEmbedder:
    """Embed chunks and store in ChromaDB."""

    def __init__(
        self,
        embedding_model: str = "text-embedding-3-large",
        chroma_path: str = "data/manim_docs/vector_db/chroma_db",
        batch_size: int = 100,
        max_tokens: int = 8191
    ):
        """
        Args:
            embedding_model: OpenAI embedding model to use
            chroma_path: Path to persistent ChromaDB storage
            batch_size: Number of chunks to embed at once
            max_tokens: Maximum tokens per chunk for embedding model
        """
        self.embedding_model = embedding_model
        self.chroma_path = chroma_path
        self.batch_size = batch_size
        self.max_tokens = max_tokens

        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.encoder = tiktoken.get_encoding("cl100k_base")

        self.chroma_client = chromadb.PersistentClient(path=chroma_path)

        # Create collection without default embedding function
        # We provide OpenAI embeddings manually
        try:
            self.collection = self.chroma_client.get_collection(name="manim_docs")
        except:
            self.collection = self.chroma_client.create_collection(
                name="manim_docs",
                metadata={
                    "description": "Manim Community Documentation for RAG",
                    "embedding_model": self.embedding_model,
                    "embedding_dimensions": 3072
                }
            )

    def embed_and_store(self, chunks: List[DocChunk]) -> None:
        """
        Embed chunks and store in ChromaDB with metadata.

        Processes chunks in batches for efficiency.
        """
        total_chunks = len(chunks)
        print(f"Embedding and storing {total_chunks} chunks...")

        for i in tqdm(range(0, total_chunks, self.batch_size), desc="Processing batches"):
            batch = chunks[i:i + self.batch_size]

            ids = [chunk.chunk_id for chunk in batch]
            documents = [chunk.content for chunk in batch]

            embeddings = self._get_embeddings_batch(documents)

            metadatas = []
            for chunk in batch:
                metadatas.append({
                    "source_url": chunk.source_url,
                    "source_title": chunk.source_title,
                    "section": chunk.section,
                    "chunk_type": chunk.chunk_type,
                    "manim_classes": ",".join(chunk.manim_classes),
                    "animation_types": ",".join(chunk.animation_types),
                    "concept_tags": ",".join(chunk.concept_tags),
                    "breadcrumb": " > ".join(chunk.breadcrumb)
                })

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

        print(f"Successfully stored {total_chunks} chunks in ChromaDB")

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts from OpenAI."""
        validated_texts = []
        for text in texts:
            tokens = self.encoder.encode(text)
            if len(tokens) > self.max_tokens:
                print(f"Warning: Truncating chunk from {len(tokens)} to {self.max_tokens} tokens")
                truncated_tokens = tokens[:self.max_tokens]
                text = self.encoder.decode(truncated_tokens)
            validated_texts.append(text)

        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=validated_texts
        )

        return [item.embedding for item in response.data]

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text."""
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text
        )

        return response.data[0].embedding

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        count = self.collection.count()

        return {
            "total_chunks": count,
            "collection_name": self.collection.name,
            "chroma_path": self.chroma_path
        }
