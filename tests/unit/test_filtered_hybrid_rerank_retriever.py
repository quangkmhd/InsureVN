import pytest

from src.models.evidence import Evidence, HardFilters, RetrievalMode, SourceType
from src.services.document_retrieval.filtered_hybrid_rerank_retriever import (
    FilteredHybridRerankRetriever,
    HardFilterRequiredError,
)


class FakeQdrantRetriever:
    def __init__(self, evidence_items: list[Evidence]) -> None:
        self.evidence_items = evidence_items
        self.received_plan = None

    def retrieve(self, retrieval_plan):
        self.received_plan = retrieval_plan
        return list(self.evidence_items)


class FakeEvidenceReranker:
    def __init__(self) -> None:
        self.received_query: str | None = None
        self.received_evidence_count: int | None = None
        self.received_top_k: int | None = None

    def rerank_evidence(
        self,
        *,
        query: str,
        evidence_items: list[Evidence],
        top_k: int | None = None,
    ) -> list[Evidence]:
        self.received_query = query
        self.received_evidence_count = len(evidence_items)
        self.received_top_k = top_k
        return list(reversed(evidence_items))[: top_k or len(evidence_items)]


def test_filtered_hybrid_rerank_retriever_enforces_official_strategy() -> None:
    evidence_items = [
        Evidence(
            source_type=SourceType.QDRANT_CHUNK,
            source_id=f"chunk-{index}",
            content=f"candidate {index}",
            confidence=0.5,
            retrieved_by="QdrantRetriever",
        )
        for index in range(30)
    ]
    qdrant_retriever = FakeQdrantRetriever(evidence_items=evidence_items)
    evidence_reranker = FakeEvidenceReranker()
    retriever = FilteredHybridRerankRetriever(
        qdrant_retriever=qdrant_retriever,
        evidence_reranker=evidence_reranker,
        top_k=10,
        candidate_top_k=30,
    )

    result = retriever.retrieve(
        query="quyền lợi nội trú của PTI?",
        filters=HardFilters(company_codes=["PTI"]),
    )

    assert qdrant_retriever.received_plan.mode == RetrievalMode.HYBRID
    assert qdrant_retriever.received_plan.filters == HardFilters(
        company_codes=["PTI"]
    )
    assert qdrant_retriever.received_plan.top_k == 30
    assert evidence_reranker.received_query == "quyền lợi nội trú của PTI?"
    assert evidence_reranker.received_evidence_count == 30
    assert evidence_reranker.received_top_k == 10
    assert len(result) == 10
    assert result[0].source_id == "chunk-29"


@pytest.mark.parametrize(
    "filters",
    [
        None,
        HardFilters(),
        HardFilters(company_codes=[]),
        HardFilters(company_codes=[""]),
        HardFilters(company_codes=["  "]),
    ],
)
def test_filtered_hybrid_rerank_retriever_requires_hard_filters(
    filters: HardFilters | None,
) -> None:
    retriever = FilteredHybridRerankRetriever(
        qdrant_retriever=FakeQdrantRetriever(evidence_items=[]),
        evidence_reranker=FakeEvidenceReranker(),
    )

    with pytest.raises(HardFilterRequiredError):
        retriever.retrieve(query="quyền lợi nội trú?", filters=filters)


def test_rejects_candidate_top_k_below_final_top_k() -> None:
    retriever = FilteredHybridRerankRetriever(
        qdrant_retriever=FakeQdrantRetriever(evidence_items=[]),
        evidence_reranker=FakeEvidenceReranker(),
        top_k=10,
        candidate_top_k=5,
    )

    with pytest.raises(ValueError, match="candidate_top_k"):
        retriever.retrieve(
            query="quyền lợi nội trú?",
            filters=HardFilters(company_codes=["PTI"]),
        )


@pytest.mark.parametrize("top_k", [0, -1])
def test_rejects_invalid_final_top_k(top_k: int) -> None:
    retriever = FilteredHybridRerankRetriever(
        qdrant_retriever=FakeQdrantRetriever(evidence_items=[]),
        evidence_reranker=FakeEvidenceReranker(),
        top_k=10,
        candidate_top_k=30,
    )

    with pytest.raises(ValueError, match="top_k"):
        retriever.retrieve(
            query="quyền lợi nội trú?",
            filters=HardFilters(company_codes=["PTI"]),
            top_k=top_k,
        )


@pytest.mark.parametrize("candidate_top_k", [0, -1])
def test_rejects_invalid_candidate_top_k(candidate_top_k: int) -> None:
    retriever = FilteredHybridRerankRetriever(
        qdrant_retriever=FakeQdrantRetriever(evidence_items=[]),
        evidence_reranker=FakeEvidenceReranker(),
        top_k=10,
        candidate_top_k=30,
    )

    with pytest.raises(ValueError, match="candidate_top_k"):
        retriever.retrieve(
            query="quyền lợi nội trú?",
            filters=HardFilters(company_codes=["PTI"]),
            candidate_top_k=candidate_top_k,
        )
