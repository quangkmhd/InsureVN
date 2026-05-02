# Design Specification: InsureVN Database MCP Server

## 1. Overview
This document specifies the design for a new Model Context Protocol (MCP) server within the InsureVN project. The server will expose the local SQLite database (`insurevn.db`) to LangGraph agents (acting as MCP clients) using the FastMCP framework. The internal name for this server will be `insurevn-db`.

## 2. Architecture & Approach
*   **MCP Provider:** The server will be built using the `FastMCP` framework from the official Anthropic `mcp` SDK.
*   **Transport Layer:** Standard standard input/output (`stdio`) will be used to communicate between the LangGraph agent process and the MCP server sub-process.
*   **Integration:** LangGraph agents will use `langchain-mcp-adapters` to initialize an `MCPToolkit`, seamlessly converting the MCP tools into standard LangChain tools.

## 3. Directory Structure
The MCP server code will be isolated from the core application logic to maintain clear boundaries.

```
src/
└── mcp_servers/
    └── sqlite/
        ├── __init__.py
        ├── server.py        # Contains FastMCP server initialization and @mcp.tool definitions
        └── db_manager.py    # (Optional) specific DB helper logic, though we will prioritize reusing src.core.database
```

## 4. MCP Tools Provided
The `insurevn-db` MCP server will expose the following tools:

1.  **`list_tables`**: 
    *   **Description:** Returns a list of all tables in the `insurevn.db` database.
    *   **Parameters:** None
2.  **`get_schema`**: 
    *   **Description:** Returns the DDL (Data Definition Language) `CREATE TABLE` statements for requested tables.
    *   **Parameters:** `table_names` (List of strings)
3.  **`execute_query`**: 
    *   **Description:** Executes a SQL query against the database.
    *   **Security:** This function must strictly validate that the query is a read-only statement (e.g., starts with `SELECT`) to prevent unintended data modification or drops.
    *   **Parameters:** `query` (String)

## 5. Dependencies and Reuse
*   The server will utilize the existing `get_db_connection` function from `src.core.database` to ensure it connects to the correct database path defined in `settings.SQLITE_DB_PATH`.
*   Requires `mcp` (which includes FastMCP) to be installed in the project environment.