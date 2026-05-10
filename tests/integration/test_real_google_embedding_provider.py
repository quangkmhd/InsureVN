import pytest

from src.core.config import settings
from src.services.document_retrieval.qdrant_retriever import GoogleGenAIEmbeddingProvider


@pytest.mark.real_api
@pytest.mark.skipif(
    not settings.GOOGLE_API_KEY,
    reason="GOOGLE_API_KEY is required for real Google embedding tests.",
)
def test_real_google_embedding_provider_uses_env_credentials() -> None:
    provider = GoogleGenAIEmbeddingProvider(
        model_name=settings.RAG_EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        vector_size=settings.RAG_DENSE_VECTOR_SIZE,
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
