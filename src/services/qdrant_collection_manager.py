from dataclasses import dataclass
from typing import Any

from qdrant_client import models

from src.services.observability import service_observe
from src.services.retrieval_readiness import RetrievalReadinessReport

QDRANT_FILTER_PAYLOAD_INDEX_FIELDS = (
    "company_code",
    "document_id",
    "document_type",
    "product_line",
    "plan_code",
    "section_type",
    "effective_date",
    "source_table_id",
)


@dataclass(frozen=True)
class QdrantCollectionConfig:
    """Configuration for the Qdrant document retrieval collection."""

    collection_name: str
    dense_vector_size: int
    dense_vector_name: str = "text_dense"
    sparse_vector_name: str = "text_sparse"
    sparse_index_on_disk: bool = False


class QdrantCollectionManager:
    """Create and validate Qdrant collection infrastructure for document RAG."""

    def __init__(self, *, client: Any, config: QdrantCollectionConfig) -> None:
        """Initialize the collection manager.

        Args:
            client: Qdrant-compatible client.
            config: Collection and vector configuration.
        """
        self.client = client
        self.config = config

    @service_observe(
        name="service.qdrant_collection_manager.ensure_collection",
        component="qdrant_collection_manager",
    )
    def ensure_collection(self, *, recreate: bool = False) -> None:
        """Create the hybrid Qdrant collection when it does not exist."""
        if recreate and self._collection_exists():
            self.client.delete_collection(self.config.collection_name)

        if self._collection_exists():
            return

        self.client.create_collection(
            collection_name=self.config.collection_name,
            vectors_config={
                self.config.dense_vector_name: models.VectorParams(
                    size=self.config.dense_vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                self.config.sparse_vector_name: models.SparseVectorParams(
                    index=models.SparseIndexParams(
                        on_disk=self.config.sparse_index_on_disk,
                    ),
                )
            },
        )

    @service_observe(
        name="service.qdrant_collection_manager.ensure_payload_indexes",
        component="qdrant_collection_manager",
    )
    def ensure_payload_indexes(self) -> None:
        """Create keyword payload indexes required for hard-filter retrieval."""
        for field_name in QDRANT_FILTER_PAYLOAD_INDEX_FIELDS:
            self.client.create_payload_index(
                collection_name=self.config.collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    @service_observe(
        name="service.qdrant_collection_manager.build_readiness_report",
        component="qdrant_collection_manager",
    )
    def build_readiness_report(
        self,
        *,
        dense_only_degraded: bool = False,
    ) -> RetrievalReadinessReport:
        """Inspect collection metadata and return a production readiness report."""
        collection_info = self.client.get_collection(self.config.collection_name)
        dense_vectors = _extract_named_config(collection_info, "vectors")
        sparse_vectors = _extract_named_config(collection_info, "sparse_vectors")
        payload_schema = _extract_payload_schema(collection_info)

        missing_payload_indexes = [
            field_name
            for field_name in QDRANT_FILTER_PAYLOAD_INDEX_FIELDS
            if field_name not in payload_schema
        ]
        return RetrievalReadinessReport(
            collection_name=self.config.collection_name,
            has_dense_vector=self.config.dense_vector_name in dense_vectors,
            has_sparse_vector=self.config.sparse_vector_name in sparse_vectors,
            missing_payload_indexes=missing_payload_indexes,
            dense_only_degraded=dense_only_degraded,
        )

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.config.collection_name)
        except Exception:
            return False
        return True


def _extract_named_config(collection_info: Any, field_name: str) -> dict[str, Any]:
    if isinstance(collection_info, dict):
        params = collection_info.get("config", {}).get("params", {})
        return dict(params.get(field_name, {}))

    config = getattr(collection_info, "config", None)
    params = getattr(config, "params", None)
    value = getattr(params, field_name, None)
    if value is None:
        return {}
    return dict(value) if isinstance(value, dict) else value.model_dump()


def _extract_payload_schema(collection_info: Any) -> dict[str, Any]:
    if isinstance(collection_info, dict):
        return dict(collection_info.get("payload_schema", {}))

    payload_schema = getattr(collection_info, "payload_schema", None)
    if payload_schema is None:
        return {}
    return dict(payload_schema)
