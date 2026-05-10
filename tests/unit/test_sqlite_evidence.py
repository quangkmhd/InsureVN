import pytest
from src.services.evidence.sqlite_evidence import SqliteEvidenceMapper, SqliteProfileMapper
from src.models.evidence import SourceType

def test_sqlite_evidence_mapper(mcp_result_fixture):
    evidence = SqliteEvidenceMapper.from_mcp_result("search_benefits", mcp_result_fixture)
    
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.source_id == "benefits_1"
    assert evidence.content == "benefit_name: Inpatient, limit_amount: 5000000"
    assert evidence.metadata["company_code"] == "C01"
    assert evidence.metadata["tool_name"] == "search_benefits"

def test_sqlite_profile_mapper(profile_row_fixture):
    evidence = SqliteProfileMapper.from_profile_row(profile_row_fixture)
    
    assert evidence.source_type == SourceType.SQLITE_ROW
    assert evidence.source_id == "U123"
    assert "age: 30" in evidence.content
