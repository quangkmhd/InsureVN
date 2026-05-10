from src.services.document_retrieval import qdrant_retriever
from src.services.document_retrieval.qwen_embedding_provider import (
    QWEN3_DEFAULT_QUERY_TASK_DESCRIPTION,
    Qwen3EmbeddingProvider,
)


def test_legacy_local_embedding_provider_is_not_exposed() -> None:
    legacy_provider_name = "".join(["Hash", "ing", "EmbeddingProvider"])
    assert not hasattr(qdrant_retriever, legacy_provider_name)


def test_build_dense_embedding_provider_uses_qwen_provider(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeQwen3EmbeddingProvider:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        qdrant_retriever,
        "Qwen3EmbeddingProvider",
        FakeQwen3EmbeddingProvider,
    )

    provider = qdrant_retriever.build_dense_embedding_provider(
        provider="HUGGINGFACE",
        model_name="Qwen/Qwen3-Embedding-8B",
        vector_size=4096,
        batch_size=4,
        max_length=8192,
        load_in_4bit=True,
        device_map="auto",
        attn_implementation="flash_attention_2",
        query_task_description=QWEN3_DEFAULT_QUERY_TASK_DESCRIPTION,
    )

    assert isinstance(provider, FakeQwen3EmbeddingProvider)
    assert captured == {
        "model_name": "Qwen/Qwen3-Embedding-8B",
        "vector_size": 4096,
        "batch_size": 4,
        "max_length": 8192,
        "query_task_description": QWEN3_DEFAULT_QUERY_TASK_DESCRIPTION,
        "load_in_4bit": True,
        "device_map": "auto",
        "attn_implementation": "flash_attention_2",
    }


def test_build_dense_embedding_provider_rejects_google_provider() -> None:
    try:
        qdrant_retriever.build_dense_embedding_provider(
            provider="GOOGLE",
            model_name="gemini-embedding-2",
            vector_size=768,
        )
    except ValueError as exc:
        assert "Unsupported RAG_EMBEDDING_PROVIDER" in str(exc)
        assert "HUGGINGFACE" in str(exc)
    else:
        raise AssertionError("Google embedding provider must be rejected.")


def test_qwen_provider_formats_query_with_instruction() -> None:
    provider = Qwen3EmbeddingProvider(
        model_name="Qwen/Qwen3-Embedding-8B",
        vector_size=4096,
    )

    assert provider._prepare_query_text("Thời gian chờ bệnh đặc biệt là bao lâu?") == (
        f"Instruct: {QWEN3_DEFAULT_QUERY_TASK_DESCRIPTION}\n"
        "Query:Thời gian chờ bệnh đặc biệt là bao lâu?"
    )
