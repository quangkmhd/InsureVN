import pytest
from langchain_core.cross_encoders import BaseCrossEncoder
from langchain_core.documents import Document

from src.models.evidence import Evidence, SourceType
from src.services.evidence_merger import EvidenceMerger, EvidenceReranker


class StaticInsuranceCrossEncoder(BaseCrossEncoder):
    """Deterministic cross-encoder stub for rerank method tests."""

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        """Return higher scores for the intended evidence snippets."""
        scores: list[float] = []
        for _query, text in text_pairs:
            if "limit_amount: 100000000" in text:
                scores.append(0.91)
            elif "EXCLUDES" in text:
                scores.append(0.88)
            elif "Avastin" in text:
                scores.append(0.86)
            elif "Điều khoản bảo hiểm nội trú" in text:
                scores.append(0.22)
            else:
                scores.append(0.1)
        return scores


class MixedRangeCrossEncoder(BaseCrossEncoder):
    """Cross-encoder stub with positive and negative provider scores."""

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        """Return mixed-range scores like Jina can return."""
        assert len(text_pairs) == 2
        return [0.31, -0.08]


def test_evidence_merger_deduplication() -> None:
    ev1 = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="1",
        content="Same content",
        confidence=1.0,
        retrieved_by="AgentA",
    )
    ev2 = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="1",
        content="Same content",
        confidence=1.0,
        retrieved_by="AgentB",
    )
    ev3 = Evidence(
        source_type=SourceType.QDRANT_DOC,
        source_id="chunk_2",
        content="Different content",
        confidence=0.8,
        retrieved_by="AgentC",
    )

    merged = EvidenceMerger.merge([ev1, ev2, ev3])

    assert len(merged.evidences) == 2
    assert merged.evidences[0].source_id == "1"


def test_evidence_merger_conflict_detection() -> None:
    # Same source, different content
    ev1 = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="price_1",
        content="Premium: 5M",
        confidence=1.0,
        retrieved_by="AgentA",
    )
    ev2 = Evidence(
        source_type=SourceType.QDRANT_DOC,
        source_id="price_1",
        content="Premium: 6M",
        confidence=0.8,
        retrieved_by="AgentB",
    )

    merged = EvidenceMerger.merge([ev1, ev2])

    # Ideally we flag a conflict or keep both depending on rules,
    # but the blueprint says: "detect simple conflicts"
    assert len(merged.conflicts) > 0
    assert "price_1" in merged.conflicts[0]


def test_evidence_merger_reranks_sqlite_first_for_numeric_queries() -> None:
    qdrant_policy_text = Evidence(
        source_type=SourceType.QDRANT_CHUNK,
        source_id="policy-section-1",
        content="Điều khoản bảo hiểm nội trú giải thích phạm vi nằm viện.",
        metadata={"retrieval_mode": "hybrid", "fusion_score": 0.94},
        confidence=0.94,
        retrieved_by="QdrantRetriever",
    )
    sqlite_limit_row = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="benefit_limits:12",
        content="benefit_name: Nội trú, limit_amount: 100000000",
        confidence=0.72,
        retrieved_by="DatabaseAgent",
    )

    merged = EvidenceMerger.merge(
        [qdrant_policy_text, sqlite_limit_row],
        rerank_query="hạn mức nội trú bao nhiêu tiền?",
        reranker=EvidenceReranker(cross_encoder=StaticInsuranceCrossEncoder()),
    )

    assert merged.evidences[0].source_id == "benefit_limits:12"
    assert merged.evidences[0].metadata["rerank_score"] > 0
    assert merged.evidences[0].metadata["rerank_rank"] == 1


def test_evidence_merger_reranks_graph_first_for_relationship_queries() -> None:
    sqlite_waiting_period = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="waiting_periods:2",
        content="condition: bệnh có sẵn, waiting_days: 365",
        confidence=0.9,
        retrieved_by="DatabaseAgent",
    )
    graph_relationship = Evidence(
        source_type=SourceType.GRAPH_TRIPLE,
        source_id="plan:gold->exclusion:pre_existing_condition",
        content=(
            "plan:gold EXCLUDES condition:pre_existing_condition -> "
            "condition:pre_existing_condition HAS_WAITING_PERIOD waiting_period:365"
        ),
        metadata={"relationship_types": ["EXCLUDES", "HAS_WAITING_PERIOD"]},
        confidence=0.68,
        retrieved_by="graph_retriever",
    )

    merged = EvidenceMerger.merge(
        [sqlite_waiting_period, graph_relationship],
        rerank_query="gói Gold loại trừ bệnh có sẵn liên quan thời gian chờ nào?",
        reranker=EvidenceReranker(cross_encoder=StaticInsuranceCrossEncoder()),
    )

    assert merged.evidences[0].source_type == SourceType.GRAPH_TRIPLE


def test_evidence_merger_applies_top_k_after_reranking() -> None:
    qdrant_keyword_match = Evidence(
        source_type=SourceType.QDRANT_CHUNK,
        source_id="doc-avastin",
        content="Avastin được loại trừ trong điều khoản thuốc đặc trị.",
        metadata={"retrieval_mode": "bm25", "sparse_score": 0.97},
        confidence=0.83,
        retrieved_by="QdrantRetriever",
    )
    unrelated_row = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="premium:basic",
        content="premium_amount: 2000000",
        confidence=1.0,
        retrieved_by="DatabaseAgent",
    )

    merged = EvidenceMerger.merge(
        [unrelated_row, qdrant_keyword_match],
        rerank_query="Avastin có bị loại trừ không?",
        top_k=1,
        reranker=EvidenceReranker(cross_encoder=StaticInsuranceCrossEncoder()),
    )

    assert len(merged.evidences) == 1
    assert merged.evidences[0].source_id == "doc-avastin"


def test_evidence_reranker_compresses_langchain_documents() -> None:
    reranker = EvidenceReranker(cross_encoder=StaticInsuranceCrossEncoder())
    documents = [
        Document(
            page_content="premium_amount: 2000000",
            metadata={"source_type": SourceType.SQLITE_ROW.value, "confidence": 1.0},
        ),
        Document(
            page_content="Điều khoản thuốc Avastin trong hợp đồng.",
            metadata={"source_type": SourceType.QDRANT_CHUNK.value, "confidence": 0.8},
        ),
    ]

    reranked_documents = reranker.compress_documents(
        documents=documents,
        query="Avastin có trong điều khoản nào?",
    )

    assert reranked_documents[0].page_content.startswith("Điều khoản thuốc Avastin")
    assert reranked_documents[0].metadata["rerank_rank"] == 1
    assert reranked_documents[0].metadata["rerank_score"] > 0


def test_evidence_reranker_requires_cross_encoder() -> None:
    reranker = EvidenceReranker()

    with pytest.raises(ValueError, match="cross_encoder"):
        reranker.compress_documents(documents=[], query="hạn mức")


def test_evidence_reranker_uses_cross_encoder_method_when_provided() -> None:
    reranker = EvidenceReranker(cross_encoder=StaticInsuranceCrossEncoder())
    documents = [
        Document(
            page_content="Điều khoản bảo hiểm nội trú giải thích phạm vi nằm viện.",
            metadata={
                "source_id": "policy-section-1",
                "source_type": SourceType.QDRANT_CHUNK.value,
                "confidence": 0.94,
            },
        ),
        Document(
            page_content="benefit_name: Nội trú, limit_amount: 100000000",
            metadata={
                "source_id": "benefit_limits:12",
                "source_type": SourceType.SQLITE_ROW.value,
                "confidence": 0.72,
            },
        ),
    ]

    reranked_documents = reranker.compress_documents(
        documents=documents,
        query="hạn mức nội trú bao nhiêu tiền?",
    )

    assert reranked_documents[0].metadata["source_id"] == "benefit_limits:12"
    assert reranked_documents[0].metadata["rerank_method"] == "cross_encoder"
    assert reranked_documents[0].metadata["rerank_score"] == 0.91
    assert reranked_documents[0].metadata["rerank_rank"] == 1


def test_evidence_reranker_normalizes_mixed_range_scores_monotonically() -> None:
    reranker = EvidenceReranker(cross_encoder=MixedRangeCrossEncoder())
    documents = [
        Document(page_content="best evidence", metadata={"source_id": "best"}),
        Document(page_content="weaker evidence", metadata={"source_id": "weaker"}),
    ]

    reranked_documents = reranker.compress_documents(
        documents=documents,
        query="hạn mức",
    )

    assert reranked_documents[0].metadata["source_id"] == "best"
    assert (
        reranked_documents[0].metadata["rerank_score"]
        > reranked_documents[1].metadata["rerank_score"]
    )


def test_evidence_merger_preserves_cross_encoder_rerank_metadata() -> None:
    qdrant_policy_text = Evidence(
        source_type=SourceType.QDRANT_CHUNK,
        source_id="policy-section-1",
        content="Điều khoản bảo hiểm nội trú giải thích phạm vi nằm viện.",
        confidence=0.94,
        retrieved_by="QdrantRetriever",
    )
    sqlite_limit_row = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="benefit_limits:12",
        content="benefit_name: Nội trú, limit_amount: 100000000",
        confidence=0.72,
        retrieved_by="DatabaseAgent",
    )

    merged = EvidenceMerger.merge(
        [qdrant_policy_text, sqlite_limit_row],
        rerank_query="hạn mức nội trú bao nhiêu tiền?",
        reranker=EvidenceReranker(cross_encoder=StaticInsuranceCrossEncoder()),
    )

    assert merged.evidences[0].metadata["rerank_method"] == "cross_encoder"
    assert merged.evidences[0].metadata["rerank_raw_score"] == 0.91
