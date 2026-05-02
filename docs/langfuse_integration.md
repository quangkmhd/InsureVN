# Langfuse Integration in InsureVN

This document describes how Langfuse is currently integrated into the InsureVN codebase to provide observability, tracing, and prompt management for our multi-agent system.

## 1. Architectural Overview

Langfuse acts as the central observability hub for InsureVN. It is integrated across two main layers:
1.  **Agent Logic (LangChain/LangGraph)**: High-level reasoning and execution traces.
2.  **Tool Execution (MCP Servers)**: Low-level tool calls and database interactions.

## 2. Implementation Details

### 2.1 Tracing Agent Execution
The `DatabaseAgent` (`src/agents/database_agent.py`) is instrumented using the `langfuse.langchain.CallbackHandler`. Every time the agent is invoked, a new trace is created in Langfuse.

-   **Automatic Tracing**: By passing the `CallbackHandler` to the LangChain `ainvoke` method, we capture the full model interaction, including thought process, tool selections, and final responses.
-   **Context Propagation**: We use `propagate_attributes` to enrich traces with `user_id`, `session_id`, and `agent_type`. This allows us to group traces by user session in the Langfuse dashboard.

### 2.2 Remote Prompt Management
InsureVN has migrated from hardcoded system prompts to **Langfuse Prompt Management**.

-   **Dynamic Fetching**: The `DatabaseAgent` fetches the system prompt `database-agent-system` (labeled `production`) at runtime using the Langfuse SDK.
-   **Resilience**: A fallback system prompt is implemented in the code. If the Langfuse API is unavailable, the agent defaults to a local version, ensuring system availability.
-   **Versioning**: This integration allows the team to iterate on agent instructions via the Langfuse UI without changing the source code.

### 2.3 MCP Tool Instrumentation
Individual database tools in the SQLite MCP server (`src/mcp_servers/sqlite/server.py`) are instrumented using a custom `@mcp_observe` decorator.

-   **Span Management**: This decorator wraps the tool logic, creating a nested span within the agent's trace.
-   **Detailed Metadata**: Tool arguments are truncated and stored in metadata, alongside result sizes and status messages.
-   **Status Reporting**: The decorator automatically marks spans as `ERROR` or `WARNING` based on the tool's execution result, providing granular visibility into failures.

## 3. Data Flow & Propagation

1.  **Request Initiation**: A query arrives with `user_id` and `session_id`.
2.  **Attribute Propagation**: `DatabaseAgent.invoke` starts a `propagate_attributes` block.
3.  **Callback Attachment**: The `CallbackHandler` is initialized and added to the LangChain config.
4.  **Trace Synchronization**: As the agent calls tools (via MCP), the `@mcp_observe` decorator in the MCP server ensures that these calls are linked to the parent trace.
5.  **Flushing**: `get_client().flush()` is called in `finally` blocks to ensure data delivery in asynchronous environments.

## 4. Environment Configuration

The integration relies on centralized settings in `src/core/config.py`, which loads the following from the `.env` file:
-   `LANGFUSE_PUBLIC_KEY`
-   `LANGFUSE_SECRET_KEY`
-   `LANGFUSE_HOST` (defaults to local for development)
