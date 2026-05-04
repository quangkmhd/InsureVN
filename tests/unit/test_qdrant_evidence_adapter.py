import pytest

from src.models.evidence import SourceType
from src.services.qdrant_evidence_adapter import QdrantEvidenceAdapter


def test_qdrant_evidence_adapter_preserves_required_citations() -> None:
    payload = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "plan_code": "gold",
        "section_type": "waiting_period",
        "page_number": 12,
        "chunk_index": 3,
        "source_path": "data/processed/aia/health.md",
        "source_table_id": "documents:1",
        "effective_date": "2026-01-01",
        "parent_text": "Thoi gian cho cua benh dac biet la 90 ngay.",
    }

    evidence = QdrantEvidenceAdapter.from_payload(
        point_id="doc-aia-health:waiting-period:3",
        payload=payload,
        score=0.87,
    )

    assert evidence.source_type == SourceType.QDRANT_CHUNK
    assert evidence.source_id == "doc-aia-health:waiting-period:3"
    assert evidence.content == payload["parent_text"]
    assert evidence.confidence == 0.87
    assert evidence.retrieved_by == "QdrantRetriever"
    assert evidence.metadata["company_code"] == "AIA"
    assert evidence.metadata["source_table_id"] == "documents:1"


def test_qdrant_evidence_adapter_rejects_missing_required_payload_fields() -> None:
    payload = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "plan_code": "gold",
        "section_type": "waiting_period",
        "chunk_index": 3,
        "source_path": "data/processed/aia/health.md",
        "source_table_id": "documents:1",
        "effective_date": "2026-01-01",
        "text": "Missing page number.",
    }

    with pytest.raises(ValueError, match="page_number"):
        QdrantEvidenceAdapter.from_payload(
            point_id="doc-aia-health:waiting-period:3",
            payload=payload,
            score=0.87,
        )
