"""Qdrant-backed document retrieval with dense and keyword pillars."""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import FastEmbedSparse, SparseEmbeddings
from langchain_qdrant import RetrievalMode as LangChainQdrantRetrievalMode
from qdrant_client import QdrantClient, models

from src.core.logger import get_logger
from src.models.evidence import Evidence, HardFilters, RetrievalMode, RetrievalPlan
from src.services.document_chunker import ChildChunk
from src.services.langchain_qdrant_adapter import LangChainQdrantAdapter
from src.services.observability import service_observe
from src.services.qdrant_collection_manager import (
    QdrantCollectionConfig,
    QdrantCollectionManager,
)
from src.services.qdrant_evidence_adapter import QdrantEvidenceAdapter

logger = get_logger("qdrant_retriever")


class RetrievalReadinessError(RuntimeError):
    """Raised when retriever configuration is not production-ready."""


class EmbeddingProvider(Embeddings):
    """Protocol for dense query and document embeddings."""

    vector_size: int


@dataclass(frozen=True)
class GoogleGenAIEmbeddingProvider(EmbeddingProvider):
    """Google Generative AI embedding provider with explicit vector sizing."""

    model_name: str
    google_api_key: str
    vector_size: int
    _google_genai_embeddings: GoogleGenerativeAIEmbeddings = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Initialize the underlying LangChain Google embedding client."""
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for Google GenAI embeddings.")
        object.__setattr__(
            self,
            "_google_genai_embeddings",
            GoogleGenerativeAIEmbeddings(
                model=self.model_name,
                google_api_key=self.google_api_key,
                output_dimensionality=self.vector_size,
            ),
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents into dense vectors."""
        return self._google_genai_embeddings.embed_documents(
            texts,
            batch_size=1,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=self.vector_size,
        )

    def embed_query(self, text: str) -> list[float]:
        """Embed query text into a dense vector."""
        return self._google_genai_embeddings.embed_query(
            text,
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=self.vector_size,
        )


@dataclass(frozen=True)
class _ScoredPayload:
    point_id: str
    payload: dict[str, Any]
    score: float


class QdrantRetriever:
    """Retrieve citation-rich document evidence from Qdrant."""

    def __init__(
        self,
        *,
        client: QdrantClient,
        collection_name: str,
        embedding_provider: EmbeddingProvider,
        sparse_embedding_provider: SparseEmbeddings | None = None,
        sparse_model_name: str = "Qdrant/bm25",
        keyword_enabled: bool = True,
        allow_dense_only_degraded_mode: bool = False,
        dense_vector_name: str = "text_dense",
        sparse_vector_name: str = "text_sparse",
    ) -> None:
        """Initialize the retriever.

        Args:
            client: Qdrant client. Tests can use `QdrantClient(":memory:")`.
            collection_name: Qdrant collection containing child chunks.
            embedding_provider: Provider used for query and chunk vectors.
            sparse_embedding_provider: Provider used for LangChain sparse retrieval.
            sparse_model_name: FastEmbed sparse model used when no provider is passed.
            keyword_enabled: Whether the BM25-style keyword pillar is enabled.
            allow_dense_only_degraded_mode: Allows local dense-only retrieval, but
                `assert_production_ready()` still rejects it.
            dense_vector_name: Qdrant named dense vector used for semantic search.
            sparse_vector_name: Qdrant named sparse vector reserved for hybrid search.
        """
        self.client = client
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.sparse_embedding_provider = sparse_embedding_provider or FastEmbedSparse(
            model_name=sparse_model_name
        )
        self.keyword_enabled = keyword_enabled
        self.allow_dense_only_degraded_mode = allow_dense_only_degraded_mode
        self.dense_vector_name = dense_vector_name
        self.sparse_vector_name = sparse_vector_name
        self._langchain_qdrant_adapter = LangChainQdrantAdapter(
            collection_name=collection_name,
            dense_vector_name=dense_vector_name,
            sparse_vector_name=sparse_vector_name,
        )

        if not keyword_enabled and not allow_dense_only_degraded_mode:
            raise RetrievalReadinessError(
                "keyword retrieval is disabled; "
                "set explicit degraded mode for local use"
            )

    @service_observe(
        name="service.qdrant_retriever.setup_collection", component="qdrant_retriever"
    )
    def setup_collection(self, *, recreate: bool = False) -> None:
        """Create the Qdrant collection when it does not exist."""
        manager = QdrantCollectionManager(
            client=self.client,
            config=QdrantCollectionConfig(
                collection_name=self.collection_name,
                dense_vector_name=self.dense_vector_name,
                sparse_vector_name=self.sparse_vector_name,
                dense_vector_size=self.embedding_provider.vector_size,
            ),
        )
        manager.ensure_collection(recreate=recreate)

    @service_observe(
        name="service.qdrant_retriever.index_chunks", component="qdrant_retriever"
    )
    def index_chunks(self, chunks: list[ChildChunk]) -> None:
        """Index child chunks with LangChain's Qdrant vector store."""
        if not chunks:
            return

        documents = []
        ids = []
        for chunk in chunks:
            payload = dict(chunk.payload)
            payload["chunk_id"] = chunk.chunk_id
            payload["parent_section_id"] = chunk.parent_section_id
            documents.append(
                Document(
                    page_content=normalize_vietnamese_text(chunk.text),
                    metadata=payload,
                )
            )
            ids.append(_point_id(chunk.chunk_id))

        self._create_vector_store(
            LangChainQdrantRetrievalMode.HYBRID,
        ).add_documents(documents, ids=ids)
        logger.info(
            "Indexed Qdrant chunks",
            extra={
                "component": "qdrant_indexer",
                "collection_name": self.collection_name,
                "chunk_count": len(documents),
            },
        )

    @service_observe(
        name="service.qdrant_retriever.retrieve", component="qdrant_retriever"
    )
    def retrieve(self, retrieval_plan: RetrievalPlan) -> list[Evidence]:
        """Retrieve evidence for the given retrieval plan."""
        if (
            retrieval_plan.mode == RetrievalMode.VECTOR
            and not self.allow_dense_only_degraded_mode
        ):
            raise RetrievalReadinessError(
                "VECTOR retrieval mode is dense-only; "
                "set explicit degraded mode for local use"
            )
        if retrieval_plan.mode == RetrievalMode.VECTOR:
            logger.warning(
                "Dense-only degraded retrieval",
                extra={
                    "component": "qdrant_retriever",
                    "collection_name": self.collection_name,
                    "retrieval_degraded": True,
                },
            )

        started_at = time.perf_counter()
        query_text = " ".join(retrieval_plan.search_queries)
        query_filter = self._build_filter(retrieval_plan.filters)
        top_k = retrieval_plan.top_k

        ranked_results = self._langchain_search(
            mode=retrieval_plan.mode,
            query_text=query_text,
            query_filter=query_filter,
            top_k=top_k,
        )
        evidence_items = [
            QdrantEvidenceAdapter.from_payload(
                point_id=result.payload.get("chunk_id", result.point_id),
                payload={
                    **result.payload,
                    "retrieval_mode": retrieval_plan.mode.value,
                    "fusion_score": result.score,
                    "dense_score": result.payload.get("dense_score", result.score),
                    "sparse_score": result.payload.get("sparse_score", result.score),
                },
                score=result.score,
            )
            for result in ranked_results
        ]

        logger.info(
            "Retrieved Qdrant evidence",
            extra={
                "component": "qdrant_retriever",
                "collection_name": self.collection_name,
                "hard_filters": (
                    retrieval_plan.filters.model_dump(exclude_none=True)
                    if retrieval_plan.filters
                    else {}
                ),
                "top_k": top_k,
                "latency_ms": round((time.perf_counter() - started_at) * 1000, 3),
                "retrieved_count": len(evidence_items),
            },
        )
        return evidence_items

    @service_observe(
        name="service.qdrant_retriever.assert_production_ready",
        component="qdrant_retriever",
    )
    def assert_production_ready(self) -> None:
        """Reject degraded retrieval settings for production gates."""
        if not self.keyword_enabled:
            raise RetrievalReadinessError(
                "keyword retrieval is disabled; dense-only mode is degraded"
            )

    def _langchain_search(
        self,
        *,
        mode: RetrievalMode,
        query_text: str,
        query_filter: models.Filter | None,
        top_k: int,
    ) -> list[_ScoredPayload]:
        vector_store = self._create_vector_store(_to_langchain_retrieval_mode(mode))
        scored_documents = vector_store.similarity_search_with_score(
            normalize_vietnamese_text(query_text),
            k=top_k,
            filter=query_filter,
        )
        return [
            _ScoredPayload(
                point_id=str(document.metadata.get("chunk_id", index)),
                payload={
                    **document.metadata,
                    "text": document.metadata.get("text", document.page_content),
                },
                score=max(0.0, min(float(score), 1.0)),
            )
            for index, (document, score) in enumerate(scored_documents)
        ]

    def _create_vector_store(
        self,
        retrieval_mode: LangChainQdrantRetrievalMode,
    ) -> Any:
        dense_embeddings = (
            self.embedding_provider
            if retrieval_mode
            in {
                LangChainQdrantRetrievalMode.DENSE,
                LangChainQdrantRetrievalMode.HYBRID,
            }
            else None
        )
        sparse_embeddings = (
            self.sparse_embedding_provider
            if retrieval_mode
            in {
                LangChainQdrantRetrievalMode.SPARSE,
                LangChainQdrantRetrievalMode.HYBRID,
            }
            else None
        )
        return self._langchain_qdrant_adapter.create_vector_store(
            client=self.client,
            embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
            retrieval_mode=retrieval_mode,
        )

    def _build_filter(self, filters: HardFilters | None) -> models.Filter | None:
        if filters is None:
            return None

        filter_values = {
            "company_code": filters.company_codes,
            "document_id": filters.document_ids,
            "document_type": filters.document_types,
            "product_line": filters.product_lines,
            "plan_code": filters.plan_codes,
            "section_type": filters.section_types,
        }
        conditions = [
            _field_condition(key, values)
            for key, values in filter_values.items()
            if values
        ]
        if not conditions:
            return None
        return models.Filter(must=conditions)

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            return False
        return True


def normalize_vietnamese_text(text: str) -> str:
    """Normalize Vietnamese text for keyword matching."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def _field_condition(key: str, values: list[str]) -> models.FieldCondition:
    metadata_key = f"metadata.{key}"
    if len(values) == 1:
        return models.FieldCondition(
            key=metadata_key,
            match=models.MatchValue(value=values[0]),
        )
    return models.FieldCondition(
        key=metadata_key,
        match=models.MatchAny(any=values),
    )


def _point_id(chunk_id: str) -> int:
    digest = hashlib.md5(chunk_id.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def _to_langchain_retrieval_mode(
    mode: RetrievalMode,
) -> LangChainQdrantRetrievalMode:
    if mode == RetrievalMode.VECTOR:
        return LangChainQdrantRetrievalMode.DENSE
    if mode == RetrievalMode.BM25:
        return LangChainQdrantRetrievalMode.SPARSE
    return LangChainQdrantRetrievalMode.HYBRID
