import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from mcp.server.fastmcp import FastMCP

def test_server_initialization():
    from src.mcp_servers.sqlite.server import mcp
    assert isinstance(mcp, FastMCP)
    assert mcp.name == "insurevn-db"

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
