# InsureVN - AI Coding Instructions

## 1. Project Overview

InsureVN is a **multi-agent AI system** for the Vietnamese insurance industry.
It automates the full insurance lifecycle: policy explanation, claim processing, document extraction, fraud detection, and customer advisory.

**Core Mission**: Solve pain points and optimize time for employees, customers, and all stakeholders in the insurance ecosystem.

---

## 2. Tech Stack

| Layer               | Technology                                             |
| :------------------ | :----------------------------------------------------- |
| Language            | Python 3.12.3                                          |
| Agent Framework     | LangChain, LangGraph                                   |
| LLM Provider        | Ollama cloud (called through LangChain)                |
| Web Framework       | FastAPI                                                |
| Vector Database     | Qdrant                                                 |
| Relational Database | SQLite                                                 |
| Observability       | Langfuse (Tracing, Prompt Mgmt, Evaluation)            |
| PDF/OCR             |                                                        |


---

## 3. Coding Standards

- **Style**: PEP 8, enforced by `ruff`
- **Formatting**: `ruff format`
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Type hints**: Required on all function signatures
- **Docstrings**: Google style, required on all public functions/classes
- **Imports**: Group by stdlib → third-party → local, sorted alphabetically

---

## 4. Project Structure

```
InsureVN/
├── GEMINI.md                # AI coding instructions (this file)
├── README.md                # Project documentation
├── .env                     # Environment variables (gitignored)
├── .gitignore               # Git ignore rules
│
├── CICD/                    # CI/CD configurations
│   ├── docker-compose.yml    # Local dev services (Qdrant, etc.)
│   └── langfuse-compose.yml  # Langfuse observability stack
│
├── src/                     # Core source code
│   ├── main.py               # FastAPI app entry point
│   │
│   ├── agents/               # LangGraph agent definitions
│   │   ├── database_agent.py # DB interaction via MCP tools
│   │   └── ...               # (Planned) orchestrator, policy, claim agents
│   │
│   ├── mcp_servers/          # Custom MCP server implementations
│   │   └── sqlite/           # SQLite MCP server
│   │
│   ├── tools/                # LangChain tools & clients
│   │   ├── mcp_client.py     # Generic MCP client for tool binding
│   │   └── ...
│   │
│   ├── api/                  # FastAPI routes
│   │   ├── routes/           # Endpoint definitions
│   │   └── dependencies.py   # DI containers
│   │
│   ├── models/               # Data models & schemas
│   │   ├── schemas.py        # Pydantic models
│   │   └── schema.sql        # SQLite schema definition
│   │
│   ├── core/                 # Config, settings, shared utilities
│   │   ├── config.py         # Environment-based settings
│   │   ├── logger.py         # Structured JSON logging
│   │   └── database.py       # DB connection utilities
│   │
│   └── prompts/              # System prompts for agents
│
├── tests/                   # Test suite
│   ├── unit/                # Component-level tests
│   ├── integration/         # Multi-component/Tool tests
│   └── e2e/                  # Full agentic flow tests
│
├── scripts/                 # Data pipeline & utility scripts
│   ├── 01_acquisition/      # Scraping (Firecrawl, Deep search)
│   ├── 02_preprocessing/    # PDF classification & organization
│   ├── 03_conversion/       # PDF to Markdown (Marker, Datalab)
│   ├── 04_extraction/       # OCR & structured data extraction
│   ├── 05_training_eval/    # VLM fine-tuning (Oumi, Gemma4)
│   ├── 06_db_ingestion/     # Data ingestion to SQLite
│   └── 06_ipynb/            # Research & training notebooks
│
├── database/                # SQLite database files
│   └── insurevn.db
│
├── data/                    # Data storage (gitignored)
│   ├── raw/                 # Original scraped files
│   ├── processed/           # Intermediate conversion results
│   ├── health_insurance/    # Domain-specific extracted data
│   └── qdrant/              # Vector store data
│
├── config/                  # Configuration files
│   └── finetune/            # Fine-tuning dataset configs (JSONL)
│
├── log/                     # Application logs (e.g., mcp_database.log)
├── docs/                    # Documentation and reports
│   ├── mcp_insurevn_db_reference.md
│   ├── database_agent.md
│   ├── database_observability.md
│   ├── langfuse_integration.md
│   └── ...
└── gemma4-e2b-finetuned-lora/ # Local finetuned model weights

```

When creating new files, always place them in the correct directory per this structure. Use descriptive, lowercase filenames with underscores.

---

## 5. Agent Architecture

### Core Agents

- **Orchestrator** → central controller, routes to specialized agents
- **PolicyAgent** → query & explain policy via RAG over Qdrant
- **DatabaseAgent** → execute complex queries and data retrieval via SQLite MCP tools
- **ClaimAgent** → evaluate claim eligibility (rules + LLM reasoning)
- **DocumentAgent** → OCR + extract structured data from PDFs
- **ValidationAgent** → check missing/invalid documents
- **CalculationAgent** → compute payout/premium (deterministic, no LLM)


### Advanced Agents

- **FraudAgent** → detect abnormal patterns
- **AdvisorAgent** → recommend insurance plans
- **ExplanationAgent** → simplify complex outputs for end users

### Memory

- **Short-term**: conversation context (per session)
- **Long-term**: user profile, claim history (SQLite)
- **State**: workflow step tracking (e.g., upload → validate → evaluate)

### Observability

- **Tracing**: Langfuse for end-to-end tracing of agent reasoning and tool calls
- **Prompt Management**: Remote management and versioning of system prompts
- **Metrics**: Latency, cost, and quality tracking per agent interaction


---

## 6. Mandatory Workflows & Skills

The use of skills is mandatory for all tasks. You MUST select the appropriate skill and announce its usage before starting any changes.

### 6.1 Skill Activation & Compliance

1. **Check & Select**: ALWAYS check and select the most relevant skill (e.g., `tdd-workflow`, `systematic-debugging`) BEFORE responding or taking action.
2. **Announce Usage**: Always start by announcing the skill you are using (e.g., "Using `tdd-workflow` skill to implement feature...").
3. **Strict Adherence**: No skipping steps or taking shortcuts. All processes within a skill (like TDD's RED-GREEN-REFACTOR) are mandatory.
4. **No Excuses**: Reasons like "too simple to use a skill" or "will use it later" are unacceptable.

### 6.2 Before Writing Code

1. **Always use `context7`** to look up current library docs/APIs before coding. Do NOT rely on training data — it may be outdated.
2. **Always read source files** to understand existing code. Never guess from README, docs, or memory alone.
3. **Apply relevant hooks** when available. Do not hesitate to use them.

### 6.3 After Writing Code

1. **Follow TDD Cycle**: Write failing test (RED) -> Minimal code (GREEN) -> Refactor.
2. **Create unit tests** for every new component/function created.
3. **Create end-to-end tests** when the change affects a user-facing flow.
4. **Run tests** to verify everything passes before considering a task done.

### 6.4 File & Folder Hygiene

- Every new file must be placed in the correct directory per the project structure.
- File and folder names must be descriptive, lowercase, with underscores.
- Do not create files at the project root unless they are config files.

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
- Ask yourself: *"Would a senior engineer say this is overcomplicated?"* If yes, simplify.

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

- *"Add validation"* → write tests for invalid inputs, then make them pass
- *"Fix the bug"* → write a test that reproduces it, then make it pass
- *"Refactor X"* → ensure tests pass before and after

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

## 8. Scope

This is a **production-grade product**, not an MVP. Build with:

- Proper error handling and logging
- Production-ready code quality
- Security considerations
- Scalability in mind
- Comprehensive test coverage
