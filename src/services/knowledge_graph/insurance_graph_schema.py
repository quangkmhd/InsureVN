"""Runtime Knowledge Graph schema for Vietnamese health insurance."""

from src.core.vietnamese_text import slugify_vietnamese
from src.services.knowledge_graph.graph_schema import (
    ALLOWED_NODE_LABELS,
    ALLOWED_RELATIONSHIP_TYPES,
    NODE_PROPERTY_NAMES,
    RELATIONSHIP_PROPERTY_NAMES,
)
from src.services.observability import service_observe

REQUIRED_RELATIONSHIP_PROPERTIES = set(RELATIONSHIP_PROPERTY_NAMES)

NEO4J_UNIQUENESS_CONSTRAINTS = tuple(
    (node_label, "id") for node_label in ALLOWED_NODE_LABELS
)
__all__ = [
    "ALLOWED_NODE_LABELS",
    "ALLOWED_RELATIONSHIP_TYPES",
    "NEO4J_UNIQUENESS_CONSTRAINTS",
    "NODE_PROPERTY_NAMES",
    "RELATIONSHIP_PROPERTY_NAMES",
    "REQUIRED_RELATIONSHIP_PROPERTIES",
    "build_chunk_id",
    "build_company_id",
    "build_document_id",
    "build_plan_id",
]


@service_observe(
    name="service.knowledge_graph.insurance_graph_schema.build_company_id",
    component="insurance_graph_schema",
)
def build_company_id(company_code: str) -> str:
    """Build a stable InsuranceCompany node ID."""
    return f"insurance_company:{company_code.strip().upper()}"


@service_observe(
    name="service.knowledge_graph.insurance_graph_schema.build_document_id",
    component="insurance_graph_schema",
)
def build_document_id(document_id: str) -> str:
    """Build a stable InsuranceDocument node ID."""
    return f"insurance_document:{_stable_slug(document_id)}"


@service_observe(
    name="service.knowledge_graph.insurance_graph_schema.build_plan_id",
    component="insurance_graph_schema",
)
def build_plan_id(company_code: str, plan_code: str) -> str:
    """Build a stable InsurancePlan node ID."""
    return f"insurance_plan:{company_code.strip().upper()}:{_stable_slug(plan_code)}"


@service_observe(
    name="service.knowledge_graph.insurance_graph_schema.build_chunk_id",
    component="insurance_graph_schema",
)
def build_chunk_id(document_id: str, chunk_index: int) -> str:
    """Build a stable source chunk identifier for graph lineage."""
    return f"source_chunk:{_stable_slug(document_id)}:{chunk_index}"


def _stable_slug(value: str) -> str:
    return slugify_vietnamese(value, separator="_", fallback="unknown")
