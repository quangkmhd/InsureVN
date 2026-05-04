# Phase 04: Supervisor Routing Graph

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 04 = Design Spec Phase 3 (Supervisor + Routing). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 3.

### Dependencies

New packages to install:
- `langgraph` — state graph, conditional edges, checkpointing
- `langgraph-checkpoint-sqlite` — persistent checkpointing for dev/local

## 1. Thong Tin Chung

**Muc tieu cot loi:** Implement the first LangGraph `StateGraph` with a `SupervisorAgent` node that classifies intent/risk, validates hard filters, creates a retrieval plan, and routes to fast, verified, or high-risk lanes.

**Definition of Done:**
- Typed graph state exists with append-only reducers for messages, gathered evidence, and draft decisions.
- Minimal FastAPI workflow boundary exists from Phase 00 and can invoke the graph through a service function.
- `SupervisorDecision` schema supports intent group, risk level, workflow, required evidence, hard filters, and clarification.
- Supervisor structured output works with the configured model and has JSON repair fallback for local/Ollama models.
- Hard filters are validated against known SQLite values before retrieval.
- `EnsembleRetriever` composes per-lane retrieval from Qdrant, Graph, and DatabaseAgent sources.
- Primary chat API endpoint (`POST /api/chat`) accepts user messages and invokes the graph.
- 100 benchmark cases route to expected intent/risk/workflow with target accuracy documented.

**Quantitative success criteria (from design spec):**
- 90%+ routing accuracy on 100 benchmark intents
- 95%+ high-risk cases routed to high-risk lane
- False-positive high-risk rate < 10% (simple questions over-routed)

## 2. Scope

**Can lam:**
- Build SupervisorAgent and routing graph skeleton.
- Add workflow service boundary that accepts API/test requests and invokes the graph.
- Wrap existing `DatabaseAgent.invoke()` as a LangGraph node interface, but do not redesign it.
- Add lane stubs that return planned retrieval requirements.
- Validate company/product/plan filters against SQLite caches.

**Khong duoc lam trong phase nay:**
- Do not implement final specialist synthesis.
- Do not add HITL interrupts.
- Do not call live SearchAgent as a graph node.
- Do not use unvalidated LLM filter values for Qdrant.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangGraph for state, routing, conditional edges, checkpoint-compatible execution, and future fan-out. Use LangChain for model initialization, structured output, and existing agent/tool wrappers. Deep Agents remains the future top-level operator for long-running project/session orchestration, not the runtime app layer in this phase.

**EnsembleRetriever composition:** Create `src/services/ensemble_retriever.py` that composes `QdrantRetriever` (Phase 02) + `GraphRetriever` (Phase 03) + `DatabaseAgent` results per-lane using LangChain's `EnsembleRetriever` or a custom equivalent. Each lane defines which retrievers to activate and their weights. This is the central evidence-gathering mechanism referenced in the design spec.

**Prompt management convention:** Agent system prompts follow the existing pattern in `database_agent.py`: fetch from Langfuse with production label, fall back to `FALLBACK_PROMPT` string. Fallback prompt text lives inline in agent files, NOT in `src/prompts/`. The `src/prompts/` directory is reserved for future prompt template files if Langfuse is unavailable.

**Error handling strategy (applies to all subsequent phases):**
- **LLM call failures:** Retry up to 2 times with exponential backoff (use `tenacity` or LangChain built-in retry). Log every retry with `component`, `retry_count`, `error_type`.
- **MCP/DB failures:** Fail the node, set `error` field in state, let the graph route to a "service unavailable" response. Do NOT silently return empty results.
- **Qdrant/Graph failures:** Degrade gracefully — if Qdrant is down, the lane proceeds with SQLite-only evidence and logs `degraded_mode=true`. If Graph is down, skip graph evidence. Never block the entire workflow for a single retriever failure.
- **Structured output parse failures:** Use JSON repair for local models (log `repair_attempted=true`). If repair fails, ask for clarification instead of guessing.

**Files to create:**
- `src/agents/supervisor_agent.py`
- `src/agents/insurevn_graph.py`
- `src/models/agent_state.py`
- `src/models/supervisor.py`
- `src/services/ensemble_retriever.py`: composes QdrantRetriever + GraphRetriever + DatabaseAgent per-lane.
- `src/services/filter_registry.py`
- `src/api/routes/chat.py`: primary chat API endpoint (`POST /api/chat`) that accepts user messages and invokes the LangGraph app with `thread_id`.
- `tests/unit/test_supervisor_schema.py`
- `tests/unit/test_filter_registry.py`
- `tests/unit/test_ensemble_retriever.py`
- `tests/integration/test_supervisor_routing.py`
- `tests/integration/test_chat_api.py`
- `tests/e2e/test_supervisor_benchmark_routing.py`

**Files to modify:**
- `src/core/config.py`: add `SUPERVISOR_LLM_*`, `SUPERVISOR_ROUTING_CONFIDENCE_THRESHOLD`, and checkpoint config.
- `src/main.py`: include workflow routes from Phase 00.
- `.env`: register supervisor-specific settings.
- `src/agents/database_agent.py`: only if needed to expose a node wrapper without changing existing `invoke()` behavior.

**Tools/MCP/DB:**
- SQLite MCP remains behind `DatabaseAgent`.
- Direct SQLite lookup is allowed in `FilterRegistry` only for startup cache/validation of known companies, documents, plans, and product lines.
- Qdrant/Graph retrievers from earlier phases are referenced through interfaces.

## 4. Data Flow

**Input:**
- API or test request containing `session_id`, `user_id`, and user message.
- Optional synthetic scenario/profile ID.
- Benchmark case rows.

**Output:**
- Updated graph state:
  `messages`, `user_profile`, `synthetic_scenario`, `intent`, `risk_level`, `retrieval_plan`, `required_evidence`, `needs_clarification`, `clarification_question`.
- Route target: `fast_policy`, `verified_compare`, `high_risk_claim`, or `lifecycle_advisory`.

## 5. Huong Dan Trien Khai

1. Write failing schema tests for valid and invalid `SupervisorDecision` values.
2. Implement `src/models/supervisor.py` with Pydantic models and enums.
3. Write failing state reducer tests for append-only `gathered_evidence`, `draft_decisions`, and `messages`.
4. Implement `src/models/agent_state.py` using LangGraph-compatible typed state.
5. Write failing filter validation tests using known and hallucinated company/plan values.
6. Implement `FilterRegistry` with startup cache and warning logs for dropped unknown filters.
7. Write failing routing tests for representative policy, comparison, advisory, claim, payout, hospital, registration, renewal questions.
8. Implement `SupervisorAgent.create()` with `SUPERVISOR_LLM_*` config and structured output.
9. Add JSON repair fallback that logs `repair_attempted=true` and never silently accepts invalid fields.
10. Build `StateGraph` with Supervisor node and conditional edges to lane stubs.
11. Add `WorkflowService.invoke_message(session_id, user_id, message)` as the app boundary.
12. Add FastAPI workflow route tests for request validation and graph invocation through the service.
13. Add benchmark routing E2E test over 100 cases.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `supervisor_agent`, `filter_registry`, `insurevn_graph`
- `session_id`
- `user_id`
- `intent_group`
- `risk_level`
- `workflow`
- `required_evidence`
- `hard_filters_before_validation`
- `hard_filters_after_validation`
- `dropped_filter_keys`
- `routing_confidence`
- `benchmark_case_id`

**Langfuse tracking:**
- Trace node: `supervisor-routing`
- Tags: `supervisor_agent`, `routing`, workflow tag.
- Metadata: prompt version, model provider/model, `session_id`, `user_id`, intent, risk, workflow, hard filters, needs clarification.
- Scores in benchmark mode: `routing_correct`, `risk_correct`, `workflow_correct`.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Supervisor schema validation.
- Filter registry validation.
- State reducers.
- Route selection function.

**Integration tests:**
- SupervisorAgent structured output with a mocked model.
- SQLite-backed filter registry.
- LangGraph invoke with lane stubs.
- FastAPI workflow route invokes `WorkflowService` and returns typed route output.

**E2E tests:**
- 100 benchmark cases route to expected groups.
- High-risk claim/payout cases route to high-risk lane at 95%+ target before moving on.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/integration/test_supervisor_routing.py -v`.
- Run one benchmark case by ID and log full SupervisorDecision.
- Compare raw LLM filters against registry-validated filters.

**Verification before next phase:**
- `pytest tests/unit/test_supervisor_schema.py tests/unit/test_filter_registry.py -v`
- `pytest tests/integration/test_supervisor_routing.py -v`
- `pytest tests/e2e/test_supervisor_benchmark_routing.py -v`
- `ruff check src tests`
- `ruff format --check src tests`

## 9. Execution Task Breakdown

### Task 1: Supervisor Schemas And State

**Files:**
- Create: `src/models/supervisor.py`
- Create: `src/models/agent_state.py`
- Test: `tests/unit/test_supervisor_schema.py`

- [ ] Step 1: Write failing schema and reducer tests.
- [ ] Step 2: Implement Pydantic schemas and LangGraph-compatible state.
- [ ] Step 3: Run `pytest tests/unit/test_supervisor_schema.py -v`; expected PASS.

### Task 2: Filter Registry And Supervisor

**Files:**
- Create: `src/services/filter_registry.py`
- Create: `src/agents/supervisor_agent.py`
- Test: `tests/unit/test_filter_registry.py`
- Test: `tests/integration/test_supervisor_routing.py`

- [ ] Step 1: Write failing filter and routing tests.
- [ ] Step 2: Implement registry, structured-output SupervisorAgent, and JSON repair fallback.
- [ ] Step 3: Run unit and integration routing tests; expected PASS.

### Task 3: Graph And API Boundary

**Files:**
- Create: `src/agents/insurevn_graph.py`
- Create: `src/services/workflow_service.py`
- Create: `src/api/routes/workflows.py`
- Modify: `src/main.py`
- Test: `tests/e2e/test_supervisor_benchmark_routing.py`

- [ ] Step 1: Write failing graph invoke and API route tests.
- [ ] Step 2: Wire StateGraph, workflow service, and FastAPI route.
- [ ] Step 3: Run `pytest tests/e2e/test_supervisor_benchmark_routing.py -v`; expected PASS or documented benchmark threshold result.
