# Phase 01: Evidence Foundation And Benchmark Fixtures

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 01 = Design Spec Phase 1 (Evidence Foundation + Benchmark Fixtures). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 1.

### Dependencies

No new external packages required. Uses existing `pydantic`, `langchain`, `langfuse` from project.

## 1. Thong Tin Chung

**Muc tieu cot loi:** Create the shared evidence contracts, SQLite/profile adapters, citation formatter, evidence merger, and 100-case benchmark fixture layer needed by every later LangGraph workflow.

**Definition of Done:**
- `Evidence`, `RetrievalPlan`, `Citation`, and benchmark case schemas exist with Pydantic validation.
- Existing SQLite MCP results can be normalized into `Evidence(source_type="sqlite_row")`.
- Minimal synthetic profile tables and seed fixtures exist in SQLite.
- `Evidence`, `RetrievalPlan`, `Citation`, and `BenchmarkCase` schemas exist with strict Pydantic validation.
- Minimal synthetic profile tables (users, policies) exist in SQLite to serve as the foundation for future LLM-based dataset generation.
- Unit and integration tests pass for schemas, adapters, merger, citations, and benchmark seed validation.

## 2. Scope

**Can lam:**
- Create shared domain models for evidence and retrieval planning.
- Wrap current SQLite MCP output shapes without redesigning the MCP server.
- Add minimal synthetic profile tables: `synthetic_users`, `synthetic_policies`, and `synthetic_benchmark_cases`.
- Prepare the database schema for future generation by adding empty synthetic tables. (Note: Both the personas and benchmark questions will be generated dynamically by an LLM in Phase 06).
- Implement pure-Python evidence merging and citation formatting.

**Khong duoc lam trong phase nay:**
- Do not build Qdrant indexing, embeddings, or real document retrieval.
- Do not build SupervisorAgent routing logic.
- Do not implement PolicyAgent, ClaimAgent, AdvisorAgent, or HITL interrupts.
- Do not add Neo4j or any graph database dependency.
- Do not replace the existing `DatabaseAgent` or SQLite MCP tools.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangChain only for existing MCP tool compatibility in this phase. LangGraph and Deep Agents are planned but not required until workflow orchestration begins.

**Models directory organization:** All Pydantic domain models live as separate files directly under `src/models/` (flat structure). Each file groups related schemas (e.g., `evidence.py` contains `Evidence`, `Citation`, `RetrievalPlan`). Do NOT create subpackages like `src/models/domain/`. This convention applies to all subsequent phases.

**Service layer convention:** All modules under `src/services/` are **stateless, pure-Python** service functions/classes. Services do not own LLM instances or MCP connections — those belong to agents. Services may accept data as parameters and return transformed data. This convention applies to all subsequent phases.

**Files to create:**
- `src/models/evidence.py`: Pydantic models for `Evidence`, `Citation`, `RetrievalPlan`, `HardFilters`, `BenchmarkCase`.
- `src/services/evidence_adapters.py`: `StructuredEvidenceAdapter` and `ProfileEvidenceAdapter`.
- `src/services/evidence_merger.py`: deterministic dedupe, grouping, conflict detection, compact context builder.
- `src/services/citation_formatter.py`: citation rendering and validation helpers.
- `tests/fixtures/`: directory for JSON/YAML fixture data files (sample MCP results).
- `tests/conftest.py`: shared pytest fixtures (temporary SQLite DB factory, sample MCP result dicts, benchmark case loader). All subsequent phases reuse fixtures from this file.
- `tests/fixtures/`: directory for JSON/YAML fixture data files (sample MCP results, benchmark cases).
- `tests/unit/test_evidence_models.py`
- `tests/unit/test_evidence_adapters.py`
- `tests/unit/test_evidence_merger.py`
- `tests/unit/test_citation_formatter.py`


**Files to modify:**
- `src/models/schema.sql`: add synthetic tables only.
- `src/core/config.py`: add prefixed synthetic/evidence settings if needed, for example `EVIDENCE_MAX_CONTEXT_CHARS`.
- `.env`: register every new setting with comments.

**Tools/MCP/DB:**
- SQLite MCP remains the structured source.
- Direct SQLite access is allowed only in ingestion/seed scripts and low-level database utilities, not inside agents.

## 4. Data Flow

**Input:**
- Existing MCP tool result dictionaries from tools such as `search_benefits`, `get_premium_quotes`, `search_waiting_periods`, and `search_claim_payouts`.
- Synthetic user/profile rows.
- Customer intent questions from `docs/customer_intent_scenarios_100_questions.md`.

**Output:**
- Normalized `Evidence` objects with `source_type`, `source_id`, `content`, `metadata`, `confidence`, and `retrieved_by`.
- Citation strings containing available `company_code`, `document_id`, `document_name`, `source_file_path`, `source_table_id`, and page fields.
- `MergedEvidencePacket` containing all collected evidence, flagged conflicts, grouped sources, and complete context.
- 100 benchmark cases with expected `intent_group`, `risk_level`, `workflow`, and `expected_evidence_types`. (Schema only)

## 5. Huong Dan Trien Khai

1. Write failing model tests for required fields, enum values, and invalid source types.
2. Implement `src/models/evidence.py` with strict Pydantic models and typed enums.
3. Write failing adapter tests using representative MCP result fixtures with `source_table_id`, `document_id`, `source_file_path`, `company_code`, and `document_name`.
4. Implement `StructuredEvidenceAdapter.from_mcp_result(tool_name, row)` and `ProfileEvidenceAdapter.from_profile_row(row)`.
5. Write failing merger tests for duplicate source IDs, duplicate content hash, SQLite/Qdrant conflict fixture, and citation preservation.
6. Implement `EvidenceMerger.merge(evidence_items)` as pure Python. Use `source_type + source_id + content_hash` as the dedupe key.
7. Write failing citation tests requiring source lineage for important claims.
8. Implement `CitationFormatter.format(evidence)` and `CitationFormatter.validate_required_fields(evidence)`.
9. Extend `src/models/schema.sql` with synthetic tables using clear foreign-key references to existing company/document/plan IDs where available.
10. Create the seed script with deterministic fixtures first. LLM-generated scaling is deferred to Phase 06.
11. Add integration test that seeds a temporary SQLite database and verifies exactly 100 benchmark cases with valid expected workflow fields.

## 6. Observability

**Log format:** Use existing JSON logger from `src/core/logger.py`.

**Required log metadata:**
- `component`: `structured_evidence_adapter`, `profile_evidence_adapter`, `evidence_merger`, or `synthetic_seed`
- `source_type`
- `source_id`
- `retrieved_by`
- `total_evidence_count`
- `conflict_count`
- `conflict_count`

**Langfuse tracking:** No agent trace is required yet. If integration code touches `DatabaseAgent`, preserve existing Langfuse callback behavior and add metadata only through config/callbacks, not direct global calls in service helpers.

## 7. Testing Strategy

Apply `tdd-workflow`:
- RED: add tests for schema validation, adapter normalization, dedupe, conflict detection, citation fields, and benchmark count.
- GREEN: implement minimum code.
- REFACTOR: remove duplicate fixture builders and keep helpers under `tests/fixtures/` only if repeated by multiple test files.

**Unit tests:**
- `tests/unit/test_evidence_models.py`
- `tests/unit/test_evidence_adapters.py`
- `tests/unit/test_evidence_merger.py`
- `tests/unit/test_citation_formatter.py`

**Integration tests:**
- None in this phase.

**E2E tests:** None in this phase.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run a single failing adapter test with `pytest tests/unit/test_evidence_adapters.py -v`.
- Print JSON logs for one fixture conversion and verify `source_id` and `source_table_id` survive.
- Seed a temporary DB twice to confirm idempotency.

**Verification before next phase:**
- `pytest tests/unit/test_evidence_models.py tests/unit/test_evidence_adapters.py tests/unit/test_evidence_merger.py tests/unit/test_citation_formatter.py -v`
- `pytest tests/unit/test_evidence_models.py tests/unit/test_evidence_adapters.py tests/unit/test_evidence_merger.py tests/unit/test_citation_formatter.py -v`
- `ruff check src tests scripts/06_db_ingestion`
- `ruff format --check src tests scripts/06_db_ingestion`

## 9. Execution Task Breakdown

### Task 1: Evidence Contracts

**Files:**
- Create: `src/models/evidence.py`
- Test: `tests/unit/test_evidence_models.py`

- [ ] Step 1: Write failing tests for `Evidence`, `Citation`, `RetrievalPlan`, `HardFilters`, and `BenchmarkCase`.
- [ ] Step 2: Implement strict Pydantic models with enums for `source_type`, `retrieval_mode`, `intent_group`, `risk_level`, and `workflow`.
- [ ] Step 3: Run `pytest tests/unit/test_evidence_models.py -v`; expected PASS.

### Task 2: Evidence Adapters And Merger

**Files:**
- Create: `src/services/evidence_adapters.py`
- Create: `src/services/evidence_merger.py`
- Create: `src/services/citation_formatter.py`
- Test: `tests/unit/test_evidence_adapters.py`
- Test: `tests/unit/test_evidence_merger.py`
- Test: `tests/unit/test_citation_formatter.py`

- [ ] Step 1: Write failing adapter, merger, and citation tests with explicit MCP fixture rows.
- [ ] Step 2: Implement adapters, dedupe/conflict logic, and citation formatting.
- [ ] Step 3: Run all Phase 01 unit tests; expected PASS.

### Task 3: Synthetic Foundation Schema

**Files:**
- Modify: `src/models/schema.sql`

- [ ] Step 1: Extend `src/models/schema.sql` to include empty tables for `synthetic_users`, `synthetic_policies`, and `synthetic_benchmark_cases`.
- [ ] Step 2: Ensure correct foreign keys are defined for these tables linking to core insurance tables.
