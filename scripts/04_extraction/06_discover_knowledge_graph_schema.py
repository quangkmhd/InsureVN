"""Discover candidate knowledge graph schema from Vietnamese markdown files."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.config import settings  # noqa: E402
from src.core.logger import get_logger  # noqa: E402
from src.services.knowledge_graph.insurance_graph_schema_discovery import (  # noqa: E402
    MarkdownSchemaDiscoveryChunker,
    SchemaDiscoveryAggregator,
    SchemaDiscoveryCanonicalizer,
    SchemaDiscoveryCheckpointStore,
    SchemaDiscoveryProviderSlot,
    SchemaDiscoveryRunner,
    build_provider_slots_from_settings,
    find_markdown_files,
    write_schema_discovery_markdown_report,
    write_summary_json,
)
from src.services.knowledge_graph.insurance_graph_schema_discovery_clients import (  # noqa: E402
    HttpSchemaDiscoveryClient,
)

logger = get_logger(__name__)


def main() -> None:
    """Run schema discovery from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-document-path",
        type=Path,
        default=Path("data/processed"),
        help="Markdown/TXT file or directory to scan.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(settings.KG_SCHEMA_DISCOVERY_OUTPUT_DIR),
        help="Directory for checkpoint, summaries, and report files.",
    )
    parser.add_argument(
        "--checkpoint-path",
        type=Path,
        default=None,
        help="Optional JSONL checkpoint path. Defaults inside output-dir.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=settings.KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY,
        help="Maximum concurrent provider slots.",
    )
    parser.add_argument(
        "--attempt-timeout-seconds",
        type=float,
        default=settings.KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS,
        help="Hard timeout for one provider attempt before retrying.",
    )
    parser.add_argument(
        "--canonical-provider-slot-id",
        default="",
        help="Provider slot ID for AI schema merging. Defaults to the first slot.",
    )
    parser.add_argument(
        "--skip-canonicalization",
        action="store_true",
        help="Only write raw summary without AI schema merging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print file/chunk/provider counts without calling provider APIs.",
    )
    args = parser.parse_args()

    asyncio.run(_main_async(args))


async def _main_async(args: argparse.Namespace) -> None:
    output_dir: Path = args.output_dir
    checkpoint_path = args.checkpoint_path or output_dir / "checkpoint.jsonl"
    markdown_files = find_markdown_files(args.input_document_path)
    chunks = MarkdownSchemaDiscoveryChunker(
        max_chunk_chars=settings.KG_SCHEMA_DISCOVERY_CHUNK_CHARS,
        overlap_chars=settings.KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP,
    ).chunk_files(markdown_files)
    provider_slots = build_provider_slots_from_settings()

    run_plan = {
        "input_document_path": str(args.input_document_path),
        "output_dir": str(output_dir),
        "checkpoint_path": str(checkpoint_path),
        "file_count": len(markdown_files),
        "chunk_count": len(chunks),
        "provider_slot_count": len(provider_slots),
        "provider_slots": [slot.slot_id for slot in provider_slots],
        "attempt_timeout_seconds": args.attempt_timeout_seconds,
        "dry_run": args.dry_run,
    }
    print(json.dumps(run_plan, ensure_ascii=False))
    if args.dry_run:
        return
    if not chunks:
        raise ValueError("No markdown or text chunks found for schema discovery.")
    if not provider_slots:
        raise ValueError("No schema discovery provider slots configured.")

    checkpoint_store = SchemaDiscoveryCheckpointStore(checkpoint_path)
    runner = SchemaDiscoveryRunner(
        checkpoint_store=checkpoint_store,
        provider_slots=provider_slots,
        max_concurrency=args.max_concurrency,
        attempt_timeout_seconds=args.attempt_timeout_seconds,
    )
    client = HttpSchemaDiscoveryClient()
    results = await runner.run(chunks=chunks, client=client)

    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_results_path = output_dir / "chunk_results.json"
    chunk_results_path.write_text(
        json.dumps(
            [asdict(result) for result in results],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    aggregator = SchemaDiscoveryAggregator()
    raw_summary = aggregator.aggregate(results)
    raw_summary_path = output_dir / "raw_schema_summary.json"
    write_summary_json(raw_summary, raw_summary_path)

    if args.skip_canonicalization:
        final_summary = raw_summary
        canonical_map_payload = {"node_map": {}, "relationship_map": {}}
    else:
        canonical_slot = _select_canonicalization_slot(
            provider_slots,
            args.canonical_provider_slot_id,
        )
        canonical_map = await SchemaDiscoveryCanonicalizer().canonicalize(
            raw_summary=raw_summary,
            client=client,
            slot=canonical_slot,
            fallback_to_identity=True,
        )
        canonical_map_payload = asdict(canonical_map)
        final_summary = aggregator.aggregate(
            results,
            canonical_node_map=canonical_map.node_map,
            canonical_relationship_map=canonical_map.relationship_map,
        )

    canonical_map_path = output_dir / "canonical_schema_map.json"
    canonical_map_path.write_text(
        json.dumps(canonical_map_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    final_summary_path = output_dir / "schema_summary.json"
    final_report_path = output_dir / "schema_summary.md"
    write_summary_json(final_summary, final_summary_path)
    write_schema_discovery_markdown_report(final_summary, final_report_path)

    logger.info(
        "completed schema discovery",
        extra={
            "component": "insurance_graph_schema_discovery",
            "file_count": len(markdown_files),
            "chunk_count": len(chunks),
            "result_count": len(results),
            "node_schema_count": len(final_summary.nodes),
            "relationship_schema_count": len(final_summary.relationships),
            "output_dir": str(output_dir),
        },
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "chunk_results_path": str(chunk_results_path),
                "raw_summary_path": str(raw_summary_path),
                "canonical_map_path": str(canonical_map_path),
                "summary_path": str(final_summary_path),
                "report_path": str(final_report_path),
                "processed_chunk_count": len(results),
            },
            ensure_ascii=False,
        )
    )


def _select_canonicalization_slot(
    provider_slots: list[SchemaDiscoveryProviderSlot],
    requested_slot_id: str,
) -> SchemaDiscoveryProviderSlot:
    if requested_slot_id:
        for slot in provider_slots:
            if slot.slot_id == requested_slot_id:
                return slot
        raise ValueError(f"Unknown canonical provider slot: {requested_slot_id}")
    return provider_slots[0]


if __name__ == "__main__":
    main()
