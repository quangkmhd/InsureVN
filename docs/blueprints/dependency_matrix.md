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
| `networkx` | Unit-test fixture graph and local graph algorithm checks; not production graph storage | Phase 00 | ✅ Installed |
| `httpx` | Async HTTP client for testing and API calls | Phase 00 | ✅ Installed |
| `rich` | Terminal formatting and logging | Phase 00 | ✅ Installed |
| `pytest` | Testing framework | Phase 00 (Dev) | ✅ Installed |
| `ruff` | Linting and formatting | Phase 00 (Dev) | ✅ Installed |
| `langchain-mcp-adapters` | Integration with MCP servers | Phase 00 | ✅ Installed |
| `langchain-qdrant` | LangChain `QdrantVectorStore` integration and retriever contract for Qdrant RAG | Phase 02 | Planned |
| `fastembed` | Local dense/sparse embeddings, including Qdrant BM25-style sparse retrieval support | Phase 02 | Planned |
| `langchain-google-genai` | Gemini embedding/model integration for cloud RAG mode | Phase 02 | Planned |
| `sentence-transformers` | Local embedding fallback when selected model is not available through FastEmbed/Ollama | Phase 02 | Planned |
| `underthesea` | Vietnamese segmentation and keyword normalization for retrieval | Phase 02 | Planned |
| `langchain-neo4j` | LangChain Neo4j graph, graph document, Cypher QA, and Neo4j vector/hybrid integration | Phase 03 | Planned |
| `neo4j` | Official Neo4j Python driver for constraints, indexes, and deterministic integration tests | Phase 03 | Planned |
| `langchain-graph-retriever` | LangChain Graph RAG retriever with `GraphRetriever` and `Eager` traversal strategy | Phase 03 | Planned |
| `deepagents` | Deep Agents operator shell for long-running curation and future agent tooling | Phase 03+ | Planned |

## Installation

```bash
pip install -e ".[dev]"
```

## Maintenance

Dependencies are managed in `pyproject.toml`. Use `pip-compile` if a locked dependency file is required in the future.
