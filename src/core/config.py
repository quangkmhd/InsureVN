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
    
    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.SQLITE_DB_PATH}"

settings = Settings()
