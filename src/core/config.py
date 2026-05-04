import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    PROJECT_NAME: str = "InsureVN"

    # Database
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "database/insurevn.db")

    # Langfuse Tracing
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

    # LLM Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:31b-cloud")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")

    # Database Agent Specific
    DATABASE_LLM_PROVIDER: str = os.getenv("DATABASE_LLM_PROVIDER", LLM_PROVIDER)
    DATABASE_LLM_MODEL: str = os.getenv("DATABASE_LLM_MODEL", LLM_MODEL)
    DATABASE_LLM_API_KEY: str = os.getenv("DATABASE_LLM_API_KEY", LLM_API_KEY)
    DATABASE_LLM_BASE_URL: str = os.getenv("DATABASE_LLM_BASE_URL", LLM_BASE_URL)
    DATABASE_LLM_TEMPERATURE: float = float(
        os.getenv("DATABASE_LLM_TEMPERATURE", "1.0")
    )
    DATABASE_LLM_TOP_P: float = float(os.getenv("DATABASE_LLM_TOP_P", "0.95"))
    DATABASE_LLM_TOP_K: int = int(os.getenv("DATABASE_LLM_TOP_K", "64"))

    # Search Agent Specific
    SEARCH_TAVILY_API_KEY: str = os.getenv(
        "SEARCH_TAVILY_API_KEY", os.getenv("TAVILY_API_KEY", "")
    )
    SEARCH_MAX_RESULTS: int = int(os.getenv("SEARCH_MAX_RESULTS", "50"))
    SEARCH_LLM_PROVIDER: str = os.getenv("SEARCH_LLM_PROVIDER", LLM_PROVIDER)
    SEARCH_LLM_MODEL: str = os.getenv("SEARCH_LLM_MODEL", LLM_MODEL)
    SEARCH_LLM_API_KEY: str = os.getenv("SEARCH_LLM_API_KEY", LLM_API_KEY)
    SEARCH_LLM_BASE_URL: str = os.getenv("SEARCH_LLM_BASE_URL", LLM_BASE_URL)
    SEARCH_LLM_TEMPERATURE: float = float(os.getenv("SEARCH_LLM_TEMPERATURE", "0.7"))
    SEARCH_LLM_TOP_P: float = float(os.getenv("SEARCH_LLM_TOP_P", "0.95"))
    SEARCH_LLM_TOP_K: int = int(os.getenv("SEARCH_LLM_TOP_K", "64"))

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.SQLITE_DB_PATH}"


settings = Settings()
