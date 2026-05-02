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

@mcp.tool()
def execute_query(query: str) -> list[dict]:
    """Execute a read-only SQL query against the database and return results as a list of dictionaries."""
    query_upper = query.strip().upper()
    # Basic security check for read-only operations
    if not any(query_upper.startswith(prefix) for prefix in ["SELECT", "PRAGMA", "EXPLAIN"]):
        raise ValueError("Security Error: Only SELECT queries are allowed.")
    
    with get_db_connection() as conn:
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        
        # Convert sqlite3.Row objects to standard dicts based on cursor description
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return []
if __name__ == "__main__":
    mcp.run()
