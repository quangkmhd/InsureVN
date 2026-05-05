import hashlib
import math
from collections.abc import Sequence
from typing import Any

from langchain_core.cross_encoders import BaseCrossEncoder
from langchain_core.documents import BaseDocumentCompressor, Document
from pydantic import BaseModel, ConfigDict

from src.core.logger import get_logger
from src.models.evidence import Evidence
from src.services.jina_rerank_cross_encoder import build_default_rerank_cross_encoder
from src.services.observability import add_current_service_metadata, service_observe

logger = get_logger("evidence_merger")
RERANK_EVIDENCE_METADATA_KEYS = (
    "rerank_raw_score",
    "rerank_method",
)


class MergedEvidencePacket(BaseModel):
    """Merged evidence bundle passed from retrieval lanes to specialist agents."""

    evidences: list[Evidence]
    conflicts: list[str]


class EvidenceReranker(BaseDocumentCompressor):
    """Rerank evidence-compatible LangChain documents with a cross-encoder."""

    cross_encoder: BaseCrossEncoder | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @service_observe(
        name="service.evidence_reranker.compress_documents",
        component="evidence_reranker",
    )
    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Any | None = None,
    ) -> Sequence[Document]:
        """Return documents ordered by query relevance."""
        del callbacks
        if self.cross_encoder is None:
            raise ValueError("cross_encoder is required for evidence reranking.")

        rerank_method = "cross_encoder"
        ranked_documents = _rank_documents_with_cross_encoder(
            documents=documents,
            query=query,
            cross_encoder=self.cross_encoder,
        )

        add_current_service_metadata(
            {
                "rerank_method": rerank_method,
                "rerank_query_length": len(query),
                "rerank_document_count": len(ranked_documents),
            }
        )
        return [
            document.model_copy(
                update={
                    "metadata": {
                        **document.metadata,
                        "rerank_score": round(score, 6),
                        "rerank_raw_score": round(raw_score, 6),
                        "rerank_rank": rank,
                        "rerank_method": rerank_method,
                    }
                }
            )
            for rank, (score, raw_score, _index, document) in enumerate(
                ranked_documents,
                start=1,
            )
        ]

    @service_observe(
        name="service.evidence_reranker.rerank_evidence",
        component="evidence_reranker",
    )
    def rerank_evidence(
        self,
        *,
        query: str,
        evidence_items: list[Evidence],
        top_k: int | None = None,
    ) -> list[Evidence]:
        """Rerank evidence records and preserve their citation metadata."""
        if top_k is not None and top_k < 1:
            raise ValueError("top_k must be greater than zero.")

        evidence_by_index = dict(enumerate(evidence_items))
        documents = [
            _evidence_to_document(evidence=evidence, index=index)
            for index, evidence in evidence_by_index.items()
        ]
        ranked_documents = list(
            self.compress_documents(documents=documents, query=query)
        )
        if top_k is not None:
            ranked_documents = ranked_documents[:top_k]

        reranked_evidence: list[Evidence] = []
        for document in ranked_documents:
            evidence_index = int(document.metadata["evidence_index"])
            evidence = evidence_by_index[evidence_index]
            rerank_metadata = {
                **evidence.metadata,
                "rerank_score": document.metadata["rerank_score"],
                "rerank_rank": document.metadata["rerank_rank"],
            }
            for key in RERANK_EVIDENCE_METADATA_KEYS:
                if key in document.metadata:
                    rerank_metadata[key] = document.metadata[key]
            reranked_evidence.append(
                evidence.model_copy(update={"metadata": rerank_metadata})
            )
        return reranked_evidence


class EvidenceMerger:
    """Merge, deduplicate, conflict-check, and optionally rerank evidence."""

    @staticmethod
    @service_observe(name="service.evidence_merger.merge", component="evidence_merger")
    def merge(
        evidence_items: list[Evidence],
        *,
        rerank_query: str | None = None,
        top_k: int | None = None,
        reranker: EvidenceReranker | None = None,
    ) -> MergedEvidencePacket:
        """Merge evidence items and optionally rerank them for a query."""
        unique_evidences: dict[str, Evidence] = {}
        conflicts: list[str] = []
        source_contents: dict[str, set[str]] = {}

        for ev in evidence_items:
            content_hash = hashlib.md5(ev.content.encode("utf-8")).hexdigest()
            dedupe_key = f"{ev.source_type}_{ev.source_id}_{content_hash}"

            # Detect different content for the same source_id.
            if ev.source_id not in source_contents:
                source_contents[ev.source_id] = set()

            if (
                ev.content not in source_contents[ev.source_id]
                and len(source_contents[ev.source_id]) > 0
            ):
                existing_contents = list(source_contents[ev.source_id])
                conflicts.append(
                    f"Conflict detected for source_id '{ev.source_id}'. "
                    f"New content snippet: '{ev.content[:50]}...'. "
                    f"Existing content snippet: '{existing_contents[0][:50]}...'."
                )

            source_contents[ev.source_id].add(ev.content)

            if dedupe_key not in unique_evidences:
                unique_evidences[dedupe_key] = ev

        merged_evidences = list(unique_evidences.values())
        if rerank_query:
            evidence_reranker = reranker or EvidenceReranker(
                cross_encoder=build_default_rerank_cross_encoder()
            )
            merged_evidences = evidence_reranker.rerank_evidence(
                query=rerank_query,
                evidence_items=merged_evidences,
                top_k=top_k,
            )
        elif top_k is not None:
            if top_k < 1:
                raise ValueError("top_k must be greater than zero.")
            merged_evidences = merged_evidences[:top_k]

        logger.info(
            "Merged evidence",
            extra={
                "component": "evidence_merger",
                "total_evidence_count": len(evidence_items),
                "conflict_count": len(conflicts),
                "merged_evidence_count": len(merged_evidences),
                "rerank_applied": bool(rerank_query),
            },
        )

        return MergedEvidencePacket(evidences=merged_evidences, conflicts=conflicts)


def _evidence_to_document(*, evidence: Evidence, index: int) -> Document:
    return Document(
        page_content=evidence.content,
        id=evidence.source_id,
        metadata={
            **evidence.metadata,
            "evidence_index": index,
            "source_type": evidence.source_type.value,
            "source_id": evidence.source_id,
            "retrieved_by": evidence.retrieved_by,
            "confidence": evidence.confidence,
        },
    )


def _rank_documents_with_cross_encoder(
    *,
    documents: Sequence[Document],
    query: str,
    cross_encoder: BaseCrossEncoder,
) -> list[tuple[float, float, int, Document]]:
    document_list = list(documents)
    raw_scores = cross_encoder.score(
        [(query, document.page_content) for document in document_list]
    )
    if len(raw_scores) != len(document_list):
        raise ValueError("cross_encoder returned a score count mismatch.")

    finite_raw_scores = [_finite_float(raw_score) for raw_score in raw_scores]
    normalized_scores = _normalize_cross_encoder_scores(finite_raw_scores)

    return sorted(
        (
            (
                normalized_score,
                raw_score,
                index,
                document,
            )
            for index, (normalized_score, raw_score, document) in enumerate(
                zip(normalized_scores, finite_raw_scores, document_list, strict=True)
            )
        ),
        key=lambda item: (-item[1], item[2]),
    )


def _normalize_cross_encoder_scores(raw_scores: list[float]) -> list[float]:
    if all(0.0 <= score <= 1.0 for score in raw_scores):
        return raw_scores
    return [_sigmoid_score(score) for score in raw_scores]


def _sigmoid_score(score: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-score))
    except OverflowError:
        return 0.0 if score < 0 else 1.0


def _finite_float(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score if math.isfinite(score) else 0.0
