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
        self.DATABASE_LLM_PROVIDER: str = os.getenv(
            "DATABASE_LLM_PROVIDER", "ollama"
        )
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
        self.RAG_QDRANT_COLLECTION: str = os.getenv(
            "RAG_QDRANT_COLLECTION", "insurevn_policy_chunks"
        )
        self.GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
        self.RAG_EMBEDDING_MODEL: str = os.getenv(
            "RAG_EMBEDDING_MODEL", "hashing-local"
        )
        self.RAG_VIETNAMESE_SEGMENTER: str = os.getenv(
            "RAG_VIETNAMESE_SEGMENTER", "underthesea"
        )
        self.RAG_CHILD_CHUNK_TOKENS: int = int(
            os.getenv("RAG_CHILD_CHUNK_TOKENS", "1200")
        )
        self.RAG_CHILD_CHUNK_OVERLAP: int = int(
            os.getenv("RAG_CHILD_CHUNK_OVERLAP", "150")
        )
        self.RAG_PARENT_SECTION_MAX_CHARS: int = int(
            os.getenv("RAG_PARENT_SECTION_MAX_CHARS", "6000")
        )
        self.RAG_RETRIEVAL_TOP_K: int = int(os.getenv("RAG_RETRIEVAL_TOP_K", "5"))
        self.RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE: bool = _env_bool(
            "RAG_ALLOW_DENSE_ONLY_DEGRADED_MODE", default=False
        )

        # Knowledge Graph
        self.GRAPH_JSON_PATH: str = os.getenv(
            "GRAPH_JSON_PATH",
            "data/processed/knowledge_graph/insurevn_graph.json",
        )
        self.GRAPH_MAX_HOPS: int = int(os.getenv("GRAPH_MAX_HOPS", "2"))
        self.GRAPH_RELOAD_ON_STARTUP: bool = _env_bool(
            "GRAPH_RELOAD_ON_STARTUP", default=True
        )

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        return f"sqlite:///{self.SQLITE_DB_PATH}"


settings = Settings()
