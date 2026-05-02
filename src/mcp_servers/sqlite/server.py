from mcp.server.fastmcp import FastMCP
from src.core.database import get_db_connection

# Initialize FastMCP server
mcp = FastMCP("insurevn-db")

@mcp.tool()
def list_tables() -> list[str]:
    """Return a list of all tables in the insurevn.db database."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        rows = cursor.fetchall()
        return [row["name"] for row in rows]

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