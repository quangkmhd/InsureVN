"""Official filtered hybrid retrieval strategy with local reranking."""

from __future__ import annotations

from qdrant_client import QdrantClient

from src.core.config import settings
from src.models.evidence import Evidence, HardFilters, RetrievalMode, RetrievalPlan
from src.services.document_retrieval.qdrant_retriever import (
    QdrantRetriever,
    build_dense_embedding_provider,
)
from src.services.document_retrieval.rerank_cross_encoder import (
    build_default_rerank_cross_encoder,
)
from src.services.evidence.evidence_merger import EvidenceReranker
from src.services.observability import service_observe


class HardFilterRequiredError(ValueError):
    """Raised when official production retrieval is called without hard filters."""


class FilteredHybridRerankRetriever:
    """Retrieve with HYBRID mode, mandatory hard filters, then ViRanker rerank."""

    def __init__(
        self,
        *,
        qdrant_retriever: QdrantRetriever,
        evidence_reranker: EvidenceReranker,
        top_k: int = settings.RAG_RETRIEVAL_TOP_K,
        candidate_top_k: int = settings.RAG_RERANK_CANDIDATE_TOP_K,
    ) -> None:
        """Initialize the official production retrieval strategy."""
        self.qdrant_retriever = qdrant_retriever
        self.evidence_reranker = evidence_reranker
        self.top_k = top_k
        self.candidate_top_k = candidate_top_k

    @service_observe(
        name="service.filtered_hybrid_rerank_retriever.retrieve",
        component="filtered_hybrid_rerank_retriever",
    )
    def retrieve(
        self,
        *,
        query: str,
        filters: HardFilters | None,
        top_k: int | None = None,
        candidate_top_k: int | None = None,
    ) -> list[Evidence]:
        """Retrieve filtered HYBRID candidates and rerank them to final top-k."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank.")
        if settings.RAG_REQUIRE_HARD_FILTERS and not _has_hard_filters(filters):
            raise HardFilterRequiredError(
                "HYBRID + ViRanker production retrieval requires hard filters."
            )

        final_top_k = self.top_k if top_k is None else top_k
        retrieval_candidate_top_k = (
            self.candidate_top_k if candidate_top_k is None else candidate_top_k
        )
        if final_top_k < 1:
            raise ValueError("top_k must be greater than zero.")
        if retrieval_candidate_top_k < final_top_k:
            raise ValueError("candidate_top_k must be greater than or equal to top_k.")

        candidate_evidence = self.qdrant_retriever.retrieve(
            RetrievalPlan(
                search_queries=[normalized_query],
                mode=RetrievalMode.HYBRID,
                filters=filters,
                top_k=retrieval_candidate_top_k,
            )
        )
        return self.evidence_reranker.rerank_evidence(
            query=normalized_query,
            evidence_items=candidate_evidence,
            top_k=final_top_k,
        )


def build_default_filtered_hybrid_rerank_retriever() -> FilteredHybridRerankRetriever:
    """Build the configured official production document retrieval strategy."""
    client_kwargs: dict[str, str] = {"url": settings.RAG_QDRANT_URL}
    if settings.RAG_QDRANT_API_KEY:
        client_kwargs["api_key"] = settings.RAG_QDRANT_API_KEY

    embedding_provider = build_dense_embedding_provider(
        provider=settings.RAG_EMBEDDING_PROVIDER,
        model_name=settings.RAG_EMBEDDING_MODEL,
        vector_size=settings.RAG_DENSE_VECTOR_SIZE,
        batch_size=settings.RAG_EMBEDDING_BATCH_SIZE,
        max_length=settings.RAG_EMBEDDING_MAX_LENGTH,
        load_in_4bit=settings.RAG_EMBEDDING_LOAD_IN_4BIT,
        device_map=settings.RAG_EMBEDDING_DEVICE_MAP,
        attn_implementation=settings.RAG_EMBEDDING_ATTN_IMPLEMENTATION,
        query_task_description=settings.RAG_EMBEDDING_QUERY_TASK_DESCRIPTION,
    )
    qdrant_retriever = QdrantRetriever(
        client=QdrantClient(**client_kwargs),
        collection_name=settings.RAG_QDRANT_COLLECTION,
        embedding_provider=embedding_provider,
        keyword_enabled=True,
        allow_dense_only_degraded_mode=False,
    )
    evidence_reranker = EvidenceReranker(
        cross_encoder=build_default_rerank_cross_encoder()
    )
    return FilteredHybridRerankRetriever(
        qdrant_retriever=qdrant_retriever,
        evidence_reranker=evidence_reranker,
    )


def _has_hard_filters(filters: HardFilters | None) -> bool:
    if filters is None:
        return False
    return any(
        bool(values) and any(value.strip() for value in values)
        for values in (
            filters.company_codes,
            filters.document_ids,
            filters.document_types,
            filters.product_lines,
            filters.plan_codes,
            filters.section_types,
        )
    )
