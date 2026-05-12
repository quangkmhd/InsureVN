from pydantic_settings import BaseSettings

import src.eval.config as eval_config
from src.core.config import Settings


def test_settings_uses_pydantic_base_settings() -> None:
    assert issubclass(Settings, BaseSettings)
    assert Settings.model_config["env_ignore_empty"] is True
    assert Settings.model_config["extra"] == "ignore"


def test_settings_loads_explicit_env_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_MAX_CHARS", raising=False)
    monkeypatch.delenv("RAG_RERANK_TRUST_REMOTE_CODE", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SQLITE_DB_PATH=database/from-env-file.db",
                "RAG_CHILD_CHUNK_MAX_CHARS=777",
                "RAG_RERANK_TRUST_REMOTE_CODE=true",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.SQLITE_DB_PATH == "database/from-env-file.db"
    assert settings.RAG_CHILD_CHUNK_MAX_CHARS == 777
    assert settings.RAG_RERANK_TRUST_REMOTE_CODE is True


def test_settings_init_kwargs_override_env_file_for_custom_resolvers(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SQL_AGENT_PROVIDER", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LANGFUSE_BASE_URL=http://from-file:3000",
                "LLM_BASE_URL=https://from-file.example",
                "DATABASE_LLM_PROVIDER=OLLAMA",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(
        _env_file=env_file,
        LANGFUSE_BASE_URL="http://from-init:3000",
        LLM_BASE_URL="https://from-init.example",
        DATABASE_LLM_PROVIDER="NVIDIA",
    )

    assert settings.LANGFUSE_BASE_URL == "http://from-init:3000"
    assert settings.LANGFUSE_HOST == "http://from-init:3000"
    assert settings.LLM_BASE_URL == "https://from-init.example"
    assert settings.DATABASE_LLM_PROVIDER == "NVIDIA"


def test_phase_02_rag_settings_have_typed_defaults(monkeypatch) -> None:
    monkeypatch.delenv("RAG_QDRANT_URL", raising=False)
    monkeypatch.delenv("RAG_QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("RAG_QDRANT_COLLECTION", raising=False)
    monkeypatch.delenv("RAG_DENSE_VECTOR_NAME", raising=False)
    monkeypatch.delenv("RAG_SPARSE_VECTOR_NAME", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("RAG_DENSE_VECTOR_SIZE", raising=False)
    monkeypatch.delenv("RAG_SPARSE_MODEL", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_MAX_CHARS", raising=False)
    monkeypatch.delenv("RAG_CHILD_CHUNK_OVERLAP", raising=False)
    monkeypatch.delenv("RAG_CHUNKING_STRATEGY", raising=False)
    monkeypatch.delenv("RAG_PARENT_SECTION_MAX_CHARS", raising=False)
    monkeypatch.delenv("RAG_RETRIEVAL_TOP_K", raising=False)
    monkeypatch.delenv("RAG_RERANK_CANDIDATE_TOP_K", raising=False)
    monkeypatch.delenv("RAG_RETRIEVAL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("RAG_RERANK_PROVIDER", raising=False)
    monkeypatch.delenv("RAG_RERANK_MODEL", raising=False)
    monkeypatch.delenv("RAG_RERANK_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RAG_RERANK_MAX_LENGTH", raising=False)
    monkeypatch.delenv("RAG_RERANK_DEVICE", raising=False)
    monkeypatch.delenv("RAG_RERANK_TRUST_REMOTE_CODE", raising=False)
    monkeypatch.delenv("RAG_RERANK_BACKEND", raising=False)
    monkeypatch.delenv("RAG_RERANK_LOAD_IN_4BIT", raising=False)
    monkeypatch.delenv("RAG_RERANK_DEVICE_MAP", raising=False)
    monkeypatch.delenv("RAG_RERANK_ATTN_IMPLEMENTATION", raising=False)
    monkeypatch.delenv("RAG_RERANK_TORCH_DTYPE", raising=False)
    monkeypatch.delenv("RAG_REQUIRE_HYBRID_SEARCH", raising=False)
    monkeypatch.delenv("RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", raising=False)
    monkeypatch.delenv("RAG_REQUIRE_HARD_FILTERS", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_BATCH_SIZE", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_MAX_LENGTH", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_LOAD_IN_4BIT", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_DEVICE_MAP", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_ATTN_IMPLEMENTATION", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_QUERY_TASK_DESCRIPTION", raising=False)
    monkeypatch.delenv("QWEN_EMBEDDING_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.RAG_QDRANT_URL == "http://localhost:6333"
    assert settings.RAG_QDRANT_API_KEY == ""
    assert settings.RAG_QDRANT_COLLECTION == "insurevn_policy_chunks"
    assert settings.RAG_DENSE_VECTOR_NAME == "text_dense"
    assert settings.RAG_SPARSE_VECTOR_NAME == "text_sparse"
    assert settings.RAG_EMBEDDING_PROVIDER == "HUGGINGFACE"
    assert settings.RAG_EMBEDDING_MODEL == "Qwen/Qwen3-Embedding-8B"
    assert settings.RAG_EMBEDDING_API_KEY == ""
    assert settings.RAG_DENSE_VECTOR_SIZE == 4096
    assert settings.RAG_SPARSE_MODEL == "Qdrant/bm25"
    assert isinstance(settings.RAG_CHILD_CHUNK_MAX_CHARS, int)
    assert settings.RAG_CHILD_CHUNK_MAX_CHARS == 1200
    assert settings.RAG_CHILD_CHUNK_OVERLAP == 150
    assert settings.RAG_CHUNKING_STRATEGY == "hierarchical_header_recursive"
    assert settings.RAG_PARENT_SECTION_MAX_CHARS == 6000
    assert settings.RAG_RETRIEVAL_TOP_K == 10
    assert settings.RAG_RERANK_CANDIDATE_TOP_K == 30
    assert settings.RAG_RETRIEVAL_TIMEOUT_SECONDS == 30.0
    assert settings.RAG_RERANK_PROVIDER == "HUGGINGFACE"
    assert settings.RAG_RERANK_MODEL == "namdp-ptit/ViRanker"
    assert settings.RAG_RERANK_BATCH_SIZE == 8
    assert settings.RAG_RERANK_MAX_LENGTH == 1024
    assert settings.RAG_RERANK_DEVICE == "cuda"
    assert settings.RAG_RERANK_TRUST_REMOTE_CODE is False
    assert settings.RAG_RERANK_BACKEND == "torch"
    assert settings.RAG_RERANK_LOAD_IN_4BIT is False
    assert settings.RAG_RERANK_DEVICE_MAP == ""
    assert settings.RAG_RERANK_ATTN_IMPLEMENTATION == ""
    assert settings.RAG_RERANK_TORCH_DTYPE == ""
    assert settings.RAG_REQUIRE_HYBRID_SEARCH is True
    assert settings.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE is False
    assert settings.RAG_REQUIRE_HARD_FILTERS is True
    assert settings.RAG_EMBEDDING_BATCH_SIZE == 4
    assert settings.RAG_EMBEDDING_MAX_LENGTH == 8192
    assert settings.RAG_EMBEDDING_LOAD_IN_4BIT is True
    assert settings.RAG_EMBEDDING_DEVICE_MAP == "auto"
    assert settings.RAG_EMBEDDING_ATTN_IMPLEMENTATION == ""
    assert (
        settings.RAG_EMBEDDING_QUERY_TASK_DESCRIPTION
        == "Given a web search query, retrieve relevant passages that answer the query"
    )


def test_phase_02_rag_settings_cast_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("RAG_CHILD_CHUNK_MAX_CHARS", "900")
    monkeypatch.setenv("RAG_CHILD_CHUNK_OVERLAP", "90")
    monkeypatch.setenv("RAG_PARENT_SECTION_MAX_CHARS", "4500")
    monkeypatch.setenv("RAG_DENSE_VECTOR_SIZE", "1024")
    monkeypatch.setenv("RAG_RETRIEVAL_TOP_K", "8")
    monkeypatch.setenv("RAG_RERANK_CANDIDATE_TOP_K", "24")
    monkeypatch.setenv("RAG_RETRIEVAL_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "HUGGINGFACE")
    monkeypatch.setenv("RAG_RERANK_MODEL", "Qwen/Qwen3-Reranker-0.6B")
    monkeypatch.setenv("RAG_RERANK_BATCH_SIZE", "3")
    monkeypatch.setenv("RAG_RERANK_MAX_LENGTH", "2048")
    monkeypatch.setenv("RAG_RERANK_DEVICE", "cuda")
    monkeypatch.setenv("RAG_RERANK_TRUST_REMOTE_CODE", "true")
    monkeypatch.setenv("RAG_RERANK_BACKEND", "torch")
    monkeypatch.setenv("RAG_RERANK_LOAD_IN_4BIT", "true")
    monkeypatch.setenv("RAG_RERANK_DEVICE_MAP", "auto")
    monkeypatch.setenv("RAG_RERANK_ATTN_IMPLEMENTATION", "flash_attention_2")
    monkeypatch.setenv("RAG_RERANK_TORCH_DTYPE", "float16")
    monkeypatch.setenv("RAG_REQUIRE_HYBRID_SEARCH", "false")
    monkeypatch.setenv("RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", "true")
    monkeypatch.setenv("RAG_REQUIRE_HARD_FILTERS", "false")
    monkeypatch.setenv("RAG_EMBEDDING_BATCH_SIZE", "2")
    monkeypatch.setenv("RAG_EMBEDDING_MAX_LENGTH", "4096")
    monkeypatch.setenv("RAG_EMBEDDING_LOAD_IN_4BIT", "false")
    monkeypatch.setenv("RAG_EMBEDDING_DEVICE_MAP", "cpu")
    monkeypatch.setenv("RAG_EMBEDDING_ATTN_IMPLEMENTATION", "flash_attention_2")
    monkeypatch.setenv(
        "RAG_EMBEDDING_QUERY_TASK_DESCRIPTION",
        "Retrieve Vietnamese insurance clauses relevant to the question",
    )

    settings = Settings(_env_file=None)

    assert settings.RAG_CHILD_CHUNK_MAX_CHARS == 900
    assert settings.RAG_CHILD_CHUNK_OVERLAP == 90
    assert settings.RAG_PARENT_SECTION_MAX_CHARS == 4500
    assert settings.RAG_DENSE_VECTOR_SIZE == 1024
    assert settings.RAG_RETRIEVAL_TOP_K == 8
    assert settings.RAG_RERANK_CANDIDATE_TOP_K == 24
    assert settings.RAG_RETRIEVAL_TIMEOUT_SECONDS == 12.5
    assert settings.RAG_RERANK_PROVIDER == "HUGGINGFACE"
    assert settings.RAG_RERANK_MODEL == "Qwen/Qwen3-Reranker-0.6B"
    assert settings.RAG_RERANK_BATCH_SIZE == 3
    assert settings.RAG_RERANK_MAX_LENGTH == 2048
    assert settings.RAG_RERANK_DEVICE == "cuda"
    assert settings.RAG_RERANK_TRUST_REMOTE_CODE is True
    assert settings.RAG_RERANK_BACKEND == "torch"
    assert settings.RAG_RERANK_LOAD_IN_4BIT is True
    assert settings.RAG_RERANK_DEVICE_MAP == "auto"
    assert settings.RAG_RERANK_ATTN_IMPLEMENTATION == "flash_attention_2"
    assert settings.RAG_RERANK_TORCH_DTYPE == "float16"
    assert settings.RAG_REQUIRE_HYBRID_SEARCH is False
    assert settings.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE is True
    assert settings.RAG_REQUIRE_HARD_FILTERS is False
    assert settings.RAG_EMBEDDING_BATCH_SIZE == 2
    assert settings.RAG_EMBEDDING_MAX_LENGTH == 4096
    assert settings.RAG_EMBEDDING_LOAD_IN_4BIT is False
    assert settings.RAG_EMBEDDING_DEVICE_MAP == "cpu"
    assert settings.RAG_EMBEDDING_ATTN_IMPLEMENTATION == "flash_attention_2"
    assert (
        settings.RAG_EMBEDDING_QUERY_TASK_DESCRIPTION
        == "Retrieve Vietnamese insurance clauses relevant to the question"
    )


def test_rag_embedding_api_key_supports_indirect_env_alias(monkeypatch) -> None:
    monkeypatch.setenv("RAG_EMBEDDING_API_KEY", "QWEN_LOCAL_PLACEHOLDER_KEY")
    monkeypatch.setenv("QWEN_LOCAL_PLACEHOLDER_KEY", "resolved-qwen-key")

    settings = Settings(_env_file=None)

    assert settings.RAG_EMBEDDING_API_KEY == "resolved-qwen-key"


def test_phase_03_graph_settings_have_typed_defaults(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URLS", raising=False)
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

    settings = Settings(_env_file=None)

    assert settings.NEO4J_URI == "bolt://localhost:7687"
    assert settings.NEO4J_USERNAME == "neo4j"
    assert settings.NEO4J_PASSWORD == ""
    assert settings.NEO4J_DATABASE == "neo4j"
    assert settings.GRAPH_EAGER_K == 5
    assert settings.GRAPH_EAGER_START_K == 1
    assert settings.GRAPH_EAGER_MAX_DEPTH == 2
    assert settings.GRAPH_MIN_CONFIDENCE == 0.75
    assert settings.KG_EXTRACTION_LLM_PROVIDER == ""
    assert settings.KG_EXTRACTION_LLM_MODEL == ""
    assert settings.KG_EXTRACTION_LLM_API_KEY == ""
    assert settings.KG_EXTRACTION_LLM_BASE_URL == "http://localhost:11434"
    assert settings.KG_EXTRACTION_LLM_TEMPERATURE == 0.0
    assert settings.KG_EXTRACTION_MAX_RETRIES == 2
    assert settings.KG_CYPHER_QA_LLM_PROVIDER == ""
    assert settings.KG_CYPHER_QA_LLM_MODEL == ""


def test_phase_03_graph_settings_cast_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_EAGER_K", "8")
    monkeypatch.setenv("GRAPH_EAGER_START_K", "2")
    monkeypatch.setenv("GRAPH_EAGER_MAX_DEPTH", "3")
    monkeypatch.setenv("GRAPH_MIN_CONFIDENCE", "0.82")
    monkeypatch.setenv("KG_EXTRACTION_LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("KG_EXTRACTION_MAX_RETRIES", "4")

    settings = Settings(_env_file=None)

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

    settings = Settings(_env_file=None)

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

    settings = Settings(_env_file=None)

    assert settings.LANGFUSE_BASE_URL == "http://langfuse.local:3000"
    assert settings.LANGFUSE_HOST == "http://langfuse.local:3000"


def test_settings_collect_all_numbered_google_api_keys_even_with_gaps(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRIMARY_GOOGLE_KEY", "google-key-0")
    monkeypatch.setenv("GOOGLE_API_KEY", "PRIMARY_GOOGLE_KEY")
    for index in range(1, 12):
        monkeypatch.delenv(f"GOOGLE_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY_1", "google-key-1")
    monkeypatch.setenv("GOOGLE_API_KEY_3", "google-key-3")
    monkeypatch.setenv("GOOGLE_API_KEY_10", "google-key-10")

    settings = Settings(_env_file=None)

    assert settings.GOOGLE_API_KEYS == [
        "google-key-0",
        "google-key-1",
        "google-key-3",
        "google-key-10",
    ]


def test_settings_preserves_direct_plural_api_key_lists(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEYS", "google-key-a, google-key-b")
    monkeypatch.setenv("OPENROUTER_API_KEYS", "openrouter-key-a,openrouter-key-b")
    monkeypatch.setenv("NVIDIA_API_KEYS", "nvidia-key-a,nvidia-key-b")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    for index in range(1, 50):
        monkeypatch.delenv(f"GOOGLE_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"OPENROUTER_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"NVIDIA_API_KEY_{index}", raising=False)

    settings = Settings(_env_file=None)

    assert settings.GOOGLE_API_KEYS == ["google-key-a", "google-key-b"]
    assert settings.OPENROUTER_API_KEYS == [
        "openrouter-key-a",
        "openrouter-key-b",
    ]
    assert settings.NVIDIA_API_KEYS == ["nvidia-key-a", "nvidia-key-b"]


def test_eval_config_collects_all_google_keys_from_aliases_and_numbered_env(
    monkeypatch,
) -> None:
    for env_name in (
        "CHUNKING_EVAL_EMBEDDING_GOOGLE_API_KEY",
        "CHUNKING_EVAL_EMBEDDING_GOOGLE_API_KEYS",
        "RAG_EMBEDDING_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)
    for index in range(1, 8):
        monkeypatch.delenv(f"GOOGLE_API_KEY_{index}", raising=False)
        monkeypatch.delenv(f"GEMINI_API_KEY_{index}", raising=False)

    monkeypatch.setenv(
        "CHUNKING_EVAL_EMBEDDING_GOOGLE_API_KEYS",
        "GOOGLE_API_KEY_1,inline-google-key",
    )
    monkeypatch.setenv("RAG_EMBEDDING_API_KEY", "GOOGLE_API_KEY_3")
    monkeypatch.setenv("GOOGLE_API_KEY_1", "google-key-1")
    monkeypatch.setenv("GOOGLE_API_KEY_3", "google-key-3")
    monkeypatch.setenv("GOOGLE_API_KEY_5", "google-key-5")
    monkeypatch.setattr(
        eval_config.settings,
        "GOOGLE_API_KEYS",
        ["google-key-1", "settings-google-key-9"],
    )

    assert eval_config._collect_eval_google_api_keys() == (
        "google-key-1",
        "inline-google-key",
        "google-key-3",
        "google-key-5",
        "settings-google-key-9",
    )


def test_agent_llm_settings_inherit_global_llm_config(monkeypatch) -> None:
    """Verify agent-owned settings inherit shared global LLM defaults."""
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("LLM_MODEL", "global-model")
    monkeypatch.setenv("LLM_API_KEY", "global-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://global.example")
    monkeypatch.delenv("SQL_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("SQL_AGENT_MODEL", raising=False)
    monkeypatch.delenv("SQL_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("SQL_AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DATABASE_LLM_MODEL", raising=False)
    monkeypatch.delenv("DATABASE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SEARCH_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("SEARCH_AGENT_MODEL", raising=False)
    monkeypatch.delenv("SEARCH_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_AGENT_BASE_URL", raising=False)
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

    settings = Settings(_env_file=None)

    assert settings.DATABASE_LLM_PROVIDER == "nvidia"
    assert settings.DATABASE_LLM_MODEL == "global-model"
    assert settings.DATABASE_LLM_API_KEY == "global-key"
    assert settings.DATABASE_LLM_BASE_URL == "https://global.example"
    assert settings.SEARCH_LLM_PROVIDER == "nvidia"
    assert settings.SEARCH_LLM_MODEL == "global-model"
    assert settings.SEARCH_LLM_API_KEY == "global-key"
    assert settings.SEARCH_LLM_BASE_URL == "https://global.example"
    assert settings.KG_EXTRACTION_LLM_PROVIDER == "nvidia"
    assert settings.KG_EXTRACTION_LLM_MODEL == "global-model"
    assert settings.KG_EXTRACTION_LLM_API_KEY == "global-key"
    assert settings.KG_EXTRACTION_LLM_BASE_URL == "https://global.example"
    assert settings.KG_CYPHER_QA_LLM_PROVIDER == "nvidia"
    assert settings.KG_CYPHER_QA_LLM_MODEL == "global-model"
    assert settings.KG_CYPHER_QA_LLM_API_KEY == "global-key"
    assert settings.KG_CYPHER_QA_LLM_BASE_URL == "https://global.example"


def test_sql_agent_provider_alias_resolves_provider_global_key_and_base_url(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SQL_AGENT_PROVIDER", "OPENROUTER")
    monkeypatch.setenv("OPENROUTER_API_KEY", "OPENROUTER_KEY_ALIAS")
    monkeypatch.setenv("OPENROUTER_KEY_ALIAS", "resolved-openrouter-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SQL_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("SQL_AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DATABASE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_LLM_BASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.DATABASE_LLM_PROVIDER == "OPENROUTER"
    assert settings.DATABASE_LLM_API_KEY == "resolved-openrouter-key"
    assert settings.DATABASE_LLM_BASE_URL == "https://openrouter.ai/api/v1"


def test_search_agent_provider_alias_resolves_provider_global_key_and_base_url(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SEARCH_AGENT_PROVIDER", "NVIDIA")
    monkeypatch.setenv("NVIDIA_API_KEY", "NVIDIA_KEY_ALIAS")
    monkeypatch.setenv("NVIDIA_KEY_ALIAS", "resolved-nvidia-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SEARCH_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("SEARCH_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SEARCH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_LLM_BASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.SEARCH_LLM_PROVIDER == "NVIDIA"
    assert settings.SEARCH_LLM_API_KEY == "resolved-nvidia-key"
    assert settings.SEARCH_LLM_BASE_URL == "https://integrate.api.nvidia.com/v1"
