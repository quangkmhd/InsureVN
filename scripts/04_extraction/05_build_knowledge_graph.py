"""Build the document-derived InsureVN knowledge graph JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.config import settings  # noqa: E402
from src.services.knowledge_graph.builder import KnowledgeGraphBuilder  # noqa: E402
from src.services.knowledge_graph.document_extractor import GraphDocument  # noqa: E402
from src.services.knowledge_graph.quality import GraphQualityValidator  # noqa: E402
from src.services.knowledge_graph.serializer import GraphJsonSerializer  # noqa: E402


def main() -> None:
    """Build and optionally persist the Knowledge Graph from document files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-document-path",
        type=Path,
        default=Path("data/processed"),
        help="Markdown/PDF-converted text file or directory.",
    )
    parser.add_argument(
        "--qdrant-payload-export-path",
        type=Path,
        default=None,
        help="Optional JSON file containing exported Qdrant chunk payloads.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path(settings.GRAPH_JSON_PATH),
        help="Output graph JSON path.",
    )
    parser.add_argument(
        "--quality-report-path",
        type=Path,
        default=None,
        help="Optional quality report JSON path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate without writing the graph JSON.",
    )
    args = parser.parse_args()

    chunks = _load_chunks(args.qdrant_payload_export_path)
    documents = _load_documents(args.input_document_path, chunks)
    graph = KnowledgeGraphBuilder().build_from_documents(documents, chunks)
    report = GraphQualityValidator().validate(
        graph,
        document_counts=_document_counts(documents),
        chunk_counts=_chunk_counts(chunks),
    )

    if not args.dry_run:
        GraphJsonSerializer().save(graph, args.output_path)
    report_payload = {
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
        "dry_run": args.dry_run,
    }
    if args.quality_report_path is not None:
        args.quality_report_path.parent.mkdir(parents=True, exist_ok=True)
        args.quality_report_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(report_payload, ensure_ascii=False))


def _load_chunks(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    if isinstance(payload, dict) and isinstance(payload.get("chunks"), list):
        return [dict(item) for item in payload["chunks"]]
    msg = "Qdrant payload export must be a list or an object with a chunks list."
    raise ValueError(msg)


def _load_documents(path: Path, chunks: list[dict[str, Any]]) -> list[GraphDocument]:
    files = _document_files(path)
    root_path = path if path.is_dir() else path.parent
    documents: list[GraphDocument] = []
    chunk_lookup: dict[str, dict[str, Any]] = {}
    basename_lookup: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        for key in _chunk_source_keys(chunk):
            chunk_lookup.setdefault(key, chunk)
        source_path = chunk.get("source_path")
        if source_path:
            basename_lookup.setdefault(Path(str(source_path)).name, []).append(chunk)
    for file_path in files:
        chunk = _matching_chunk(file_path, root_path, chunk_lookup, basename_lookup)
        document_id = str(chunk.get("document_id") or file_path.stem)
        documents.append(
            GraphDocument(
                document_id=document_id,
                document_name=str(chunk.get("document_name") or file_path.stem),
                company_code=str(chunk.get("company_code") or "UNKNOWN"),
                source_path=str(file_path),
                text=file_path.read_text(encoding="utf-8"),
            )
        )
    return documents


def _document_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        file_path
        for file_path in path.rglob("*")
        if file_path.suffix.lower() in {".md", ".markdown", ".txt"}
    )


def _matching_chunk(
    file_path: Path,
    root_path: Path,
    chunk_lookup: dict[str, dict[str, Any]],
    basename_lookup: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    relative_path = file_path.relative_to(root_path)
    keys = {
        str(file_path),
        str(file_path.resolve()),
        str(relative_path),
        relative_path.as_posix(),
        file_path.as_posix(),
    }
    for key in keys:
        if key in chunk_lookup:
            return chunk_lookup[key]
    basename_matches = basename_lookup.get(file_path.name, [])
    if len(basename_matches) == 1:
        return basename_matches[0]
    return {}


def _chunk_source_keys(chunk: dict[str, Any]) -> set[str]:
    source_path = chunk.get("source_path")
    if not source_path:
        return set()
    path = Path(str(source_path))
    keys = {str(source_path), path.as_posix()}
    if path.is_absolute():
        keys.add(str(path.resolve()))
    return keys


def _document_counts(documents: list[GraphDocument]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for document in documents:
        counts[document.document_id] = counts.get(document.document_id, 0) + 1
    return counts


def _chunk_counts(chunks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        document_id = str(chunk.get("document_id"))
        counts[document_id] = counts.get(document_id, 0) + 1
    return counts


if __name__ == "__main__":
    main()
