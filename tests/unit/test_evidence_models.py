import pytest
from pydantic import ValidationError
from src.models.evidence import (
    Evidence, Citation, RetrievalPlan, HardFilters, BenchmarkCase,
    SourceType, RetrievalMode, IntentGroup, RiskLevel, Workflow
)

def test_hard_filters_validation():
    filters = HardFilters(company_codes=["C01"], document_types=["policy"])
    assert filters.company_codes == ["C01"]
    assert filters.document_types == ["policy"]

def test_retrieval_plan_validation():
    plan = RetrievalPlan(
        search_queries=["premium cost"],
        mode=RetrievalMode.HYBRID,
        filters=HardFilters(company_codes=["C01"])
    )
    assert plan.mode == RetrievalMode.HYBRID
    assert plan.filters.company_codes == ["C01"]

def test_evidence_validation():
    evidence = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="row_123",
        content="Coverage includes hospital stay.",
        metadata={"table": "policy_benefits"},
        confidence=0.95,
        retrieved_by="DatabaseAgent"
    )
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.confidence == 0.95

    with pytest.raises(ValidationError):
        Evidence(
            source_type="INVALID_SOURCE",
            source_id="1",
            content="test",
            metadata={},
            confidence=1.5, # > 1.0 should fail
            retrieved_by="Agent"
        )

def test_citation_validation():
    citation = Citation(
        company_code="C01",
        document_id="DOC123",
        document_name="Policy 2026",
        source_file_path="/docs/policy.pdf",
        source_table_id="table_1",
        page=5
    )
    assert citation.page == 5
    assert citation.company_code == "C01"

def test_benchmark_case_validation():
    case = BenchmarkCase(
        case_id="case_001",
        query="What is the premium?",
        intent_group=IntentGroup.PREMIUM_INQUIRY,
        risk_level=RiskLevel.LOW,
        workflow=Workflow.POLICY_QA,
        expected_evidence_types=[SourceType.SQLITE_ROW]
    )
    assert case.workflow == Workflow.POLICY_QA
