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
    
    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.SQLITE_DB_PATH}"

settings = Settings()
