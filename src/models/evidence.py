from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SourceType(str, Enum):
    SQLITE_ROW = "sqlite_row"
    QDRANT_DOC = "qdrant_doc"
    USER_INPUT = "user_input"

class RetrievalMode(str, Enum):
    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"

class IntentGroup(str, Enum):
    PREMIUM_INQUIRY = "premium_inquiry"
    CLAIM_ELIGIBILITY = "claim_eligibility"
    COVERAGE_CHECK = "coverage_check"
    GENERAL_SUPPORT = "general_support"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Workflow(str, Enum):
    POLICY_QA = "policy_qa"
    CLAIM_ASSESSMENT = "claim_assessment"
    GENERAL_SUPPORT = "general_support"

class HardFilters(BaseModel):
    company_codes: Optional[List[str]] = None
    document_types: Optional[List[str]] = None

class RetrievalPlan(BaseModel):
    search_queries: List[str]
    mode: RetrievalMode
    filters: Optional[HardFilters] = None

class Evidence(BaseModel):
    source_type: SourceType
    source_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., le=1.0, ge=0.0)
    retrieved_by: str

class Citation(BaseModel):
    company_code: str
    document_id: str
    document_name: str
    source_file_path: str
    source_table_id: str
    page: Optional[int] = None

class BenchmarkCase(BaseModel):
    case_id: str
    query: str
    intent_group: IntentGroup
    risk_level: RiskLevel
    workflow: Workflow
    expected_evidence_types: List[SourceType]
