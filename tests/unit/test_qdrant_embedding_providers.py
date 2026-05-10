from src.services.document_retrieval import qdrant_retriever


def test_google_genai_embedding_provider_uses_configured_vector_size(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeGoogleGenerativeAIEmbeddings:
        def __init__(self, **kwargs) -> None:
            captured["init"] = kwargs

        def embed_documents(self, texts: list[str], **kwargs) -> list[list[float]]:
            captured["document_texts"] = texts
            captured["document_kwargs"] = kwargs
            return [[1.0, 0.0, 0.0] for _ in texts]

        def embed_query(self, text: str, **kwargs) -> list[float]:
            captured["query_text"] = text
            captured["query_kwargs"] = kwargs
            return [0.0, 1.0, 0.0]

    monkeypatch.setattr(
        qdrant_retriever,
        "GoogleGenerativeAIEmbeddings",
        FakeGoogleGenerativeAIEmbeddings,
    )

    provider = qdrant_retriever.GoogleGenAIEmbeddingProvider(
        model_name="gemini-embedding-2",
        google_api_key="test-google-key",
        vector_size=3,
    )

    assert provider.vector_size == 3
    assert provider.embed_documents(["policy text"]) == [[1.0, 0.0, 0.0]]
    assert provider.embed_query("policy query") == [0.0, 1.0, 0.0]
    assert captured["init"] == {
        "model": "gemini-embedding-2",
        "google_api_key": "test-google-key",
        "output_dimensionality": 3,
    }
    assert captured["document_texts"] == ["policy text"]
    assert captured["document_kwargs"] == {
        "batch_size": 1,
        "task_type": "RETRIEVAL_DOCUMENT",
        "output_dimensionality": 3,
    }
    assert captured["query_text"] == "policy query"
    assert captured["query_kwargs"] == {
        "task_type": "RETRIEVAL_QUERY",
        "output_dimensionality": 3,
    }


def test_legacy_local_embedding_provider_is_not_exposed() -> None:
    legacy_provider_name = "".join(["Hash", "ing", "EmbeddingProvider"])
    assert not hasattr(qdrant_retriever, legacy_provider_name)
