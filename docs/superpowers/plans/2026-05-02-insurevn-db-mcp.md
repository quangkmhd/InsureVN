# InsureVN Database MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone Model Context Protocol (MCP) server using FastMCP that exposes the InsureVN SQLite database via `list_tables`, `get_schema`, and `execute_query` tools for LangGraph agents to use.

**Architecture:** FastMCP server wrapping `src.core.database.get_db_connection()`. Tools are defined with `@mcp.tool()`. Communication via standard I/O.

**Tech Stack:** Python 3.12, `mcp` (FastMCP), `sqlite3`, `pytest`

---

### Task 1: Setup Directories and Server Instance

**Files:**
- Create: `src/mcp_servers/__init__.py`
- Create: `src/mcp_servers/sqlite/__init__.py`
- Create: `src/mcp_servers/sqlite/server.py`
- Create: `tests/unit/test_mcp_sqlite_server.py`

- [ ] **Step 1: Create directory structure and init files**

```bash
mkdir -p src/mcp_servers/sqlite
touch src/mcp_servers/__init__.py
touch src/mcp_servers/sqlite/__init__.py
```

- [ ] **Step 2: Write failing test for server initialization**

Modify: `tests/unit/test_mcp_sqlite_server.py`
```python
import pytest
from mcp.server.fastmcp import FastMCP

def test_server_initialization():
    from src.mcp_servers.sqlite.server import mcp
    assert isinstance(mcp, FastMCP)
    assert mcp.name == "insurevn-db"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_sqlite_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.mcp_servers.sqlite.server'`

- [ ] **Step 4: Write minimal implementation**

Modify: `src/mcp_servers/sqlite/server.py`
```python
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("insurevn-db")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_sqlite_server.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mcp_servers/ tests/unit/test_mcp_sqlite_server.py
git commit -m "feat: initialize FastMCP server for insurevn-db"
```

---

### Task 2: Implement `list_tables` tool

**Files:**
- Modify: `src/mcp_servers/sqlite/server.py`
- Modify: `tests/unit/test_mcp_sqlite_server.py`

- [ ] **Step 1: Write the failing test**

Modify: `tests/unit/test_mcp_sqlite_server.py`
Add to the end:
```python
import sqlite3
from unittest.mock import patch, MagicMock

@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_list_tables(mock_get_db):
    from src.mcp_servers.sqlite.server import list_tables
    
    # Mock DB connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    
    # Mock row data returned by sqlite
    mock_row1 = {"name": "users"}
    mock_row2 = {"name": "policies"}
    mock_cursor.fetchall.return_value = [mock_row1, mock_row2]
    
    tables = list_tables()
    
    assert tables == ["users", "policies"]
    mock_conn.execute.assert_called_once_with("SELECT name FROM sqlite_master WHERE type='table';")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_sqlite_server.py::test_list_tables -v`
Expected: FAIL with `ImportError: cannot import name 'list_tables'`

- [ ] **Step 3: Write minimal implementation**

Modify: `src/mcp_servers/sqlite/server.py`
Append the following:
```python
from src.core.database import get_db_connection

@mcp.tool()
def list_tables() -> list[str]:
    """Return a list of all tables in the insurevn.db database."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        rows = cursor.fetchall()
        return [row["name"] for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_sqlite_server.py::test_list_tables -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/sqlite/server.py tests/unit/test_mcp_sqlite_server.py
git commit -m "feat: add list_tables tool to MCP server"
```

---

### Task 3: Implement `get_schema` tool

**Files:**
- Modify: `src/mcp_servers/sqlite/server.py`
- Modify: `tests/unit/test_mcp_sqlite_server.py`

- [ ] **Step 1: Write the failing test**

Modify: `tests/unit/test_mcp_sqlite_server.py`
Add to the end:
```python
@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_get_schema(mock_get_db):
    from src.mcp_servers.sqlite.server import get_schema
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    
    mock_cursor.fetchone.side_effect = [
        {"sql": "CREATE TABLE users (id INT);"},
        {"sql": "CREATE TABLE policies (id INT);"}
    ]
    
    schemas = get_schema(["users", "policies"])
    
    assert schemas == [
        "CREATE TABLE users (id INT);",
        "CREATE TABLE policies (id INT);"
    ]
    assert mock_conn.execute.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_sqlite_server.py::test_get_schema -v`
Expected: FAIL with `ImportError: cannot import name 'get_schema'`

- [ ] **Step 3: Write minimal implementation**

Modify: `src/mcp_servers/sqlite/server.py`
Append the following:
```python
@mcp.tool()
def get_schema(table_names: list[str]) -> list[str]:
    """Return the DDL CREATE TABLE statements for the requested tables."""
    schemas = []
    with get_db_connection() as conn:
        for table in table_names:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", 
                (table,)
            )
            row = cursor.fetchone()
            if row and row["sql"]:
                schemas.append(row["sql"])
            else:
                schemas.append(f"-- Schema not found for table: {table}")
    return schemas
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_sqlite_server.py::test_get_schema -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/sqlite/server.py tests/unit/test_mcp_sqlite_server.py
git commit -m "feat: add get_schema tool to MCP server"
```

---

### Task 4: Implement `execute_query` tool (Read-only)

**Files:**
- Modify: `src/mcp_servers/sqlite/server.py`
- Modify: `tests/unit/test_mcp_sqlite_server.py`

- [ ] **Step 1: Write failing tests**

Modify: `tests/unit/test_mcp_sqlite_server.py`
Add to the end:
```python
@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_execute_query_valid(mock_get_db):
    from src.mcp_servers.sqlite.server import execute_query
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    
    # Setup mock column names and rows
    mock_cursor.description = (("id", None), ("name", None))
    mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
    
    result = execute_query("SELECT * FROM users LIMIT 2")
    
    assert result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    mock_conn.execute.assert_called_once_with("SELECT * FROM users LIMIT 2")

def test_execute_query_invalid():
    from src.mcp_servers.sqlite.server import execute_query
    
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("DROP TABLE users")
    
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("UPDATE users SET name='Hack'")
    
    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("INSERT INTO users VALUES (1)")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_mcp_sqlite_server.py::test_execute_query_valid tests/unit/test_mcp_sqlite_server.py::test_execute_query_invalid -v`
Expected: FAIL with `ImportError: cannot import name 'execute_query'`

- [ ] **Step 3: Write minimal implementation**

Modify: `src/mcp_servers/sqlite/server.py`
Append the following:
```python
@mcp.tool()
def execute_query(query: str) -> list[dict]:
    """Execute a read-only SQL query against the database and return results as a list of dictionaries."""
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT") and not query_upper.startswith("PRAGMA") and not query_upper.startswith("EXPLAIN"):
        raise ValueError("Security Error: Only SELECT queries are allowed.")
    
    with get_db_connection() as conn:
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        
        # Convert sqlite3.Row objects to standard dicts based on cursor description
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_mcp_sqlite_server.py::test_execute_query_valid tests/unit/test_mcp_sqlite_server.py::test_execute_query_invalid -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_servers/sqlite/server.py tests/unit/test_mcp_sqlite_server.py
git commit -m "feat: add secure read-only execute_query tool"
```

---

### Task 5: Add CLI Entrypoint

**Files:**
- Modify: `src/mcp_servers/sqlite/server.py`

- [ ] **Step 1: Write the entrypoint code**

Modify: `src/mcp_servers/sqlite/server.py`
Append the following to make the file runnable:
```python
if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Commit**

```bash
git add src/mcp_servers/sqlite/server.py
git commit -m "feat: add CLI entrypoint for insurevn-db server"
```