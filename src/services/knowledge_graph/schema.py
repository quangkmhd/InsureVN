import re
import unicodedata

ALLOWED_NODE_LABELS = {
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
}

ALLOWED_RELATIONSHIP_TYPES = {
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
}

REQUIRED_RELATIONSHIP_PROPERTIES = {
    "source_document_id",
    "source_chunk_id",
    "source_path",
    "page_number",
    "section_type",
    "confidence",
    "extraction_method",
    "ingestion_version",
}

NEO4J_UNIQUENESS_CONSTRAINTS = (
    ("Company", "id"),
    ("Document", "id"),
    ("Plan", "id"),
    ("Benefit", "id"),
    ("Exclusion", "id"),
    ("WaitingPeriod", "id"),
    ("Condition", "id"),
    ("Hospital", "id"),
    ("GlossaryTerm", "id"),
    ("ClaimEvent", "id"),
    ("Section", "id"),
    ("Chunk", "id"),
)


def build_company_id(company_code: str) -> str:
    """Build a stable Company node ID."""
    return f"company:{company_code.strip().upper()}"


def build_document_id(document_id: str) -> str:
    """Build a stable Document node ID."""
    return f"document:{_stable_slug(document_id)}"


def build_plan_id(company_code: str, plan_code: str) -> str:
    """Build a stable Plan node ID."""
    return f"plan:{company_code.strip().upper()}:{_stable_slug(plan_code)}"


def build_chunk_id(document_id: str, chunk_index: int) -> str:
    """Build a stable Chunk node ID."""
    return f"chunk:{_stable_slug(document_id)}:{chunk_index}"


def _stable_slug(value: str) -> str:
    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "unknown"
