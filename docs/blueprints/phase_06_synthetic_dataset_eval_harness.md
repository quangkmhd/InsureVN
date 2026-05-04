# Phase 06: Synthetic Dataset And Eval Harness

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 06 = Design Spec Phase 5 (Synthetic Dataset + Eval Harness). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 5.

### Dependencies

No new external packages required. Uses existing `pydantic`, `langgraph`, `langfuse` SDK for score attachment.

## 1. Thong Tin Chung

**Muc tieu cot loi:** Make system quality measurable after every prompt, retrieval, or workflow change by first providing a minimal scorer API for Phase 05, then expanding synthetic data and adding offline plus Langfuse-backed evaluation.

**Definition of Done:**
- Full synthetic tables exist for users, policies, dependents, claims, documents, and benchmark cases.
- Generator creates valid records through Pydantic schemas and deterministic foreign-key validation.
- Eval runner can execute benchmark scenarios offline with fixtures where possible.
- Langfuse scores are attached for retrieval, evidence sufficiency, citations, hallucination, workflow, and human review outcome placeholders.
- Success metrics from the design spec are calculated and reported.
- A minimal deterministic scorer API is implemented before full dataset expansion and can be used by Phase 05 specialist workflows.

## 2. Scope

**Can lam:**
- Expand synthetic data from foundation fixtures to lifecycle personas.
- Provide a minimal scorer module early: citation, workflow, evidence sufficiency, and unsupported decision checks.
- Build benchmark runner for the 100 customer intents.
- Add deterministic and LLM-as-judge evaluation with safeguards.
- Write Langfuse score attachment integration.

**Khong duoc lam trong phase nay:**
- Do not use real customer PII/PHI.
- Do not make LLM-as-judge the only evaluator for claim/payout correctness.
- Do not tune prompts blindly without recording eval deltas.
- Do not generate companies, plans, product lines, or document IDs that do not exist in SQLite.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangChain structured output for synthetic generation and LLM-as-judge where needed. Use LangGraph workflow invocation for benchmark runs. Deep Agents can be used by developers as a project execution layer, but the production eval harness remains deterministic Python plus LangGraph calls.

**Files to create:**
- `src/models/synthetic_data.py`
- `src/services/synthetic_data_generator.py`
- `src/services/synthetic_data_validator.py`
- `src/evals/benchmark_runner.py`
- `src/evals/scorers.py`
- `src/evals/langfuse_scores.py`
- `scripts/05_training_eval/06_run_insurevn_benchmark.py`
- `tests/unit/test_synthetic_data_models.py`
- `tests/unit/test_synthetic_data_validator.py`
- `tests/unit/test_eval_scorers.py`
- `tests/integration/test_benchmark_runner.py`
- `tests/integration/test_langfuse_score_attachment.py`

**Files to modify:**
- `src/models/schema.sql`: add `synthetic_dependents`, `synthetic_claims`, `synthetic_documents`, and any missing benchmark columns.
- `src/core/config.py`: add `EVAL_*`, `SYNTHETIC_DATA_*`, and judge model settings with prefixes.
- `.env`: register settings.

**Tools/MCP/DB:**
- SQLite stores synthetic data.
- Langfuse stores traces and scores.
- Existing graph execution API runs scenarios.

## 4. Data Flow

**Input:**
- Existing real insurance metadata from SQLite.
- 100 customer intent scenarios.
- Synthetic generation seed count and deterministic random seed.
- Workflow outputs from phases 04-05.

**Output:**
- Valid synthetic lifecycle dataset.
- Benchmark result records:
  `case_id`, `workflow`, `latency_ms`, `retrieved_sources`, `citations`, `final_output`, `review_packet`, and scores.
- Langfuse scores:
  `retrieval_score`, `evidence_sufficiency_score`, `citation_score`, `hallucination_score`, `workflow_score`, `human_review_outcome`.

## 5. Huong Dan Trien Khai

1. Write failing Pydantic tests for synthetic users, policies, dependents, claims, documents, and benchmark cases.
2. Implement `src/models/synthetic_data.py`.
3. Write failing validator tests that reject unknown `company_code`, `document_id`, `plan_type_id`, and invalid claim references.
4. Implement `SyntheticDataValidator` against SQLite metadata.
5. Write failing generator tests using a mocked structured-output model.
6. Implement small-batch generation: 30-50 personas first, then configurable scale.
7. Write failing scorer tests for deterministic citation, workflow, high-risk routing, and unsupported payout checks. This step may be executed before Phase 05 starts.
8. Implement deterministic scorers as the minimal eval API consumed by Phase 05. Add LLM-as-judge only for groundedness, answer correctness, tone clarity, and missing-evidence reasoning.
9. Write failing benchmark runner integration test with three fixture cases.
10. Implement `BenchmarkRunner` to invoke the LangGraph app with stable `thread_id`.
11. Write failing Langfuse score test with mocked SDK.
12. Implement `LangfuseScoreClient` wrapper to attach scores to traces, observations, sessions, or dataset runs.
13. Add CLI script to run all 100 cases and write JSON report under `docs/reports/` or configured output path.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `synthetic_data_generator`, `synthetic_data_validator`, `benchmark_runner`, `eval_scorer`, `langfuse_scores`
- `case_id`
- `session_id`
- `thread_id`
- `workflow`
- `latency_ms`
- `score_name`
- `score_value`
- `judge_model`
- `deterministic_score`

**Langfuse tracking:**
- Dataset run per benchmark execution.
- Trace metadata: `benchmark_case_id`, expected intent/risk/workflow, synthetic profile ID, workflow.
- Scores: deterministic scores first, LLM judge scores clearly marked with judge model and prompt version.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Synthetic data schemas.
- Foreign-key validator.
- Deterministic scorers.
- Langfuse score payload builder.

**Integration tests:**
- Benchmark runner with mocked graph.
- Langfuse score attachment with mocked Langfuse client.
- SQLite synthetic seed/generate/validate loop.

**E2E tests:**
- Run all 100 benchmark scenarios in offline fixture mode.
- Run a smaller live workflow sample before using model-heavy full evaluation.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/unit/test_eval_scorers.py -v`.
- Re-run a single case with `scripts/05_training_eval/06_run_insurevn_benchmark.py --case-id Q076`.
- Compare deterministic score JSON against Langfuse score payload.

**Verification before next phase:**
- `pytest tests/unit/test_synthetic_data_models.py tests/unit/test_synthetic_data_validator.py tests/unit/test_eval_scorers.py -v`
- `pytest tests/integration/test_benchmark_runner.py tests/integration/test_langfuse_score_attachment.py -v`
- `python scripts/05_training_eval/06_run_insurevn_benchmark.py --offline-fixtures`
- `ruff check src tests scripts/05_training_eval`
- `ruff format --check src tests scripts/05_training_eval`

## 9. Execution Task Breakdown

### Task 1: Minimal Deterministic Scorers

**Files:**
- Create: `src/evals/scorers.py`
- Test: `tests/unit/test_eval_scorers.py`

- [ ] Step 1: Write failing tests for citation, workflow, evidence sufficiency, and unsupported decision scoring.
- [ ] Step 2: Implement deterministic scorer functions used by Phase 05.
- [ ] Step 3: Run `pytest tests/unit/test_eval_scorers.py -v`; expected PASS.

### Task 2: Synthetic Data Expansion

**Files:**
- Create: `src/models/synthetic_data.py`
- Create: `src/services/synthetic_data_generator.py`
- Create: `src/services/synthetic_data_validator.py`
- Modify: `src/models/schema.sql`
- Test: `tests/unit/test_synthetic_data_models.py`
- Test: `tests/unit/test_synthetic_data_validator.py`

- [ ] Step 1: Write failing schema and FK validator tests.
- [ ] Step 2: Implement models, validator, and small-batch generator.
- [ ] Step 3: Run synthetic unit tests; expected PASS.

### Task 3: Benchmark Runner And Langfuse Scores

**Files:**
- Create: `src/evals/benchmark_runner.py`
- Create: `src/evals/langfuse_scores.py`
- Create: `scripts/05_training_eval/06_run_insurevn_benchmark.py`
- Test: `tests/integration/test_benchmark_runner.py`
- Test: `tests/integration/test_langfuse_score_attachment.py`

- [ ] Step 1: Write failing integration tests with mocked graph and mocked Langfuse client.
- [ ] Step 2: Implement benchmark runner, score attachment wrapper, and CLI report output.
- [ ] Step 3: Run Phase 06 verification commands; expected PASS.
