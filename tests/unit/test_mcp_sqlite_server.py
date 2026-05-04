from unittest.mock import MagicMock, patch

import pytest
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
    mock_conn.execute.assert_called_once_with(
        "SELECT name FROM sqlite_master WHERE type='table';"
    )


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_get_schema(mock_get_db):
    from src.mcp_servers.sqlite.server import get_schema

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor

    mock_cursor.fetchone.side_effect = [
        {"sql": "CREATE TABLE users (id INT);"},
        {"sql": "CREATE TABLE policies (id INT);"},
    ]

    schemas = get_schema(["users", "policies"])

    assert schemas == [
        "CREATE TABLE users (id INT);",
        "CREATE TABLE policies (id INT);",
    ]
    assert mock_conn.execute.call_count == 2


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
    mock_get_db.assert_called_once_with(read_only=True)
    mock_conn.execute.assert_called_once_with("SELECT * FROM users LIMIT 2")


def test_execute_query_invalid():
    from src.mcp_servers.sqlite.server import execute_query

    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("DROP TABLE users")

    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("UPDATE users SET name='Hack'")

    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("INSERT INTO users VALUES (1)")

    with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
        execute_query("PRAGMA user_version = 123")


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_database_summary(mock_get_db):
    from src.mcp_servers.sqlite.server import database_summary

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.description = (("table_name", None), ("row_count", None))
    mock_cursor.fetchall.return_value = [("companies", 6), ("documents", 83)]

    result = database_summary()

    assert result == [
        {"table_name": "companies", "row_count": 6},
        {"table_name": "documents", "row_count": 83},
    ]
    mock_conn.execute.assert_called_once()


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_get_premium_quotes_filters(mock_get_db):
    from src.mcp_servers.sqlite.server import get_premium_quotes

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.description = (("company_code", None), ("premium_amount", None))
    mock_cursor.fetchall.return_value = [("aia", 3829000.0)]

    result = get_premium_quotes(
        age=25, company_code="aia", plan_code="basic", max_premium=5000000, limit=10
    )

    assert result == [{"company_code": "aia", "premium_amount": 3829000.0}]
    query, params = mock_conn.execute.call_args.args
    assert "BETWEEN pe.age_min AND pe.age_max" in query
    assert "c.code = ?" in query
    assert "pt.normalized_code = ?" in query
    assert "pe.premium_amount <= ?" in query
    assert params == [25, "aia", "basic", 5000000, 10]


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_search_glossary_terms(mock_get_db):
    from src.mcp_servers.sqlite.server import search_glossary_terms

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.description = (("term", None), ("definition", None))
    mock_cursor.fetchall.return_value = [
        ("Bệnh có sẵn", "Tình trạng sức khỏe có trước ngày hiệu lực.")
    ]

    result = search_glossary_terms("bệnh có sẵn", company_code="aia", limit=5)

    assert result == [
        {
            "term": "Bệnh có sẵn",
            "definition": "Tình trạng sức khỏe có trước ngày hiệu lực.",
        }
    ]
    query, params = mock_conn.execute.call_args.args
    assert "gt.term LIKE ?" in query
    assert "c.code = ?" in query
    assert params == ["%bệnh có sẵn%", "%bệnh có sẵn%", "aia", 5]


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_get_raw_source(mock_get_db):
    from src.mcp_servers.sqlite.server import get_raw_source

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.description = (("source_table_id", None), ("raw_json", None))
    mock_cursor.fetchall.return_value = [(12, '{"rows": []}')]

    result = get_raw_source(12)

    assert result == {"source_table_id": 12, "raw_json": '{"rows": []}'}
    query, params = mock_conn.execute.call_args.args
    assert "FROM source_tables st" in query
    assert params == (12,)


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_compare_benefits_filters(mock_get_db):
    from src.mcp_servers.sqlite.server import compare_benefits

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.description = (("company_code", None), ("value", None))
    mock_cursor.fetchall.return_value = [
        ("aia", "100.000.000"),
        ("liberty", "120.000.000"),
    ]

    result = compare_benefits(
        "ung thư", ["aia", "liberty"], plan_codes=["basic"], limit=20
    )

    assert result == [
        {"company_code": "aia", "value": "100.000.000"},
        {"company_code": "liberty", "value": "120.000.000"},
    ]
    query, params = mock_conn.execute.call_args.args
    assert "c.code IN (?, ?)" in query
    assert "pt.normalized_code IN (?)" in query
    assert params == [
        "%ung thư%",
        "%ung thư%",
        "%ung thư%",
        "aia",
        "liberty",
        "basic",
        20,
    ]


def test_compare_benefits_requires_company_codes():
    from src.mcp_servers.sqlite.server import compare_benefits

    with pytest.raises(ValueError, match="company_codes"):
        compare_benefits("ung thư", [])


@patch("src.mcp_servers.sqlite.server.get_db_connection")
def test_search_exclusions_param_order(mock_get_db):
    from src.mcp_servers.sqlite.server import search_exclusions

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.description = (("source_kind", None), ("title", None))
    mock_cursor.fetchall.return_value = [("benefit_item", "loại trừ implant")]

    result = search_exclusions(keyword="implant", company_code="aia", limit=7)

    assert result == [{"source_kind": "benefit_item", "title": "loại trừ implant"}]
    query, params = mock_conn.execute.call_args.args
    assert "UNION ALL" in query
    assert params == [
        "%loại trừ%",
        "%loại trừ%",
        "%loại trừ%",
        "%không chi trả%",
        "%không chi trả%",
        "%không chi trả%",
        "%không được bảo hiểm%",
        "%không được bảo hiểm%",
        "%không được bảo hiểm%",
        "%exclusion%",
        "%exclusion%",
        "%exclusion%",
        "%implant%",
        "%implant%",
        "%implant%",
        "aia",
        "%loại trừ%",
        "%loại trừ%",
        "%không chi trả%",
        "%không chi trả%",
        "%không được bảo hiểm%",
        "%không được bảo hiểm%",
        "%exclusion%",
        "%exclusion%",
        "%implant%",
        "%implant%",
        "aia",
        7,
    ]
