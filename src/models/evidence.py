from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    SQLITE_ROW = "sqlite_row"
    QDRANT_CHUNK = "qdrant_chunk"
    QDRANT_DOC = "qdrant_doc"
    GRAPH_TRIPLE = "graph_triple"
    USER_INPUT = "user_input"


class RetrievalMode(StrEnum):
    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"


class IntentGroup(StrEnum):
    PREMIUM_INQUIRY = "premium_inquiry"
    CLAIM_ELIGIBILITY = "claim_eligibility"
    COVERAGE_CHECK = "coverage_check"
    GENERAL_SUPPORT = "general_support"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Workflow(StrEnum):
    POLICY_QA = "policy_qa"
    CLAIM_ASSESSMENT = "claim_assessment"
    GENERAL_SUPPORT = "general_support"


class HardFilters(BaseModel):
    company_codes: list[str] | None = None
    document_ids: list[str] | None = None
    document_types: list[str] | None = None
    product_lines: list[str] | None = None
    plan_codes: list[str] | None = None
    section_types: list[str] | None = None


class RetrievalPlan(BaseModel):
    search_queries: list[str]
    mode: RetrievalMode
    filters: HardFilters | None = None
    top_k: int = Field(default=5, ge=1)


class Evidence(BaseModel):
    source_type: SourceType
    source_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., le=1.0, ge=0.0)
    retrieved_by: str


class Citation(BaseModel):
    company_code: str
    document_id: str | None = None
    document_name: str | None = None
    source_file_path: str | None = None
    source_table_id: str | None = None
    page: int | None = None


class BenchmarkCase(BaseModel):
    case_id: str
    query: str
    intent_group: IntentGroup
    risk_level: RiskLevel
    workflow: Workflow
    expected_evidence_types: list[SourceType]
