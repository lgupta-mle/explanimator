"""
One-time script to scrape, chunk, embed, and index Manim documentation.

Usage:
    python -m research_viz.preprocessing.build_manim_index
    python -m research_viz.preprocessing.build_manim_index --force-rescrape
"""

import logging
import tyro
from pathlib import Path
from research_viz.preprocessing.manim_docs_scraper import ManimDocsScraper
from research_viz.preprocessing.manim_docs_chunker import ManimDocsChunker
from research_viz.preprocessing.manim_docs_embedder import ManimDocsEmbedder

logger = logging.getLogger(__name__)


def main(
    manim_docs_url: str = "https://docs.manim.community/en/stable/",
    output_dir: str = "data/manim_docs",
    force_rescrape: bool = False,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    embedding_model: str = "text-embedding-3-large"
):
    """
    Build Manim documentation index.

    Steps:
    1. Scrape docs (or load from cache)
    2. Chunk documents
    3. Generate embeddings
    4. Store in ChromaDB

    Args:
        manim_docs_url: Base URL for Manim documentation
        output_dir: Directory to store all data
        force_rescrape: Force re-scraping even if cache exists
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks in tokens
        embedding_model: OpenAI embedding model to use

    Examples:
        # Basic usage
        python -m research_viz.preprocessing.build_manim_index

        # Force re-scrape
        python -m research_viz.preprocessing.build_manim_index --force-rescrape

        # Custom paths
        python -m research_viz.preprocessing.build_manim_index \\
            --output-dir custom/path \\
            --chunk-size 1500
    """
    raw_dir = f"{output_dir}/raw"
    processed_dir = f"{output_dir}/processed"
    vector_db_dir = f"{output_dir}/vector_db/chroma_db"

    logger.info("=" * 80)
    logger.info("MANIM DOCUMENTATION INDEX BUILDER")
    logger.info("=" * 80)

    # Step 1: Scrape documentation
    scraper = ManimDocsScraper(manim_docs_url, raw_dir)

    if force_rescrape or not Path(raw_dir).exists():
        logger.info("[1/4] Scraping Manim documentation...")
        logger.info(f"  URL: {manim_docs_url}")
        logger.info(f"  This may take 30-60 minutes...")
        docs = scraper.scrape_all()
        scraper.save(docs)
        total_pages = sum(len(pages) for pages in docs.values())
        logger.info(f"  Scraped {total_pages} pages")
    else:
        logger.info("[1/4] Loading cached documentation...")
        docs = scraper.load()
        total_pages = sum(len(pages) for pages in docs.values())
        logger.info(f"  Loaded {total_pages} pages from cache")
        logger.info(f"  (Use --force-rescrape to re-scrape)")

    # Step 2: Chunk documents
    logger.info("[2/4] Chunking documents...")
    logger.info(f"  Chunk size: {chunk_size} tokens")
    logger.info(f"  Chunk overlap: {chunk_overlap} tokens")

    chunker = ManimDocsChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = chunker.chunk_all(docs)

    chunks_path = f"{processed_dir}/chunks.json"
    chunker.save(chunks, chunks_path)
    logger.info(f"  Created {len(chunks)} chunks")
    logger.info(f"  Saved to: {chunks_path}")

    # Step 3: Generate embeddings and store in ChromaDB
    logger.info("[3/4] Generating embeddings and storing in ChromaDB...")
    logger.info(f"  Model: {embedding_model}")
    logger.info(f"  This may take 10-20 minutes...")

    embedder = ManimDocsEmbedder(
        embedding_model=embedding_model,
        chroma_path=vector_db_dir
    )
    embedder.embed_and_store(chunks)

    # Step 4: Verification
    logger.info("[4/4] Verification...")
    stats = embedder.get_collection_stats()
    logger.info(f"  Total chunks indexed: {stats['total_chunks']}")
    logger.info(f"  ChromaDB location: {stats['chroma_path']}")

    logger.info("=" * 80)
    logger.info("INDEX BUILD COMPLETE!")
    logger.info("=" * 80)
    logger.info(f"Data stored in: {output_dir}/")
    logger.info(f"  - Raw docs: {raw_dir}/")
    logger.info(f"  - Chunks: {chunks_path}")
    logger.info(f"  - Vector DB: {vector_db_dir}/")
    logger.info(f"Total storage:")
    logger.info(f"  - {total_pages} documentation pages")
    logger.info(f"  - {len(chunks)} searchable chunks")
    logger.info(f"  - {stats['total_chunks']} embedded vectors")

    logger.info("You can now use the RAG system for code generation:")
    logger.info("  python -m research_viz.manim_generator.manim_code_generator")


if __name__ == "__main__":
    tyro.cli(main)
