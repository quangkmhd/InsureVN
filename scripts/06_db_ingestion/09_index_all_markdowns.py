"""Index all health-insurance Markdown documents into Qdrant and Neo4j."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.embeddings import Embeddings
from langchain_qdrant import FastEmbedSparse
from qdrant_client import QdrantClient

from src.core.config import settings
from src.core.logger import get_logger
from src.services.document_chunker import ChildChunk, DocumentChunker
from src.services.knowledge_graph.builder import KnowledgeGraphBuilder
from src.services.knowledge_graph.document_extractor import GraphDocument
from src.services.knowledge_graph.graph_document_adapter import GraphDocumentAdapter
from src.services.knowledge_graph.neo4j_store import Neo4jKnowledgeGraphStore
from src.services.knowledge_graph.quality import GraphQualityValidator
from src.services.knowledge_graph.serializer import GraphJsonSerializer
from src.services.qdrant_retriever import GoogleGenAIEmbeddingProvider, QdrantRetriever

logger = get_logger("health_markdown_rag_indexer")

HEALTH_INSURANCE_DATA_DIR = PROJECT_ROOT / "data" / "health_insurance"
DEFAULT_MARKDOWN_DIR = (
    HEALTH_INSURANCE_DATA_DIR / "health_insurance_markdowns_interpreted_cleaned"
)
DEFAULT_TABLE_MAPPING_PATH = (
    HEALTH_INSURANCE_DATA_DIR / "health_insurance_markdowns" / "table_mapping.json"
)
DEFAULT_CHUNK_EXPORT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "qdrant_chunks"
    / "health_insurance_chunks.json"
)
DEFAULT_INGESTION_VERSION = "health_insurance_markdowns_interpreted_cleaned_v1"

COMPANY_CODE_BY_PROVIDER = {
    "aia.com.vn": "AIA",
    "baominh.com.vn": "BaoMinh",
    "bic.vn": "BIC",
    "libertyinsurance.com.vn": "Liberty",
    "pacific_cross_all_pdfs": "PacificCross",
    "pti.com.vn": "PTI",
    "pvicare.net": "PVI",
}


@dataclass(frozen=True)
class IndexInputs:
    """Prepared indexing inputs shared by Qdrant and graph import."""

    chunks: list[ChildChunk]
    graph_documents: list[GraphDocument]
    graph_chunks: list[dict[str, Any]]


def discover_markdown_documents(
    markdown_dir: Path, *, limit: int | None = None
) -> list[Path]:
    """Return all Markdown documents under the upload directory."""
    documents = sorted(markdown_dir.rglob("*.md"))
    if limit is not None:
        return documents[:limit]
    return documents


def load_table_mapping(path: Path | None) -> dict[str, Any]:
    """Load optional table mapping metadata for Markdown documents."""
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_document_metadata(
    document_path: Path,
    *,
    markdown_dir: Path,
    table_mapping: dict[str, Any],
    ingestion_version: str,
) -> dict[str, Any]:
    """Build Qdrant payload metadata from path and extracted table mapping."""
    relative_path = document_path.relative_to(markdown_dir)
    relative_key = relative_path.as_posix()
    provider = relative_path.parts[0] if relative_path.parts else "unknown"
    tables = list(table_mapping.get(relative_key, {}).get("tables", []))
    metadata: dict[str, Any] = {
        "company_code": COMPANY_CODE_BY_PROVIDER.get(provider, "UNKNOWN"),
        "document_id": stable_identifier(relative_path.with_suffix("").as_posix()),
        "document_type": infer_document_type(relative_key),
        "document_name": readable_document_name(document_path.stem),
        "product_line": "health",
        "file_name": document_path.name,
        "source_path": relative_key,
        "source_relative_path": relative_key,
        "ingestion_version": ingestion_version,
        "has_mapped_tables": bool(tables),
        "table_count": len(tables),
    }
    if tables:
        metadata.update(
            {
                "source_table_ids": [
                    table["source_table_id"]
                    for table in tables
                    if "source_table_id" in table
                ],
                "table_files": [
                    table["file_name"] for table in tables if "file_name" in table
                ],
                "table_types": sorted(
                    {
                        str(table["table_type"])
                        for table in tables
                        if table.get("table_type")
                    }
                ),
            }
        )
    return metadata


def build_index_inputs(
    *,
    document_paths: list[Path],
    markdown_dir: Path,
    table_mapping: dict[str, Any],
    ingestion_version: str,
    chunker: DocumentChunker,
) -> IndexInputs:
    """Chunk Markdown files and prepare graph documents from the same metadata."""
    chunks: list[ChildChunk] = []
    graph_documents: list[GraphDocument] = []
    graph_chunks: list[dict[str, Any]] = []

    for document_path in document_paths:
        metadata = build_document_metadata(
            document_path,
            markdown_dir=markdown_dir,
            table_mapping=table_mapping,
            ingestion_version=ingestion_version,
        )
        markdown_text = document_path.read_text(encoding="utf-8")
        chunked_document = chunker.chunk_markdown(markdown_text, metadata=metadata)
        chunks.extend(chunked_document.child_chunks)
        source_path = str(metadata["source_relative_path"])
        graph_documents.append(
            GraphDocument(
                document_id=str(metadata["document_id"]),
                document_name=str(metadata["document_name"]),
                company_code=str(metadata["company_code"]),
                source_path=source_path,
                text=markdown_text,
            )
        )
        graph_chunks.extend(
            {
                **child_chunk.payload,
                "chunk_id": child_chunk.chunk_id,
                "source_path": source_path,
            }
            for child_chunk in chunked_document.child_chunks
        )

    return IndexInputs(
        chunks=chunks,
        graph_documents=graph_documents,
        graph_chunks=graph_chunks,
    )


def run_indexing_pipeline(
    *,
    markdown_dir: Path = DEFAULT_MARKDOWN_DIR,
    table_mapping_path: Path | None = DEFAULT_TABLE_MAPPING_PATH,
    ingestion_version: str = DEFAULT_INGESTION_VERSION,
    recreate_qdrant: bool = False,
    dry_run: bool = False,
    skip_qdrant: bool = False,
    skip_neo4j: bool = False,
    chunk_export_path: Path | None = None,
    graph_json_path: Path | None = None,
    limit: int | None = None,
    qdrant_retriever: Any | None = None,
    neo4j_store: Any | None = None,
    graph_adapter: Any | None = None,
    chunking_strategy: str | None = None,
    semantic_embedding_provider: Embeddings | None = None,
) -> dict[str, Any]:
    """Index Markdown documents into Qdrant hybrid search and Neo4j graph."""
    document_paths = discover_markdown_documents(markdown_dir, limit=limit)
    table_mapping = load_table_mapping(table_mapping_path)
    dense_embedding_provider = semantic_embedding_provider
    if dense_embedding_provider is None and not dry_run and not skip_qdrant:
        dense_embedding_provider = build_dense_embedding_provider()

    chunker = build_document_chunker(
        chunking_strategy=chunking_strategy or settings.RAG_CHUNKING_STRATEGY,
        semantic_embedding_provider=dense_embedding_provider,
    )
    index_inputs = build_index_inputs(
        document_paths=document_paths,
        markdown_dir=markdown_dir,
        table_mapping=table_mapping,
        ingestion_version=ingestion_version,
        chunker=chunker,
    )
    graph_documents = build_graph_documents(
        documents=index_inputs.graph_documents,
        chunks=index_inputs.graph_chunks,
        graph_adapter=graph_adapter or GraphDocumentAdapter(),
    )

    if chunk_export_path is not None and not dry_run:
        write_chunk_export(index_inputs.chunks, chunk_export_path)

    graph_report: dict[str, Any] | None = None
    if graph_json_path is not None:
        graph_report = build_and_maybe_write_graph_json(
            documents=index_inputs.graph_documents,
            chunks=index_inputs.graph_chunks,
            graph_json_path=graph_json_path,
            dry_run=dry_run,
        )

    qdrant_indexed = False
    if not dry_run and not skip_qdrant:
        retriever = qdrant_retriever or build_qdrant_retriever(
            dense_embedding_provider=dense_embedding_provider
        )
        retriever.setup_collection(recreate=recreate_qdrant)
        retriever.index_chunks(index_inputs.chunks)
        qdrant_indexed = True

    neo4j_imported = False
    if not dry_run and not skip_neo4j:
        store = neo4j_store or build_neo4j_store()
        store.ensure_schema()
        store.import_graph_documents(graph_documents)
        neo4j_imported = True

    report = {
        "component": "health_markdown_rag_indexer",
        "dry_run": dry_run,
        "document_count": len(index_inputs.graph_documents),
        "chunk_count": len(index_inputs.chunks),
        "graph_document_count": len(graph_documents),
        "qdrant_collection": settings.RAG_QDRANT_COLLECTION,
        "qdrant_indexed": qdrant_indexed,
        "neo4j_imported": neo4j_imported,
        "table_mapping_used": bool(table_mapping),
        "chunk_export_path": str(chunk_export_path) if chunk_export_path else None,
        "graph_json_path": str(graph_json_path) if graph_json_path else None,
        "graph_report": graph_report,
    }
    logger.info("Completed health Markdown RAG indexing", extra=report)
    return report


def build_document_chunker(
    *,
    chunking_strategy: str,
    semantic_embedding_provider: Embeddings | None,
) -> DocumentChunker:
    """Build the configured Markdown chunker for indexing."""
    return DocumentChunker(
        child_chunk_chars=settings.RAG_CHILD_CHUNK_TOKENS,
        child_chunk_overlap=settings.RAG_CHILD_CHUNK_OVERLAP,
        chunking_strategy=chunking_strategy,
        semantic_embedding_provider=semantic_embedding_provider,
        semantic_target_chars=settings.RAG_SEMANTIC_TARGET_CHARS,
        semantic_max_chars=settings.RAG_SEMANTIC_MAX_CHARS,
        semantic_min_chars=settings.RAG_SEMANTIC_MIN_CHARS,
        semantic_breakpoint_type=settings.RAG_SEMANTIC_BREAKPOINT_TYPE,
        semantic_breakpoint_amount=settings.RAG_SEMANTIC_BREAKPOINT_AMOUNT,
        table_line_ratio_threshold=settings.RAG_TABLE_LINE_RATIO_THRESHOLD,
        table_chunk_chars=settings.RAG_TABLE_CHUNK_MAX_CHARS,
    )


def build_dense_embedding_provider() -> GoogleGenAIEmbeddingProvider:
    """Build the configured dense embedding provider for Qdrant indexing."""
    if settings.RAG_EMBEDDING_PROVIDER != "google_genai":
        raise ValueError(
            "Unsupported RAG_EMBEDDING_PROVIDER. "
            "Use 'google_genai' for health Markdown indexing."
        )
    return GoogleGenAIEmbeddingProvider(
        model_name=settings.RAG_EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        vector_size=settings.RAG_DENSE_VECTOR_SIZE,
        batch_size=settings.RAG_EMBEDDING_BATCH_SIZE,
        document_task_type=settings.RAG_EMBEDDING_TASK_TYPE_DOCUMENT,
        query_task_type=settings.RAG_EMBEDDING_TASK_TYPE_QUERY,
    )


def build_qdrant_retriever(
    *,
    dense_embedding_provider: Embeddings | None,
) -> QdrantRetriever:
    """Build Qdrant retriever configured for dense vector + BM25 indexing."""
    if dense_embedding_provider is None:
        raise ValueError("Dense embedding provider is required for Qdrant indexing.")
    client_kwargs: dict[str, Any] = {"url": settings.RAG_QDRANT_URL}
    if settings.RAG_QDRANT_API_KEY:
        client_kwargs["api_key"] = settings.RAG_QDRANT_API_KEY
    return QdrantRetriever(
        client=QdrantClient(**client_kwargs),
        collection_name=settings.RAG_QDRANT_COLLECTION,
        embedding_provider=dense_embedding_provider,
        sparse_embedding_provider=FastEmbedSparse(model_name=settings.RAG_SPARSE_MODEL),
        keyword_enabled=True,
    )


def build_neo4j_store() -> Neo4jKnowledgeGraphStore:
    """Build Neo4j graph store from centralized settings."""
    return Neo4jKnowledgeGraphStore.from_connection(
        url=settings.NEO4J_URI,
        username=settings.NEO4J_USERNAME,
        password=settings.NEO4J_PASSWORD,
        database=settings.NEO4J_DATABASE,
    )


def build_graph_documents(
    *,
    documents: list[GraphDocument],
    chunks: list[dict[str, Any]],
    graph_adapter: Any,
) -> list[Any]:
    """Convert extracted document/chunk data to LangChain graph documents."""
    return [graph_adapter.from_document(document, chunks) for document in documents]


def build_and_maybe_write_graph_json(
    *,
    documents: list[GraphDocument],
    chunks: list[dict[str, Any]],
    graph_json_path: Path,
    dry_run: bool,
) -> dict[str, Any]:
    """Build a NetworkX graph quality report and optionally persist graph JSON."""
    graph = KnowledgeGraphBuilder().build_from_documents(documents, chunks)
    report = GraphQualityValidator().validate(
        graph,
        document_counts=document_counts(documents),
        chunk_counts=chunk_counts(chunks),
    )
    if not dry_run:
        GraphJsonSerializer().save(graph, graph_json_path)
    return {
        "is_valid": report.is_valid,
        "node_count": report.node_count,
        "edge_count": report.edge_count,
        "entity_type_counts": report.entity_type_counts,
        "relationship_type_counts": report.relationship_type_counts,
        "orphan_nodes": report.orphan_nodes,
        "missing_document_lineage": report.missing_document_lineage,
        "dangling_chunk_references": report.dangling_chunk_references,
        "low_confidence_edges": report.low_confidence_edges,
        "invalid_relationships": report.invalid_relationships,
    }


def write_chunk_export(chunks: list[ChildChunk], output_path: Path) -> None:
    """Write chunk payloads for graph/debug replay."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "id": chunk.chunk_id,
            "parent_id": chunk.parent_section_id,
            "text": chunk.text,
            "payload": chunk.payload,
        }
        for chunk in chunks
    ]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def infer_document_type(relative_key: str) -> str:
    """Infer a coarse document type from available folder and file names."""
    normalized_key = normalized_lookup_text(relative_key)
    if any(token in normalized_key for token in ["bieu phi", "premium"]):
        return "premium_table"
    if any(
        token in normalized_key
        for token in ["danh sach co so y te", "benh vien", "hospital"]
    ):
        return "hospital_list"
    if any(token in normalized_key for token in ["quy tac", "dieu khoan", "terms"]):
        return "terms_and_rules"
    if "tom tat" in normalized_key:
        return "summary"
    if any(
        token in normalized_key
        for token in ["brochure", "gioi thieu", "tai lieu san pham"]
    ):
        return "product_brochure"
    if any(token in normalized_key for token in ["to khai", "yeu cau bao hiem"]):
        return "form"
    return "policy"


def readable_document_name(stem: str) -> str:
    """Turn a Markdown stem into a readable document name."""
    return re.sub(r"[-_]+", " ", stem).strip() or stem


def stable_identifier(value: str) -> str:
    """Build a deterministic identifier from a relative file path."""
    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value.lower()).strip("_") or "unknown"


def normalized_lookup_text(value: str) -> str:
    """Normalize Vietnamese text for simple filename classification."""
    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    normalized_value = re.sub(r"[^a-zA-Z0-9]+", " ", ascii_value.lower()).strip()
    return re.sub(r"\s+", " ", normalized_value)


def document_counts(documents: list[GraphDocument]) -> dict[str, int]:
    """Count graph source documents by stable document ID."""
    counts: dict[str, int] = {}
    for document in documents:
        counts[document.document_id] = counts.get(document.document_id, 0) + 1
    return counts


def chunk_counts(chunks: list[dict[str, Any]]) -> dict[str, int]:
    """Count graph chunk payloads by source document ID."""
    counts: dict[str, int] = {}
    for chunk in chunks:
        document_id = str(chunk.get("document_id"))
        counts[document_id] = counts.get(document_id, 0) + 1
    return counts


def main() -> None:
    """Run health Markdown indexing into Qdrant and Neo4j."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument(
        "--table-mapping-json", type=Path, default=DEFAULT_TABLE_MAPPING_PATH
    )
    parser.add_argument("--ingestion-version", default=DEFAULT_INGESTION_VERSION)
    parser.add_argument(
        "--chunk-export-json", type=Path, default=DEFAULT_CHUNK_EXPORT_PATH
    )
    parser.add_argument(
        "--graph-json", type=Path, default=Path(settings.GRAPH_JSON_PATH)
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recreate-qdrant", action="store_true")
    parser.add_argument("--skip-qdrant", action="store_true")
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--skip-chunk-export", action="store_true")
    parser.add_argument("--skip-graph-json", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--chunking-strategy",
        choices=["recursive", "hybrid_semantic"],
        default=None,
    )
    args = parser.parse_args()

    report = run_indexing_pipeline(
        markdown_dir=args.markdown_dir,
        table_mapping_path=args.table_mapping_json,
        ingestion_version=args.ingestion_version,
        recreate_qdrant=args.recreate_qdrant,
        dry_run=args.dry_run,
        skip_qdrant=args.skip_qdrant,
        skip_neo4j=args.skip_neo4j,
        chunk_export_path=None if args.skip_chunk_export else args.chunk_export_json,
        graph_json_path=None if args.skip_graph_json else args.graph_json,
        limit=args.limit,
        chunking_strategy=args.chunking_strategy,
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
