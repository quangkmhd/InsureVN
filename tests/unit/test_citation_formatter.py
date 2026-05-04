import pytest
from src.services.citation_formatter import CitationFormatter
from src.models.evidence import Evidence, SourceType

def test_citation_formatter():
    ev = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="row_1",
        content="Benefit XYZ",
        confidence=1.0,
        retrieved_by="Agent",
        metadata={
            "company_code": "C01",
            "document_id": "DOC01",
            "document_name": "Health Policy",
            "source_file_path": "/docs/health.pdf",
            "source_table_id": "table_1",
            "page": 10
        }
    )
    
    citation = CitationFormatter.format(ev)
    
    assert citation is not None
    assert citation.company_code == "C01"
    assert citation.page == 10
    
    # Missing required field
    ev_bad = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="row_2",
        content="Benefit XYZ",
        confidence=1.0,
        retrieved_by="Agent",
        metadata={}
    )
    
    with pytest.raises(ValueError):
        CitationFormatter.validate_required_fields(ev_bad)
