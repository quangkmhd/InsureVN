# InsureVN - AI Coding Instructions

## 1. Project Overview

InsureVN is a **hybrid full-agent-swarm platform** for the Vietnamese insurance
industry. It automates policy explanation, product comparison, claim advisory,
claim/payout drafting, document extraction, and employee review workflows using
a shared evidence foundation.

**Core Mission**: Solve pain points and optimize time for employees, customers, and all stakeholders in the insurance ecosystem.

**Canonical architecture sources**:

- `docs/2026-05-03-insurevn-multi-agent-platform-design.md`
- `docs/2026-05-04-quad-retrieval-rag-architecture.md`
- `asset/insurevn-Architecture.svg`

---

## 2. Tech Stack

| Layer                   | Technology                                                                 |
| :---------------------- | :------------------------------------------------------------------------- |
| Language                | Python 3.12.3                                                              |
| API Runtime             | FastAPI, Uvicorn                                                           |
| Agent & Workflow Layer  | LangChain agents/tools/retrievers, LangGraph StateGraph/checkpoints/HITL, Deep Agents operator shell |
| LLM/Embedding Providers | Ollama, Google Gemini/GenAI, OpenRouter, NVIDIA, Jina rerank via typed config |
| Structured Data         | SQLite plus FastMCP SQLite server                                          |
| Vector Retrieval        | Qdrant dense + sparse/BM25 hybrid search via `langchain-qdrant`            |
| Graph Retrieval         | Neo4j via `langchain-neo4j`; NetworkX for diagnostics and unit fixtures     |
| Observability           | Langfuse tracing, prompt management, eval metadata, structured JSON logs    |
| PDF/OCR/Data Prep       | Marker, Datalab, Gemma4/VLM extraction, table-to-narrative conversion      |
| Testing & Quality       | pytest, ruff, retrieval readiness gates, synthetic benchmark fixtures       |

---

## 2.1 Implementation Memory

- In `src/`, all `import` and `from ... import ...` statements must stay at the top of the file. Do not place imports inside `def`, class methods, or runtime branches unless there is a documented unavoidable reason.
- For architecture decisions, treat `docs/2026-05-03-insurevn-multi-agent-platform-design.md`, `docs/2026-05-04-quad-retrieval-rag-architecture.md`, and `asset/insurevn-Architecture.svg` as current. `docs/multi_agent_system_architecture_design.md` is historical brainstorming only.
- Use framework primitives before custom code: LangGraph for workflow orchestration, checkpointing, and HITL; LangChain for tools, retrievers, provider adapters, and existing agents; Deep Agents for long-running operator/developer shells.
- Services under `src/services/` should remain stateless transformation/retrieval utilities. Agents own LLM instances, MCP tools, and workflow state.
- High-risk workflows such as claims, payouts, rejections, appeals, and fraud suspicion must preserve evidence, citations, verifier checks, and human review gates.

---

## 3. Coding Standards

- **Style**: PEP 8, enforced by `ruff`
- **Formatting**: `ruff format`
- **Naming**:
  - `snake_case` for functions/variables, `PascalCase` for classes.
  - **Agent Objects**: Use descriptive, searchable names with agent prefixes (e.g., `database_agent_llm`, `search_agent_tools`).
  - **No generic names**: Avoid naming objects simply `agent` or `llm` inside agent-specific logic to ensure global searchability via agent keys.
- **Type hints**: Required on all function signatures
- **Docstrings**: Google style, required on all public functions/classes
- **Imports**: Group by stdlib → third-party → local, sorted alphabetically

---

## 4. Project Structure

```
InsureVN/
├── GEMINI.md                 # AI coding instructions for Gemini-style agents
├── AGENTS.md                 # AI coding instructions for Codex/agent runtimes
├── README.md                 # Project documentation
├── pyproject.toml            # Python package metadata and tool config
├── requirements.txt          # Runtime dependency list
├── .env                      # Environment variables (gitignored)
├── .gitignore                # Git ignore rules
│
├── CICD/                     # CI/CD configurations
│   ├── docker-compose.yml     # Local dev services (Qdrant, Neo4j, etc.)
│   └── langfuse-compose.yml   # Langfuse observability stack
│
├── src/                      # Core source code
│   ├── main.py                # FastAPI app entry point
│   │
│   ├── agents/                # Intelligent agents
│   │   └── database_agent.py  # Structured data agent over SQLite MCP
│   │
│   ├── mcp_servers/           # Custom MCP server implementations
│   │   └── sqlite/            # FastMCP SQLite server
│   │
│   ├── tools/                 # LangChain tools and clients
│   │   ├── mcp_client.py      # Generic MCP client for tool binding
│   │   └── search_tool.py     # Tavily web search tool for live market data
│   │
│   ├── api/                   # FastAPI routes
│   │   └── routes/health.py   # Health endpoint
│   │
│   ├── models/                # Data models and schemas
│   │   ├── evidence.py        # Evidence, citation, retrieval plan models
│   │   └── schema.sql         # SQLite insurance + synthetic schema
│   │
│   ├── core/                  # Config, settings, shared utilities
│   │   ├── config.py          # Typed settings registry
│   │   ├── logger.py          # Structured JSON logging + Langfuse handler
│   │   ├── database.py        # SQLite connection utilities
│   │   └── vietnamese_text.py # Vietnamese normalization helpers
│   │
│   ├── services/              # Stateless retrieval/evidence/graph services
│   │   ├── document_chunker.py
│   │   ├── qdrant_collection_manager.py
│   │   ├── qdrant_vector_store.py
│   │   ├── qdrant_retriever.py
│   │   ├── qdrant_evidence.py
│   │   ├── sqlite_evidence.py
│   │   ├── evidence_merger.py
│   │   ├── citation_formatter.py
│   │   ├── retrieval_readiness.py
│   │   ├── observability.py
│   │   └── knowledge_graph/    # Neo4j, NetworkX, GraphRAG, schema services
│   │
│   └── prompts/               # System prompts for agents
│
├── tests/                    # Test suite
│   ├── unit/                 # Component-level tests
│   ├── integration/          # Multi-component/tool tests
│   ├── e2e/                  # Full agentic flow tests
│   └── fixtures/             # Shared fixtures
│
├── scripts/                  # Data pipeline and utility scripts
│   ├── 01_acquisition/       # Scraping (Firecrawl, deep search)
│   ├── 02_preprocessing/     # PDF classification and organization
│   ├── 03_conversion/        # PDF to Markdown, table-to-text, cleanup
│   ├── 04_extraction/        # OCR, JSON extraction, Knowledge Graph schema/build
│   ├── 05_training_eval/     # VLM fine-tuning (Oumi, Gemma4)
│   ├── 06_db_ingestion/      # SQLite, Qdrant, Graph ingestion/indexing
│   ├── 07_knowledge_graph/   # Knowledge Graph discovery, canonicalization, and build
│   └── 06_ipynb/             # Research and training notebooks
│
├── database/                 # Local database files
│   ├── insurevn.db           # SQLite insurance database
│   └── qdrant/storage/       # Local Qdrant storage
│
├── data/                     # Data storage (gitignored)
│   ├── raw/                  # Original scraped files
│   ├── processed/            # Intermediate conversion results
│   └── health_insurance/     # Domain-specific extracted data
│
├── config/                   # Configuration files
│   └── finetune/             # Fine-tuning dataset configs (JSONL)
│
├── asset/                    # Generated architecture images
│   └── insurevn-Architecture.svg
│
├── log/                      # Application logs (e.g., mcp_database.log)
├── docs/                     # Documentation, specs, plans, reports, logs
│   ├── 2026-05-03-insurevn-multi-agent-platform-design.md
│   ├── 2026-05-04-quad-retrieval-rag-architecture.md
│   ├── blueprints/
│   ├── superpowers/specs/
│   ├── superpowers/plans/
│   ├── work_log/
│   └── ...
└── gemma4-e2b-finetuned-lora/ # Local finetuned model weights

```

When creating new files, always place them in the correct directory per this structure. Use descriptive, lowercase filenames with underscores.

---

## 5. Agent Architecture

The current architecture is a **Hybrid Full Agent Swarm** with shared evidence,
not a monolithic RAG bot. The current visual source is
`asset/insurevn-Architecture.svg`.

### Runtime Flow

1. **User / Synthetic Scenario** enters the system.
2. **SupervisorAgent** classifies intent, extracts hard filters, assigns risk,
   and routes to one of three lanes.
3. **Fast Lane (Q&A)** uses the Ensemble Retriever for policy explanation.
4. **Verified Lane (Advisor)** uses Ensemble Retriever + DatabaseAgent +
   Profile Store for comparison and recommendations.
5. **High-Risk Lane (Claim)** uses OCR DocumentAgent + Ensemble Retriever +
   DatabaseAgent + Profile Store for claim/payout workflows.
6. **Merge & Rerank Evidence** deduplicates, detects conflicts, preserves
   citations, and optionally reranks with a cross-encoder.
7. **PolicyAgent**, **ComparisonAdvisorAgent**, or **ClaimAgent** drafts the
   response from evidence.
8. **ValidationAgent** and deterministic **CalculationAgent** check reasoning,
   missing evidence, limits, premiums, payouts, and self-correction needs.
9. **VerifierAgent** checks safety, compliance, evidence sufficiency,
   citations, and risk gates.
10. High-risk outputs go through **Customer Confirm** and **Employee Approve**.

### Agent Boundaries

- `SupervisorAgent`: intent/risk classification, hard-filter extraction,
  retrieval planning, workflow selection.
- `DatabaseAgent`: existing LangChain `create_agent` specialist over SQLite
  MCP tools; wrap as a LangGraph node when used in workflows.
- `PolicyAgent`: explains policy clauses, exclusions, waiting periods, claim
  procedures, and glossary terms from evidence only.
- `ComparisonAdvisorAgent`: compares plans and recommends options. It may use
  `SearchAgent` as an optional Tavily-backed tool for live market data.
- `ClaimAgent`: drafts claim decisions, missing-document guidance,
  rejection/appeal explanations, and payout narratives from evidence.
- `OCR DocumentAgent`: processes user-uploaded evidence; fixture-backed until
  production OCR integration is added.
- `ValidationAgent`: blind-review judge that can trigger self-correction.
- `CalculationAgent`: deterministic math/Python node; never uses LLM guesses.
- `VerifierAgent`: checks evidence quality and risk gates; it does not invent a
  new answer.

Deferred agents from older brainstorming docs, such as underwriting,
compliance guardrail, tone classifier, PII anonymization, market sentiment, and
predictive optimization agents, must not be added unless a current spec revives
them.

### Memory And Human Review

- Use LangGraph checkpointing with `thread_id` for multi-turn sessions.
- Development/local persistence should use SQLite checkpointers; production can
  migrate to Postgres checkpointers.
- Foundation release user profiles are synthetic data in SQLite, not real
  customer data.
- Claim, payout, rejection, appeal, and fraud-suspicion workflows require
  customer fact confirmation and employee approval before finalization.

### Observability

- Langfuse traces agent reasoning, tool calls, HTTP spans, service metadata,
  prompt versions, and eval outputs.
- Services should return metadata that callers attach to Langfuse instead of
  creating global traces directly.
- Important outputs must preserve citation lineage: company, document, source
  path, page/section, source table ID, and graph path where available.

---

## 6. Data Pipeline And Evidence Foundation

InsureVN's data flow follows the 6-phase processing lifecycle documented in
`docs/work_log/data_pipeline_processing_log.md`.

1. **Acquisition**: scrape PDF/web sources from Vietnamese insurers.
2. **Preprocessing & QA**: classify PDFs, filter non-health-insurance content,
   and organize source folders.
3. **Conversion & Interpretation**: convert PDFs to Markdown, clean image
   noise, and convert complex tables into narrative text.
4. **Extraction**: extract JSON/table/image data, filter Good/Trash content,
   discover/canonicalize Knowledge Graph schema, and map JSON keys to SQL.
5. **Training & Eval**: prepare Oumi/Gemma4 VLM datasets, train/evaluate/export
   the model, and run inference checks.
6. **Ingestion**: load structured facts into SQLite, index document chunks into
   Qdrant, and build/import Knowledge Graph data for Neo4j/GraphRAG.

### Evidence Rules

- The system is **tri-canonical**:
  - SQLite = structured facts, numbers, premiums, limits, waiting periods.
  - Qdrant = document text, clauses, legal wording, contextual citations.
  - Knowledge Graph = entity relationships and multi-hop reasoning paths.
- Quad retrieval combines semantic vector search, sparse/BM25 keyword search,
  graph retrieval, and SQLite structured lookup.
- Hard filters for company, document, product line, plan, section, and date must
  be applied whenever available.
- All retrievers and adapters normalize output into `Evidence` and preserve
  citation metadata for employee review.
- If SQLite, Qdrant, and graph evidence conflict, flag the conflict and route
  the workflow to human review instead of hiding the disagreement.

---


## 7. Behavioral Guidelines

> These guidelines bias toward **caution over speed**. For trivial tasks, use judgment.

### 7.1 Think Before Coding

- **State assumptions explicitly.** If uncertain, ask.
- **If multiple interpretations exist**, present them — don't pick silently.
- **If a simpler approach exists**, say so. Push back when warranted.
- **If something is unclear**, stop. Name what's confusing. Ask.

### 7.2 Simplicity First

- No features beyond what was asked.
- No abstractions for single-use code.
- No speculative "flexibility" or "configurability".
- No error handling for impossible scenarios.
- If 200 lines can be 50, rewrite it.
- Ask yourself: _"Would a senior engineer say this is overcomplicated?"_ If yes, simplify.

### 7.3 Surgical Changes

When editing existing code:

- **Don't "improve"** adjacent code, comments, or formatting.
- **Don't refactor** things that aren't broken.
- **Match existing style**, even if you'd do it differently.
- If you notice unrelated dead code, **mention it** — don't delete it.

When your changes create orphans:

- **Remove** imports/variables/functions that YOUR changes made unused.
- **Don't remove** pre-existing dead code unless asked.

**The test:** Every changed line should trace directly to the user's request.

### 7.4 Goal-Driven Execution

Transform tasks into verifiable goals:

- _"Add validation"_ → write tests for invalid inputs, then make them pass
- _"Fix the bug"_ → write a test that reproduces it, then make it pass
- _"Refactor X"_ → ensure tests pass before and after

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

### Success Criteria

These guidelines are working if:

- ✅ Fewer unnecessary changes in diffs
- ✅ Fewer rewrites due to overcomplication
- ✅ Clarifying questions come **before** implementation, not after mistakes

---

## 9. Configuration Standards

- **Strict Agent Isolation**: Every agent must have its own dedicated and isolated configuration parameters. Never use global variables or shared environment keys for agent-specific logic (e.g., LLM settings, tool limits, API keys).
- **Prefix-Based Ownership**: All agent settings in `.env` and `Settings` MUST be prefixed with the agent's identity (e.g., `[AGENT_NAME]_[PARAMETER]`). This ensures clear parameter ownership and prevents configuration leakage between agents.
- **Decoupled Configuration Layer**: Agents must remain decoupled from the environment. They must never call `os.getenv`, `load_dotenv`, or access raw config files. All inputs must be proxied through a centralized, type-safe registry (e.g., `src/core/config.py`).
- **Mandatory Type Safety**: Configuration parameters must be explicitly cast to their functional types (e.g., `float`, `int`, `bool`) at the configuration layer. No raw string-based logic is allowed for numeric or boolean controls.
- **Tool-Specific Encapsulation**: If a tool is used by an agent, its specific parameters (API keys, base URLs, retry limits) must be encapsulated within that agent's configuration block to allow independent tuning.
- **Mandatory `.env` Registration**: Every agent-specific parameter must be explicitly added to the `.env` file with clear comments. This ensures that the environment is self-documenting and easy to configure for local development.

---

## 10. Success Criteria

This is a **production-grade product**, not an MVP. Build with:

- Proper error handling and logging
- Production-ready code quality
- Security considerations
- Scalability in mind
- Comprehensive test coverage
