"""Select the compact v1 knowledge graph schema from cleaned discovery output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.config import settings  # noqa: E402
from src.core.logger import get_logger  # noqa: E402
from src.services.knowledge_graph.insurance_graph_schema_discovery import (  # noqa: E402
    build_final_schema_v1,
    build_final_schema_v1_contract,
    load_summary_json,
    write_final_schema_v1_property_csvs,
    write_schema_discovery_markdown_report,
    write_summary_json,
)

logger = get_logger(__name__)

GRAPH_SCHEMA_DIR = REPO_ROOT / "src/services/knowledge_graph/graph_schema"


def main() -> None:
    """Run final v1 schema selection from clean_schema_summary.json."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema-discovery-dir",
        type=Path,
        default=Path(settings.KG_SCHEMA_DISCOVERY_OUTPUT_DIR),
        help="Directory containing clean_schema_summary.json.",
    )
    parser.add_argument(
        "--clean-summary-path",
        type=Path,
        default=None,
        help=(
            "Optional clean schema summary path. Defaults inside schema-discovery-dir."
        ),
    )
    parser.add_argument(
        "--max-node-labels",
        type=int,
        default=60,
        help="Maximum node labels to keep in final schema v1.",
    )
    parser.add_argument(
        "--max-relationship-labels",
        type=int,
        default=90,
        help="Maximum relationship labels to keep in final schema v1.",
    )
    parser.add_argument(
        "--graph-schema-dir",
        type=Path,
        default=GRAPH_SCHEMA_DIR,
        help="Runtime graph schema directory to update with v1 contract files.",
    )
    args = parser.parse_args()

    schema_discovery_dir: Path = args.schema_discovery_dir
    clean_summary_path = args.clean_summary_path or (
        schema_discovery_dir / "clean_schema_summary.json"
    )
    clean_summary = load_summary_json(clean_summary_path)
    final_summary = build_final_schema_v1(
        clean_summary,
        max_node_labels=args.max_node_labels,
        max_relationship_labels=args.max_relationship_labels,
    )
    contract = build_final_schema_v1_contract(final_summary)

    final_summary_path = schema_discovery_dir / "final_schema_v1_summary.json"
    final_report_path = schema_discovery_dir / "final_schema_v1_summary.md"
    contract_path = schema_discovery_dir / "final_schema_v1_contract.json"
    property_contract_path = (
        schema_discovery_dir / "final_schema_v1_property_contract.json"
    )

    write_summary_json(final_summary, final_summary_path)
    write_schema_discovery_markdown_report(final_summary, final_report_path)
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    property_contract_path.write_text(
        json.dumps(
            {
                "schema_name": contract["schema_name"],
                "schema_version": contract["schema_version"],
                "node_properties": contract["node_properties"],
                "relationship_properties": contract["relationship_properties"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    property_csv_paths = write_final_schema_v1_property_csvs(
        contract,
        schema_discovery_dir,
    )
    graph_schema_paths = _write_runtime_graph_schema_files(
        contract=contract,
        graph_schema_dir=args.graph_schema_dir,
    )

    logger.info(
        "completed final schema v1 selection",
        extra={
            "component": "insurance_graph_schema_discovery",
            "clean_node_count": len(clean_summary.nodes),
            "clean_relationship_count": len(clean_summary.relationships),
            "final_node_count": len(final_summary.nodes),
            "final_relationship_count": len(final_summary.relationships),
            "output_dir": str(schema_discovery_dir),
        },
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "clean_node_count": len(clean_summary.nodes),
                "clean_relationship_count": len(clean_summary.relationships),
                "final_node_count": len(final_summary.nodes),
                "final_relationship_count": len(final_summary.relationships),
                "final_summary_path": str(final_summary_path),
                "final_report_path": str(final_report_path),
                "contract_path": str(contract_path),
                "property_contract_path": str(property_contract_path),
                "node_properties_csv_path": str(property_csv_paths["node_properties"]),
                "relationship_properties_csv_path": str(
                    property_csv_paths["relationship_properties"]
                ),
                "runtime_allowed_nodes_csv_path": str(
                    graph_schema_paths["allowed_nodes"]
                ),
                "runtime_allowed_relationships_csv_path": str(
                    graph_schema_paths["allowed_relationships"]
                ),
                "runtime_node_properties_csv_path": str(
                    graph_schema_paths["node_properties"]
                ),
                "runtime_relationship_properties_csv_path": str(
                    graph_schema_paths["relationship_properties"]
                ),
            },
            ensure_ascii=False,
        )
    )


def _write_runtime_graph_schema_files(
    *,
    contract: dict[str, object],
    graph_schema_dir: Path,
) -> dict[str, Path]:
    graph_schema_dir.mkdir(parents=True, exist_ok=True)
    allowed_nodes_path = graph_schema_dir / "allowed_nodes.csv"
    allowed_relationships_path = graph_schema_dir / "allowed_relationships.csv"
    node_properties_path = graph_schema_dir / "node_properties.csv"
    relationship_properties_path = graph_schema_dir / "relationship_properties.csv"
    _write_single_column_csv(
        allowed_nodes_path,
        header="node_type",
        values=[str(label) for label in contract["allowed_node_labels"]],
    )
    _write_single_column_csv(
        allowed_relationships_path,
        header="relationship_type",
        values=[str(label) for label in contract["allowed_relationship_types"]],
    )
    _write_single_column_csv(
        node_properties_path,
        header="property_name",
        values=_unique_compact_property_names(
            labels=[str(label) for label in contract["allowed_node_labels"]],
            property_payload=dict(contract["node_properties"]),
            excluded_names={"id"},
        ),
    )
    _write_single_column_csv(
        relationship_properties_path,
        header="property_name",
        values=_unique_compact_property_names(
            labels=[str(label) for label in contract["allowed_relationship_types"]],
            property_payload=dict(contract["relationship_properties"]),
            excluded_names={"id"},
        ),
    )
    return {
        "allowed_nodes": allowed_nodes_path,
        "allowed_relationships": allowed_relationships_path,
        "node_properties": node_properties_path,
        "relationship_properties": relationship_properties_path,
    }


def _write_single_column_csv(path: Path, *, header: str, values: list[str]) -> None:
    lines = [header, *values]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _unique_compact_property_names(
    *,
    labels: list[str],
    property_payload: dict[str, object],
    excluded_names: set[str],
) -> list[str]:
    property_names: list[str] = []
    for label in labels:
        raw_property_definitions = property_payload.get(label, [])
        if not isinstance(raw_property_definitions, list):
            continue
        for raw_property_definition in raw_property_definitions:
            if not isinstance(raw_property_definition, dict):
                continue
            property_name = str(raw_property_definition.get("name", ""))
            if not property_name or property_name in excluded_names:
                continue
            if property_name not in property_names:
                property_names.append(property_name)
    return property_names


if __name__ == "__main__":
    main()
