from dataclasses import dataclass
from typing import Any

from langchain_qdrant import QdrantVectorStore, RetrievalMode

from src.services.observability import service_observe


@dataclass(frozen=True)
class LangChainQdrantAdapter:
    """Factory for LangChain's Qdrant vector store integration."""

    collection_name: str
    dense_vector_name: str
    sparse_vector_name: str

    @service_observe(
        name="service.langchain_qdrant_adapter.create_vector_store",
        component="langchain_qdrant_adapter",
    )
    def create_vector_store(
        self,
        *,
        client: Any,
        embeddings: Any | None,
        sparse_embeddings: Any | None,
        retrieval_mode: RetrievalMode = RetrievalMode.HYBRID,
    ) -> Any:
        """Create a LangChain Qdrant vector store."""
        return QdrantVectorStore(
            client=client,
            collection_name=self.collection_name,
            embedding=embeddings,
            sparse_embedding=sparse_embeddings,
            vector_name=self.dense_vector_name,
            sparse_vector_name=self.sparse_vector_name,
            retrieval_mode=retrieval_mode,
        )
