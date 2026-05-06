from src.services.knowledge_graph.insurance_graph_schema import (
    ALLOWED_NODE_LABELS,
    ALLOWED_RELATIONSHIP_TYPES,
    NEO4J_UNIQUENESS_CONSTRAINTS,
    NODE_PROPERTY_NAMES,
    RELATIONSHIP_PROPERTY_NAMES,
    REQUIRED_RELATIONSHIP_PROPERTIES,
    build_chunk_id,
    build_company_id,
    build_document_id,
    build_plan_id,
)


def test_knowledge_graph_schema_uses_runtime_health_insurance_v1() -> None:
    assert len(ALLOWED_NODE_LABELS) == 42
    assert len(ALLOWED_RELATIONSHIP_TYPES) == 68
    assert {
        "InsuranceCompany",
        "InsurancePolicy",
        "InsuranceDocument",
        "InsurancePlan",
        "Benefit",
        "Exclusion",
        "WaitingPeriod",
        "Claim",
        "MedicalFacility",
    } <= set(ALLOWED_NODE_LABELS)
    assert {
        "ISSUES",
        "HAS_BENEFIT",
        "HAS_EXCLUSION",
        "HAS_WAITING_PERIOD",
        "REQUIRES_DOCUMENT",
        "DEFINED_IN",
        "GOVERNED_BY",
    } <= set(ALLOWED_RELATIONSHIP_TYPES)
    assert "Plan" not in ALLOWED_NODE_LABELS
    assert "DOCUMENT_DEFINES" not in ALLOWED_RELATIONSHIP_TYPES


def test_knowledge_graph_schema_exposes_property_contracts() -> None:
    assert "source_document_id" in NODE_PROPERTY_NAMES
    assert "source_chunk_id" in NODE_PROPERTY_NAMES
    assert "evidence_text" in NODE_PROPERTY_NAMES
    assert "source_document_id" in RELATIONSHIP_PROPERTY_NAMES
    assert "confidence" in REQUIRED_RELATIONSHIP_PROPERTIES
    assert "page_number" not in REQUIRED_RELATIONSHIP_PROPERTIES


def test_knowledge_graph_schema_builds_stable_v1_node_ids() -> None:
    assert build_company_id("AIA") == "insurance_company:AIA"
    assert build_document_id("aia health 2026") == "insurance_document:aia_health_2026"
    assert build_plan_id("AIA", "Gold Plus") == "insurance_plan:AIA:gold_plus"
    assert build_chunk_id("aia health 2026", 12) == "source_chunk:aia_health_2026:12"


def test_knowledge_graph_schema_defines_v1_uniqueness_constraints() -> None:
    assert ("InsuranceCompany", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
    assert ("InsuranceDocument", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
    assert ("InsurancePlan", "id") in NEO4J_UNIQUENESS_CONSTRAINTS
    assert ("Plan", "id") not in NEO4J_UNIQUENESS_CONSTRAINTS
