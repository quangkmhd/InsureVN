import sqlite3
from pathlib import Path
from urllib.parse import quote
from src.core.config import settings

def get_db_connection(read_only: bool = False):
    """Establish a connection to the SQLite database."""
    if read_only:
        db_path = Path(settings.SQLITE_DB_PATH).resolve()
        db_uri = f"file:{quote(str(db_path), safe='/')}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
    else:
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
