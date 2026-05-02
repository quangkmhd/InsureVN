# Database Observability & AI Error Recovery

This document describes the technical implementation of database observability in InsureVN and how it enables self-correcting AI behavior.

## 1. Structured Logging Implementation

InsureVN uses a centralized logging architecture defined in `src/core/logger.py`.

### 1.1 JSON Schema for Logs
All logs are emitted in a structured JSON format to enable automated monitoring. The schema includes:
-   `timestamp`: ISO-8601 formatted time.
-   `level`: Standard logging levels (INFO, WARNING, ERROR).
-   `logger`: The component name (e.g., `mcp-insurevn-db`).
-   `message`: A human-readable description of the event.
-   `extra_fields`: Dynamic fields like `tool_name`, `error_type`, and `suggestion`.

### 1.2 Storage & Management
-   **File**: `log/mcp_database.log`.
-   **Rotation**: Files are limited to 10MB with 5 backups retained using `RotatingFileHandler`.
-   **Protocol Compatibility**: In the MCP server, logs are sent to `sys.stderr` to avoid corrupting the standard I/O communication protocol used by MCP.

## 2. Database Output Formats

The SQLite MCP server (`src/mcp_servers/sqlite/server.py`) returns data in two primary formats:

### 2.1 Success Format (List of Dictionaries)
When a query succeeds, the tool returns a JSON-serialized list of objects. This allows the AI to parse column names and values directly.
```json
[
  {"id": 1, "company_name": "Bao Viet", "plan_name": "An Gia"},
  {"id": 2, "company_name": "PVI", "plan_name": "Care"}
]
```

### 2.2 Error Format (Structured Payload)
If a database error occurs (syntax error, table not found, security violation), the tool catches the exception and returns a **structured error payload** instead of a raw traceback.
```json
{
  "status": "error",
  "error_type": "OperationalError",
  "message": "no such table: users",
  "tool": "execute-query",
  "suggestion": "Use 'list-tables' to verify the table names in the database."
}
```

## 3. AI Interaction Logic

The `DatabaseAgent` handles database outputs through a specific feedback loop:

1.  **Tool Result Injection**: The tool's return value (whether data or an error payload) is injected into the conversation history as a `ToolMessage`.
2.  **LLM Interpretation**: The LLM (Gemini/Ollama) is instructed via its system prompt to analyze the tool output. 
    -   If it sees a `status: error`, it reads the `suggestion` and `message`.
3.  **Self-Correction**: Based on the error details, the LLM can decide to:
    -   Correct its SQL syntax.
    -   Call a discovery tool (like `list-tables` or `get-schema`) to gather missing context.
    -   Inform the user clearly about the limitation or data absence.
4.  **Trace Visualization**: This entire loop is captured in Langfuse, where error payloads automatically trigger an `ERROR` level on the corresponding span, allowing developers to see exactly which queries caused AI confusion.
