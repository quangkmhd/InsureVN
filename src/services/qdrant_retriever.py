"""Qdrant-backed document retrieval with dense and keyword pillars."""

from __future__ import annotations

import hashlib
import math
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from src.core.logger import get_logger
from src.models.evidence import Evidence, HardFilters, RetrievalMode, RetrievalPlan
from src.services.document_chunker import ChildChunk
from src.services.qdrant_evidence_adapter import QdrantEvidenceAdapter

logger = get_logger("qdrant_retriever")


class RetrievalReadinessError(RuntimeError):
    """Raised when retriever configuration is not production-ready."""


class EmbeddingProvider(Protocol):
    """Protocol for dense query and document embeddings."""

    vector_size: int

    def embed(self, text: str) -> list[float]:
        """Embed text into a dense vector."""


@dataclass(frozen=True)
class HashingEmbeddingProvider:
    """Deterministic token-hashing embedding provider for local tests."""

    vector_size: int = 384

    def embed(self, text: str) -> list[float]:
        """Embed text with normalized token hashes.

        This is intentionally simple and deterministic. Production deployments should
        inject a real multilingual embedding provider.
        """
        vector = [0.0] * self.vector_size
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.vector_size
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


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
        keyword_enabled: bool = True,
        allow_dense_only_degraded_mode: bool = False,
    ) -> None:
        """Initialize the retriever.

        Args:
            client: Qdrant client. Tests can use `QdrantClient(":memory:")`.
            collection_name: Qdrant collection containing child chunks.
            embedding_provider: Provider used for query and chunk vectors.
            keyword_enabled: Whether the BM25-style keyword pillar is enabled.
            allow_dense_only_degraded_mode: Allows local dense-only retrieval, but
                `assert_production_ready()` still rejects it.
        """
        self.client = client
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
        self.keyword_enabled = keyword_enabled
        self.allow_dense_only_degraded_mode = allow_dense_only_degraded_mode

        if not keyword_enabled and not allow_dense_only_degraded_mode:
            raise RetrievalReadinessError(
                "keyword retrieval is disabled; "
                "set explicit degraded mode for local use"
            )

    def setup_collection(self, *, recreate: bool = False) -> None:
        """Create the Qdrant collection when it does not exist."""
        if recreate and self._collection_exists():
            self.client.delete_collection(self.collection_name)

        if self._collection_exists():
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.embedding_provider.vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def index_chunks(self, chunks: list[ChildChunk]) -> None:
        """Index child chunks with dense vectors and citation payloads."""
        points = []
        for chunk in chunks:
            payload = dict(chunk.payload)
            payload["chunk_id"] = chunk.chunk_id
            payload["parent_section_id"] = chunk.parent_section_id
            points.append(
                models.PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector=self.embedding_provider.embed(chunk.text),
                    payload=payload,
                )
            )

        if not points:
            return

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(
            "Indexed Qdrant chunks",
            extra={
                "component": "qdrant_indexer",
                "collection_name": self.collection_name,
                "chunk_count": len(points),
            },
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

        dense_results: list[_ScoredPayload] = []
        keyword_results: list[_ScoredPayload] = []

        if retrieval_plan.mode in {RetrievalMode.VECTOR, RetrievalMode.HYBRID}:
            dense_results = self._dense_search(query_text, query_filter, top_k)

        if retrieval_plan.mode in {RetrievalMode.BM25, RetrievalMode.HYBRID}:
            if self.keyword_enabled:
                keyword_results = self._keyword_search(query_text, query_filter, top_k)
            else:
                logger.warning(
                    "Dense-only degraded retrieval",
                    extra={
                        "component": "qdrant_retriever",
                        "collection_name": self.collection_name,
                        "retrieval_degraded": True,
                    },
                )

        ranked_results = _reciprocal_rank_fusion(
            [dense_results, keyword_results],
            top_k=top_k,
        )
        evidence_items = [
            QdrantEvidenceAdapter.from_payload(
                point_id=result.payload.get("chunk_id", result.point_id),
                payload=result.payload,
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

    def assert_production_ready(self) -> None:
        """Reject degraded retrieval settings for production gates."""
        if not self.keyword_enabled:
            raise RetrievalReadinessError(
                "keyword retrieval is disabled; dense-only mode is degraded"
            )

    def _dense_search(
        self,
        query_text: str,
        query_filter: models.Filter | None,
        top_k: int,
    ) -> list[_ScoredPayload]:
        query_vector = self.embedding_provider.embed(query_text)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return [
            _ScoredPayload(
                point_id=str(point.id),
                payload=dict(point.payload or {}),
                score=max(0.0, min(float(point.score), 1.0)),
            )
            for point in response.points
            if point.payload is not None
        ]

    def _keyword_search(
        self,
        query_text: str,
        query_filter: models.Filter | None,
        top_k: int,
    ) -> list[_ScoredPayload]:
        records = []
        next_offset = None
        while True:
            page_records, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=10_000,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
            )
            records.extend(page_records)
            if next_offset is None:
                break

        payloads = [dict(record.payload or {}) for record in records if record.payload]
        scored_payloads = _bm25_rank(query_text, payloads)
        return [
            _ScoredPayload(
                point_id=str(_point_id(str(payload.get("chunk_id", index)))),
                payload=payload,
                score=score,
            )
            for index, (payload, score) in enumerate(scored_payloads[:top_k])
        ]

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


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_vietnamese_text(text))


def _field_condition(key: str, values: list[str]) -> models.FieldCondition:
    if len(values) == 1:
        return models.FieldCondition(
            key=key,
            match=models.MatchValue(value=values[0]),
        )
    return models.FieldCondition(
        key=key,
        match=models.MatchAny(any=values),
    )


def _point_id(chunk_id: str) -> int:
    digest = hashlib.md5(chunk_id.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def _bm25_rank(
    query_text: str,
    payloads: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], float]]:
    query_terms = _tokenize(query_text)
    if not query_terms:
        return []

    documents = [
        _tokenize(str(payload.get("parent_text") or payload.get("text") or ""))
        for payload in payloads
    ]
    document_count = len(documents)
    if document_count == 0:
        return []

    average_length = sum(len(document) for document in documents) / document_count
    document_frequency = Counter(
        term for term in set(query_terms) for document in documents if term in document
    )

    scored: list[tuple[dict[str, Any], float]] = []
    for payload, document_terms in zip(payloads, documents, strict=True):
        term_counts = Counter(document_terms)
        score = 0.0
        for term in query_terms:
            if term_counts[term] == 0:
                continue
            idf = math.log(
                1
                + (
                    (document_count - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
            )
            denominator = term_counts[term] + 1.5 * (
                1 - 0.75 + 0.75 * (len(document_terms) / average_length)
            )
            score += idf * ((term_counts[term] * 2.5) / denominator)
        if score > 0:
            scored.append((payload, min(score, 1.0)))

    return sorted(scored, key=lambda item: item[1], reverse=True)


def _reciprocal_rank_fusion(
    ranked_lists: list[list[_ScoredPayload]],
    *,
    top_k: int,
) -> list[_ScoredPayload]:
    fused_scores: dict[str, float] = {}
    payloads_by_key: dict[str, _ScoredPayload] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            key = str(result.payload.get("chunk_id", result.point_id))
            fused_scores[key] = fused_scores.get(key, 0.0) + (1.0 / (60 + rank))
            payloads_by_key[key] = result

    sorted_keys = sorted(fused_scores, key=fused_scores.get, reverse=True)
    return [
        _ScoredPayload(
            point_id=payloads_by_key[key].point_id,
            payload=payloads_by_key[key].payload,
            score=min(fused_scores[key] * 10, 1.0),
        )
        for key in sorted_keys[:top_k]
    ]
