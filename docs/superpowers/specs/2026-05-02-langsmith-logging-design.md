# LangSmith and System Logging Architecture Design

## 1. Overview
The goal of this design is to implement comprehensive logging and tracing for the InsureVN multi-agent system, with a specific focus on tracing the `database_agent` and its MCP tool executions. We will use LangSmith for deep AI tracing and standard Python logging for local system errors.

## 2. Architecture

### 2.1 AI Tracing (LangSmith)
- **Integration**: Native integration via LangChain/LangGraph environment variables.
- **Environment Variables**:
  - `LANGCHAIN_TRACING_V2=true`
  - `LANGCHAIN_ENDPOINT=https://api.smith.langchain.com`
  - `LANGCHAIN_API_KEY=<secret>`
  - `LANGCHAIN_PROJECT=InsureVN`
- **Tracing Scope**: Automatically captures all Agent routing, LLM reasoning steps, and Tool executions (including MCP database queries).
- **Run Tagging**: Agent invocations will be explicitly tagged using `config={"tags": ["database_agent"], "run_name": "Database_MCP_Execution"}` to improve observability on the LangSmith dashboard.

### 2.2 System Error Logging (Local)
- **Library**: Standard Python `logging` module.
- **Location**: `src/core/logger.py`
- **Scope**: Captures system startup errors, FastAPI route errors, and critical exceptions before the agent executes.
- **Integration**: The logger will be initialized in `src/main.py` and used across FastAPI routes and core services.

## 3. Implementation Steps
1. Create `src/core/logger.py` to initialize the system logger with appropriate formatting (console output).
2. Update `src/main.py` to integrate the system logger for API request/error tracking.
3. Update `.env.example` and documentation to include LangSmith variables.
4. Update agent execution code (e.g., `src/agents/database_agent.py` or orchestrator) to pass `tags` and `run_name` into the LangGraph `.invoke()` or `.stream()` method.

## 4. Constraints & Considerations
- **Security**: `LANGCHAIN_API_KEY` must never be committed to version control. It will reside only in `.env`.
- **Performance**: LangSmith tracing happens asynchronously via LangChain's callback system, ensuring minimal impact on the main API response time.
