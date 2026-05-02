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