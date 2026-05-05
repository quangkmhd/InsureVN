from src.core.config import Settings


def test_phase_02_rag_settings_have_typed_defaults(monkeypatch) -> None:
    monkeypatch.delenv("RAG_QDRANT_URL", raising=False)
    monkeypatch.delenv("RAG_QDRANT_COLLECTION", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_TOKENS", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_OVERLAP", raising=False)
    monkeypatch.delenv("RAG_PARENT_SECTION_MAX_CHARS", raising=False)
    monkeypatch.delenv("RAG_RETRIEVAL_TOP_K", raising=False)
    monkeypatch.delenv("RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", raising=False)

    settings = Settings()

    assert settings.RAG_QDRANT_URL == "http://localhost:6333"
    assert settings.RAG_QDRANT_COLLECTION == "insurevn_policy_chunks"
    assert settings.RAG_EMBEDDING_MODEL == "hashing-local"
    assert isinstance(settings.RAG_CHILD_CHUNK_TOKENS, int)
    assert settings.RAG_CHILD_CHUNK_TOKENS == 1200
    assert settings.RAG_CHILD_CHUNK_OVERLAP == 150
    assert settings.RAG_PARENT_SECTION_MAX_CHARS == 6000
    assert settings.RAG_RETRIEVAL_TOP_K == 5
    assert settings.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE is False


def test_phase_02_rag_settings_cast_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("RAG_CHILD_CHUNK_TOKENS", "900")
    monkeypatch.setenv("RAG_CHILD_CHUNK_OVERLAP", "90")
    monkeypatch.setenv("RAG_PARENT_SECTION_MAX_CHARS", "4500")
    monkeypatch.setenv("RAG_RETRIEVAL_TOP_K", "8")
    monkeypatch.setenv("RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", "true")

    settings = Settings()

    assert settings.RAG_CHILD_CHUNK_TOKENS == 900
    assert settings.RAG_CHILD_CHUNK_OVERLAP == 90
    assert settings.RAG_PARENT_SECTION_MAX_CHARS == 4500
    assert settings.RAG_RETRIEVAL_TOP_K == 8
    assert settings.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE is True
