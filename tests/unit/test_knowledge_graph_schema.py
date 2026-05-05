from src.services.knowledge_graph.schema import (
    ALLOWED_NODE_LABELS,
    ALLOWED_RELATIONSHIP_TYPES,
    NEO4J_UNIQUENESS_CONSTRAINTS,
    build_chunk_id,
    build_company_id,
    build_document_id,
    build_plan_id,
)


def test_knowledge_graph_schema_includes_product_labels_and_relationships() -> None:
    assert {
        "Company",
        "Document",
        "Plan",
        "Benefit",
        "Exclusion",
        "WaitingPeriod",
        "Condition",
        "Hospital",
        "GlossaryTerm",
        "ClaimEvent",
        "Section",
        "Chunk",
    } <= ALLOWED_NODE_LABELS
    assert {
        "OFFERS",
        "INCLUDES",
        "EXCLUDES",
        "APPLIES_TO",
        "HAS_WAITING_PERIOD",
        "USES_NETWORK",
        "DOCUMENT_DEFINES",
        "DOCUMENT_CONTAINS",
        "SECTION_CONTAINS",
        "MENTIONED_IN",
        "COVERS",
        "GOVERNED_BY",
        "BLOCKED_BY",
    } <= ALLOWED_RELATIONSHIP_TYPES


def test_knowledge_graph_schema_builds_stable_node_ids() -> None:
    assert build_company_id("AIA") == "company:AIA"
    assert build_document_id("aia health 2026") == "document:aia_health_2026"
    assert build_plan_id("AIA", "Gold Plus") == "plan:AIA:gold_plus"
    assert build_chunk_id("aia health 2026", 12) == "chunk:aia_health_2026:12"


def test_knowledge_graph_schema_defines_neo4j_uniqueness_constraints() -> None:
    assert ("Company", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
    assert ("Document", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
    assert ("Plan", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
    assert ("Chunk", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
