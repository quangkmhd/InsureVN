import os
from pathlib import Path
from typing import Any, ClassVar

from dotenv import dotenv_values
from pydantic import PrivateAttr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _env_files(env_file: Any) -> list[Path]:
    """Normalize pydantic-settings env_file values into a list of paths."""
    if env_file is None:
        return []
    if isinstance(env_file, (str, Path)):
        return [Path(env_file)]
    if isinstance(env_file, (list, tuple)):
        return [Path(file_path) for file_path in env_file if file_path is not None]
    return []


def _build_raw_env(env_file: Any) -> dict[str, str]:
    """Build an env snapshot that includes dotenv values for custom resolvers."""
    raw_env: dict[str, str] = {}
    for file_path in _env_files(env_file):
        if not file_path.exists():
            continue
        for name, value in dotenv_values(file_path).items():
            if value:
                raw_env[name] = value
    for name, value in os.environ.items():
        if value:
            raw_env[name] = value
    return raw_env


def _raw_env_value(value: Any) -> str:
    """Convert explicit init values into resolver-compatible env strings."""
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)


def _merge_unique(*value_groups: list[str]) -> list[str]:
    """Merge ordered string lists without duplicates."""
    merged_values: list[str] = []
    for values in value_groups:
        for value in values:
            if value not in merged_values:
                merged_values.append(value)
    return merged_values


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore",
        validate_default=True,
    )

    _DERIVED_SETTING_RESOLVERS: ClassVar[dict[str, str]] = {
        "LANGFUSE_HOST": "_derived_langfuse_host",
        "GOOGLE_API_KEYS": "_derived_google_api_keys",
        "OPENROUTER_API_KEYS": "_derived_openrouter_api_keys",
        "NVIDIA_API_KEYS": "_derived_nvidia_api_keys",
        "OLLAMA_API_KEYS": "_derived_ollama_api_keys",
        "OLLAMA_BASE_URLS": "_derived_ollama_base_urls",
        "GOOGLE_API_KEY": "_derived_google_api_key",
        "GEMINI_API_KEY": "_derived_gemini_api_key",
        "OPENROUTER_API_KEY": "_derived_openrouter_api_key",
        "NVIDIA_API_KEY": "_derived_nvidia_api_key",
        "LLM_PROVIDER": "_derived_llm_provider",
        "LLM_MODEL": "_derived_llm_model",
        "LLM_API_KEY": "_derived_llm_api_key",
        "LLM_BASE_URL": "_derived_llm_base_url",
        "DATABASE_LLM_PROVIDER": "_derived_database_llm_provider",
        "DATABASE_LLM_MODEL": "_derived_database_llm_model",
        "DATABASE_LLM_API_KEY": "_derived_database_llm_api_key",
        "DATABASE_LLM_BASE_URL": "_derived_database_llm_base_url",
        "SEARCH_TAVILY_API_KEY": "_derived_search_tavily_api_key",
        "SEARCH_LLM_PROVIDER": "_derived_search_llm_provider",
        "SEARCH_LLM_MODEL": "_derived_search_llm_model",
        "SEARCH_LLM_API_KEY": "_derived_search_llm_api_key",
        "SEARCH_LLM_BASE_URL": "_derived_search_llm_base_url",
        "LLM_CHUNKING_PROVIDER": "_derived_llm_chunking_provider",
        "LLM_CHUNKING_MODEL": "_derived_llm_chunking_model",
        "LLM_CHUNKING_API_KEY": "_derived_llm_chunking_api_key",
        "LLM_CHUNKING_BASE_URL": "_derived_llm_chunking_base_url",
        "LLM_CHUNKING_MAX_INPUT_CHARS": "_derived_llm_chunking_max_input_chars",
        "LLM_CHUNKING_TIMEOUT_SECONDS": "_derived_llm_chunking_timeout_seconds",
        "LLM_CHUNKING_CACHE_PATH": "_derived_llm_chunking_cache_path",
        "LLM_CHUNKING_UNIT_PREVIEW_CHARS": "_derived_llm_chunking_preview_chars",
        "RAG_QDRANT_API_KEY": "_derived_rag_qdrant_api_key",
        "RAG_EMBEDDING_API_KEY": "_derived_rag_embedding_api_key",
        "RAG_SPARSE_MODEL": "_derived_rag_sparse_model",
        "RAG_CHILD_CHUNK_MAX_CHARS": "_derived_rag_child_chunk_max_chars",
        "RAG_CHILD_CHUNK_OVERLAP": "_derived_rag_child_chunk_overlap",
        "KG_EXTRACTION_MAX_RETRIES": "_derived_kg_extraction_max_retries",
        "KG_SCHEMA_DISCOVERY_OUTPUT_DIR": "_derived_kg_schema_output_dir",
        "KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY": "_derived_kg_schema_concurrency",
        "KG_SCHEMA_DISCOVERY_CHUNK_CHARS": "_derived_kg_schema_chunk_chars",
        "KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP": "_derived_kg_schema_chunk_overlap",
        "KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS": ("_derived_kg_schema_timeout"),
        "KG_SCHEMA_DISCOVERY_OLLAMA_MODEL": "_derived_kg_schema_ollama_model",
        "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS": ("_derived_kg_schema_ollama_base_urls"),
        "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS": ("_derived_kg_schema_ollama_api_keys"),
        "KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL": ("_derived_kg_schema_openrouter_model"),
        "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS": (
            "_derived_kg_schema_openrouter_api_keys"
        ),
        "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL": (
            "_derived_kg_schema_openrouter_base_url"
        ),
        "KG_SCHEMA_DISCOVERY_NVIDIA_MODEL": "_derived_kg_schema_nvidia_model",
        "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS": ("_derived_kg_schema_nvidia_api_keys"),
        "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL": ("_derived_kg_schema_nvidia_base_url"),
        "KG_SCHEMA_DISCOVERY_GEMINI_MODEL": "_derived_kg_schema_gemini_model",
        "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS": ("_derived_kg_schema_gemini_api_keys"),
        "KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL": ("_derived_kg_schema_gemini_base_url"),
    }
    _DERIVED_INT_SETTINGS: ClassVar[tuple[str, ...]] = (
        "LLM_CHUNKING_MAX_INPUT_CHARS",
        "LLM_CHUNKING_UNIT_PREVIEW_CHARS",
        "RAG_CHILD_CHUNK_MAX_CHARS",
        "RAG_CHILD_CHUNK_OVERLAP",
        "KG_EXTRACTION_MAX_RETRIES",
        "KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY",
        "KG_SCHEMA_DISCOVERY_CHUNK_CHARS",
        "KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP",
    )
    _DERIVED_FLOAT_SETTINGS: ClassVar[tuple[str, ...]] = (
        "LLM_CHUNKING_TIMEOUT_SECONDS",
        "KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS",
    )

    # Core
    SQLITE_DB_PATH: str = "database/insurevn.db"

    # Langfuse tracing
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "http://localhost:3000"

    # Provider defaults registered in .env
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_LLM_MODEL: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_LLM_MODEL: str = ""
    QWEN_EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"

    # Database Agent
    SQL_AGENT_PROVIDER: str = ""
    SQL_AGENT_MODEL: str = ""
    SQL_AGENT_API_KEY: str = ""
    DATABASE_LLM_TEMPERATURE: float = 1.0

    # Search Agent
    TAVILY_API_KEY: str = ""
    SEARCH_AGENT_PROVIDER: str = ""
    SEARCH_AGENT_MODEL: str = ""
    SEARCH_AGENT_API_KEY: str = ""
    SEARCH_LLM_TEMPERATURE: float = 0.7
    SEARCH_MAX_RESULTS: int = 50

    # RAG/Qdrant
    RAG_QDRANT_URL: str = "http://localhost:6333"
    RAG_QDRANT_COLLECTION: str = "insurevn_policy_chunks"
    RAG_DENSE_VECTOR_NAME: str = "text_dense"
    RAG_SPARSE_VECTOR_NAME: str = "text_sparse"
    RAG_EMBEDDING_PROVIDER: str = "HUGGINGFACE"
    RAG_EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    RAG_DENSE_VECTOR_SIZE: int = 4096
    RAG_CHUNKING_STRATEGY: str = "hierarchical_header_recursive"
    RAG_RETRIEVAL_TOP_K: int = 10
    RAG_RERANK_CANDIDATE_TOP_K: int = 30
    RAG_RERANK_PROVIDER: str = "HUGGINGFACE"
    RAG_RERANK_MODEL: str = "namdp-ptit/ViRanker"
    RAG_RERANK_BATCH_SIZE: int = 8
    RAG_RERANK_MAX_LENGTH: int = 1024
    RAG_RERANK_DEVICE: str = "cuda"
    RAG_RERANK_TRUST_REMOTE_CODE: bool = False
    RAG_RERANK_BACKEND: str = "torch"
    RAG_RERANK_LOAD_IN_4BIT: bool = False
    RAG_RERANK_DEVICE_MAP: str = ""
    RAG_RERANK_ATTN_IMPLEMENTATION: str = ""
    RAG_RERANK_TORCH_DTYPE: str = ""
    RAG_REQUIRE_HYBRID_SEARCH: bool = True
    RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE: bool = False
    RAG_REQUIRE_HARD_FILTERS: bool = True
    RAG_EMBEDDING_BATCH_SIZE: int = 4
    RAG_EMBEDDING_MAX_LENGTH: int = 8192
    RAG_EMBEDDING_LOAD_IN_4BIT: bool = True
    RAG_EMBEDDING_DEVICE_MAP: str = "auto"
    RAG_EMBEDDING_ATTN_IMPLEMENTATION: str = ""
    RAG_EMBEDDING_QUERY_TASK_DESCRIPTION: str = (
        "Given a web search query, retrieve relevant passages that answer the query"
    )

    # Knowledge Graph
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    GRAPH_JSON_PATH: str = "data/processed/knowledge_graph/insurevn_graph.json"
    GRAPH_MAX_HOPS: int = 2

    KG_EXTRACTION_LLM_PROVIDER: str = ""
    KG_EXTRACTION_LLM_MODEL: str = ""
    KG_EXTRACTION_LLM_API_KEY: str = ""
    KG_EXTRACTION_LLM_BASE_URL: str = ""
    KG_EXTRACTION_LLM_TEMPERATURE: float = 0.0

    KG_CYPHER_QA_LLM_PROVIDER: str = ""
    KG_CYPHER_QA_LLM_MODEL: str = ""
    KG_CYPHER_QA_LLM_API_KEY: str = ""
    KG_CYPHER_QA_LLM_BASE_URL: str = ""
    KG_CYPHER_QA_LLM_TEMPERATURE: float = 0.0

    _raw_env: dict[str, str] = PrivateAttr(default_factory=dict)

    def __init__(self, **values: Any) -> None:
        """Load settings through pydantic-settings and retain raw env aliases."""
        env_file = values.get("_env_file", ENV_FILE)
        raw_env = _build_raw_env(env_file)
        raw_env.update(
            {
                name: _raw_env_value(value)
                for name, value in values.items()
                if not name.startswith("_") and value is not None
            }
        )
        super().__init__(**values)
        self._raw_env = raw_env
        self._validate_derived_numeric_settings()
        self._apply_derived_field_values()

    def __getattr__(self, name: str) -> Any:
        """Resolve compatibility settings that are not BaseSettings fields."""
        resolver_name = self._DERIVED_SETTING_RESOLVERS.get(name)
        if resolver_name is not None:
            return getattr(self, resolver_name)()
        return super().__getattr__(name)

    @field_validator(
        "RAG_RERANK_ATTN_IMPLEMENTATION",
        "RAG_RERANK_TORCH_DTYPE",
        "RAG_EMBEDDING_ATTN_IMPLEMENTATION",
    )
    @classmethod
    def _strip_optional_runtime_value(cls, value: str) -> str:
        """Strip optional backend flags so blank values stay predictable."""
        return value.strip()

    def _apply_derived_field_values(self) -> None:
        """Normalize declared fields that still support env aliases."""
        self.LANGFUSE_BASE_URL = self._get_env(
            "LANGFUSE_BASE_URL",
            self._get_env("LANGFUSE_HOST", "http://localhost:3000"),
        )
        self.RAG_EMBEDDING_MODEL = self._resolve_indirect(
            self.RAG_EMBEDDING_MODEL or self.QWEN_EMBEDDING_MODEL
        )
        self.RAG_RERANK_MODEL = self._resolve_indirect(
            self.RAG_RERANK_MODEL or "namdp-ptit/ViRanker"
        )

        self.KG_EXTRACTION_LLM_PROVIDER = self._normalize_provider(
            self.KG_EXTRACTION_LLM_PROVIDER or self.LLM_PROVIDER
        )
        self.KG_EXTRACTION_LLM_MODEL = self._resolve_indirect(
            self.KG_EXTRACTION_LLM_MODEL or self.LLM_MODEL
        )
        self.KG_EXTRACTION_LLM_API_KEY = self._resolve_indirect(
            self.KG_EXTRACTION_LLM_API_KEY
        ) or self._resolve_api_key(
            "KG_EXTRACTION_LLM",
            provider=self.KG_EXTRACTION_LLM_PROVIDER,
        )
        self.KG_EXTRACTION_LLM_BASE_URL = self._resolve_indirect(
            self.KG_EXTRACTION_LLM_BASE_URL
        ) or self._resolve_base_url(
            "KG_EXTRACTION_LLM",
            provider=self.KG_EXTRACTION_LLM_PROVIDER,
        )

        self.KG_CYPHER_QA_LLM_PROVIDER = self._normalize_provider(
            self.KG_CYPHER_QA_LLM_PROVIDER or self.LLM_PROVIDER
        )
        self.KG_CYPHER_QA_LLM_MODEL = self._resolve_indirect(
            self.KG_CYPHER_QA_LLM_MODEL or self.LLM_MODEL
        )
        self.KG_CYPHER_QA_LLM_API_KEY = self._resolve_indirect(
            self.KG_CYPHER_QA_LLM_API_KEY
        ) or self._resolve_api_key(
            "KG_CYPHER_QA_LLM",
            provider=self.KG_CYPHER_QA_LLM_PROVIDER,
        )
        self.KG_CYPHER_QA_LLM_BASE_URL = self._resolve_indirect(
            self.KG_CYPHER_QA_LLM_BASE_URL
        ) or self._resolve_base_url(
            "KG_CYPHER_QA_LLM",
            provider=self.KG_CYPHER_QA_LLM_PROVIDER,
        )

    def _validate_derived_numeric_settings(self) -> None:
        """Fail fast for numeric compatibility settings stored outside fields."""
        for setting_name in self._DERIVED_INT_SETTINGS:
            if not self._get_env(setting_name):
                continue
            self._env_int(setting_name, 0)
        for setting_name in self._DERIVED_FLOAT_SETTINGS:
            if not self._get_env(setting_name):
                continue
            self._env_float(setting_name, 0.0)

    def _derived_langfuse_host(self) -> str:
        return self.LANGFUSE_BASE_URL

    def _derived_google_api_keys(self) -> list[str]:
        gathered_keys = self._gather_numbered_keys(
            "GOOGLE_API_KEY"
        ) or self._gather_numbered_keys("GEMINI_API_KEY")
        return _merge_unique(gathered_keys, self._env_csv("GOOGLE_API_KEYS"))

    def _derived_openrouter_api_keys(self) -> list[str]:
        return _merge_unique(
            self._gather_numbered_keys("OPENROUTER_API_KEY"),
            self._env_csv("OPENROUTER_API_KEYS"),
        )

    def _derived_nvidia_api_keys(self) -> list[str]:
        gathered_keys = self._gather_numbered_keys(
            "NVIDIA_API_KEY"
        ) or self._gather_numbered_keys("NVIDIA_PAI_KEY")
        return _merge_unique(gathered_keys, self._env_csv("NVIDIA_API_KEYS"))

    def _derived_ollama_api_keys(self) -> list[str]:
        return _merge_unique(
            self._gather_numbered_keys("OLLAMA_API_KEY"),
            self._env_csv("OLLAMA_API_KEYS"),
        )

    def _derived_ollama_base_urls(self) -> list[str]:
        return self._env_csv("OLLAMA_BASE_URLS") or [self.OLLAMA_BASE_URL]

    def _derived_google_api_key(self) -> str:
        google_api_keys = self.GOOGLE_API_KEYS
        return google_api_keys[0] if google_api_keys else ""

    def _derived_gemini_api_key(self) -> str:
        return (
            self._resolve_indirect(self._get_env("GEMINI_API_KEY"))
            or self.GOOGLE_API_KEY
        )

    def _derived_openrouter_api_key(self) -> str:
        openrouter_api_keys = self.OPENROUTER_API_KEYS
        return openrouter_api_keys[0] if openrouter_api_keys else ""

    def _derived_nvidia_api_key(self) -> str:
        nvidia_api_keys = self.NVIDIA_API_KEYS
        return nvidia_api_keys[0] if nvidia_api_keys else ""

    def _derived_llm_provider(self) -> str:
        return self._normalize_provider(self._get_env("LLM_PROVIDER"))

    def _derived_llm_model(self) -> str:
        explicit_model = self._resolve_indirect(self._get_env("LLM_MODEL"))
        if explicit_model:
            return explicit_model

        provider_upper = self.LLM_PROVIDER.upper()
        if provider_upper == "OPENROUTER":
            return self.OPENROUTER_LLM_MODEL
        if provider_upper == "NVIDIA":
            return self.NVIDIA_LLM_MODEL
        if provider_upper in {"GOOGLE", "GOOGLE_GENAI", "GEMINI"}:
            return self._resolve_indirect(
                self._get_env(
                    "GOOGLE_LLM_MODEL",
                    self._get_env("GOOGLE_LLM_MODEL_1"),
                )
            )
        return self.OLLAMA_LLM_MODEL

    def _derived_llm_api_key(self) -> str:
        return self._resolve_indirect(self._get_env("LLM_API_KEY"))

    def _derived_llm_base_url(self) -> str:
        return self._resolve_indirect(
            self._get_env("LLM_BASE_URL", self.OLLAMA_BASE_URL)
        )

    def _derived_database_llm_provider(self) -> str:
        return self._normalize_provider(
            self.SQL_AGENT_PROVIDER
            or self._get_env("DATABASE_LLM_PROVIDER")
            or self.LLM_PROVIDER
        )

    def _derived_database_llm_model(self) -> str:
        return self._resolve_indirect(
            self.SQL_AGENT_MODEL
            or self._get_env("DATABASE_LLM_MODEL")
            or self.LLM_MODEL
        )

    def _derived_database_llm_api_key(self) -> str:
        direct_key = self._resolve_indirect(
            self.SQL_AGENT_API_KEY or self._get_env("DATABASE_LLM_API_KEY")
        )
        if direct_key:
            return direct_key
        return self._resolve_api_key(
            "DATABASE_LLM",
            provider=self.DATABASE_LLM_PROVIDER,
        )

    def _derived_database_llm_base_url(self) -> str:
        direct_url = self._resolve_indirect(
            self._get_env("SQL_AGENT_BASE_URL")
            or self._get_env("DATABASE_LLM_BASE_URL")
        )
        if direct_url:
            return direct_url
        return self._resolve_base_url(
            "DATABASE_LLM",
            provider=self.DATABASE_LLM_PROVIDER,
        )

    def _derived_search_tavily_api_key(self) -> str:
        return self._resolve_indirect(
            self._get_env("SEARCH_TAVILY_API_KEY", self.TAVILY_API_KEY)
        )

    def _derived_search_llm_provider(self) -> str:
        return self._normalize_provider(
            self.SEARCH_AGENT_PROVIDER
            or self._get_env("SEARCH_LLM_PROVIDER")
            or self.LLM_PROVIDER
        )

    def _derived_search_llm_model(self) -> str:
        return self._resolve_indirect(
            self.SEARCH_AGENT_MODEL
            or self._get_env("SEARCH_LLM_MODEL")
            or self.LLM_MODEL
        )

    def _derived_search_llm_api_key(self) -> str:
        direct_key = self._resolve_indirect(
            self.SEARCH_AGENT_API_KEY or self._get_env("SEARCH_LLM_API_KEY")
        )
        if direct_key:
            return direct_key
        return self._resolve_api_key(
            "SEARCH_LLM",
            provider=self.SEARCH_LLM_PROVIDER,
        )

    def _derived_search_llm_base_url(self) -> str:
        direct_url = self._resolve_indirect(
            self._get_env("SEARCH_AGENT_BASE_URL")
            or self._get_env("SEARCH_LLM_BASE_URL")
        )
        if direct_url:
            return direct_url
        return self._resolve_base_url(
            "SEARCH_LLM",
            provider=self.SEARCH_LLM_PROVIDER,
        )

    def _derived_llm_chunking_provider(self) -> str:
        return self._normalize_provider(
            self._get_env("LLM_CHUNKING_PROVIDER", self.LLM_PROVIDER)
        )

    def _derived_llm_chunking_model(self) -> str:
        return self._resolve_indirect(
            self._get_env("LLM_CHUNKING_MODEL", self.LLM_MODEL)
        )

    def _derived_llm_chunking_api_key(self) -> str:
        return self._resolve_api_key(
            "LLM_CHUNKING",
            provider=self.LLM_CHUNKING_PROVIDER,
        )

    def _derived_llm_chunking_base_url(self) -> str:
        return self._resolve_base_url(
            "LLM_CHUNKING",
            provider=self.LLM_CHUNKING_PROVIDER,
        )

    def _derived_llm_chunking_max_input_chars(self) -> int:
        return self._env_int("LLM_CHUNKING_MAX_INPUT_CHARS", 50000)

    def _derived_llm_chunking_timeout_seconds(self) -> float:
        return self._env_float("LLM_CHUNKING_TIMEOUT_SECONDS", 120.0)

    def _derived_llm_chunking_cache_path(self) -> str:
        return self._get_env(
            "LLM_CHUNKING_CACHE_PATH",
            "reports/chunking_compare_llm/llm_chunk_cache.json",
        )

    def _derived_llm_chunking_preview_chars(self) -> int:
        return self._env_int("LLM_CHUNKING_UNIT_PREVIEW_CHARS", 220)

    def _derived_rag_qdrant_api_key(self) -> str:
        return self._resolve_indirect(self._get_env("RAG_QDRANT_API_KEY"))

    def _derived_rag_embedding_api_key(self) -> str:
        return self._resolve_indirect(self._get_env("RAG_EMBEDDING_API_KEY"))

    def _derived_rag_sparse_model(self) -> str:
        return self._get_env("RAG_SPARSE_MODEL", "Qdrant/bm25")

    def _derived_rag_child_chunk_max_chars(self) -> int:
        return self._env_int("RAG_CHILD_CHUNK_MAX_CHARS", 1200)

    def _derived_rag_child_chunk_overlap(self) -> int:
        return self._env_int("RAG_CHILD_CHUNK_OVERLAP", 150)

    def _derived_kg_extraction_max_retries(self) -> int:
        return self._env_int("KG_EXTRACTION_MAX_RETRIES", 2)

    def _derived_kg_schema_output_dir(self) -> str:
        return self._get_env(
            "KG_SCHEMA_DISCOVERY_OUTPUT_DIR",
            "data/processed/knowledge_graph/discovery",
        )

    def _derived_kg_schema_concurrency(self) -> int:
        return self._env_int("KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY", 4)

    def _derived_kg_schema_chunk_chars(self) -> int:
        return self._env_int("KG_SCHEMA_DISCOVERY_CHUNK_CHARS", 12000)

    def _derived_kg_schema_chunk_overlap(self) -> int:
        return self._env_int("KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP", 500)

    def _derived_kg_schema_timeout(self) -> float:
        return self._env_float("KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS", 60.0)

    def _derived_kg_schema_ollama_model(self) -> str:
        return self._get_env("KG_SCHEMA_DISCOVERY_OLLAMA_MODEL", self.OLLAMA_LLM_MODEL)

    def _derived_kg_schema_ollama_base_urls(self) -> list[str]:
        return self._env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
            default=self.OLLAMA_BASE_URLS,
        )

    def _derived_kg_schema_ollama_api_keys(self) -> list[str]:
        return self._env_csv("KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS", default=[])

    def _derived_kg_schema_openrouter_model(self) -> str:
        return self._get_env(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL",
            self.OPENROUTER_LLM_MODEL,
        )

    def _derived_kg_schema_openrouter_api_keys(self) -> list[str]:
        return self._env_csv("KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS", default=[])

    def _derived_kg_schema_openrouter_base_url(self) -> str:
        return self._get_env(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL",
            self.OPENROUTER_BASE_URL,
        )

    def _derived_kg_schema_nvidia_model(self) -> str:
        return self._get_env("KG_SCHEMA_DISCOVERY_NVIDIA_MODEL", self.NVIDIA_LLM_MODEL)

    def _derived_kg_schema_nvidia_api_keys(self) -> list[str]:
        return self._env_csv("KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS", default=[])

    def _derived_kg_schema_nvidia_base_url(self) -> str:
        return self._get_env(
            "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL",
            self.NVIDIA_BASE_URL,
        )

    def _derived_kg_schema_gemini_model(self) -> str:
        return self._get_env(
            "KG_SCHEMA_DISCOVERY_GEMINI_MODEL",
            self._get_env("GOOGLE_LLM_MODEL_1"),
        )

    def _derived_kg_schema_gemini_api_keys(self) -> list[str]:
        return self._env_csv("KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS", default=[])

    def _derived_kg_schema_gemini_base_url(self) -> str:
        return self._get_env("KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL")

    def _get_env(self, name: str, default: str = "") -> str:
        """Read from the merged env snapshot used by project-specific resolvers."""
        return self._raw_env.get(name, default)

    def _env_csv(self, name: str, *, default: list[str] | None = None) -> list[str]:
        """Read a comma-separated list from the env snapshot."""
        value = self._get_env(name)
        if not value:
            return list(default or [])
        return [item.strip() for item in value.split(",") if item.strip()]

    def _env_int(self, name: str, default: int) -> int:
        """Read an integer from the env snapshot."""
        value = self._resolve_indirect(self._get_env(name))
        if not value:
            return default
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid integer setting {name}: {value!r}") from exc

    def _env_float(self, name: str, default: float) -> float:
        """Read a float from the env snapshot."""
        value = self._resolve_indirect(self._get_env(name))
        if not value:
            return default
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"Invalid float setting {name}: {value!r}") from exc

    def _resolve_indirect(self, value: str | None) -> str:
        """Resolve a value that might be an environment variable reference."""
        if value is None:
            return ""
        if value in self._raw_env:
            return self._raw_env[value]
        return value

    def _normalize_provider(self, value: str | None) -> str:
        """Strip and preserve provider name as provided (e.g., GOOGLE, OLLAMA)."""
        if not value:
            return ""
        return value.strip()

    def _gather_numbered_keys(self, prefix: str) -> list[str]:
        """Gather API keys from prefix, prefix_1, prefix_2, etc."""
        keys: list[str] = []
        base_val = self._resolve_indirect(self._get_env(prefix))
        if base_val:
            keys.append(base_val)

        numbered_values: list[tuple[int, str]] = []
        prefix_with_separator = f"{prefix}_"
        for environment_name, environment_value in self._raw_env.items():
            if not environment_name.startswith(prefix_with_separator):
                continue
            suffix = environment_name.removeprefix(prefix_with_separator)
            if not suffix.isdigit() or not environment_value:
                continue
            numbered_value = self._resolve_indirect(environment_value)
            if numbered_value:
                numbered_values.append((int(suffix), numbered_value))
        for _, numbered_value in sorted(numbered_values):
            if numbered_value not in keys:
                keys.append(numbered_value)
        return keys

    def _resolve_api_key(
        self,
        component_prefix: str,
        *,
        provider: str | None = None,
    ) -> str:
        """Resolve API key for a component with fallback to provider defaults."""
        key = self._resolve_indirect(self._get_env(f"{component_prefix}_API_KEY"))
        if key:
            return key

        global_key = self.LLM_API_KEY
        if global_key:
            return global_key

        resolved_provider = provider or self._get_env(
            f"{component_prefix}_PROVIDER",
            self.LLM_PROVIDER,
        )
        provider_upper = resolved_provider.upper()
        if provider_upper in {"GOOGLE_GENAI", "GOOGLE", "GEMINI"}:
            return self.GOOGLE_API_KEY
        if provider_upper == "OPENROUTER":
            return self.OPENROUTER_API_KEY
        if provider_upper == "NVIDIA":
            return self.NVIDIA_API_KEY
        if provider_upper == "OLLAMA":
            ollama_api_keys = self.OLLAMA_API_KEYS
            return ollama_api_keys[0] if ollama_api_keys else ""
        return ""

    def _resolve_base_url(
        self,
        component_prefix: str,
        *,
        provider: str | None = None,
    ) -> str:
        """Resolve base URL for a component with fallback to provider defaults."""
        url = self._resolve_indirect(self._get_env(f"{component_prefix}_BASE_URL"))
        if url:
            return url

        global_url = self.LLM_BASE_URL
        if self._get_env("LLM_BASE_URL") and global_url:
            return global_url

        resolved_provider = provider or self._get_env(
            f"{component_prefix}_PROVIDER",
            self.LLM_PROVIDER,
        )
        provider_upper = resolved_provider.upper()
        if provider_upper == "OLLAMA":
            ollama_base_urls = self.OLLAMA_BASE_URLS
            return ollama_base_urls[0] if ollama_base_urls else ""
        if provider_upper == "OPENROUTER":
            return self.OPENROUTER_BASE_URL
        if provider_upper == "NVIDIA":
            return self.NVIDIA_BASE_URL
        return global_url


settings = Settings()
