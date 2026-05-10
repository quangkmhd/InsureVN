# InsureVN Documentation Map

This folder is organized by document purpose so architecture, implementation
references, project planning, and work history are easy to separate.

## Start Here

- [Architecture: Multi-Agent Platform](architecture/2026-05-03-multi-agent-platform-design.md)
- [Architecture: Quad-Retrieval RAG](architecture/2026-05-04-quad-retrieval-rag-architecture.md)
- [Architecture: KG Schema Discovery & Pipeline](architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md)
- [Architecture: Benchmark V2 Generation Logic](architecture/2026-05-09-benchmark-v2-generation-logic-technical-report.md)
- [Data Pipeline Work Log](work_log/2026-05-09-data-pipeline-processing-technical-report.md)
- [Ensemble Retriever Log](work_log/2026-05-09-ensemble-retriever-flow-technical-report.md)
- [SQLite Schema Specification](database/sqlite_database_schema_specification.md)
- [Database MCP Reference](database/mcp_insurevn_db_reference.md)

## Folder Guide

| Folder | Purpose |
| --- | --- |
| `architecture/` | Canonical system design docs and historical architecture brainstorming. |
| `assets/` | Images, SVGs, diagrams, and other documentation media. |
| `blueprints/` | Phase-by-phase build blueprints and dependency planning. |
| `database/` | SQLite schema, ERD, MCP server reference, DatabaseAgent docs, and JSON schema analysis. |
| `observability/` | Langfuse integration and database observability notes. |
| `product/` | Customer scenarios and insurance lifecycle/product mapping. |
| `superpowers/specs/` | Design specs produced during planning sessions. |
| `superpowers/plans/` | Implementation plans produced from approved specs. |
| `work_log/` | Progress logs, source inventory, retrieval logs, and work history. |

## Naming Convention

- Use lowercase filenames with underscores for domain references.
- Use date-prefixed filenames for architecture, specs, plans, and time-bound logs.
- Keep canonical docs under their topic folder instead of the docs root.
- Put generated diagrams or media under `assets/`, not the docs root.
