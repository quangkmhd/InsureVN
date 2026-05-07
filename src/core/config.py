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

        # LLM Configuration
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:31b-cloud")
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")

        # Database Agent Specific
        self.DATABASE_LLM_PROVIDER: str = os.getenv("DATABASE_LLM_PROVIDER", "ollama")
        self.DATABASE_LLM_MODEL: str = os.getenv(
            "DATABASE_LLM_MODEL", "gemma4:31b-cloud"
        )
        self.DATABASE_LLM_API_KEY: str = os.getenv("DATABASE_LLM_API_KEY", "")
        self.DATABASE_LLM_BASE_URL: str = os.getenv(
            "DATABASE_LLM_BASE_URL", "http://localhost:11434"
        )
        self.DATABASE_LLM_TEMPERATURE: float = float(
            os.getenv("DATABASE_LLM_TEMPERATURE", "1.0")
        )
        self.DATABASE_LLM_TOP_P: float = float(os.getenv("DATABASE_LLM_TOP_P", "0.95"))
        self.DATABASE_LLM_TOP_K: int = int(os.getenv("DATABASE_LLM_TOP_K", "64"))

        # Search Agent Specific
        self.SEARCH_TAVILY_API_KEY: str = os.getenv(
            "SEARCH_TAVILY_API_KEY", os.getenv("TAVILY_API_KEY", "")
        )
        self.SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "50"))
        self.SEARCH_LLM_PROVIDER: str = os.getenv("SEARCH_LLM_PROVIDER", "ollama")
        self.SEARCH_LLM_MODEL: str = os.getenv("SEARCH_LLM_MODEL", "gemma4:31b-cloud")
        self.SEARCH_LLM_API_KEY: str = os.getenv("SEARCH_LLM_API_KEY", "")
        self.SEARCH_LLM_BASE_URL: str = os.getenv(
            "SEARCH_LLM_BASE_URL", "http://localhost:11434"
        )
        self.SEARCH_LLM_TEMPERATURE: float = float(
            os.getenv("SEARCH_LLM_TEMPERATURE", "0.7")
        )
        self.SEARCH_LLM_TOP_P: float = float(os.getenv("SEARCH_LLM_TOP_P", "0.95"))
        self.SEARCH_LLM_TOP_K: int = int(os.getenv("SEARCH_LLM_TOP_K", "64"))

        # RAG/Qdrant Document Retrieval
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
        self.GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
        self.RAG_EMBEDDING_MODEL: str = os.getenv(
            "RAG_EMBEDDING_MODEL", "gemini-embedding-2"
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
            "RAG_CHUNKING_STRATEGY", "hybrid_semantic"
        )
        self.RAG_SEMANTIC_TARGET_CHARS: int = int(
            os.getenv("RAG_SEMANTIC_TARGET_CHARS", "1400")
        )
        self.RAG_SEMANTIC_MAX_CHARS: int = int(
            os.getenv("RAG_SEMANTIC_MAX_CHARS", "3500")
        )
        self.RAG_SEMANTIC_MIN_CHARS: int = int(
            os.getenv("RAG_SEMANTIC_MIN_CHARS", "350")
        )
        self.RAG_SEMANTIC_BREAKPOINT_TYPE: str = os.getenv(
            "RAG_SEMANTIC_BREAKPOINT_TYPE", "interquartile"
        )
        self.RAG_SEMANTIC_BREAKPOINT_AMOUNT: float = float(
            os.getenv("RAG_SEMANTIC_BREAKPOINT_AMOUNT", "1.5")
        )
        self.SEMANTIC_CHUNKING_EMBEDDING_PROVIDER: str = os.getenv(
            "SEMANTIC_CHUNKING_EMBEDDING_PROVIDER", "ollama"
        )
        self.SEMANTIC_CHUNKING_EMBEDDING_MODEL: str = os.getenv(
            "SEMANTIC_CHUNKING_EMBEDDING_MODEL", "qwen3-embedding:8b"
        )
        self.SEMANTIC_CHUNKING_OLLAMA_BASE_URL: str = os.getenv(
            "SEMANTIC_CHUNKING_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        )
        self.RAG_TABLE_LINE_RATIO_THRESHOLD: float = float(
            os.getenv("RAG_TABLE_LINE_RATIO_THRESHOLD", "0.55")
        )
        self.RAG_TABLE_CHUNK_MAX_CHARS: int = int(
            os.getenv("RAG_TABLE_CHUNK_MAX_CHARS", "3500")
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
            "GRAPH_JSON_PATH",
            "data/processed/knowledge_graph/insurevn_graph.json",
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
            "KG_EXTRACTION_LLM_PROVIDER", "ollama"
        )
        self.KG_EXTRACTION_LLM_MODEL: str = os.getenv(
            "KG_EXTRACTION_LLM_MODEL", "gemma4:31b-cloud"
        )
        self.KG_EXTRACTION_LLM_API_KEY: str = os.getenv("KG_EXTRACTION_LLM_API_KEY", "")
        self.KG_EXTRACTION_LLM_BASE_URL: str = os.getenv(
            "KG_EXTRACTION_LLM_BASE_URL", "http://localhost:11434"
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
            "KG_CYPHER_QA_LLM_PROVIDER", "ollama"
        )
        self.KG_CYPHER_QA_LLM_MODEL: str = os.getenv(
            "KG_CYPHER_QA_LLM_MODEL", "gemma4:31b-cloud"
        )
        self.KG_CYPHER_QA_LLM_API_KEY: str = os.getenv("KG_CYPHER_QA_LLM_API_KEY", "")
        self.KG_CYPHER_QA_LLM_BASE_URL: str = os.getenv(
            "KG_CYPHER_QA_LLM_BASE_URL", "http://localhost:11434"
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

        # Knowledge graph schema discovery
        schema_discovery_ollama_base_urls = _env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS"
        )
        schema_discovery_ollama_base_url = os.getenv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URL",
            "",
        ).strip()
        if not schema_discovery_ollama_base_urls and schema_discovery_ollama_base_url:
            schema_discovery_ollama_base_urls = [schema_discovery_ollama_base_url]
        self.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
            default=schema_discovery_ollama_base_urls or ["http://localhost:11434"],
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS",
        )
        self.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OLLAMA_MODEL",
            self.LLM_MODEL,
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS",
            default=_env_csv("OPENROUTER_API_KEY"),
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL",
            "google/gemini-2.5-flash",
        )
        self.KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS",
            default=_env_csv("NVIDIA_API_KEY"),
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_MODEL",
            "meta/llama-3.3-70b-instruct",
        )
        self.KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS: list[str] = _env_csv(
            "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS",
            default=_env_csv("GEMINI_API_KEY"),
        )
        self.KG_SCHEMA_DISCOVERY_GEMINI_MODEL: str = os.getenv(
            "KG_SCHEMA_DISCOVERY_GEMINI_MODEL",
            "gemini-2.5-flash",
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

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return f"sqlite:///{self.SQLITE_DB_PATH}"


settings = Settings()
