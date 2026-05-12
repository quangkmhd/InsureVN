import os
from pathlib import Path
from typing import Annotated, Any

from dotenv import dotenv_values
from pydantic import Field, PrivateAttr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
CsvList = Annotated[list[str], NoDecode]


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

    PROJECT_NAME: str = "InsureVN"

    # Database
    SQLITE_DB_PATH: str = "database/insurevn.db"

    # Langfuse Tracing
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "http://localhost:3000"
    LANGFUSE_HOST: str = "http://localhost:3000"

    # Standard Provider Globals
    GOOGLE_API_KEYS: CsvList = Field(default_factory=list)
    OPENROUTER_API_KEYS: CsvList = Field(default_factory=list)
    NVIDIA_API_KEYS: CsvList = Field(default_factory=list)
    OLLAMA_BASE_URLS: CsvList = Field(default_factory=list)
    QWEN_EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"

    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""

    # Global LLM defaults
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""

    # Database Agent
    DATABASE_LLM_PROVIDER: str = ""
    DATABASE_LLM_MODEL: str = ""
    DATABASE_LLM_API_KEY: str = ""
    DATABASE_LLM_BASE_URL: str = ""
    DATABASE_LLM_TEMPERATURE: float = 1.0
    DATABASE_LLM_TOP_P: float = 0.95
    DATABASE_LLM_TOP_K: int = 64

    # Search Agent
    SEARCH_TAVILY_API_KEY: str = ""
    SEARCH_MAX_RESULTS: int = 50
    SEARCH_LLM_PROVIDER: str = ""
    SEARCH_LLM_MODEL: str = ""
    SEARCH_LLM_API_KEY: str = ""
    SEARCH_LLM_BASE_URL: str = ""
    SEARCH_LLM_TEMPERATURE: float = 0.7
    SEARCH_LLM_TOP_P: float = 0.95
    SEARCH_LLM_TOP_K: int = 64

    # LLM Chunking
    LLM_CHUNKING_PROVIDER: str = ""
    LLM_CHUNKING_MODEL: str = ""
    LLM_CHUNKING_API_KEY: str = ""
    LLM_CHUNKING_BASE_URL: str = ""
    LLM_CHUNKING_MAX_INPUT_CHARS: int = 50000
    LLM_CHUNKING_TIMEOUT_SECONDS: float = 120
    LLM_CHUNKING_CACHE_PATH: str = "reports/chunking_compare_llm/llm_chunk_cache.json"
    LLM_CHUNKING_UNIT_PREVIEW_CHARS: int = 220

    # RAG/Qdrant
    RAG_QDRANT_URL: str = "http://localhost:6333"
    RAG_QDRANT_API_KEY: str = ""
    RAG_QDRANT_COLLECTION: str = "insurevn_policy_chunks"
    RAG_DENSE_VECTOR_NAME: str = "text_dense"
    RAG_SPARSE_VECTOR_NAME: str = "text_sparse"
    RAG_EMBEDDING_PROVIDER: str = "HUGGINGFACE"
    RAG_EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    RAG_EMBEDDING_API_KEY: str = ""
    RAG_DENSE_VECTOR_SIZE: int = 4096
    RAG_SPARSE_MODEL: str = "Qdrant/bm25"
    RAG_VIETNAMESE_SEGMENTER: str = "underthesea"
    RAG_CHILD_CHUNK_MAX_CHARS: int = 1200
    RAG_CHILD_CHUNK_OVERLAP: int = 150
    RAG_CHUNKING_STRATEGY: str = "hierarchical_header_recursive"
    RAG_PARENT_SECTION_MAX_CHARS: int = 6000
    RAG_RETRIEVAL_TOP_K: int = 10
    RAG_RERANK_CANDIDATE_TOP_K: int = 30
    RAG_RETRIEVAL_TIMEOUT_SECONDS: float = 30.0
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
    RAG_EMBEDDING_TASK_TYPE_DOCUMENT: str = "RETRIEVAL_DOCUMENT"
    RAG_EMBEDDING_TASK_TYPE_QUERY: str = "RETRIEVAL_QUERY"
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
    GRAPH_RELOAD_ON_STARTUP: bool = True
    GRAPH_EAGER_K: int = 5
    GRAPH_EAGER_START_K: int = 1
    GRAPH_EAGER_MAX_DEPTH: int = 2
    GRAPH_MIN_CONFIDENCE: float = 0.75

    KG_EXTRACTION_LLM_PROVIDER: str = ""
    KG_EXTRACTION_LLM_MODEL: str = ""
    KG_EXTRACTION_LLM_API_KEY: str = ""
    KG_EXTRACTION_LLM_BASE_URL: str = ""
    KG_EXTRACTION_LLM_TEMPERATURE: float = 0.0
    KG_EXTRACTION_LLM_TOP_P: float = 0.95
    KG_EXTRACTION_LLM_TOP_K: int = 64
    KG_EXTRACTION_MAX_RETRIES: int = 2

    KG_CYPHER_QA_LLM_PROVIDER: str = ""
    KG_CYPHER_QA_LLM_MODEL: str = ""
    KG_CYPHER_QA_LLM_API_KEY: str = ""
    KG_CYPHER_QA_LLM_BASE_URL: str = ""
    KG_CYPHER_QA_LLM_TEMPERATURE: float = 0.0
    KG_CYPHER_QA_LLM_TOP_P: float = 0.95
    KG_CYPHER_QA_LLM_TOP_K: int = 64

    # Knowledge Graph Schema Discovery
    KG_SCHEMA_DISCOVERY_OUTPUT_DIR: str = "data/processed/knowledge_graph/discovery"
    KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY: int = 4
    KG_SCHEMA_DISCOVERY_CHUNK_CHARS: int = 12000
    KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP: int = 500
    KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS: float = 60.0
    KG_SCHEMA_DISCOVERY_OLLAMA_MODEL: str = "gemma4:31b-cloud"
    KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS: CsvList = Field(default_factory=list)
    KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS: CsvList = Field(default_factory=list)
    KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS: CsvList = Field(default_factory=list)
    KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    KG_SCHEMA_DISCOVERY_NVIDIA_MODEL: str = "meta/llama-3.1-70b-instruct"
    KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS: CsvList = Field(default_factory=list)
    KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    KG_SCHEMA_DISCOVERY_GEMINI_MODEL: str = "gemini-2.0-flash"
    KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS: CsvList = Field(default_factory=list)
    KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL: str = ""

    _raw_env: dict[str, str] = PrivateAttr(default_factory=dict)

    def __init__(self, **values: Any) -> None:
        """Load settings through pydantic-settings, then apply project fallbacks."""
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
        self._apply_derived_settings()

    @field_validator(
        "GOOGLE_API_KEYS",
        "OPENROUTER_API_KEYS",
        "NVIDIA_API_KEYS",
        "OLLAMA_BASE_URLS",
        "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
        "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS",
        "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS",
        "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS",
        "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS",
        mode="before",
    )
    @classmethod
    def _parse_csv_list(cls, value: Any) -> list[str]:
        """Parse legacy comma-separated environment values into lists."""
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value)

    def _get_env(self, name: str, default: str = "") -> str:
        """Read from the merged env snapshot used by project-specific resolvers."""
        return self._raw_env.get(name, default)

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

    def _apply_derived_settings(self) -> None:
        """Apply backward-compatible fallbacks and indirect references."""
        direct_google_api_keys = list(self.GOOGLE_API_KEYS)
        direct_openrouter_api_keys = list(self.OPENROUTER_API_KEYS)
        direct_nvidia_api_keys = list(self.NVIDIA_API_KEYS)

        self.LANGFUSE_BASE_URL = self._get_env(
            "LANGFUSE_BASE_URL",
            self._get_env("LANGFUSE_HOST", "http://localhost:3000"),
        )
        self.LANGFUSE_HOST = self.LANGFUSE_BASE_URL

        gathered_google_api_keys = self._gather_numbered_keys(
            "GOOGLE_API_KEY"
        ) or self._gather_numbered_keys("GEMINI_API_KEY")
        self.GOOGLE_API_KEYS = _merge_unique(
            gathered_google_api_keys,
            direct_google_api_keys,
        )
        self.OPENROUTER_API_KEYS = _merge_unique(
            self._gather_numbered_keys("OPENROUTER_API_KEY"),
            direct_openrouter_api_keys,
        )
        gathered_nvidia_api_keys = self._gather_numbered_keys(
            "NVIDIA_API_KEY"
        ) or self._gather_numbered_keys("NVIDIA_PAI_KEY")
        self.NVIDIA_API_KEYS = _merge_unique(
            gathered_nvidia_api_keys,
            direct_nvidia_api_keys,
        )
        self.OLLAMA_BASE_URLS = self._env_csv("OLLAMA_BASE_URLS") or [
            self._get_env("OLLAMA_BASE_URL", "http://localhost:11434")
        ]

        self.GOOGLE_API_KEY = self.GOOGLE_API_KEYS[0] if self.GOOGLE_API_KEYS else ""
        self.GEMINI_API_KEY = self.GOOGLE_API_KEY
        self.OPENROUTER_API_KEY = (
            self.OPENROUTER_API_KEYS[0] if self.OPENROUTER_API_KEYS else ""
        )
        self.NVIDIA_API_KEY = self.NVIDIA_API_KEYS[0] if self.NVIDIA_API_KEYS else ""

        self.LLM_BASE_URL = self._get_env("LLM_BASE_URL", self.OLLAMA_BASE_URLS[0])

        self.DATABASE_LLM_PROVIDER = self._normalize_provider(
            self._get_env(
                "SQL_AGENT_PROVIDER",
                self._get_env("DATABASE_LLM_PROVIDER", self.LLM_PROVIDER),
            )
        )
        self.DATABASE_LLM_MODEL = self._resolve_indirect(
            self._get_env(
                "SQL_AGENT_MODEL",
                self._get_env("DATABASE_LLM_MODEL", self.LLM_MODEL),
            )
        )
        self.DATABASE_LLM_API_KEY = self._get_env(
            "SQL_AGENT_API_KEY"
        ) or self._resolve_api_key(
            "DATABASE_LLM",
            provider=self.DATABASE_LLM_PROVIDER,
        )
        self.DATABASE_LLM_BASE_URL = self._get_env(
            "SQL_AGENT_BASE_URL"
        ) or self._resolve_base_url(
            "DATABASE_LLM",
            provider=self.DATABASE_LLM_PROVIDER,
        )

        self.SEARCH_TAVILY_API_KEY = self._get_env(
            "SEARCH_TAVILY_API_KEY",
            self._get_env("TAVILY_API_KEY", ""),
        )
        self.SEARCH_LLM_PROVIDER = self._normalize_provider(
            self._get_env(
                "SEARCH_AGENT_PROVIDER",
                self._get_env("SEARCH_LLM_PROVIDER", self.LLM_PROVIDER),
            )
        )
        self.SEARCH_LLM_MODEL = self._resolve_indirect(
            self._get_env(
                "SEARCH_AGENT_MODEL",
                self._get_env("SEARCH_LLM_MODEL", self.LLM_MODEL),
            )
        )
        self.SEARCH_LLM_API_KEY = self._get_env(
            "SEARCH_AGENT_API_KEY"
        ) or self._resolve_api_key(
            "SEARCH_LLM",
            provider=self.SEARCH_LLM_PROVIDER,
        )
        self.SEARCH_LLM_BASE_URL = self._get_env(
            "SEARCH_AGENT_BASE_URL"
        ) or self._resolve_base_url(
            "SEARCH_LLM",
            provider=self.SEARCH_LLM_PROVIDER,
        )

        self.LLM_CHUNKING_PROVIDER = self._normalize_provider(
            self._get_env("LLM_CHUNKING_PROVIDER", self.LLM_PROVIDER)
        )
        self.LLM_CHUNKING_MODEL = self._resolve_indirect(
            self._get_env("LLM_CHUNKING_MODEL", self.LLM_MODEL)
        )
        self.LLM_CHUNKING_API_KEY = self._resolve_api_key(
            "LLM_CHUNKING",
            provider=self.LLM_CHUNKING_PROVIDER,
        )
        self.LLM_CHUNKING_BASE_URL = self._resolve_base_url(
            "LLM_CHUNKING",
            provider=self.LLM_CHUNKING_PROVIDER,
        )

        self.RAG_EMBEDDING_MODEL = self._resolve_indirect(
            self._get_env("RAG_EMBEDDING_MODEL", self.QWEN_EMBEDDING_MODEL)
        )
        self.RAG_EMBEDDING_API_KEY = self._resolve_indirect(
            self._get_env("RAG_EMBEDDING_API_KEY")
        )
        self.RAG_RERANK_MODEL = self._resolve_indirect(
            self._get_env("RAG_RERANK_MODEL", "namdp-ptit/ViRanker")
        )
        self.RAG_RERANK_ATTN_IMPLEMENTATION = (
            self.RAG_RERANK_ATTN_IMPLEMENTATION.strip()
        )
        self.RAG_RERANK_TORCH_DTYPE = self.RAG_RERANK_TORCH_DTYPE.strip()
        self.RAG_EMBEDDING_ATTN_IMPLEMENTATION = (
            self.RAG_EMBEDDING_ATTN_IMPLEMENTATION.strip()
        )

        self.KG_EXTRACTION_LLM_PROVIDER = self._normalize_provider(
            self._get_env("KG_EXTRACTION_LLM_PROVIDER", self.LLM_PROVIDER)
        )
        self.KG_EXTRACTION_LLM_MODEL = self._resolve_indirect(
            self._get_env("KG_EXTRACTION_LLM_MODEL", self.LLM_MODEL)
        )
        self.KG_EXTRACTION_LLM_API_KEY = self._resolve_api_key(
            "KG_EXTRACTION_LLM",
            provider=self.KG_EXTRACTION_LLM_PROVIDER,
        )
        self.KG_EXTRACTION_LLM_BASE_URL = self._resolve_indirect(
            self._resolve_base_url(
                "KG_EXTRACTION_LLM",
                provider=self.KG_EXTRACTION_LLM_PROVIDER,
            )
        )

        self.KG_CYPHER_QA_LLM_PROVIDER = self._normalize_provider(
            self._get_env("KG_CYPHER_QA_LLM_PROVIDER", self.LLM_PROVIDER)
        )
        self.KG_CYPHER_QA_LLM_MODEL = self._resolve_indirect(
            self._get_env("KG_CYPHER_QA_LLM_MODEL", self.LLM_MODEL)
        )
        self.KG_CYPHER_QA_LLM_API_KEY = self._resolve_api_key(
            "KG_CYPHER_QA_LLM",
            provider=self.KG_CYPHER_QA_LLM_PROVIDER,
        )
        self.KG_CYPHER_QA_LLM_BASE_URL = self._resolve_indirect(
            self._resolve_base_url(
                "KG_CYPHER_QA_LLM",
                provider=self.KG_CYPHER_QA_LLM_PROVIDER,
            )
        )

        self.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS = self._env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
            default=self.OLLAMA_BASE_URLS,
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS = self._env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS",
            default=[],
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS = self._env_csv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS",
            default=[],
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS = self._env_csv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS",
            default=[],
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS = self._env_csv(
            "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS",
            default=[],
        )

    def _env_csv(self, name: str, *, default: list[str] | None = None) -> list[str]:
        """Read a comma-separated list from the env snapshot."""
        value = self._get_env(name)
        if not value:
            return list(default or [])
        return [item.strip() for item in value.split(",") if item.strip()]

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
        key = self._get_env(f"{component_prefix}_API_KEY")
        if key:
            return key

        global_key = self._get_env("LLM_API_KEY")
        if global_key:
            return global_key

        resolved_provider = provider or self._get_env(
            f"{component_prefix}_PROVIDER",
            self.LLM_PROVIDER,
        )
        provider_upper = resolved_provider.upper()
        if provider_upper in {"GOOGLE_GENAI", "GOOGLE"}:
            return self.GOOGLE_API_KEY
        if provider_upper == "OPENROUTER":
            return self.OPENROUTER_API_KEY
        if provider_upper == "NVIDIA":
            return self.NVIDIA_API_KEY
        return self.LLM_API_KEY

    def _resolve_base_url(
        self,
        component_prefix: str,
        *,
        provider: str | None = None,
    ) -> str:
        """Resolve base URL for a component with fallback to provider defaults."""
        url = self._get_env(f"{component_prefix}_BASE_URL")
        if url:
            return url

        global_url = self._get_env("LLM_BASE_URL")
        if global_url:
            return global_url

        resolved_provider = provider or self._get_env(
            f"{component_prefix}_PROVIDER",
            self.LLM_PROVIDER,
        )
        provider_upper = resolved_provider.upper()
        if provider_upper == "OLLAMA":
            return (
                self.OLLAMA_BASE_URLS[0]
                if self.OLLAMA_BASE_URLS
                else "http://localhost:11434"
            )
        if provider_upper == "OPENROUTER":
            return "https://openrouter.ai/api/v1"
        if provider_upper == "NVIDIA":
            return "https://integrate.api.nvidia.com/v1"
        return self.LLM_BASE_URL


settings = Settings()
