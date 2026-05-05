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


def test_langfuse_settings_prefer_current_base_url(monkeypatch) -> None:
    """Verify Langfuse uses the current SDK base URL setting."""
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://langfuse.local:3000")
    monkeypatch.setenv("LANGFUSE_HOST", "http://legacy-langfuse.local:3000")

    settings = Settings()

    assert settings.LANGFUSE_BASE_URL == "http://langfuse.local:3000"
    assert settings.LANGFUSE_HOST == "http://langfuse.local:3000"


def test_agent_llm_settings_do_not_inherit_global_llm_config(monkeypatch) -> None:
    """Verify agent-owned settings remain isolated from global LLM settings."""
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("LLM_MODEL", "global-model")
    monkeypatch.setenv("LLM_API_KEY", "global-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://global.example")
    monkeypatch.delenv("DATABASE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DATABASE_LLM_MODEL", raising=False)
    monkeypatch.delenv("DATABASE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SEARCH_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SEARCH_LLM_MODEL", raising=False)
    monkeypatch.delenv("SEARCH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_LLM_BASE_URL", raising=False)

    settings = Settings()

    assert settings.DATABASE_LLM_PROVIDER == "ollama"
    assert settings.DATABASE_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.DATABASE_LLM_API_KEY == ""
    assert settings.DATABASE_LLM_BASE_URL == "http://localhost:11434"
    assert settings.SEARCH_LLM_PROVIDER == "ollama"
    assert settings.SEARCH_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.SEARCH_LLM_API_KEY == ""
    assert settings.SEARCH_LLM_BASE_URL == "http://localhost:11434"
