from typing import Any

from src.models.evidence import Evidence, SourceType
from src.services.chunking.document_chunker import REQUIRED_QDRANT_PAYLOAD_FIELDS
from src.services.observability import service_observe


class QdrantEvidenceMapper:
    """Convert Qdrant chunk payloads into shared evidence objects."""

    @classmethod
    @service_observe(
        name="service.qdrant_evidence.from_payload",
        component="qdrant_evidence",
    )
    def from_payload(
        cls,
        point_id: str,
        payload: dict[str, Any],
        score: float,
    ) -> Evidence:
        """Build evidence from a retrieved Qdrant point payload.

        Args:
            point_id: Qdrant point ID.
            payload: Qdrant payload containing citation fields and text.
            score: Retrieval score normalized by the retriever.

        Returns:
            Evidence with `source_type="qdrant_chunk"`.
        """
        cls.validate_payload(payload)
        content = str(payload.get("parent_text") or payload.get("text") or "")

        return Evidence(
            source_type=SourceType.QDRANT_CHUNK,
            source_id=point_id,
            content=content,
            metadata=dict(payload),
            confidence=max(0.0, min(score, 1.0)),
            retrieved_by="QdrantRetriever",
        )

    @staticmethod
    @service_observe(
        name="service.qdrant_evidence.validate_payload",
        component="qdrant_evidence",
    )
    def validate_payload(payload: dict[str, Any]) -> None:
        """Validate required Qdrant evidence citation fields."""
        missing_fields = [
            field for field in REQUIRED_QDRANT_PAYLOAD_FIELDS if field not in payload
        ]
        if missing_fields:
            raise ValueError(
                "Missing Qdrant payload field(s): " + ", ".join(missing_fields)
            )
