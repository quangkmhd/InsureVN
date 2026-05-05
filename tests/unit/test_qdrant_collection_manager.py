from qdrant_client import models

from src.services.qdrant_collection_manager import (
    QDRANT_FILTER_PAYLOAD_INDEX_FIELDS,
    QdrantCollectionConfig,
    QdrantCollectionManager,
)


class FakeQdrantClient:
    def __init__(self) -> None:
        self.created_collections = []
        self.created_indexes = []
        self.deleted_collections = []
        self.collection_exists = False

    def get_collection(self, collection_name: str):
        if not self.collection_exists:
            raise ValueError(f"missing collection: {collection_name}")
        return {}

    def delete_collection(self, collection_name: str) -> None:
        self.deleted_collections.append(collection_name)
        self.collection_exists = False

    def create_collection(self, **kwargs) -> None:
        self.created_collections.append(kwargs)
        self.collection_exists = True

    def create_payload_index(self, **kwargs) -> None:
        self.created_indexes.append(kwargs)


def test_qdrant_collection_manager_creates_hybrid_collection() -> None:
    client = FakeQdrantClient()
    manager = QdrantCollectionManager(
        client=client,
        config=QdrantCollectionConfig(
            collection_name="insurevn_chunks",
            dense_vector_name="text_dense",
            sparse_vector_name="text_sparse",
            dense_vector_size=768,
        ),
    )

    manager.ensure_collection(recreate=True)

    assert client.deleted_collections == []
    collection_call = client.created_collections[0]
    assert collection_call["collection_name"] == "insurevn_chunks"
    assert collection_call["vectors_config"] == {
        "text_dense": models.VectorParams(
            size=768,
            distance=models.Distance.COSINE,
        )
    }
    assert collection_call["sparse_vectors_config"] == {
        "text_sparse": models.SparseVectorParams(
            index=models.SparseIndexParams(on_disk=False),
        )
    }


def test_qdrant_collection_manager_creates_required_payload_indexes() -> None:
    client = FakeQdrantClient()
    manager = QdrantCollectionManager(
        client=client,
        config=QdrantCollectionConfig(
            collection_name="insurevn_chunks",
            dense_vector_size=384,
        ),
    )

    manager.ensure_payload_indexes()

    indexed_fields = {call["field_name"] for call in client.created_indexes}
    assert indexed_fields == set(QDRANT_FILTER_PAYLOAD_INDEX_FIELDS)
    assert all(
        call["field_schema"] == models.PayloadSchemaType.KEYWORD
        for call in client.created_indexes
    )
