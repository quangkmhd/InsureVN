# Dependency Matrix

This document tracks the core dependencies of the InsureVN project, their purpose, and which implementation phase introduces or relies on them.

| Package | Purpose | Owning Phase | Status |
| :--- | :--- | :--- | :--- |
| `fastapi` | Web framework for API layer | Phase 00 | ✅ Installed |
| `uvicorn` | ASGI server for FastAPI | Phase 00 | ✅ Installed |
| `pydantic` | Data validation and settings management | Phase 00 | ✅ Installed |
| `python-dotenv` | Environment variable management | Phase 00 | ✅ Installed |
| `langchain` | Core agent framework | Phase 00 | ✅ Installed |
| `langgraph` | Agent orchestration and state management | Phase 00 | ✅ Installed |
| `langfuse` | AI observability and tracing | Phase 00 | ✅ Installed |
| `qdrant-client` | Vector database for RAG | Phase 00 | ✅ Installed |
| `networkx` | Knowledge graph representation | Phase 00 | ✅ Installed |
| `httpx` | Async HTTP client for testing and API calls | Phase 00 | ✅ Installed |
| `rich` | Terminal formatting and logging | Phase 00 | ✅ Installed |
| `pytest` | Testing framework | Phase 00 (Dev) | ✅ Installed |
| `ruff` | Linting and formatting | Phase 00 (Dev) | ✅ Installed |
| `langchain-mcp-adapters` | Integration with MCP servers | Phase 00 | ✅ Installed |

## Installation

```bash
pip install -e ".[dev]"
```

## Maintenance

Dependencies are managed in `pyproject.toml`. Use `pip-compile` if a locked dependency file is required in the future.
