import sqlite3
from src.core.config import settings

def get_db_connection():
    """Establish a connection to the SQLite database."""
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    # Enable DictCursor-like behavior in sqlite3
    conn.row_factory = sqlite3.Row
    return conn

def execute_sql_file(file_path: str):
    """Execute a SQL file."""
    with get_db_connection() as conn:
        with open(file_path, "r", encoding="utf-8") as f:
            sql_script = f.read()
            conn.executescript(sql_script)
        conn.commit()
