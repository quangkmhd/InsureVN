# Phase 00: Project Bootstrap And API Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

## 1. Thong Tin Chung

**Muc tieu cot loi:** Establish the root dependency manifest, repeatable developer commands, local service configuration, and minimal FastAPI application boundary required before the multi-agent phases can execute reliably.

**Definition of Done:**
- Root project dependency manifest exists and covers runtime, dev, LangChain, LangGraph, Qdrant, NetworkX, FastAPI, Langfuse, and checkpoint packages used by later phases.
- `ruff`, `pytest`, and import checks run from the repository root.
- `src/main.py` exposes a minimal FastAPI app with health and workflow placeholder routes.
- Local service instructions exist for SQLite, Qdrant, Langfuse, and optional Postgres checkpointing.
- CI-ready commands are documented and verified locally.

## 2. Scope

**Can lam:**
- Add root dependency/config files for Python 3.12.3.
- Add minimal app entrypoint and route registration pattern.
- Add developer commands and service bootstrap docs.
- Add tests for health route, importability, and configuration typing.

**Khong duoc lam trong phase nay:**
- Do not implement business agent workflows.
- Do not add Qdrant indexing or graph construction.
- Do not change existing `DatabaseAgent` or `SearchAgent` behavior.
- Do not introduce real user authentication yet; auth/RBAC is handled in Phase 07.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use FastAPI for the service boundary. Use LangChain/LangGraph/Deep Agents only as dependencies and import checks in this phase; no agent graph is built here.

**Files to create:**
- `pyproject.toml`: project metadata, dependencies, ruff/pytest config.
- `src/main.py`: FastAPI application factory and health endpoint.
- `src/api/routes/health.py`: health route.
- `docs/blueprints/dependency_matrix.md`: dependency purpose, owning phase, and install notes.
- `tests/unit/test_project_imports.py`
- `tests/integration/test_health_api.py`

**Files to modify:**
- `README.md`: add bootstrap commands if missing.
- `.env`: register service-level defaults only when needed.

**Tools/MCP/DB:**
- SQLite database remains at `database/insurevn.db`.
- Qdrant and Langfuse run through existing compose files or documented local commands.

## 4. Data Flow

**Input:**
- Developer commands from the repository root.
- Environment variables from `.env`.
- HTTP `GET /health`.

**Output:**
- Installable project environment.
- Health response with project name, status, and configured service flags.
- Stable command surface for later phases.

## 5. Huong Dan Trien Khai

1. Write failing import tests for `src.main`, `src.agents.database_agent`, `src.agents.search_agent`, and key third-party packages used by later phases.
2. Create `pyproject.toml` with runtime and dev dependencies. Include at minimum: `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `langchain`, `langgraph`, `langchain-mcp-adapters`, `langfuse`, `qdrant-client`, `networkx`, `pytest`, `pytest-asyncio`, `httpx`, and `ruff`.
3. Write failing health API test using `httpx.AsyncClient` or FastAPI `TestClient`.
4. Implement `src/main.py` and `src/api/routes/health.py`.
5. Add dependency matrix documenting why each major package exists and which phase consumes it.
6. Update `README.md` with install, lint, format, test, and dev server commands.

## 6. Observability

**Log format:** JSON through `src/core/logger.py`.

**Required log metadata:**
- `component`: `bootstrap`, `health_api`, or `dependency_check`
- `project_name`
- `python_version`
- `service_name`
- `status`

**Langfuse tracking:** No traces required. This phase only verifies that Langfuse dependencies can be imported and existing environment settings remain typed.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Import checks for local modules and required libraries.
- Config type assertions for existing settings.

**Integration tests:**
- Health route contract.
- App startup import path from repository root.

**E2E tests:** None in this phase.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/unit/test_project_imports.py -v`.
- Run `pytest tests/integration/test_health_api.py -v`.
- Start `uvicorn src.main:app --reload` and request `/health`.

**Verification before next phase:**
- `pytest tests/unit/test_project_imports.py tests/integration/test_health_api.py -v`
- `ruff check src tests`
- `ruff format --check src tests`

## 9. Execution Task Breakdown

### Task 1: Dependency Manifest

**Files:**
- Create: `pyproject.toml`
- Create: `docs/blueprints/dependency_matrix.md`
- Test: `tests/unit/test_project_imports.py`

- [ ] Step 1: Write failing import tests.
- [ ] Step 2: Add `pyproject.toml` and install dependencies.
- [ ] Step 3: Run `pytest tests/unit/test_project_imports.py -v`; expected PASS.
- [ ] Step 4: Run `ruff check src tests`; expected PASS.

### Task 2: FastAPI Foundation

**Files:**
- Create: `src/main.py`
- Create: `src/api/routes/health.py`
- Test: `tests/integration/test_health_api.py`

- [ ] Step 1: Write failing health route test.
- [ ] Step 2: Implement app factory and health router.
- [ ] Step 3: Run `pytest tests/integration/test_health_api.py -v`; expected PASS.
- [ ] Step 4: Document run command in `README.md`.
