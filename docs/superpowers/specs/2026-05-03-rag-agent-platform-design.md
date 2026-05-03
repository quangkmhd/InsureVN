# Design Spec: RAG Agent Platform for InsureVN

## Status

Draft in progress. Sections 1-5 are reviewed in conversation. Final self-review and user approval are pending.

## Decision Log

| Question | Decision |
|---|---|
| Which RAG product scope should be covered first: Policy Q&A, Claim Advisory, or Product Comparison? | Cover all three and solve all 100 scenarios in `docs/customer_intent_scenarios_100_questions.md`. |
| Production posture: local-first, hybrid, or accuracy-first cloud? | Hybrid production. Use local/small models for cheaper tasks and stronger models for hard/final reasoning. |
| First product target: balanced assistant, claim-safe advisor, or comparison engine? | Cover all three target areas. |
| Build order: foundation first, user-flow first, or claim first? | Foundation first. |
| Data source strategy: Markdown-primary, SQLite-primary, or dual-canonical? | Dual-canonical: SQLite for structured facts, Qdrant for document text. |
| SLA strategy: strict fast, balanced lanes, or strict accuracy? | Balanced lanes. Simple questions should be fast; comparison/claim can be slower and more verified. |
| Architecture option: monolithic RAG, routed RAG platform, or full agent swarm? | Full agent swarm. |
| Swarm control style: autonomous agents, orchestrated workflows, or hybrid swarm? | Hybrid swarm. High-risk workflows are controlled; low-risk explanation can be more flexible. |
| Foundation release agent priority: Policy/Evidence, Claim/Rule/Calculator, or Comparison/Advisor? | Include all three verticals in the foundation release, but build them through shared evidence foundation. |
| User data source: chat intake, SQLite profiles, or hybrid? | No real user data. Use AI-generated synthetic data set up before user interaction. |
| Synthetic data scope: basic personas, lifecycle personas, or benchmark dataset? | Include all three: basic personas, lifecycle personas, and benchmark cases. |
| Legal/operational responsibility: advisory, decision support, or operational automation? | Operational automation that creates draft decisions/recommendations. |
| Human review flow: employee first, customer first, or two-step? | Two-step: customer confirms input facts; employee reviews final decision/payout/recommendation. |
| Visual companion usage? | Accepted initially, then user asked to stop updating the browser each question and continue by text. |

## 1. Core Architecture

InsureVN will use a **Hybrid Full Agent Swarm** with a shared evidence foundation. It is not a single monolithic RAG agent.

High-level flow:

```text
User / Synthetic Scenario
-> SupervisorAgent
   - intent classification
   - risk classification
   - evidence plan
   - workflow selection
-> Parallel Evidence Gathering
   - Qdrant Retriever
   - DatabaseAgent / SQLite MCP
   - Synthetic Profile Store
   - Document fixtures/OCR later
-> Specialist Workflow
   - PolicyAgent
   - ComparisonAdvisorAgent
   - ClaimAgent + Rule/Calculator tools
-> VerifierAgent
-> Review Packet
-> Customer confirms input
-> Employee approves final decision
```

The initial implementation should combine orchestrator, intent router, risk router, and evidence planner into one `SupervisorAgent` node to reduce sequential LLM calls. The boundaries still remain explicit in the structured output and tests.

Domain capabilities:

- `SupervisorAgent`: classifies intent/risk, creates retrieval plan, selects workflow.
- `PolicyAgent`: explains policy clauses, exclusions, waiting periods, claim procedures, and glossary terms from evidence.
- `DatabaseAgent`: existing structured data agent over SQLite MCP.
- `ComparisonAdvisorAgent`: compares plans, ranks options, and personalizes recommendations.
- `ClaimAgent`: drafts claim decisions, missing-document guidance, rejection/appeal explanations.
- `VerifierAgent`: checks evidence sufficiency, citations, conflicts, and risk gates.
- `RuleChecker`: deterministic Python rule logic, not an LLM agent in v1.
- `Calculator`: deterministic Python payout, premium, deductible, and limit calculations, not an LLM agent in v1.
- `DocumentAgent`: fixture-backed in the foundation release; later connected to real OCR/document extraction.

High-risk flows such as claim, payout, rejection, appeal, and fraud suspicion must be orchestrated workflows with strict evidence contracts and human review. Lower-risk explanation and research tasks may use more flexible agent behavior.

## 2. Data & Evidence Layer

The data strategy is **dual-canonical**:

```text
SQLite = structured canonical source
Qdrant = document canonical source
```

SQLite already exists as a structured evidence provider through the FastMCP server and `DatabaseAgent`. The RAG platform should not redesign SQLite retrieval. It should add adapters that normalize existing MCP results into shared evidence objects.

Existing SQLite MCP tools include:

- `search_benefits`
- `compare_benefits`
- `get_benefit_matrix`
- `get_premium_quotes`
- `search_hospitals`
- `search_waiting_periods`
- `search_claim_payouts`
- `search_glossary_terms`
- `search_exclusions`
- `get_raw_source`
- `list_documents`
- `list_source_tables`

Most MCP results already include source lineage such as `source_table_id`, `document_id`, `source_file_path`, `company_code`, and `document_name`.

Shared evidence schema:

```text
Evidence
- evidence_id
- source_type: sqlite_row | qdrant_chunk | synthetic_profile | document_extract
- source_id
- content
- metadata
- confidence
- retrieved_by
```

SQLite evidence should be produced by a `StructuredEvidenceAdapter`:

```text
MCP tool result
-> StructuredEvidenceAdapter
-> Evidence(source_type="sqlite_row", source_id=source_table_id/tool/row, metadata=...)
-> shared gathered_evidence state
```

Qdrant payload fields:

```text
company_code
document_id
document_type
document_name
product_line
plan_code
section_type
page_number
chunk_index
source_path
source_table_id
effective_date
language
```

Qdrant retrieval must use hard filters when the user question names or implies a specific company, product, plan, document type, or section. Embedding-only search is not acceptable for company/product-specific insurance questions because policy language is similar across insurers.

`RetrievalPlan` should include:

```text
query_text
hard_filters:
  company_code
  document_id
  document_type
  product_line
  plan_code
  section_type
  language
retrieval_mode: vector | keyword | hybrid
expansion_mode: child_only | parent_section | sibling_window
top_k
rerank_required
```

Qdrant should use a parent-child retrieval pattern:

```text
search child chunks -> expand to parent section -> evidence uses expanded parent text
```

Child chunks optimize search precision. Parent sections preserve legal/policy context.

Retrieval lanes:

- Fast Lane: glossary and simple policy Q&A. Use small `top_k`, hard filters where available, and no raw-source verification by default.
- Verified Lane: comparison, advisor, product recommendation. Run Qdrant and SQLite retrieval in parallel, merge/deduplicate evidence, and rerank or score evidence.
- High-risk Lane: claim eligibility, payout, rejection, appeal, fraud suspicion. Require SQLite facts for limits, payout, waiting period, premium, or network questions. Use `get_raw_source` when source-table verification is needed.

Evidence merge rules:

- SQLite is preferred for normalized numbers: amount, limit, premium, waiting days, payout rate.
- Qdrant is preferred for legal wording, conditions, exceptions, and explanatory context.
- If SQLite and Qdrant conflict, mark the conflict and route to human review.

Citation requirements:

Every important answer or draft decision must keep enough source lineage for employee review:

```text
company
document_name
document_id
source_file_path or source_path
page_number when available
source_table_id when available
```

Knowledge Graph enrichment is useful later, but not required in the foundation release. Vector + keyword/hybrid search and SQLite source lineage should be stabilized first.

## 3. Agent Workflows & Routing

The platform uses a **Hybrid Swarm**: specialist capabilities exist, but high-risk flows are controlled by LangGraph state, routing, and verification gates.

Core graph state:

```text
messages
user_profile
synthetic_scenario
intent
risk_level
retrieval_plan
gathered_evidence
draft_decisions
review_packet
final_output
```

Append-only fields should use reducers so parallel nodes do not overwrite one another:

```text
gathered_evidence
draft_decisions
messages
```

The `SupervisorAgent` should use structured output, ideally with a Pydantic schema and `llm.with_structured_output(...)`. Local/Ollama models may need JSON repair fallback, while stronger hybrid/cloud models should be preferred for reliable routing.

Supervisor output:

```text
intent_group: policy_qa | comparison | advisory | claim | payout | onboarding | renewal
risk_level: low | medium | high
workflow: fast_policy | verified_compare | high_risk_claim | lifecycle_advisory
required_evidence: qdrant | sqlite | profile | document
hard_filters
needs_clarification
clarification_question
```

Fast Policy Lane:

```text
Supervisor
-> Qdrant/MCP glossary retrieval
-> PolicyAgent
-> Citation check
-> Answer
```

Verified Compare/Advisor Lane:

```text
Supervisor
-> parallel SQLite MCP + Qdrant retrieval + synthetic profile lookup
-> EvidenceMerger
-> ComparisonAdvisorAgent
-> VerifierAgent
-> Recommendation packet
```

High-risk Claim/Payout Lane:

```text
Supervisor
-> profile/policy lookup
-> SQLite MCP: benefits, waiting periods, claim payouts, hospitals
-> Qdrant: clauses, exclusions, claim process
-> EvidenceMerger
-> RuleChecker
-> Calculator tools
-> ClaimAgent drafts decision
-> VerifierAgent
-> Customer confirms input
-> Employee reviews final decision
```

`EvidenceMerger` should be pure Python in the foundation release:

```text
normalize source keys
deduplicate by source_type + source_id + content hash
group by company/document/plan
detect simple conflicts
build compact evidence context
preserve citations
```

Parallel retrieval:

- Fixed providers can be routed through conditional edges to multiple nodes.
- Dynamic fan-out, such as multiple Qdrant tasks per company/product/query, should use LangGraph `Send`.

Specialist boundaries:

- `PolicyAgent` explains only from evidence and does not calculate payout.
- `ComparisonAdvisorAgent` ranks and recommends, but structured facts come from SQLite/evidence.
- `ClaimAgent` drafts claim decisions, but deterministic checks and calculations use tools/nodes.
- `VerifierAgent` checks evidence quality and risk; it does not invent a new answer.
- `DatabaseAgent` remains the existing structured data specialist over MCP.

Human-in-the-loop:

```text
Draft decision
-> customer confirms facts/input
-> employee approves/edits/rejects
-> final response
```

LangGraph interrupts and checkpointing should be used for the customer confirmation and employee approval pauses.

## 4. Synthetic Data, Evaluation & Review

The foundation release will use AI-generated synthetic user data because the project does not yet have real customer profiles, contracts, or claim histories. Synthetic data must be stored like product data so agents can query it through normal workflows.

Synthetic data layers:

```text
1. Basic Personas
- age
- gender
- income
- job
- city
- family/dependents
- lifestyle
- health background
- risk tolerance

2. Lifecycle Personas
- active policies
- plan/company/product_line
- effective date
- payment status
- renewal date
- dependents
- preferred hospitals
- previous claims
- claim statuses

3. Scenario Benchmark Cases
- maps to the 100 customer intents
- user profile
- input question
- expected evidence types
- expected behavior
- risk level
- acceptance criteria
```

Synthetic data should be stored in SQLite with clearly prefixed tables:

```text
synthetic_users
synthetic_policies
synthetic_dependents
synthetic_claims
synthetic_documents
synthetic_benchmark_cases
```

Synthetic data generation should use LLM structured output plus deterministic validation:

```text
LLM + Pydantic schema
-> small seed generation
-> deterministic validation
-> SQLite insert
-> benchmark/eval run
-> scale up only after validation passes
```

Start with 30-50 personas and 100 benchmark cases mapped to the 100 intent scenarios. Scale to 500-1,000 personas only after the schema, validation, and eval loop are stable.

Synthetic data must reference real insurance data where possible:

```text
company_code
document_id
plan_type_id
product_line
plan_code
```

The generator must not invent companies, product lines, or plan identifiers that do not exist in the real SQLite insurance tables.

Evaluation layers:

```text
Retrieval eval:
- correct company/product/document
- hard filters used when required
- source_table_id/document_id/page retained

Evidence eval:
- sufficient evidence for answer
- SQLite vs Qdrant conflicts detected
- citations trace back to source

Answer eval:
- correct intent
- no hallucinated numbers/benefits
- admits missing evidence when evidence is incomplete

Workflow eval:
- claim/payout uses RuleChecker and Calculator
- high-risk flows create review packets
- HITL pauses at customer confirmation and employee review
```

Langfuse Scores should be used for repeatable evaluation. Current Langfuse docs support attaching scores to traces, observations, sessions, and dataset runs through the SDK/API.

Recommended scores:

```text
retrieval_score
evidence_sufficiency_score
citation_score
hallucination_score
workflow_score
human_review_outcome
```

Use deterministic scores where possible:

```text
citation_score = 1 if every important claim has citation, else 0
workflow_score = 1 if high-risk claim went through RuleChecker + Calculator + HITL, else 0
```

Use LLM-as-a-Judge only for qualitative dimensions:

```text
answer_correctness
groundedness
tone_clarity
missing_evidence_reasoning
```

LLM-as-a-Judge must not be the only evaluator for high-risk claim/payout decisions.

Human review packets:

Customer confirmation packet:

```text
user profile facts used
policy assumed
claim/event details assumed
documents received/missing
questions needing confirmation
```

Employee review packet:

```text
draft decision
payout estimate if any
rule checks
calculator output
evidence list with citations
conflicts or missing evidence
recommended final action
editable final response
```

Review outcomes:

```text
customer_confirmed
customer_corrected
employee_approved
employee_edited
employee_rejected
needs_more_evidence
```

## 5. Implementation Phasing & Testing

Because the scope is large, implementation should be split into verticals that can be tested independently.

### Phase 1: Evidence Foundation

Goal: normalize evidence from existing SQLite MCP, minimal synthetic profiles, and Qdrant stubs/fixtures.

Build:

```text
Evidence schema
StructuredEvidenceAdapter for existing SQLite MCP results
synthetic_users and synthetic_policies minimal tables
basic synthetic seed data, deterministic or small hand-authored fixture
profile lookup adapter
EvidenceMerger pure Python
Citation formatter
RetrievalPlan schema
```

Tests:

```text
MCP row -> Evidence object
profile row -> Evidence object
deduplicate evidence by source_id/content hash
citation contains document_id/source_table_id/source_file_path
conflict detection between SQLite and Qdrant fixture
```

### Phase 2: Qdrant Document Retrieval

Goal: add the document canonical source.

Build:

```text
Markdown/PDF chunking pipeline
parent-child chunk metadata
Qdrant collection setup
hard-filtered retrieval
hybrid vector + keyword retrieval if feasible
parent section expansion
```

Tests:

```text
company-specific query cannot retrieve another company when hard filter exists
child search returns parent context
payload has required citation fields
retrieval benchmark for policy/exclusion/waiting-period cases
```

### Phase 3: Supervisor + Routing

Goal: route requests to the correct lane/workflow.

Build:

```text
SupervisorDecision Pydantic schema
llm.with_structured_output for Supervisor
JSON repair fallback for local model
LangGraph state schema
fixed parallel retrieval branches
Send-based dynamic fan-out later
```

Tests:

```text
100 intent examples route to expected intent_group
high-risk questions become high-risk
company/product questions produce hard_filters
ambiguous product questions ask clarification or switch comparison workflow
```

### Phase 4: Specialist Workflows

Goal: run the three main verticals end-to-end.

Build:

```text
Fast Policy Lane
Verified Compare/Advisor Lane
High-risk Claim/Payout Lane
RuleChecker deterministic node
Calculator deterministic tools
VerifierAgent
```

Tests:

```text
Policy Q&A answer cites sources
Comparison uses SQLite benefits/premiums and Qdrant context
Claim workflow calls RuleChecker + Calculator
Verifier blocks unsupported payout/claim decisions
```

### Phase 5: Synthetic Dataset + Eval Harness

Goal: make quality measurable after every prompt/code change.

Build:

```text
LLM + Pydantic synthetic data generator
full SQLite synthetic tables:
  synthetic_dependents
  synthetic_claims
  synthetic_documents
  synthetic_benchmark_cases
100 benchmark cases
eval runner
Langfuse score attachment
```

Tests:

```text
generated synthetic data validates foreign keys
each benchmark case has expected evidence/workflow
eval scores are written deterministically
benchmark can run offline with fixtures where possible
```

### Phase 6: HITL Review Workflow

Goal: operational automation with customer confirmation and employee approval.

Build:

```text
ReviewPacket schema
customer confirmation interrupt
employee review interrupt
approval/edit/reject outcomes
persistent LangGraph checkpointing
stable thread_id/session_id for every HITL workflow
```

Use a persistent checkpointer. In local/dev, SQLite checkpointer is acceptable. For production-like concurrency, Postgres checkpointer is preferable. Memory checkpointers are not acceptable for review flows that can resume after server restart or across different days.

Tests:

```text
high-risk claim pauses for customer confirmation
edited customer facts trigger recomputation
employee rejection prevents final decision
approved packet creates final response
workflow can resume after process restart when using persistent checkpoint
```

### Testing Pyramid

```text
Unit:
- schemas
- adapters
- rule checks
- calculators
- citation formatter
- evidence merger

Integration:
- SQLite MCP tools
- DatabaseAgent
- Qdrant retriever
- Supervisor routing
- LangGraph lane execution

E2E:
- 100 benchmark scenarios
- claim/payout high-risk scenarios
- comparison/advisory scenarios
- HITL resume flows
```

### Success Criteria

Foundation release is acceptable only if:

```text
90%+ routing accuracy on 100 benchmark intents
95%+ high-risk cases routed to high-risk lane
0 unsupported payout final decisions without review
every important answer has citation
SQLite/Qdrant conflict becomes review-required
benchmark results are logged to Langfuse Scores
```
