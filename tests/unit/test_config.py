from src.core.config import Settings


def test_phase_02_rag_settings_have_typed_defaults(monkeypatch) -> None:
    monkeypatch.delenv("RAG_QDRANT_URL", raising=False)
    monkeypatch.delenv("RAG_QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("RAG_QDRANT_COLLECTION", raising=False)
    monkeypatch.delenv("RAG_DENSE_VECTOR_NAME", raising=False)
    monkeypatch.delenv("RAG_SPARSE_VECTOR_NAME", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("RAG_DENSE_VECTOR_SIZE", raising=False)
    monkeypatch.delenv("RAG_SPARSE_MODEL", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_MAX_CHARS", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_OVERLAP", raising=False)
    monkeypatch.delenv("RAG_CHUNKING_STRATEGY", raising=False)
    monkeypatch.delenv("RAG_PARENT_SECTION_MAX_CHARS", raising=False)
    monkeypatch.delenv("RAG_RETRIEVAL_TOP_K", raising=False)
    monkeypatch.delenv("RAG_RETRIEVAL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("RAG_REQUIRE_HYBRID_SEARCH", raising=False)
    monkeypatch.delenv("RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", raising=False)

    settings = Settings()

    assert settings.RAG_QDRANT_URL == "http://localhost:6333"
    assert settings.RAG_QDRANT_API_KEY == ""
    assert settings.RAG_QDRANT_COLLECTION == "insurevn_policy_chunks"
    assert settings.RAG_DENSE_VECTOR_NAME == "text_dense"
    assert settings.RAG_SPARSE_VECTOR_NAME == "text_sparse"
    assert settings.RAG_EMBEDDING_PROVIDER == "google_genai"
    assert settings.RAG_EMBEDDING_MODEL == "gemini-embedding-2"
    assert settings.RAG_DENSE_VECTOR_SIZE == 768
    assert settings.RAG_SPARSE_MODEL == "Qdrant/bm25"
    assert isinstance(settings.RAG_CHILD_CHUNK_MAX_CHARS, int)
    assert settings.RAG_CHILD_CHUNK_MAX_CHARS == 1200
    assert settings.RAG_CHILD_CHUNK_OVERLAP == 150
    assert settings.RAG_CHUNKING_STRATEGY == "hierarchical_header_recursive"
    assert settings.RAG_PARENT_SECTION_MAX_CHARS == 6000
    assert settings.RAG_RETRIEVAL_TOP_K == 5
    assert settings.RAG_RETRIEVAL_TIMEOUT_SECONDS == 30.0
    assert settings.RAG_REQUIRE_HYBRID_SEARCH is True
    assert settings.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE is False


def test_phase_02_rag_settings_cast_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("RAG_CHILD_CHUNK_MAX_CHARS", "900")
    monkeypatch.setenv("RAG_CHILD_CHUNK_OVERLAP", "90")
    monkeypatch.setenv("RAG_PARENT_SECTION_MAX_CHARS", "4500")
    monkeypatch.setenv("RAG_DENSE_VECTOR_SIZE", "512")
    monkeypatch.setenv("RAG_RETRIEVAL_TOP_K", "8")
    monkeypatch.setenv("RAG_RETRIEVAL_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("RAG_REQUIRE_HYBRID_SEARCH", "false")
    monkeypatch.setenv("RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", "true")

    settings = Settings()

    assert settings.RAG_CHILD_CHUNK_MAX_CHARS == 900
    assert settings.RAG_CHILD_CHUNK_OVERLAP == 90
    assert settings.RAG_PARENT_SECTION_MAX_CHARS == 4500
    assert settings.RAG_DENSE_VECTOR_SIZE == 512
    assert settings.RAG_RETRIEVAL_TOP_K == 8
    assert settings.RAG_RETRIEVAL_TIMEOUT_SECONDS == 12.5
    assert settings.RAG_REQUIRE_HYBRID_SEARCH is False
    assert settings.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE is True


def test_phase_03_graph_settings_have_typed_defaults(monkeypatch) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USERNAME", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)
    monkeypatch.delenv("GRAPH_EAGER_K", raising=False)
    monkeypatch.delenv("GRAPH_EAGER_START_K", raising=False)
    monkeypatch.delenv("GRAPH_EAGER_MAX_DEPTH", raising=False)
    monkeypatch.delenv("GRAPH_MIN_CONFIDENCE", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_MODEL", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_API_KEY", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_TEMPERATURE", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_MAX_RETRIES", raising=False)
    monkeypatch.delenv("KG_CYPHER_QA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("KG_CYPHER_QA_LLM_MODEL", raising=False)

    settings = Settings()

    assert settings.NEO4J_URI == "bolt://localhost:7687"
    assert settings.NEO4J_USERNAME == "neo4j"
    assert settings.NEO4J_PASSWORD == ""
    assert settings.NEO4J_DATABASE == "neo4j"
    assert settings.GRAPH_EAGER_K == 5
    assert settings.GRAPH_EAGER_START_K == 1
    assert settings.GRAPH_EAGER_MAX_DEPTH == 2
    assert settings.GRAPH_MIN_CONFIDENCE == 0.75
    assert settings.KG_EXTRACTION_LLM_PROVIDER == "ollama"
    assert settings.KG_EXTRACTION_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.KG_EXTRACTION_LLM_API_KEY == ""
    assert settings.KG_EXTRACTION_LLM_BASE_URL == "http://localhost:11434"
    assert settings.KG_EXTRACTION_LLM_TEMPERATURE == 0.0
    assert settings.KG_EXTRACTION_MAX_RETRIES == 2
    assert settings.KG_CYPHER_QA_LLM_PROVIDER == "ollama"
    assert settings.KG_CYPHER_QA_LLM_MODEL == "gemma4:31b-cloud"


def test_phase_03_graph_settings_cast_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_EAGER_K", "8")
    monkeypatch.setenv("GRAPH_EAGER_START_K", "2")
    monkeypatch.setenv("GRAPH_EAGER_MAX_DEPTH", "3")
    monkeypatch.setenv("GRAPH_MIN_CONFIDENCE", "0.82")
    monkeypatch.setenv("KG_EXTRACTION_LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("KG_EXTRACTION_MAX_RETRIES", "4")

    settings = Settings()

    assert settings.GRAPH_EAGER_K == 8
    assert settings.GRAPH_EAGER_START_K == 2
    assert settings.GRAPH_EAGER_MAX_DEPTH == 3
    assert settings.GRAPH_MIN_CONFIDENCE == 0.82
    assert settings.KG_EXTRACTION_LLM_TEMPERATURE == 0.2
    assert settings.KG_EXTRACTION_MAX_RETRIES == 4


def test_schema_discovery_provider_settings_cast_env_values(monkeypatch) -> None:
    monkeypatch.setenv(
        "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
        "http://ollama-1:11434,http://ollama-2:11434",
    )
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS", "ol-1,ol-2")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS", "or-1,or-2")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS", "nv-1,nv-2,nv-3")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS", "gm-1")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY", "8")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_CHUNK_CHARS", "9000")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP", "300")
    monkeypatch.setenv("KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS", "45.5")

    settings = Settings()

    assert settings.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS == [
        "http://ollama-1:11434",
        "http://ollama-2:11434",
    ]
    assert settings.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS == ["ol-1", "ol-2"]
    assert settings.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS == ["or-1", "or-2"]
    assert settings.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS == ["nv-1", "nv-2", "nv-3"]
    assert settings.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS == ["gm-1"]
    assert settings.KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY == 8
    assert settings.KG_SCHEMA_DISCOVERY_CHUNK_CHARS == 9000
    assert settings.KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP == 300
    assert settings.KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS == 45.5


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
    monkeypatch.delenv("KG_EXTRACTION_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_MODEL", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_API_KEY", raising=False)
    monkeypatch.delenv("KG_EXTRACTION_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KG_CYPHER_QA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("KG_CYPHER_QA_LLM_MODEL", raising=False)
    monkeypatch.delenv("KG_CYPHER_QA_LLM_API_KEY", raising=False)
    monkeypatch.delenv("KG_CYPHER_QA_LLM_BASE_URL", raising=False)

    settings = Settings()

    assert settings.DATABASE_LLM_PROVIDER == "ollama"
    assert settings.DATABASE_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.DATABASE_LLM_API_KEY == ""
    assert settings.DATABASE_LLM_BASE_URL == "http://localhost:11434"
    assert settings.SEARCH_LLM_PROVIDER == "ollama"
    assert settings.SEARCH_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.SEARCH_LLM_API_KEY == ""
    assert settings.SEARCH_LLM_BASE_URL == "http://localhost:11434"
    assert settings.KG_EXTRACTION_LLM_PROVIDER == "ollama"
    assert settings.KG_EXTRACTION_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.KG_EXTRACTION_LLM_API_KEY == ""
    assert settings.KG_EXTRACTION_LLM_BASE_URL == "http://localhost:11434"
    assert settings.KG_CYPHER_QA_LLM_PROVIDER == "ollama"
    assert settings.KG_CYPHER_QA_LLM_MODEL == "gemma4:31b-cloud"
    assert settings.KG_CYPHER_QA_LLM_API_KEY == ""
    assert settings.KG_CYPHER_QA_LLM_BASE_URL == "http://localhost:11434"
