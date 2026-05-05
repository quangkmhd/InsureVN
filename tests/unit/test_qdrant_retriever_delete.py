from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_qdrant import SparseEmbeddings
from langchain_qdrant.sparse_embeddings import SparseVector

from src.services.qdrant_retriever import QdrantRetriever


class FakeEmbeddingProvider(Embeddings):
    """Dense embeddings with a stable three-dimensional output."""

    vector_size = 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return stable vectors for document texts."""
        return [[0.1, 0.2, 0.3] for _text in texts]

    def embed_query(self, _text: str) -> list[float]:
        """Return a stable vector for query text."""
        return [0.1, 0.2, 0.3]


class FakeSparseEmbeddingProvider(SparseEmbeddings):
    """Sparse embeddings accepted by LangChain Qdrant hybrid mode."""

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        """Return stable sparse vectors for document texts."""
        return [SparseVector(indices=[1], values=[1.0]) for _text in texts]

    def embed_query(self, _text: str) -> SparseVector:
        """Return a stable sparse vector for query text."""
        return SparseVector(indices=[1], values=[1.0])


class FakeQdrantClient:
    """Qdrant client double that records delete calls."""

    def __init__(self) -> None:
        """Initialize recorded calls and a fake operation result."""
        self.delete_calls: list[dict[str, Any]] = []
        self.operation_result = {"status": "completed"}

    def delete(self, **kwargs: Any) -> dict[str, str]:
        """Record a delete request."""
        self.delete_calls.append(kwargs)
        return self.operation_result


def test_qdrant_retriever_deletes_documents_by_point_ids() -> None:
    qdrant_client = FakeQdrantClient()
    retriever = QdrantRetriever(
        client=qdrant_client,
        collection_name="insurevn_policy_chunks",
        embedding_provider=FakeEmbeddingProvider(),
        sparse_embedding_provider=FakeSparseEmbeddingProvider(),
        keyword_enabled=True,
    )

    result = retriever.delete_documents_by_ids([101, "chunk-uuid"])

    assert result == {"status": "completed"}
    assert qdrant_client.delete_calls == [
        {
            "collection_name": "insurevn_policy_chunks",
            "points_selector": [101, "chunk-uuid"],
            "wait": True,
        }
    ]


def test_qdrant_retriever_skips_empty_document_id_deletes() -> None:
    qdrant_client = FakeQdrantClient()
    retriever = QdrantRetriever(
        client=qdrant_client,
        collection_name="insurevn_policy_chunks",
        embedding_provider=FakeEmbeddingProvider(),
        sparse_embedding_provider=FakeSparseEmbeddingProvider(),
        keyword_enabled=True,
    )

    result = retriever.delete_documents_by_ids([])

    assert result is None
    assert qdrant_client.delete_calls == []
