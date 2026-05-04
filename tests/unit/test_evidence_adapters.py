import pytest
from src.services.evidence_adapters import StructuredEvidenceAdapter, ProfileEvidenceAdapter
from src.models.evidence import SourceType

def test_structured_evidence_adapter():
    mcp_result = {
        "source_table_id": "benefits_1",
        "document_id": "DOC001",
        "source_file_path": "/data/doc.pdf",
        "company_code": "C01",
        "document_name": "Health Policy",
        "benefit_name": "Inpatient",
        "limit_amount": 5000000
    }
    
    evidence = StructuredEvidenceAdapter.from_mcp_result("search_benefits", mcp_result)
    
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.source_id == "benefits_1"
    assert evidence.content == "benefit_name: Inpatient, limit_amount: 5000000"
    assert evidence.metadata["company_code"] == "C01"
    assert evidence.metadata["tool_name"] == "search_benefits"

def test_profile_evidence_adapter():
    profile_row = {
        "user_id": "U123",
        "age": 30,
        "risk_tolerance": "low"
    }
    
    evidence = ProfileEvidenceAdapter.from_profile_row(profile_row)
    
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.source_id == "U123"
    assert "age: 30" in evidence.content
