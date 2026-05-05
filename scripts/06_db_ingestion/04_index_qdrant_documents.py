"""Index processed Markdown policy documents into Qdrant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import FastEmbedSparse, SparseEmbeddings
from qdrant_client import QdrantClient

from src.core.config import settings
from src.core.logger import get_logger
from src.services.document_chunker import ChildChunk, DocumentChunker
from src.services.qdrant_retriever import HashingEmbeddingProvider, QdrantRetriever

logger = get_logger("qdrant_indexer")


def build_dry_run_report(
    *,
    document_paths: list[Path],
    metadata: dict[str, Any],
    child_chunk_chars: int,
    child_chunk_overlap: int,
) -> dict[str, Any]:
    """Build a dry-run indexing report for Markdown documents.

    Args:
        document_paths: Markdown document paths to inspect.
        metadata: Shared document metadata. `source_path` is set per document.
        child_chunk_chars: Maximum child chunk size in characters.
        child_chunk_overlap: Character overlap between adjacent chunks.

    Returns:
        JSON-serializable report with document, parent section, and chunk counts.
    """
    chunker = DocumentChunker(
        child_chunk_chars=child_chunk_chars,
        child_chunk_overlap=child_chunk_overlap,
    )
    documents: list[dict[str, Any]] = []
    parent_section_count = 0
    chunk_count = 0
    seen_content_hashes: set[str] = set()
    duplicate_chunk_count = 0

    for document_path in document_paths:
        document_metadata = {**metadata, "source_path": str(document_path)}
        chunked_document = chunker.chunk_markdown(
            document_path.read_text(encoding="utf-8"),
            metadata=document_metadata,
        )
        parent_section_count += len(chunked_document.parent_sections)
        chunk_count += len(chunked_document.child_chunks)
        for child_chunk in chunked_document.child_chunks:
            content_hash = str(child_chunk.payload["content_hash"])
            if content_hash in seen_content_hashes:
                duplicate_chunk_count += 1
            else:
                seen_content_hashes.add(content_hash)
        documents.append(
            {
                "source_path": str(document_path),
                "parent_section_count": len(chunked_document.parent_sections),
                "chunk_count": len(chunked_document.child_chunks),
            }
        )

    return {
        "component": "qdrant_indexer",
        "dry_run": True,
        "document_count": len(document_paths),
        "parent_section_count": parent_section_count,
        "chunk_count": chunk_count,
        "unique_chunk_count": len(seen_content_hashes),
        "skipped_duplicate_count": duplicate_chunk_count,
        "readiness_result": "not_checked_dry_run",
        "documents": documents,
    }


def build_chunks(
    *,
    document_paths: list[Path],
    metadata: dict[str, Any],
    child_chunk_chars: int,
    child_chunk_overlap: int,
) -> list[ChildChunk]:
    """Chunk Markdown documents for indexing."""
    chunker = DocumentChunker(
        child_chunk_chars=child_chunk_chars,
        child_chunk_overlap=child_chunk_overlap,
    )
    chunks: list[ChildChunk] = []
    for document_path in document_paths:
        document_metadata = {**metadata, "source_path": str(document_path)}
        chunked_document = chunker.chunk_markdown(
            document_path.read_text(encoding="utf-8"),
            metadata=document_metadata,
        )
        chunks.extend(chunked_document.child_chunks)
    return chunks


def build_embedding_provider(
    *,
    provider: str,
    model_name: str,
    google_api_key: str,
) -> Embeddings:
    """Build the configured embedding provider.

    Args:
        provider: Embedding provider configured by `RAG_EMBEDDING_PROVIDER`.
        model_name: Embedding model configured by `RAG_EMBEDDING_MODEL`.
        google_api_key: Google API key for Gemini embedding providers.

    Returns:
        Embedding provider for indexing and retrieval.

    Raises:
        ValueError: If the configured model is not implemented in this phase.
    """
    if provider == "google_genai":
        return GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=google_api_key,
        )
    if provider == "hashing":
        return HashingEmbeddingProvider()
    raise ValueError(
        "Unsupported RAG_EMBEDDING_PROVIDER. "
        "Use 'google_genai' for production or 'hashing' for local tests."
    )


def build_sparse_embedding_provider(model_name: str) -> SparseEmbeddings:
    """Build LangChain's sparse embedding provider for Qdrant hybrid search."""
    return FastEmbedSparse(model_name=model_name)


def main() -> None:
    """Run the Qdrant indexing CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", action="append", required=True)
    parser.add_argument("--metadata-json", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    document_paths = [Path(document) for document in args.document]
    metadata = json.loads(Path(args.metadata_json).read_text(encoding="utf-8"))

    if args.dry_run:
        report = build_dry_run_report(
            document_paths=document_paths,
            metadata=metadata,
            child_chunk_chars=settings.RAG_CHILD_CHUNK_TOKENS,
            child_chunk_overlap=settings.RAG_CHILD_CHUNK_OVERLAP,
        )
        print(json.dumps(report, ensure_ascii=False))
        return

    chunks = build_chunks(
        document_paths=document_paths,
        metadata=metadata,
        child_chunk_chars=settings.RAG_CHILD_CHUNK_TOKENS,
        child_chunk_overlap=settings.RAG_CHILD_CHUNK_OVERLAP,
    )
    retriever = QdrantRetriever(
        client=QdrantClient(url=settings.RAG_QDRANT_URL),
        collection_name=settings.RAG_QDRANT_COLLECTION,
        embedding_provider=build_embedding_provider(
            provider=settings.RAG_EMBEDDING_PROVIDER,
            model_name=settings.RAG_EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
        ),
        sparse_embedding_provider=build_sparse_embedding_provider(
            settings.RAG_SPARSE_MODEL
        ),
        keyword_enabled=True,
    )
    retriever.setup_collection(recreate=args.recreate)
    retriever.index_chunks(chunks)
    logger.info(
        "Indexed documents into Qdrant",
        extra={
            "component": "qdrant_indexer",
            "collection_name": settings.RAG_QDRANT_COLLECTION,
            "document_count": len(document_paths),
            "chunk_count": len(chunks),
        },
    )


if __name__ == "__main__":
    main()
