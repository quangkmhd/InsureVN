# Phase 05: Specialist Workflows

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 05 = Design Spec Phase 4 (Specialist Workflows). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 4.

### Dependencies

No new external packages required beyond Phase 04 dependencies. All agent nodes use existing `langgraph`, `langchain`, `langfuse`.

## 1. Thong Tin Chung

**Muc tieu cot loi:** Implement the three main vertical workflows end-to-end: Fast Policy Q&A, Verified Compare/Advisor, and High-Risk Claim/Payout with deterministic validation and calculation nodes.

**Definition of Done:**
- Fast Policy Lane retrieves evidence and returns cited policy answers.
- Verified Compare/Advisor Lane uses SQLite facts, document context, graph paths, and profile data.
- High-Risk Claim/Payout Lane calls RuleChecker and Calculator before drafting a decision.
- `VerifierAgent` blocks unsupported answers and missing citations.
- `SearchAgent` is available as an optional tool for comparison/advisor market queries, not a core graph node.
- `OCR DocumentAgent` stub accepts fixture images/data and returns structured evidence for the High-Risk Lane. Real OCR integration is deferred to post-foundation.

**Quantitative success criteria (from design spec):**
- 0 unsupported payout final decisions without review
- Every important answer has citation
- SQLite/Qdrant/Graph conflict becomes review-required
- Fast Lane P95 latency < 5s
- Verified Lane P95 latency < 15s
- High-risk Lane P95 latency < 30s
- Evidence recall >= 80% (expected sources actually retrieved)
- Minimal benchmark scorer from Phase 06 is available before prompt-heavy specialist work begins, so each lane can report citation/workflow/evidence scores during development.

## 2. Scope

**Can lam:**
- Build PolicyAgent, ComparisonAdvisorAgent, ClaimAgent, ValidationAgent, CalculationAgent, and VerifierAgent nodes.
- Build OCR DocumentAgent stub with fixture data for High-Risk Lane evidence processing.
- Wire retrieval providers from phases 01-03 into lane execution via EnsembleRetriever (Phase 04).
- Implement `Send`-based dynamic fan-out for multi-company comparison queries.
- Add deterministic RuleChecker and Calculator functions.
- Build review packet drafts without HITL pauses.
- Add per-lane benchmark result emission compatible with the eval harness.

**Khong duoc lam trong phase nay:**
- Do not implement customer/employee interrupts yet.
- Do not allow LLMs to calculate payouts without deterministic calculator output.
- Do not let PolicyAgent answer claim decisions.
- Do not let VerifierAgent invent a replacement answer; it can approve, block, or request correction.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangGraph for lane orchestration, parallel retrieval branches, validation loops, and specialist node control. Use LangChain for model calls, tools, structured output, RAG context formatting, and optional SearchAgent tool use. Deep Agents remains an optional top-level future shell for complex operator tasks and skill loading.

**Files to create:**
- `src/agents/policy_agent.py`
- `src/agents/comparison_advisor_agent.py`
- `src/agents/claim_agent.py`
- `src/agents/validation_agent.py`
- `src/agents/calculation_agent.py`
- `src/agents/verifier_agent.py`
- `src/agents/ocr_document_agent.py`: Stub/fixture-backed agent for the High-Risk Lane. Accepts fixture data (JSON representing medical bills, ID cards, claim forms) and returns `Evidence(source_type="document_extract")`. Real OCR (PDF/image processing) is deferred to post-foundation.
- `src/services/rule_checker.py`
- `src/services/calculators.py`
- `src/services/review_packet_builder.py`
- `tests/unit/test_rule_checker.py`
- `tests/unit/test_calculators.py`
- `tests/unit/test_verifier_agent.py`
- `tests/unit/test_ocr_document_agent.py`
- `tests/integration/test_policy_lane.py`
- `tests/integration/test_comparison_advisor_lane.py`
- `tests/integration/test_claim_lane.py`
- `tests/e2e/test_specialist_workflows.py`
- `tests/e2e/test_specialist_workflow_scores.py`

**Files to modify:**
- `src/agents/insurevn_graph.py`: replace lane stubs with real nodes and conditional validation loop.
- `src/core/config.py`: add `POLICY_LLM_*`, `ADVISOR_LLM_*`, `CLAIM_LLM_*`, `VALIDATION_LLM_*`, and `VERIFIER_LLM_*`.
- `.env`: register every specialist setting.

**Tools/MCP/DB:**
- DatabaseAgent via SQLite MCP for structured facts.
- Qdrant retriever for policy text.
- GraphRetriever for relationship evidence.
- Profile adapter for synthetic user context.
- SearchAgent tool only for optional market context in advisor flows.

## 4. Data Flow

**Input:**
- Graph state from Supervisor with `workflow`, `retrieval_plan`, validated hard filters, user profile, and messages.
- Evidence from SQLite, Qdrant, graph, profile, and optional document fixtures.

**Output:**
- `draft_decisions` containing policy answer, recommendation packet, or claim draft.
- `review_packet` for high-risk flows.
- `final_output` only when Verifier approves.
- `blocked_reason` or `correction_request` when validation fails.

## 5. Huong Dan Trien Khai

1. Write failing unit tests for `RuleChecker` exclusions, waiting periods, missing evidence, and unsupported claim states.
2. Implement `src/services/rule_checker.py` as deterministic Python.
3. Write failing calculator tests for payout, premium comparison totals, pro-rata refund, and invalid numeric inputs.
4. Implement `src/services/calculators.py`; no LLM calls are allowed.
5. Write failing PolicyAgent integration test requiring citation on every important answer claim.
6. Implement PolicyAgent node with evidence-only prompt and structured response.
7. Write failing ComparisonAdvisor lane test requiring SQLite premium/benefit facts plus Qdrant/Graph context.
8. Implement ComparisonAdvisorAgent node and optional SearchAgent tool wrapper.
9. Write failing Claim lane test requiring RuleChecker and Calculator calls before ClaimAgent draft.
10. Implement ClaimAgent node and review packet draft builder.
11. Write failing Verifier tests for unsupported payout, missing citation, and evidence conflict.
12. Implement ValidationAgent and VerifierAgent with structured approve/block/correct outputs.
13. Wire validation loop in LangGraph: specialist draft -> validation -> correction path or verifier -> final.
14. Add minimal scorer calls for `citation_score`, `workflow_score`, `evidence_sufficiency_score`, and `unsupported_decision_blocked` in lane test/eval mode.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: specialist agent or deterministic service name.
- `session_id`, `user_id`, `workflow`, `risk_level`
- `evidence_count_by_source`
- `citation_count`
- `rule_check_result`
- `calculator_result_id`
- `validation_status`
- `verifier_status`
- `correction_loop_count`

**Langfuse tracking:**
- Nodes: `policy-agent`, `comparison-advisor-agent`, `claim-agent`, `rule-checker`, `calculator`, `validation-agent`, `verifier-agent`.
- Metadata: prompt version, model provider/model, evidence source counts, citation IDs, rule outcomes, calculator output hash, correction loop count.
- Scores in tests/evals: `citation_score`, `workflow_score`, `evidence_sufficiency_score`, `unsupported_decision_blocked`.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- RuleChecker.
- Calculator.
- Verifier approval/block logic.
- Review packet builder.

**Integration tests:**
- Fast Policy Lane with fixture evidence.
- Verified Compare/Advisor Lane with SQLite + Qdrant + graph fixtures.
- High-risk Claim Lane with RuleChecker + Calculator + ClaimAgent.

**E2E tests:**
- One representative case per major customer intent group.
- High-risk claim/payout scenario must not produce final decision without review packet readiness.
- Score emission exists for each specialist workflow and can be consumed by Phase 06 full benchmark runner.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/integration/test_claim_lane.py -v`.
- Inspect Langfuse trace for missing `rule-checker` or `calculator` node before ClaimAgent.
- Dump `review_packet` JSON and verify citations and conflicts are present.

**Verification before next phase:**
- `pytest tests/unit/test_rule_checker.py tests/unit/test_calculators.py tests/unit/test_verifier_agent.py -v`
- `pytest tests/integration/test_policy_lane.py tests/integration/test_comparison_advisor_lane.py tests/integration/test_claim_lane.py -v`
- `pytest tests/e2e/test_specialist_workflows.py -v`
- `pytest tests/e2e/test_specialist_workflow_scores.py -v`
- `ruff check src tests`
- `ruff format --check src tests`

## 9. Execution Task Breakdown

### Task 1: Deterministic Rule And Calculation Layer

**Files:**
- Create: `src/services/rule_checker.py`
- Create: `src/services/calculators.py`
- Test: `tests/unit/test_rule_checker.py`
- Test: `tests/unit/test_calculators.py`

- [ ] Step 1: Write failing unit tests for exclusions, waiting periods, payout, premiums, and invalid inputs.
- [ ] Step 2: Implement deterministic services with no LLM calls.
- [ ] Step 3: Run deterministic unit tests; expected PASS.

### Task 2: Specialist Agents

**Files:**
- Create: `src/agents/policy_agent.py`
- Create: `src/agents/comparison_advisor_agent.py`
- Create: `src/agents/claim_agent.py`
- Create: `src/services/review_packet_builder.py`
- Test: `tests/integration/test_policy_lane.py`
- Test: `tests/integration/test_comparison_advisor_lane.py`
- Test: `tests/integration/test_claim_lane.py`

- [ ] Step 1: Write failing lane integration tests using fixture evidence.
- [ ] Step 2: Implement evidence-only specialist nodes and review packet builder.
- [ ] Step 3: Run lane integration tests; expected PASS.

### Task 3: Validation, Verifier, And Scores

**Files:**
- Create: `src/agents/validation_agent.py`
- Create: `src/agents/verifier_agent.py`
- Modify: `src/agents/insurevn_graph.py`
- Test: `tests/unit/test_verifier_agent.py`
- Test: `tests/e2e/test_specialist_workflows.py`
- Test: `tests/e2e/test_specialist_workflow_scores.py`

- [ ] Step 1: Write failing verifier, validation-loop, and score-emission tests.
- [ ] Step 2: Implement approve/block/correct outputs and graph validation loop.
- [ ] Step 3: Run Phase 05 unit, integration, and E2E tests; expected PASS.
