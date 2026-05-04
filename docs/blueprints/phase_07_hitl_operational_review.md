# Phase 07: HITL Operational Review And Production Readiness

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 07 = Design Spec Phase 6 (HITL Review Workflow). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 6.

### Dependencies

New packages to install:
- `langgraph-checkpoint-postgres` — persistent checkpointing for production
- `psycopg[binary]` — PostgreSQL driver for checkpoint backend

## 1. Thong Tin Chung

**Muc tieu cot loi:** Add human-in-the-loop customer confirmation and employee approval using persistent LangGraph checkpointing, then harden the operational path for high-risk claims, payout, rejection, and recommendation review.

**Definition of Done:**
- High-risk workflows pause for customer confirmation before final decision drafting.
- Employee approval/edit/reject interrupt gates final claim, payout, rejection, appeal, and high-impact recommendations.
- Workflow resumes with the same `thread_id` after process restart using persistent checkpointing.
- Review outcomes are stored, logged, and scored.
- No unsupported payout final decision can bypass review.
- Employee approval APIs enforce explicit reviewer identity and role authorization.
- Audit trail records review packet ID, reviewer ID, outcome, timestamp, and final release decision.

## 2. Scope

**Can lam:**
- Implement `ReviewPacket` schema and persistence.
- Add LangGraph interrupts for customer confirmation and employee approval.
- Add API/service boundaries for starting and resuming workflows.
- Add production readiness checks for logging, Langfuse metadata, checkpoint configuration, and security-sensitive paths.
- Add lightweight RBAC/authorization boundary for employee review actions.
- Add immutable audit outcome records for customer and employee review decisions.

**Khong duoc lam trong phase nay:**
- Do not build a full employee UI unless separately specified.
- Do not store real PII/PHI beyond synthetic/test records.
- Do not use `MemorySaver` for review flows.
- Do not allow approval state to be inferred from user text without explicit resume payload.
- Do not accept employee approval without authenticated reviewer identity and required role.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangGraph interrupts, `Command(resume=...)`, and persistent checkpointers for HITL. Use LangChain only inside existing agent nodes. Deep Agents may be considered later for internal operator tooling, but production review flow must remain explicit LangGraph control.

**Files to create:**
- `src/models/review.py`
- `src/services/checkpointing.py`
- `src/services/review_outcomes.py`
- `src/services/review_authorization.py`
- `src/services/review_audit.py`
- `src/api/routes/workflows.py`
- `tests/unit/test_review_models.py`
- `tests/unit/test_review_outcomes.py`
- `tests/unit/test_review_authorization.py`
- `tests/unit/test_review_audit.py`
- `tests/integration/test_hitl_interrupts.py`
- `tests/integration/test_checkpoint_resume.py`
- `tests/e2e/test_high_risk_hitl_flow.py`

**Files to modify:**
- `src/agents/insurevn_graph.py`: add interrupt nodes and resume handling.
- `src/core/config.py`: add `WORKFLOW_CHECKPOINTER_*`, `HITL_*`, and API route settings.
- `src/models/schema.sql`: add review outcome/audit tables if SQLite is the chosen audit store.
- `.env`: register checkpoint and HITL settings.
- `src/main.py`: include workflow routes through the Phase 00 FastAPI app entrypoint.

**Tools/MCP/DB:**
- Dev/local: SQLite checkpointer from `langgraph-checkpoint-sqlite`.
- Production-like: Postgres checkpointer from `langgraph-checkpoint-postgres`.
- SQLite application DB stores review outcome records or references if not already captured by checkpoint state.
- Review authorization uses a minimal internal role model in this phase. External identity provider integration is deferred, but API payloads must include explicit reviewer identity and role for testability.

## 4. Data Flow

**Input:**
- High-risk graph state with `review_packet`.
- Customer confirmation payload:
  `confirmed`, corrected facts, missing document notes, and questions answered.
- Employee review payload:
  `approved`, `edited`, `rejected`, `needs_more_evidence`, edited final response, and reviewer metadata.
- Employee authorization payload:
  reviewer ID, role, session ID, and requested action.

**Output:**
- Resumed graph state with explicit review outcome.
- Final customer/employee response only when approval rules pass.
- Audit log and Langfuse trace metadata with review decisions.
- Durable review audit row or append-only audit event.

## 5. Huong Dan Trien Khai

1. Write failing model tests for customer confirmation packet, employee review packet, and review outcomes.
2. Implement `src/models/review.py` with explicit enums: `customer_confirmed`, `customer_corrected`, `employee_approved`, `employee_edited`, `employee_rejected`, `needs_more_evidence`.
3. Write failing checkpoint tests that reject `MemorySaver` for HITL workflows.
4. Implement `src/services/checkpointing.py` with SQLite dev and Postgres production factory functions.
5. Write failing interrupt integration test for high-risk claim pausing at customer confirmation.
6. Add customer confirmation interrupt node using LangGraph `interrupt(...)`.
7. Write failing resume test where corrected facts trigger RuleChecker and Calculator recomputation.
8. Implement resume path with `Command(resume=...)` and explicit correction handling.
9. Write failing employee approval tests for approve, edit, reject, and needs-more-evidence.
10. Write failing authorization tests proving missing reviewer identity, wrong role, or mismatched session cannot approve.
11. Implement `ReviewAuthorizationService` and integrate it before resume approval.
12. Write failing audit tests for append-only customer and employee review outcomes.
13. Implement `ReviewAuditService` and optional SQLite audit table.
14. Add employee approval interrupt node and final response gate.
15. Write failing API tests for start workflow, get interrupt state, resume workflow, and get final output.
16. Implement workflow API routes with typed request/response models.
17. Add E2E test that restarts the graph/checkpointer factory and resumes the same `thread_id`.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `hitl_customer_confirmation`, `hitl_employee_review`, `checkpointing`, `workflow_api`
- `session_id`
- `thread_id`
- `user_id`
- `review_packet_id`
- `review_outcome`
- `employee_reviewer_id` when available
- `employee_reviewer_role`
- `authorization_status`
- `resume_attempt`
- `checkpoint_backend`
- `final_decision_released`

**Langfuse tracking:**
- Nodes: `customer-confirmation-interrupt`, `employee-review-interrupt`, `workflow-resume`, `final-response-gate`.
- Metadata: review packet ID, outcome, corrected facts count, employee edit flag, checkpoint backend, resume latency.
- Scores: `human_review_outcome`, `workflow_score`, `unsupported_decision_blocked`.
- Audit metadata: audit event ID, review packet ID, reviewer ID, authorization status.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Review schemas and outcome transitions.
- Review authorization role checks.
- Append-only audit event creation.
- Checkpointer factory validation.
- Final response gate logic.

**Integration tests:**
- Customer interrupt/resume.
- Employee interrupt/resume.
- Persistent checkpoint resume.
- API route contract tests.
- Unauthorized employee review payload rejection.

**E2E tests:**
- High-risk claim from user query to customer confirmation, employee approval, and final response.
- Employee rejection prevents final decision.
- Customer-corrected facts trigger recomputation.
- Unauthorized employee approval cannot release final response.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/integration/test_hitl_interrupts.py -v`.
- Inspect graph state with `graph.get_state(config, subgraphs=True)` for the stuck `thread_id`.
- Replay one `Command(resume=...)` payload from test fixtures.

**Verification before production hardening sign-off:**
- `pytest tests/unit/test_review_models.py tests/unit/test_review_outcomes.py -v`
- `pytest tests/unit/test_review_authorization.py tests/unit/test_review_audit.py -v`
- `pytest tests/integration/test_hitl_interrupts.py tests/integration/test_checkpoint_resume.py -v`
- `pytest tests/e2e/test_high_risk_hitl_flow.py -v`
- `python scripts/05_training_eval/06_run_insurevn_benchmark.py --offline-fixtures`
- `ruff check src tests`
- `ruff format --check src tests`

## 9. Execution Task Breakdown

### Task 1: Review Models, Checkpointing, And Interrupts

**Files:**
- Create: `src/models/review.py`
- Create: `src/services/checkpointing.py`
- Modify: `src/agents/insurevn_graph.py`
- Test: `tests/unit/test_review_models.py`
- Test: `tests/integration/test_hitl_interrupts.py`
- Test: `tests/integration/test_checkpoint_resume.py`

- [ ] Step 1: Write failing review schema and checkpoint tests.
- [ ] Step 2: Implement persistent checkpointer factory and customer/employee interrupt nodes.
- [ ] Step 3: Run HITL unit and integration tests; expected PASS.

### Task 2: Authorization And Audit

**Files:**
- Create: `src/services/review_authorization.py`
- Create: `src/services/review_audit.py`
- Modify: `src/models/schema.sql`
- Test: `tests/unit/test_review_authorization.py`
- Test: `tests/unit/test_review_audit.py`

- [ ] Step 1: Write failing tests for missing reviewer, wrong role, mismatched session, and append-only audit records.
- [ ] Step 2: Implement authorization and audit services.
- [ ] Step 3: Run authorization and audit tests; expected PASS.

### Task 3: Workflow API And E2E Gate

**Files:**
- Create: `src/api/routes/workflows.py`
- Modify: `src/main.py`
- Test: `tests/e2e/test_high_risk_hitl_flow.py`

- [ ] Step 1: Write failing API and E2E resume tests.
- [ ] Step 2: Implement start/resume/final-output routes with explicit approval payloads.
- [ ] Step 3: Run Phase 07 verification commands; expected PASS.
