# Spec: Renaming Knowledge Graph Services for Clarity

## 1. Overview
The current file names in `src/services/knowledge_graph/` are too generic (`builder.py`, `quality.py`, etc.), making it difficult to understand their specific roles within the multi-agent system. This task involves renaming these files to more descriptive, technical names that reflect their actual implementation (e.g., usage of NetworkX, specific validation logic).

## 2. Proposed Changes

| Current File | New File Name | Rationale |
| :--- | :--- | :--- |
| `builder.py` | `networkx_graph_builder.py` | Specifically builds NetworkX graphs for diagnostics. |
| `quality.py` | `graph_quality_validator.py` | Specifically validates graph integrity and constraints. |
| `retriever.py` | `networkx_path_retriever.py` | Specifically handles path traversal on NetworkX graphs. |
| `schema.py` | `insurance_graph_schema.py` | Defines the insurance-specific entity schema and ID generation. |
| `serializer.py` | `graph_json_serializer.py` | Specifically handles JSON serialization of graph data. |

## 3. Impact Analysis
- **Imports**: All files importing from these modules must be updated.
- **Observability**: Decorators like `@service_observe` use names derived from the module path. These should be updated to maintain clear tracing.
- **Tests**: Any tests targeting these files must be updated.

## 4. Verification Plan
- **Static Analysis**: Run `ruff` to ensure no broken imports.
- **Unit Tests**: Run tests in `tests/` to verify that the logic remains intact after renaming.
- **E2E Flow**: Verify that the document extraction and knowledge graph building flow still works.
