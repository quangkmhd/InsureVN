import pytest

from src.models.evidence import SourceType
from src.services.qdrant_evidence import QdrantEvidenceMapper


def test_qdrant_evidence_mapper_preserves_required_citations() -> None:
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
        "parent_section_id": "doc-aia-health:waiting-period:0",
        "content_hash": "abc123",
        "ingestion_version": "rag-2026-05-05",
        "retrieval_mode": "hybrid",
        "dense_score": 0.71,
        "sparse_score": 0.94,
        "fusion_score": 0.87,
        "parent_text": "Thoi gian cho cua benh dac biet la 90 ngay.",
    }

    evidence = QdrantEvidenceMapper.from_payload(
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
    assert evidence.metadata["retrieval_mode"] == "hybrid"
    assert evidence.metadata["dense_score"] == 0.71
    assert evidence.metadata["sparse_score"] == 0.94
    assert evidence.metadata["fusion_score"] == 0.87


def test_qdrant_evidence_mapper_rejects_missing_required_payload_fields() -> None:
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
        "parent_section_id": "doc-aia-health:waiting-period:0",
        "content_hash": "abc123",
        "ingestion_version": "rag-2026-05-05",
        "text": "Missing page number.",
    }

    with pytest.raises(ValueError, match="page_number"):
        QdrantEvidenceMapper.from_payload(
            point_id="doc-aia-health:waiting-period:3",
            payload=payload,
            score=0.87,
        )


def test_qdrant_evidence_mapper_requires_production_lineage_fields() -> None:
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
        "parent_section_id": "doc-aia-health:waiting-period:0",
        "content_hash": "abc123",
        "text": "Missing ingestion version.",
    }

    with pytest.raises(ValueError, match="ingestion_version"):
        QdrantEvidenceMapper.from_payload(
            point_id="doc-aia-health:waiting-period:3",
            payload=payload,
            score=0.87,
        )
