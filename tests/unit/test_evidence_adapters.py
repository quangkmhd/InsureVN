import pytest
from src.services.evidence_adapters import StructuredEvidenceAdapter, ProfileEvidenceAdapter
from src.models.evidence import SourceType

def test_structured_evidence_adapter(mcp_result_fixture):
    evidence = StructuredEvidenceAdapter.from_mcp_result("search_benefits", mcp_result_fixture)
    
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.source_id == "benefits_1"
    assert evidence.content == "benefit_name: Inpatient, limit_amount: 5000000"
    assert evidence.metadata["company_code"] == "C01"
    assert evidence.metadata["tool_name"] == "search_benefits"

def test_profile_evidence_adapter(profile_row_fixture):
    evidence = ProfileEvidenceAdapter.from_profile_row(profile_row_fixture)
    
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.source_id == "U123"
    assert "age: 30" in evidence.content
