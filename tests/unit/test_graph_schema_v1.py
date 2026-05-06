import csv

from src.services.knowledge_graph.graph_schema import (
    ALLOWED_NODE_LABELS,
    ALLOWED_NODES_CSV_PATH,
    ALLOWED_RELATIONSHIP_TYPES,
    ALLOWED_RELATIONSHIPS_CSV_PATH,
    NODE_PROPERTIES_CSV_PATH,
    NODE_PROPERTY_NAMES,
    RELATIONSHIP_PROPERTIES_CSV_PATH,
    RELATIONSHIP_PROPERTY_NAMES,
    SCHEMA_DIR,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    get_graph_schema_contract,
    get_llm_graph_transformer_schema,
)


def test_graph_schema_v1_exports_labels_and_properties() -> None:
    contract = get_graph_schema_contract()

    assert SCHEMA_NAME == "health_insurance_kg_schema_v1"
    assert SCHEMA_VERSION == "v1"
    assert len(ALLOWED_NODE_LABELS) == 42
    assert len(ALLOWED_RELATIONSHIP_TYPES) == 68
    assert contract["allowed_node_labels"] == list(ALLOWED_NODE_LABELS)
    assert contract["allowed_relationship_types"] == list(ALLOWED_RELATIONSHIP_TYPES)
    assert contract["node_properties"] == list(NODE_PROPERTY_NAMES)
    assert contract["relationship_properties"] == list(RELATIONSHIP_PROPERTY_NAMES)
    assert "id" not in NODE_PROPERTY_NAMES
    assert {"name", "evidence_text", "confidence"} <= set(NODE_PROPERTY_NAMES)
    assert {"amount", "currency", "payment_frequency"} <= set(NODE_PROPERTY_NAMES)
    assert {"source_document_id", "evidence_text", "confidence"} <= set(
        RELATIONSHIP_PROPERTY_NAMES
    )


def test_graph_schema_v1_keeps_only_compact_runtime_files() -> None:
    assert ALLOWED_NODES_CSV_PATH.exists()
    assert ALLOWED_RELATIONSHIPS_CSV_PATH.exists()
    assert NODE_PROPERTIES_CSV_PATH.exists()
    assert RELATIONSHIP_PROPERTIES_CSV_PATH.exists()
    assert not (SCHEMA_DIR / "health_insurance_kg_schema_v1.json").exists()
    assert not (
        SCHEMA_DIR / "health_insurance_kg_schema_v1_node_properties.csv"
    ).exists()
    assert not (
        SCHEMA_DIR / "health_insurance_kg_schema_v1_relationship_properties.csv"
    ).exists()

    node_rows = list(
        csv.DictReader(
            NODE_PROPERTIES_CSV_PATH.read_text(encoding="utf-8").splitlines()
        )
    )
    relationship_rows = list(
        csv.DictReader(
            RELATIONSHIP_PROPERTIES_CSV_PATH.read_text(encoding="utf-8").splitlines()
        )
    )

    assert node_rows[0] == {"property_name": "name"}
    assert relationship_rows[0]["property_name"] == "source_document_id"


def test_graph_schema_v1_exports_compact_transformer_schema() -> None:
    transformer_schema = get_llm_graph_transformer_schema()

    assert transformer_schema == {
        "allowed_nodes": list(ALLOWED_NODE_LABELS),
        "allowed_relationships": list(ALLOWED_RELATIONSHIP_TYPES),
        "node_properties": list(NODE_PROPERTY_NAMES),
        "relationship_properties": list(RELATIONSHIP_PROPERTY_NAMES),
    }
    assert "InsuranceCompany" in transformer_schema["allowed_nodes"]
    assert "HAS_PREMIUM" in transformer_schema["allowed_relationships"]
    assert "id" not in transformer_schema["node_properties"]
    assert {"name", "evidence_text", "confidence"} <= set(
        transformer_schema["node_properties"]
    )
    assert {"source_document_id", "evidence_text", "confidence"} <= set(
        transformer_schema["relationship_properties"]
    )


def test_graph_schema_v1_keeps_sample_style_compact_csv_files() -> None:
    assert ALLOWED_NODES_CSV_PATH.exists()
    assert ALLOWED_RELATIONSHIPS_CSV_PATH.exists()
    assert NODE_PROPERTIES_CSV_PATH.exists()
    assert RELATIONSHIP_PROPERTIES_CSV_PATH.exists()

    allowed_node_rows = list(
        csv.DictReader(ALLOWED_NODES_CSV_PATH.read_text(encoding="utf-8").splitlines())
    )
    allowed_relationship_rows = list(
        csv.DictReader(
            ALLOWED_RELATIONSHIPS_CSV_PATH.read_text(encoding="utf-8").splitlines()
        )
    )
    node_property_rows = list(
        csv.DictReader(
            NODE_PROPERTIES_CSV_PATH.read_text(encoding="utf-8").splitlines()
        )
    )
    relationship_property_rows = list(
        csv.DictReader(
            RELATIONSHIP_PROPERTIES_CSV_PATH.read_text(encoding="utf-8").splitlines()
        )
    )

    assert allowed_node_rows[0] == {"node_type": "InsuranceCompany"}
    assert allowed_relationship_rows[0] == {"relationship_type": "ISSUES"}
    assert node_property_rows[0] == {"property_name": "name"}
    assert relationship_property_rows[0] == {"property_name": "source_document_id"}
