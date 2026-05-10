import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, *, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Typed application settings loaded from environment variables."""

    def _resolve_indirect(self, value: str | None) -> str:
        """Resolve a value that might be an environment variable reference."""
        if value is None:
            return ""
        if value in os.environ:
            return os.environ[value]
        return value

    def _normalize_provider(self, value: str | None) -> str:
        """Strip and preserve provider name as provided (e.g., GOOGLE, OLLAMA)."""
        if not value:
            return ""
        return value.strip()

    def __init__(self) -> None:
        """Load settings with explicit type casts."""
        self.PROJECT_NAME: str = "InsureVN"

        # Database
        self.SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "database/insurevn.db")

        # Langfuse Tracing
        self.LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.LANGFUSE_BASE_URL: str = os.getenv(
            "LANGFUSE_BASE_URL",
            os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
        )
        self.LANGFUSE_HOST: str = self.LANGFUSE_BASE_URL

        # --- Standard Provider Globals ---
        self.GOOGLE_API_KEYS: list[str] = self._gather_numbered_keys(
            "GOOGLE_API_KEY"
        ) or self._gather_numbered_keys("GEMINI_API_KEY")
        self.OPENROUTER_API_KEYS: list[str] = self._gather_numbered_keys(
            "OPENROUTER_API_KEY"
        )
        self.NVIDIA_API_KEYS: list[str] = self._gather_numbered_keys(
            "NVIDIA_API_KEY"
        ) or self._gather_numbered_keys("NVIDIA_PAI_KEY")
        self.OLLAMA_BASE_URLS: list[str] = _env_csv("OLLAMA_BASE_URLS") or [
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ]
        self.QWEN_EMBEDDING_MODEL: str = os.getenv(
            "QWEN_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B"
        )

        # Legacy single keys for backward compatibility
        self.GOOGLE_API_KEY: str = (
            self.GOOGLE_API_KEYS[0] if self.GOOGLE_API_KEYS else ""
        )
        self.GEMINI_API_KEY: str = self.GOOGLE_API_KEY
        self.OPENROUTER_API_KEY: str = (
            self.OPENROUTER_API_KEYS[0] if self.OPENROUTER_API_KEYS else ""
        )
        self.NVIDIA_API_KEY: str = (
            self.NVIDIA_API_KEYS[0] if self.NVIDIA_API_KEYS else ""
        )

        # Global LLM defaults (explicit configuration required)
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "")
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", self.OLLAMA_BASE_URLS[0])

        # --- Component Specific LLM Settings (with fallback) ---

        # Database Agent (SQL Agent)
        self.DATABASE_LLM_PROVIDER: str = self._normalize_provider(
            os.getenv(
                "SQL_AGENT_PROVIDER",
                os.getenv("DATABASE_LLM_PROVIDER", self.LLM_PROVIDER),
            )
        )
        self.DATABASE_LLM_MODEL: str = self._resolve_indirect(
            os.getenv(
                "SQL_AGENT_MODEL",
                os.getenv("DATABASE_LLM_MODEL", self.LLM_MODEL),
            )
        )
        self.DATABASE_LLM_API_KEY: str = os.getenv(
            "SQL_AGENT_API_KEY"
        ) or self._resolve_api_key("DATABASE_LLM")
        self.DATABASE_LLM_BASE_URL: str = os.getenv(
            "SQL_AGENT_BASE_URL"
        ) or self._resolve_base_url("DATABASE_LLM")
        self.DATABASE_LLM_TEMPERATURE: float = float(
            os.getenv("DATABASE_LLM_TEMPERATURE", "1.0")
        )
        self.DATABASE_LLM_TOP_P: float = float(os.getenv("DATABASE_LLM_TOP_P", "0.95"))
        self.DATABASE_LLM_TOP_K: int = int(os.getenv("DATABASE_LLM_TOP_K", "64"))

        # Search Agent
        self.SEARCH_TAVILY_API_KEY: str = os.getenv(
            "SEARCH_TAVILY_API_KEY", os.getenv("TAVILY_API_KEY", "")
        )
        self.SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "50"))
        self.SEARCH_LLM_PROVIDER: str = self._normalize_provider(
            os.getenv(
                "SEARCH_AGENT_PROVIDER",
                os.getenv("SEARCH_LLM_PROVIDER", self.LLM_PROVIDER),
            )
        )
        self.SEARCH_LLM_MODEL: str = self._resolve_indirect(
            os.getenv(
                "SEARCH_AGENT_MODEL",
                os.getenv("SEARCH_LLM_MODEL", self.LLM_MODEL),
            )
        )
        self.SEARCH_LLM_API_KEY: str = os.getenv(
            "SEARCH_AGENT_API_KEY"
        ) or self._resolve_api_key("SEARCH_LLM")
        self.SEARCH_LLM_BASE_URL: str = os.getenv(
            "SEARCH_AGENT_BASE_URL"
        ) or self._resolve_base_url("SEARCH_LLM")
        self.SEARCH_LLM_TEMPERATURE: float = float(
            os.getenv("SEARCH_LLM_TEMPERATURE", "0.7")
        )
        self.SEARCH_LLM_TOP_P: float = float(os.getenv("SEARCH_LLM_TOP_P", "0.95"))
        self.SEARCH_LLM_TOP_K: int = int(os.getenv("SEARCH_LLM_TOP_K", "64"))

        # LLM Chunking
        self.LLM_CHUNKING_PROVIDER: str = self._normalize_provider(
            os.getenv("LLM_CHUNKING_PROVIDER", self.LLM_PROVIDER)
        )
        self.LLM_CHUNKING_MODEL: str = self._resolve_indirect(
            os.getenv("LLM_CHUNKING_MODEL", self.LLM_MODEL)
        )
        self.LLM_CHUNKING_API_KEY: str = self._resolve_api_key("LLM_CHUNKING")
        self.LLM_CHUNKING_BASE_URL: str = self._resolve_base_url("LLM_CHUNKING")
        self.LLM_CHUNKING_MAX_INPUT_CHARS: int = int(
            os.getenv("LLM_CHUNKING_MAX_INPUT_CHARS", "50000")
        )
        self.LLM_CHUNKING_TIMEOUT_SECONDS: float = float(
            os.getenv("LLM_CHUNKING_TIMEOUT_SECONDS", "120")
        )
        self.LLM_CHUNKING_CACHE_PATH: str = os.getenv(
            "LLM_CHUNKING_CACHE_PATH",
            "reports/chunking_compare_llm/llm_chunk_cache.json",
        )
        self.LLM_CHUNKING_UNIT_PREVIEW_CHARS: int = int(
            os.getenv("LLM_CHUNKING_UNIT_PREVIEW_CHARS", "220")
        )

        # RAG/Qdrant
        self.RAG_QDRANT_URL: str = os.getenv("RAG_QDRANT_URL", "http://localhost:6333")
        self.RAG_QDRANT_API_KEY: str = os.getenv("RAG_QDRANT_API_KEY", "")
        self.RAG_QDRANT_COLLECTION: str = os.getenv(
            "RAG_QDRANT_COLLECTION", "insurevn_policy_chunks"
        )
        self.RAG_DENSE_VECTOR_NAME: str = os.getenv(
            "RAG_DENSE_VECTOR_NAME", "text_dense"
        )
        self.RAG_SPARSE_VECTOR_NAME: str = os.getenv(
            "RAG_SPARSE_VECTOR_NAME", "text_sparse"
        )
        self.RAG_EMBEDDING_PROVIDER: str = self._normalize_provider(
            os.getenv("RAG_EMBEDDING_PROVIDER", "HUGGINGFACE")
        )
        self.RAG_EMBEDDING_MODEL: str = self._resolve_indirect(
            os.getenv("RAG_EMBEDDING_MODEL", self.QWEN_EMBEDDING_MODEL)
        )
        self.RAG_EMBEDDING_API_KEY: str = self._resolve_indirect(
            os.getenv("RAG_EMBEDDING_API_KEY")
        )
        self.RAG_DENSE_VECTOR_SIZE: int = int(
            os.getenv("RAG_DENSE_VECTOR_SIZE", "4096")
        )
        self.RAG_SPARSE_MODEL: str = os.getenv("RAG_SPARSE_MODEL", "Qdrant/bm25")
        self.RAG_VIETNAMESE_SEGMENTER: str = os.getenv(
            "RAG_VIETNAMESE_SEGMENTER", "underthesea"
        )
        self.RAG_CHILD_CHUNK_MAX_CHARS: int = int(
            os.getenv("RAG_CHILD_CHUNK_MAX_CHARS", "1200")
        )
        self.RAG_CHILD_CHUNK_OVERLAP: int = int(
            os.getenv("RAG_CHILD_CHUNK_OVERLAP", "150")
        )
        self.RAG_CHUNKING_STRATEGY: str = os.getenv(
            "RAG_CHUNKING_STRATEGY", "hierarchical_header_recursive"
        )
        self.RAG_PARENT_SECTION_MAX_CHARS: int = int(
            os.getenv("RAG_PARENT_SECTION_MAX_CHARS", "6000")
        )
        self.RAG_RETRIEVAL_TOP_K: int = int(os.getenv("RAG_RETRIEVAL_TOP_K", "5"))
        self.RAG_RETRIEVAL_TIMEOUT_SECONDS: float = float(
            os.getenv("RAG_RETRIEVAL_TIMEOUT_SECONDS", "30.0")
        )
        self.JINA_API_KEY: str = os.getenv("JINA_API_KEY", "")
        self.RAG_RERANK_PROVIDER: str = os.getenv("RAG_RERANK_PROVIDER", "jina")
        self.RAG_RERANK_MODEL: str = os.getenv("RAG_RERANK_MODEL", "jina-reranker-v3")
        self.RAG_RERANK_BASE_URL: str = os.getenv(
            "RAG_RERANK_BASE_URL", "https://api.jina.ai/v1/rerank"
        )
        self.RAG_RERANK_TIMEOUT_SECONDS: float = float(
            os.getenv("RAG_RERANK_TIMEOUT_SECONDS", "30.0")
        )
        self.RAG_REQUIRE_HYBRID_SEARCH: bool = _env_bool(
            "RAG_REQUIRE_HYBRID_SEARCH", default=True
        )
        self.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE: bool = _env_bool(
            "RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", default=False
        )
        self.RAG_EMBEDDING_BATCH_SIZE: int = int(
            os.getenv("RAG_EMBEDDING_BATCH_SIZE", "4")
        )
        self.RAG_EMBEDDING_TASK_TYPE_DOCUMENT: str = os.getenv(
            "RAG_EMBEDDING_TASK_TYPE_DOCUMENT", "RETRIEVAL_DOCUMENT"
        )
        self.RAG_EMBEDDING_TASK_TYPE_QUERY: str = os.getenv(
            "RAG_EMBEDDING_TASK_TYPE_QUERY", "RETRIEVAL_QUERY"
        )
        self.RAG_EMBEDDING_MAX_LENGTH: int = int(
            os.getenv("RAG_EMBEDDING_MAX_LENGTH", "8192")
        )
        self.RAG_EMBEDDING_LOAD_IN_4BIT: bool = _env_bool(
            "RAG_EMBEDDING_LOAD_IN_4BIT", default=True
        )
        self.RAG_EMBEDDING_DEVICE_MAP: str = os.getenv(
            "RAG_EMBEDDING_DEVICE_MAP", "auto"
        )
        self.RAG_EMBEDDING_ATTN_IMPLEMENTATION: str = os.getenv(
            "RAG_EMBEDDING_ATTN_IMPLEMENTATION", ""
        ).strip()
        self.RAG_EMBEDDING_QUERY_TASK_DESCRIPTION: str = os.getenv(
            "RAG_EMBEDDING_QUERY_TASK_DESCRIPTION",
            (
                "Given a web search query, retrieve relevant passages "
                "that answer the query"
            ),
        )

        # Knowledge Graph
        self.NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
        self.NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
        self.NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
        self.GRAPH_JSON_PATH: str = os.getenv(
            "GRAPH_JSON_PATH", "data/processed/knowledge_graph/insurevn_graph.json"
        )
        self.GRAPH_MAX_HOPS: int = int(os.getenv("GRAPH_MAX_HOPS", "2"))
        self.GRAPH_RELOAD_ON_STARTUP: bool = _env_bool(
            "GRAPH_RELOAD_ON_STARTUP", default=True
        )
        self.GRAPH_EAGER_K: int = int(os.getenv("GRAPH_EAGER_K", "5"))
        self.GRAPH_EAGER_START_K: int = int(os.getenv("GRAPH_EAGER_START_K", "1"))
        self.GRAPH_EAGER_MAX_DEPTH: int = int(os.getenv("GRAPH_EAGER_MAX_DEPTH", "2"))
        self.GRAPH_MIN_CONFIDENCE: float = float(
            os.getenv("GRAPH_MIN_CONFIDENCE", "0.75")
        )

        self.KG_EXTRACTION_LLM_PROVIDER: str = self._normalize_provider(
            os.getenv("KG_EXTRACTION_LLM_PROVIDER", self.LLM_PROVIDER)
        )
        self.KG_EXTRACTION_LLM_MODEL: str = self._resolve_indirect(
            os.getenv("KG_EXTRACTION_LLM_MODEL", self.LLM_MODEL)
        )
        self.KG_EXTRACTION_LLM_API_KEY: str = self._resolve_api_key("KG_EXTRACTION_LLM")
        self.KG_EXTRACTION_LLM_BASE_URL: str = self._resolve_indirect(
            self._resolve_base_url("KG_EXTRACTION_LLM")
        )
        self.KG_EXTRACTION_LLM_TEMPERATURE: float = float(
            os.getenv("KG_EXTRACTION_LLM_TEMPERATURE", "0.0")
        )
        self.KG_EXTRACTION_LLM_TOP_P: float = float(
            os.getenv("KG_EXTRACTION_LLM_TOP_P", "0.95")
        )
        self.KG_EXTRACTION_LLM_TOP_K: int = int(
            os.getenv("KG_EXTRACTION_LLM_TOP_K", "64")
        )
        self.KG_EXTRACTION_MAX_RETRIES: int = int(
            os.getenv("KG_EXTRACTION_MAX_RETRIES", "2")
        )

        self.KG_CYPHER_QA_LLM_PROVIDER: str = self._normalize_provider(
            os.getenv("KG_CYPHER_QA_LLM_PROVIDER", self.LLM_PROVIDER)
        )
        self.KG_CYPHER_QA_LLM_MODEL: str = self._resolve_indirect(
            os.getenv("KG_CYPHER_QA_LLM_MODEL", self.LLM_MODEL)
        )
        self.KG_CYPHER_QA_LLM_API_KEY: str = self._resolve_api_key("KG_CYPHER_QA_LLM")
        self.KG_CYPHER_QA_LLM_BASE_URL: str = self._resolve_indirect(
            self._resolve_base_url("KG_CYPHER_QA_LLM")
        )
        self.KG_CYPHER_QA_LLM_TEMPERATURE: float = float(
            os.getenv("KG_CYPHER_QA_LLM_TEMPERATURE", "0.0")
        )
        self.KG_CYPHER_QA_LLM_TOP_P: float = float(
            os.getenv("KG_CYPHER_QA_LLM_TOP_P", "0.95")
        )
        self.KG_CYPHER_QA_LLM_TOP_K: int = int(
            os.getenv("KG_CYPHER_QA_LLM_TOP_K", "64")
        )

        # Knowledge Graph Schema Discovery
        self.KG_SCHEMA_DISCOVERY_OUTPUT_DIR: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OUTPUT_DIR", "data/processed/knowledge_graph/discovery"
        )
        self.KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY: int = int(
            os.getenv("KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY", "4")
        )
        self.KG_SCHEMA_DISCOVERY_CHUNK_CHARS: int = int(
            os.getenv("KG_SCHEMA_DISCOVERY_CHUNK_CHARS", "12000")
        )
        self.KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP: int = int(
            os.getenv("KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP", "500")
        )
        self.KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS: float = float(
            os.getenv("KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS", "60.0")
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_MODEL", "gemma4:31b-cloud"
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
            default=self.OLLAMA_BASE_URLS,
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS", default=[]
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL", "google/gemini-2.0-flash-001"
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS", default=[]
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_MODEL", "meta/llama-3.1-70b-instruct"
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS", default=[]
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_GEMINI_MODEL", "gemini-2.0-flash"
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS", default=[]
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL", ""
        )

    def _gather_numbered_keys(self, prefix: str) -> list[str]:
        """Gather API keys from prefix, prefix_1, prefix_2, etc."""
        keys: list[str] = []
        base_val = self._resolve_indirect(os.getenv(prefix))
        if base_val:
            keys.append(base_val)

        numbered_values: list[tuple[int, str]] = []
        prefix_with_separator = f"{prefix}_"
        for environment_name, environment_value in os.environ.items():
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

    def _resolve_api_key(self, component_prefix: str) -> str:
        """Resolve API key for a component with fallback to provider defaults."""
        # 1. Component specific
        key = os.getenv(f"{component_prefix}_API_KEY")
        if key:
            return key

        # 2. Global LLM default
        global_key = os.getenv("LLM_API_KEY")
        if global_key:
            return global_key

        # 3. Provider global fallback
        provider = os.getenv(f"{component_prefix}_PROVIDER", self.LLM_PROVIDER)
        p_upper = provider.upper()
        if p_upper in {"GOOGLE_GENAI", "GOOGLE"}:
            return self.GOOGLE_API_KEY
        if p_upper == "OPENROUTER":
            return self.OPENROUTER_API_KEY
        if p_upper == "NVIDIA":
            return self.NVIDIA_API_KEY
        return self.LLM_API_KEY

    def _resolve_base_url(self, component_prefix: str) -> str:
        """Resolve base URL for a component with fallback to provider defaults."""
        # 1. Component specific
        url = os.getenv(f"{component_prefix}_BASE_URL")
        if url:
            return url

        # 2. Global LLM default
        global_url = os.getenv("LLM_BASE_URL")
        if global_url:
            return global_url

        # 3. Provider global fallback
        provider = os.getenv(f"{component_prefix}_PROVIDER", self.LLM_PROVIDER)
        p_upper = provider.upper()
        if p_upper == "OLLAMA":
            return (
                self.OLLAMA_BASE_URLS[0]
                if self.OLLAMA_BASE_URLS
                else "http://localhost:11434"
            )
        if p_upper == "OPENROUTER":
            return "https://openrouter.ai/api/v1"
        if p_upper == "NVIDIA":
            return "https://integrate.api.nvidia.com/v1"
        return self.LLM_BASE_URL


settings = Settings()
