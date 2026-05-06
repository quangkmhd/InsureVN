"""Canonicalize and clean discovered knowledge graph schema labels."""

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
    SchemaCanonicalizationMap,
    SchemaDiscoveryCanonicalizer,
    SchemaDiscoveryProviderSlot,
    apply_canonical_map_to_summary,
    build_normalized_schema_canonical_map,
    build_provider_slots_from_settings,
    filter_schema_summary,
    load_summary_json,
    write_schema_discovery_markdown_report,
    write_summary_json,
)
from src.services.knowledge_graph.insurance_graph_schema_discovery_clients import (  # noqa: E402
    HttpSchemaDiscoveryClient,
)

logger = get_logger(__name__)


def main() -> None:
    """Run canonicalization from existing schema discovery output files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema-discovery-dir",
        type=Path,
        default=Path(settings.KG_SCHEMA_DISCOVERY_OUTPUT_DIR),
        help="Directory containing raw_schema_summary.json.",
    )
    parser.add_argument(
        "--raw-summary-path",
        type=Path,
        default=None,
        help="Optional raw schema summary path. Defaults inside schema-discovery-dir.",
    )
    parser.add_argument(
        "--canonical-provider-slot-id",
        default="",
        help="Provider slot ID for AI schema merging. Defaults to the first slot.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=60,
        help="Maximum node/relationship labels sent per canonicalization batch.",
    )
    parser.add_argument(
        "--provider-timeout-seconds",
        type=float,
        default=settings.KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS,
        help="HTTP timeout for each canonicalization provider request.",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Use deterministic ASCII-safe normalization without provider calls.",
    )
    parser.add_argument(
        "--min-node-occurrences",
        type=int,
        default=5,
        help="Minimum occurrences for non-protected node labels in clean summary.",
    )
    parser.add_argument(
        "--min-relationship-occurrences",
        type=int,
        default=5,
        help="Minimum occurrences for non-protected relationships in clean summary.",
    )
    parser.add_argument(
        "--min-source-files",
        type=int,
        default=3,
        help="Minimum source files for non-protected labels in clean summary.",
    )
    args = parser.parse_args()

    asyncio.run(_main_async(args))


async def _main_async(args: argparse.Namespace) -> None:
    schema_discovery_dir: Path = args.schema_discovery_dir
    raw_summary_path = args.raw_summary_path or (
        schema_discovery_dir / "raw_schema_summary.json"
    )
    raw_summary = load_summary_json(raw_summary_path)
    provider_slots = build_provider_slots_from_settings()

    if args.skip_ai:
        canonical_map = build_normalized_schema_canonical_map(raw_summary)
        canonical_provider_slot_id = ""
    else:
        if not provider_slots:
            raise ValueError("No schema canonicalization provider slots configured.")
        canonical_slot = _select_canonicalization_slot(
            provider_slots,
            args.canonical_provider_slot_id,
        )
        canonical_provider_slot_id = canonical_slot.slot_id
        canonical_map = await SchemaDiscoveryCanonicalizer().canonicalize_in_batches(
            raw_summary=raw_summary,
            client=HttpSchemaDiscoveryClient(
                timeout_seconds=args.provider_timeout_seconds
            ),
            slot=canonical_slot,
            batch_size=args.batch_size,
            batch_timeout_seconds=args.provider_timeout_seconds,
            fallback_to_normalized_identity=True,
        )

    canonical_summary = apply_canonical_map_to_summary(raw_summary, canonical_map)
    clean_summary = filter_schema_summary(
        canonical_summary,
        min_node_occurrences=args.min_node_occurrences,
        min_relationship_occurrences=args.min_relationship_occurrences,
        min_source_files=args.min_source_files,
    )

    canonical_map_path = schema_discovery_dir / "canonical_schema_map.json"
    canonical_candidates_path = (
        schema_discovery_dir / "canonical_schema_candidates.json"
    )
    canonical_summary_path = schema_discovery_dir / "canonical_schema_summary.json"
    clean_summary_path = schema_discovery_dir / "clean_schema_summary.json"
    clean_report_path = schema_discovery_dir / "clean_schema_summary.md"

    canonical_map_path.write_text(
        json.dumps(asdict(canonical_map), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_summary_json(canonical_summary, canonical_summary_path)
    write_summary_json(clean_summary, clean_summary_path)
    write_schema_discovery_markdown_report(clean_summary, clean_report_path)
    canonical_candidates_path.write_text(
        json.dumps(
            _canonicalization_candidate_report(
                raw_summary_path=raw_summary_path,
                canonical_provider_slot_id=canonical_provider_slot_id,
                batch_size=args.batch_size,
                canonical_map=canonical_map,
                raw_node_count=len(raw_summary.nodes),
                raw_relationship_count=len(raw_summary.relationships),
                canonical_node_count=len(canonical_summary.nodes),
                canonical_relationship_count=len(canonical_summary.relationships),
                clean_node_count=len(clean_summary.nodes),
                clean_relationship_count=len(clean_summary.relationships),
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info(
        "completed schema canonicalization",
        extra={
            "component": "insurance_graph_schema_discovery",
            "raw_node_count": len(raw_summary.nodes),
            "raw_relationship_count": len(raw_summary.relationships),
            "canonical_node_count": len(canonical_summary.nodes),
            "canonical_relationship_count": len(canonical_summary.relationships),
            "clean_node_count": len(clean_summary.nodes),
            "clean_relationship_count": len(clean_summary.relationships),
            "output_dir": str(schema_discovery_dir),
        },
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "canonical_map_path": str(canonical_map_path),
                "canonical_candidates_path": str(canonical_candidates_path),
                "canonical_summary_path": str(canonical_summary_path),
                "clean_summary_path": str(clean_summary_path),
                "clean_report_path": str(clean_report_path),
            },
            ensure_ascii=False,
        )
    )


def _canonicalization_candidate_report(
    *,
    raw_summary_path: Path,
    canonical_provider_slot_id: str,
    batch_size: int,
    canonical_map: SchemaCanonicalizationMap,
    raw_node_count: int,
    raw_relationship_count: int,
    canonical_node_count: int,
    canonical_relationship_count: int,
    clean_node_count: int,
    clean_relationship_count: int,
) -> dict[str, object]:
    return {
        "raw_summary_path": str(raw_summary_path),
        "canonical_provider_slot_id": canonical_provider_slot_id,
        "batch_size": batch_size,
        "raw_node_count": raw_node_count,
        "raw_relationship_count": raw_relationship_count,
        "canonical_node_count": canonical_node_count,
        "canonical_relationship_count": canonical_relationship_count,
        "clean_node_count": clean_node_count,
        "clean_relationship_count": clean_relationship_count,
        "node_changed_count": sum(
            1
            for raw_label, canonical_label in canonical_map.node_map.items()
            if raw_label != canonical_label
        ),
        "relationship_changed_count": sum(
            1
            for raw_label, canonical_label in canonical_map.relationship_map.items()
            if raw_label != canonical_label
        ),
        "node_map": canonical_map.node_map,
        "relationship_map": canonical_map.relationship_map,
    }


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
