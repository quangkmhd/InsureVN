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

        # Global LLM defaults
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:31b-cloud")
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", self.OLLAMA_BASE_URLS[0])

        # --- Component Specific LLM Settings (with fallback) ---

        # Database Agent
        self.DATABASE_LLM_PROVIDER: str = os.getenv(
            "DATABASE_LLM_PROVIDER", self.LLM_PROVIDER
        )
        self.DATABASE_LLM_MODEL: str = os.getenv("DATABASE_LLM_MODEL", self.LLM_MODEL)
        self.DATABASE_LLM_API_KEY: str = self._resolve_api_key("DATABASE_LLM")
        self.DATABASE_LLM_BASE_URL: str = self._resolve_base_url("DATABASE_LLM")
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
        self.SEARCH_LLM_PROVIDER: str = os.getenv(
            "SEARCH_LLM_PROVIDER", self.LLM_PROVIDER
        )
        self.SEARCH_LLM_MODEL: str = os.getenv("SEARCH_LLM_MODEL", self.LLM_MODEL)
        self.SEARCH_LLM_API_KEY: str = self._resolve_api_key("SEARCH_LLM")
        self.SEARCH_LLM_BASE_URL: str = self._resolve_base_url("SEARCH_LLM")
        self.SEARCH_LLM_TEMPERATURE: float = float(
            os.getenv("SEARCH_LLM_TEMPERATURE", "0.7")
        )
        self.SEARCH_LLM_TOP_P: float = float(os.getenv("SEARCH_LLM_TOP_P", "0.95"))
        self.SEARCH_LLM_TOP_K: int = int(os.getenv("SEARCH_LLM_TOP_K", "64"))

        # LLM Chunking
        self.LLM_CHUNKING_PROVIDER: str = os.getenv(
            "LLM_CHUNKING_PROVIDER", self.LLM_PROVIDER
        )
        self.LLM_CHUNKING_MODEL: str = os.getenv("LLM_CHUNKING_MODEL", self.LLM_MODEL)
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
        self.RAG_EMBEDDING_PROVIDER: str = os.getenv(
            "RAG_EMBEDDING_PROVIDER", "google_genai"
        )
        self.RAG_EMBEDDING_MODEL: str = os.getenv(
            "RAG_EMBEDDING_MODEL", "gemini-embedding-2"
        )
        self.RAG_EMBEDDING_API_KEY: str = (
            self._resolve_api_key("RAG_EMBEDDING") or self.GOOGLE_API_KEY
        )
        self.RAG_DENSE_VECTOR_SIZE: int = int(os.getenv("RAG_DENSE_VECTOR_SIZE", "768"))
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
            os.getenv("RAG_EMBEDDING_BATCH_SIZE", "1")
        )
        self.RAG_EMBEDDING_TASK_TYPE_DOCUMENT: str = os.getenv(
            "RAG_EMBEDDING_TASK_TYPE_DOCUMENT", "RETRIEVAL_DOCUMENT"
        )
        self.RAG_EMBEDDING_TASK_TYPE_QUERY: str = os.getenv(
            "RAG_EMBEDDING_TASK_TYPE_QUERY", "RETRIEVAL_QUERY"
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

        self.KG_EXTRACTION_LLM_PROVIDER: str = os.getenv(
            "KG_EXTRACTION_LLM_PROVIDER", self.LLM_PROVIDER
        )
        self.KG_EXTRACTION_LLM_MODEL: str = os.getenv(
            "KG_EXTRACTION_LLM_MODEL", self.LLM_MODEL
        )
        self.KG_EXTRACTION_LLM_API_KEY: str = self._resolve_api_key("KG_EXTRACTION_LLM")
        self.KG_EXTRACTION_LLM_BASE_URL: str = self._resolve_base_url(
            "KG_EXTRACTION_LLM"
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

        self.KG_CYPHER_QA_LLM_PROVIDER: str = os.getenv(
            "KG_CYPHER_QA_LLM_PROVIDER", self.LLM_PROVIDER
        )
        self.KG_CYPHER_QA_LLM_MODEL: str = os.getenv(
            "KG_CYPHER_QA_LLM_MODEL", self.LLM_MODEL
        )
        self.KG_CYPHER_QA_LLM_API_KEY: str = self._resolve_api_key("KG_CYPHER_QA_LLM")
        self.KG_CYPHER_QA_LLM_BASE_URL: str = self._resolve_base_url("KG_CYPHER_QA_LLM")
        self.KG_CYPHER_QA_LLM_TEMPERATURE: float = float(
            os.getenv("KG_CYPHER_QA_LLM_TEMPERATURE", "0.0")
        )
        self.KG_CYPHER_QA_LLM_TOP_P: float = float(
            os.getenv("KG_CYPHER_QA_LLM_TOP_P", "0.95")
        )
        self.KG_CYPHER_QA_LLM_TOP_K: int = int(
            os.getenv("KG_CYPHER_QA_LLM_TOP_K", "64")
        )

        # Knowledge graph schema discovery
        self.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS: list[str] = (
            _env_csv("KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS") or self.OLLAMA_BASE_URLS
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS"
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_MODEL", self.LLM_MODEL
        )

        self.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS: list[str] = (
            _env_csv("KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS")
            or self.OPENROUTER_API_KEYS
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL", "google/gemini-2.5-flash"
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        )

        self.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS: list[str] = (
            _env_csv("KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS") or self.NVIDIA_API_KEYS
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        )

        self.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS: list[str] = (
            _env_csv("KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS") or self.GOOGLE_API_KEYS
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_GEMINI_MODEL", "gemini-2.5-flash"
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        )

        self.KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY: int = int(
            os.getenv("KG_SCHEMA_DISCOVERY_MAX_CONCURRENCY", "20")
        )
        self.KG_SCHEMA_DISCOVERY_CHUNK_CHARS: int = int(
            os.getenv("KG_SCHEMA_DISCOVERY_CHUNK_CHARS", "12000")
        )
        self.KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP: int = int(
            os.getenv("KG_SCHEMA_DISCOVERY_CHUNK_OVERLAP", "500")
        )
        self.KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS: float = float(
            os.getenv("KG_SCHEMA_DISCOVERY_ATTEMPT_TIMEOUT_SECONDS", "90.0")
        )
        self.KG_SCHEMA_DISCOVERY_OUTPUT_DIR: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OUTPUT_DIR",
            "data/processed/knowledge_graph/schema_discovery",
        )

    def _gather_numbered_keys(self, prefix: str) -> list[str]:
        """Gather API keys from prefix, prefix_API_KEYS, and prefix_1, prefix_2..."""
        keys = []

        # Determine candidate prefixes to check
        candidate_prefixes = [prefix]
        if prefix.upper() not in candidate_prefixes:
            candidate_prefixes.append(prefix.upper())

        # Specific user-requested variations
        if "OLLAMA" in prefix.upper():
            if "OllAMA" not in candidate_prefixes:
                candidate_prefixes.append("OllAMA")
            if "OllAMA_API_Key" not in candidate_prefixes:
                candidate_prefixes.append("OllAMA_API_Key")

        for p in candidate_prefixes:
            # Check base
            if val := os.getenv(p):
                keys.extend([k.strip() for k in val.split(",") if k.strip()])
            # Check _API_KEYS
            if val := os.getenv(f"{p}S") or os.getenv(f"{p}_KEYS"):
                keys.extend([k.strip() for k in val.split(",") if k.strip()])
            # Check _1, _2...
            i = 1
            while i < 50:
                if val := os.getenv(f"{p}_{i}"):
                    keys.append(val.strip())
                    i += 1
                else:
                    break
        return list(dict.fromkeys(keys))  # unique only

    def _resolve_api_key(self, prefix: str) -> str:
        """Resolve API key for a component with fallback logic."""
        # 1. Component specific
        if val := os.getenv(f"{prefix}_API_KEY"):
            return val
        # 2. Global LLM default
        if self.LLM_API_KEY:
            return self.LLM_API_KEY
        # 3. Provider global
        provider = os.getenv(f"{prefix}_PROVIDER", self.LLM_PROVIDER)
        if provider == "google_genai" and self.GOOGLE_API_KEYS:
            return self.GOOGLE_API_KEYS[0]
        if provider == "openrouter" and self.OPENROUTER_API_KEYS:
            return self.OPENROUTER_API_KEYS[0]
        if provider == "nvidia" and self.NVIDIA_API_KEYS:
            return self.NVIDIA_API_KEYS[0]
        return ""

    def _resolve_base_url(self, prefix: str) -> str:
        """Resolve Base URL for a component with fallback logic."""
        # 1. Component specific
        if val := os.getenv(f"{prefix}_BASE_URL"):
            return val
        # 2. Global LLM default
        if os.getenv("LLM_BASE_URL"):
            return os.getenv("LLM_BASE_URL", "")
        # 3. Provider global
        provider = os.getenv(f"{prefix}_PROVIDER", self.LLM_PROVIDER)
        if provider == "ollama" and self.OLLAMA_BASE_URLS:
            return self.OLLAMA_BASE_URLS[0]
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1/chat/completions"
        if provider == "nvidia":
            return "https://integrate.api.nvidia.com/v1/chat/completions"
        if provider == "google_genai":
            return "https://generativelanguage.googleapis.com/v1beta"
        return "http://localhost:11434"

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return f"sqlite:///{self.SQLITE_DB_PATH}"


settings = Settings()
