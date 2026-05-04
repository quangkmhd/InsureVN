import pytest
import sqlite3
import os

@pytest.fixture
def temp_db(tmp_path):
    # Create a temporary database for testing
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    
    # Load schema
    schema_path = os.path.join(os.path.dirname(__file__), '../src/models/schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
        
    conn.executescript(schema_sql)
    conn.close()
    
    yield str(db_file)
    
    if db_file.exists():
        db_file.unlink()
