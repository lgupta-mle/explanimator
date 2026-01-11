"""
One-time script to scrape, chunk, embed, and index Manim documentation.

Usage:
    python -m research_viz.preprocessing.build_manim_index
    python -m research_viz.preprocessing.build_manim_index --force-rescrape
"""

import tyro
from pathlib import Path
from research_viz.preprocessing.manim_docs_scraper import ManimDocsScraper
from research_viz.preprocessing.manim_docs_chunker import ManimDocsChunker
from research_viz.preprocessing.manim_docs_embedder import ManimDocsEmbedder


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

    print("=" * 80)
    print("MANIM DOCUMENTATION INDEX BUILDER")
    print("=" * 80)

    # Step 1: Scrape documentation
    scraper = ManimDocsScraper(manim_docs_url, raw_dir)

    if force_rescrape or not Path(raw_dir).exists():
        print("\n[1/4] Scraping Manim documentation...")
        print(f"  URL: {manim_docs_url}")
        print(f"  This may take 30-60 minutes...")
        docs = scraper.scrape_all()
        scraper.save(docs)
        total_pages = sum(len(pages) for pages in docs.values())
        print(f"  ✓ Scraped {total_pages} pages")
    else:
        print("\n[1/4] Loading cached documentation...")
        docs = scraper.load()
        total_pages = sum(len(pages) for pages in docs.values())
        print(f"  ✓ Loaded {total_pages} pages from cache")
        print(f"  (Use --force-rescrape to re-scrape)")

    # Step 2: Chunk documents
    print("\n[2/4] Chunking documents...")
    print(f"  Chunk size: {chunk_size} tokens")
    print(f"  Chunk overlap: {chunk_overlap} tokens")

    chunker = ManimDocsChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = chunker.chunk_all(docs)

    chunks_path = f"{processed_dir}/chunks.json"
    chunker.save(chunks, chunks_path)
    print(f"  ✓ Created {len(chunks)} chunks")
    print(f"  ✓ Saved to: {chunks_path}")

    # Step 3: Generate embeddings and store in ChromaDB
    print("\n[3/4] Generating embeddings and storing in ChromaDB...")
    print(f"  Model: {embedding_model}")
    print(f"  This may take 10-20 minutes...")

    embedder = ManimDocsEmbedder(
        embedding_model=embedding_model,
        chroma_path=vector_db_dir
    )
    embedder.embed_and_store(chunks)

    # Step 4: Verification
    print("\n[4/4] Verification...")
    stats = embedder.get_collection_stats()
    print(f"  ✓ Total chunks indexed: {stats['total_chunks']}")
    print(f"  ✓ ChromaDB location: {stats['chroma_path']}")

    print("\n" + "=" * 80)
    print("INDEX BUILD COMPLETE!")
    print("=" * 80)
    print(f"\nData stored in: {output_dir}/")
    print(f"  - Raw docs: {raw_dir}/")
    print(f"  - Chunks: {chunks_path}")
    print(f"  - Vector DB: {vector_db_dir}/")
    print(f"\nTotal storage:")
    print(f"  - {total_pages} documentation pages")
    print(f"  - {len(chunks)} searchable chunks")
    print(f"  - {stats['total_chunks']} embedded vectors")

    print("\nYou can now use the RAG system for code generation:")
    print("  python -m research_viz.manim_generator.manim_code_generator")


if __name__ == "__main__":
    tyro.cli(main)
