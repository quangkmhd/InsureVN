"""Index processed Markdown policy documents into Qdrant."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.embeddings import Embeddings
from langchain_qdrant import FastEmbedSparse, SparseEmbeddings
from qdrant_client import QdrantClient

from src.core.config import settings
from src.core.logger import get_logger
from src.services.document_chunker import (
    ChildChunk,
    ChunkingStrategy,
    DocumentChunker,
    SemanticBreakpointType,
)
from src.services.qdrant_retriever import GoogleGenAIEmbeddingProvider, QdrantRetriever

logger = get_logger("qdrant_indexer")


def build_dry_run_report(
    *,
    document_paths: list[Path],
    metadata: dict[str, Any],
    child_chunk_chars: int,
    child_chunk_overlap: int,
    chunking_strategy: ChunkingStrategy = "recursive",
    semantic_embedding_provider: Embeddings | None = None,
    semantic_target_chars: int = 1400,
    semantic_max_chars: int = 3500,
    semantic_min_chars: int = 350,
    semantic_breakpoint_type: SemanticBreakpointType = "interquartile",
    semantic_breakpoint_amount: float = 1.5,
    table_line_ratio_threshold: float = 0.55,
    table_chunk_chars: int = 3500,
    mapping_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dry-run indexing report for Markdown documents.

    Args:
        document_paths: Markdown document paths to inspect.
        metadata: Shared document metadata. `file_name` is set per document.
        child_chunk_chars: Maximum child chunk size in characters.
        child_chunk_overlap: Character overlap between adjacent chunks.
        chunking_strategy: Document chunking strategy.
        semantic_embedding_provider: Optional embeddings for semantic chunking.
        semantic_target_chars: Target semantic chunk size.
        semantic_max_chars: Maximum semantic chunk size before fallback splitting.
        semantic_min_chars: Minimum semantic chunk size.
        semantic_breakpoint_type: Semantic breakpoint strategy.
        semantic_breakpoint_amount: Semantic breakpoint threshold amount.
        table_line_ratio_threshold: Ratio that marks table-heavy sections.
        table_chunk_chars: Maximum table chunk size.
        mapping_data: Optional mapping from md file to tables.

    Returns:
        JSON-serializable report with document, parent section, and chunk counts.
    """
    chunker = build_document_chunker(
        child_chunk_chars=child_chunk_chars,
        child_chunk_overlap=child_chunk_overlap,
        chunking_strategy=chunking_strategy,
        semantic_embedding_provider=semantic_embedding_provider,
        semantic_target_chars=semantic_target_chars,
        semantic_max_chars=semantic_max_chars,
        semantic_min_chars=semantic_min_chars,
        semantic_breakpoint_type=semantic_breakpoint_type,
        semantic_breakpoint_amount=semantic_breakpoint_amount,
        table_line_ratio_threshold=table_line_ratio_threshold,
        table_chunk_chars=table_chunk_chars,
    )
    documents: list[dict[str, Any]] = []
    parent_section_count = 0
    chunk_count = 0
    seen_content_hashes: set[str] = set()
    duplicate_chunk_count = 0

    for document_path in document_paths:
        document_metadata = {**metadata, "file_name": document_path.name}

        # Look up source_table_id from mapping if available and missing in metadata
        if mapping_data and "source_table_id" not in document_metadata:
            md_dir = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns"
            try:
                rel_path = str(document_path.relative_to(md_dir))
                if rel_path in mapping_data:
                    tables = mapping_data[rel_path].get("tables", [])
                    if tables:
                        # Fallback: dùng source_table_id của bảng đầu tiên tìm thấy trong doc
                        document_metadata["source_table_id"] = tables[0]["source_table_id"]
                        logger.info(f"Mapped {document_path.name} to source_table_id: {document_metadata['source_table_id']}")
            except ValueError:
                pass
        
        # Nếu vẫn thiếu, gán fallback ID để không bị crash validate_payload
        if "source_table_id" not in document_metadata:
            document_metadata["source_table_id"] = -1
            logger.warning(f"No mapping found for {document_path.name}, using source_table_id: -1")

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
                "file_name": document_path.name,
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
        "chunking_strategy": chunking_strategy,
        "readiness_result": "not_checked_dry_run",
        "documents": documents,
    }


def build_chunks(
    *,
    document_paths: list[Path],
    metadata: dict[str, Any],
    child_chunk_chars: int,
    child_chunk_overlap: int,
    chunking_strategy: ChunkingStrategy = "recursive",
    semantic_embedding_provider: Embeddings | None = None,
    semantic_target_chars: int = 1400,
    semantic_max_chars: int = 3500,
    semantic_min_chars: int = 350,
    semantic_breakpoint_type: SemanticBreakpointType = "interquartile",
    semantic_breakpoint_amount: float = 1.5,
    table_line_ratio_threshold: float = 0.55,
    table_chunk_chars: int = 3500,
    mapping_data: dict[str, Any] | None = None,
) -> list[ChildChunk]:
    """Chunk Markdown documents for indexing."""
    chunker = build_document_chunker(
        child_chunk_chars=child_chunk_chars,
        child_chunk_overlap=child_chunk_overlap,
        chunking_strategy=chunking_strategy,
        semantic_embedding_provider=semantic_embedding_provider,
        semantic_target_chars=semantic_target_chars,
        semantic_max_chars=semantic_max_chars,
        semantic_min_chars=semantic_min_chars,
        semantic_breakpoint_type=semantic_breakpoint_type,
        semantic_breakpoint_amount=semantic_breakpoint_amount,
        table_line_ratio_threshold=table_line_ratio_threshold,
        table_chunk_chars=table_chunk_chars,
    )
    chunks: list[ChildChunk] = []
    for document_path in document_paths:
        document_metadata = {**metadata, "file_name": document_path.name}

        # Look up source_table_id from mapping if available and missing in metadata
        if mapping_data and "source_table_id" not in document_metadata:
            md_dir = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns"
            try:
                rel_path = str(document_path.relative_to(md_dir))
                if rel_path in mapping_data:
                    tables = mapping_data[rel_path].get("tables", [])
                    if tables:
                        document_metadata["source_table_id"] = tables[0]["source_table_id"]
            except ValueError:
                # Not in markdown dir, skip mapping
                pass

        chunked_document = chunker.chunk_markdown(
            document_path.read_text(encoding="utf-8"),
            metadata=document_metadata,
        )
        chunks.extend(chunked_document.child_chunks)
    return chunks


def build_document_chunker(
    *,
    child_chunk_chars: int,
    child_chunk_overlap: int,
    chunking_strategy: ChunkingStrategy,
    semantic_embedding_provider: Embeddings | None,
    semantic_target_chars: int,
    semantic_max_chars: int,
    semantic_min_chars: int,
    semantic_breakpoint_type: SemanticBreakpointType,
    semantic_breakpoint_amount: float,
    table_line_ratio_threshold: float,
    table_chunk_chars: int,
) -> DocumentChunker:
    """Build the configured document chunker."""
    return DocumentChunker(
        child_chunk_chars=child_chunk_chars,
        child_chunk_overlap=child_chunk_overlap,
        chunking_strategy=chunking_strategy,
        semantic_embedding_provider=semantic_embedding_provider,
        semantic_target_chars=semantic_target_chars,
        semantic_max_chars=semantic_max_chars,
        semantic_min_chars=semantic_min_chars,
        semantic_breakpoint_type=semantic_breakpoint_type,
        semantic_breakpoint_amount=semantic_breakpoint_amount,
        table_line_ratio_threshold=table_line_ratio_threshold,
        table_chunk_chars=table_chunk_chars,
    )


def build_embedding_provider(
    *,
    provider: str,
    model_name: str,
    google_api_key: str,
    vector_size: int,
) -> Embeddings:
    """Build the configured embedding provider.

    Args:
        provider: Embedding provider configured by `RAG_EMBEDDING_PROVIDER`.
        model_name: Embedding model configured by `RAG_EMBEDDING_MODEL`.
        google_api_key: Google API key for Gemini embedding providers.
        vector_size: Dense vector dimension configured by `RAG_DENSE_VECTOR_SIZE`.

    Returns:
        Embedding provider for indexing and retrieval.

    Raises:
        ValueError: If the configured model is not implemented in this phase.
    """
    if provider == "google_genai":
        return GoogleGenAIEmbeddingProvider(
            model_name=model_name,
            google_api_key=google_api_key,
            vector_size=vector_size,
        )
    raise ValueError(
        "Unsupported RAG_EMBEDDING_PROVIDER. "
        "Use 'google_genai' with GOOGLE_API_KEY configured."
    )


def build_sparse_embedding_provider(model_name: str) -> SparseEmbeddings:
    """Build LangChain's sparse embedding provider for Qdrant hybrid search."""
    return FastEmbedSparse(model_name=model_name)


def main() -> None:
    """Run the Qdrant indexing CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", action="append", required=True)
    parser.add_argument("--metadata-json", required=True)
    parser.add_argument("--mapping-json", help="Path to table mapping file")
    parser.add_argument("--output-json", help="Path to save chunks as JSON (skips Qdrant index if provided)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    document_paths = [Path(document) for document in args.document]
    metadata = json.loads(Path(args.metadata_json).read_text(encoding="utf-8"))
    
    mapping_data = None
    if args.mapping_json:
        mapping_data = json.loads(Path(args.mapping_json).read_text(encoding="utf-8"))
    elif (PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns" / "table_mapping.json").exists():
        # Auto-load if default mapping exists
        mapping_path = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns" / "table_mapping.json"
        mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
        logger.info(f"Auto-loaded table mapping from {mapping_path}")
    chunking_kwargs = {
        "chunking_strategy": settings.RAG_CHUNKING_STRATEGY,
        "semantic_target_chars": settings.RAG_SEMANTIC_TARGET_CHARS,
        "semantic_max_chars": settings.RAG_SEMANTIC_MAX_CHARS,
        "semantic_min_chars": settings.RAG_SEMANTIC_MIN_CHARS,
        "semantic_breakpoint_type": settings.RAG_SEMANTIC_BREAKPOINT_TYPE,
        "semantic_breakpoint_amount": settings.RAG_SEMANTIC_BREAKPOINT_AMOUNT,
        "table_line_ratio_threshold": settings.RAG_TABLE_LINE_RATIO_THRESHOLD,
        "table_chunk_chars": settings.RAG_TABLE_CHUNK_MAX_CHARS,
    }

    if args.dry_run:
        report = build_dry_run_report(
            document_paths=document_paths,
            metadata=metadata,
            child_chunk_chars=settings.RAG_CHILD_CHUNK_TOKENS,
            child_chunk_overlap=settings.RAG_CHILD_CHUNK_OVERLAP,
            mapping_data=mapping_data,
            **chunking_kwargs,
        )
        print(json.dumps(report, ensure_ascii=False))
        return

    embedding_provider = build_embedding_provider(
        provider=settings.RAG_EMBEDDING_PROVIDER,
        model_name=settings.RAG_EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        vector_size=settings.RAG_DENSE_VECTOR_SIZE,
    )
    chunks = build_chunks(
        document_paths=document_paths,
        metadata=metadata,
        child_chunk_chars=settings.RAG_CHILD_CHUNK_TOKENS,
        child_chunk_overlap=settings.RAG_CHILD_CHUNK_OVERLAP,
        semantic_embedding_provider=embedding_provider,
        mapping_data=mapping_data,
        **chunking_kwargs,
    )
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Convert ChildChunk objects to serializable dicts
        serializable_chunks = [
            {
                "id": c.chunk_id,
                "parent_id": c.parent_section_id,
                "text": c.text,
                "payload": c.payload
            }
            for c in chunks
        ]
        output_path.write_text(json.dumps(serializable_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved {len(chunks)} chunks to {args.output_json}")
        return

    retriever = QdrantRetriever(
        client=QdrantClient(url=settings.RAG_QDRANT_URL),
        collection_name=settings.RAG_QDRANT_COLLECTION,
        embedding_provider=embedding_provider,
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
