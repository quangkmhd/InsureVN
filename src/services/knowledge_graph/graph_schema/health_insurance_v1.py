"""Compact runtime schema for LangChain graph extraction."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

SCHEMA_NAME = "health_insurance_kg_schema_v1"
SCHEMA_VERSION = "v1"
SCHEMA_DIR = Path(__file__).resolve().parent
ALLOWED_NODES_CSV_PATH = SCHEMA_DIR / "allowed_nodes.csv"
ALLOWED_RELATIONSHIPS_CSV_PATH = SCHEMA_DIR / "allowed_relationships.csv"
NODE_PROPERTIES_CSV_PATH = SCHEMA_DIR / "node_properties.csv"
RELATIONSHIP_PROPERTIES_CSV_PATH = SCHEMA_DIR / "relationship_properties.csv"


@lru_cache(maxsize=1)
def get_graph_schema_contract() -> dict[str, object]:
    """Build the compact graph schema contract from runtime CSV files."""
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "allowed_node_labels": list(ALLOWED_NODE_LABELS),
        "allowed_relationship_types": list(ALLOWED_RELATIONSHIP_TYPES),
        "node_properties": list(NODE_PROPERTY_NAMES),
        "relationship_properties": list(RELATIONSHIP_PROPERTY_NAMES),
    }


def get_llm_graph_transformer_schema() -> dict[str, list[str]]:
    """Return compact schema lists for LangChain LLMGraphTransformer."""
    return {
        "allowed_nodes": list(ALLOWED_NODE_LABELS),
        "allowed_relationships": list(ALLOWED_RELATIONSHIP_TYPES),
        "node_properties": list(NODE_PROPERTY_NAMES),
        "relationship_properties": list(RELATIONSHIP_PROPERTY_NAMES),
    }


def _read_single_column_csv(path: Path, column_name: str) -> tuple[str, ...]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        values: list[str] = []
        for row in reader:
            value = str(row[column_name]).strip()
            if value:
                values.append(value)
        return tuple(values)


ALLOWED_NODE_LABELS = _read_single_column_csv(
    ALLOWED_NODES_CSV_PATH,
    "node_type",
)
ALLOWED_RELATIONSHIP_TYPES = _read_single_column_csv(
    ALLOWED_RELATIONSHIPS_CSV_PATH,
    "relationship_type",
)
NODE_PROPERTY_NAMES = _read_single_column_csv(
    NODE_PROPERTIES_CSV_PATH,
    "property_name",
)
RELATIONSHIP_PROPERTY_NAMES = _read_single_column_csv(
    RELATIONSHIP_PROPERTIES_CSV_PATH,
    "property_name",
)
