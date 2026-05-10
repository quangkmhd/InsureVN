from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode, SparseEmbeddings
from langchain_qdrant.sparse_embeddings import SparseVector
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, SparseVectorParams, VectorParams

from src.services.document_retrieval.qdrant_vector_store import QdrantVectorStoreFactory


class FakeEmbeddings(Embeddings):
    """Dense embeddings with a stable three-dimensional output."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _text in texts]

    def embed_query(self, _text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeSparseEmbeddings(SparseEmbeddings):
    """Sparse embeddings accepted by LangChain Qdrant hybrid mode."""

    def embed_documents(self, texts: list[str]) -> list[SparseVector]:
        return [SparseVector(indices=[1], values=[1.0]) for _text in texts]

    def embed_query(self, _text: str) -> SparseVector:
        return SparseVector(indices=[1], values=[1.0])


def test_qdrant_vector_store_factory_creates_hybrid_vector_store() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="insurevn_chunks",
        vectors_config={
            "text_dense": VectorParams(size=3, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "text_sparse": SparseVectorParams(
                index=models.SparseIndexParams(on_disk=False),
            ),
        },
    )
    factory = QdrantVectorStoreFactory(
        collection_name="insurevn_chunks",
        dense_vector_name="text_dense",
        sparse_vector_name="text_sparse",
    )

    vector_store = factory.create_vector_store(
        client=client,
        embeddings=FakeEmbeddings(),
        sparse_embeddings=FakeSparseEmbeddings(),
    )

    assert isinstance(vector_store, QdrantVectorStore)
    assert vector_store.retrieval_mode == RetrievalMode.HYBRID
    assert vector_store.vector_name == "text_dense"
    assert vector_store.sparse_vector_name == "text_sparse"
