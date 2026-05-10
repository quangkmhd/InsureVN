import pytest

from src.core.config import settings
from src.services.document_retrieval.qdrant_retriever import (
    build_dense_embedding_provider,
)


@pytest.mark.real_api
def test_real_qwen_embedding_provider_uses_production_config() -> None:
    provider = build_dense_embedding_provider(
        provider=settings.RAG_EMBEDDING_PROVIDER,
        model_name=settings.RAG_EMBEDDING_MODEL,
        vector_size=settings.RAG_DENSE_VECTOR_SIZE,
        batch_size=1,
        max_length=settings.RAG_EMBEDDING_MAX_LENGTH,
        load_in_4bit=settings.RAG_EMBEDDING_LOAD_IN_4BIT,
        device_map=settings.RAG_EMBEDDING_DEVICE_MAP,
        attn_implementation=settings.RAG_EMBEDDING_ATTN_IMPLEMENTATION,
        query_task_description=settings.RAG_EMBEDDING_QUERY_TASK_DESCRIPTION,
    )

    document_vectors = provider.embed_documents(
        [
            "Bao hiem suc khoe chi tra chi phi nam vien.",
            "Thoi gian cho benh dac biet la 90 ngay.",
        ]
    )
    query_vector = provider.embed_query("quyen loi nam vien bao hiem suc khoe")

    assert len(document_vectors) == 2
    assert all(
        len(vector) == settings.RAG_DENSE_VECTOR_SIZE for vector in document_vectors
    )
    assert len(query_vector) == settings.RAG_DENSE_VECTOR_SIZE
    assert any(value != 0.0 for value in query_vector)
