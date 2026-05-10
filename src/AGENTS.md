# Source Code Rules

These rules apply to files under `src/`.

This file is a layered override for source-code work. Root [AGENTS.md](/home/quangnhvn34/dev/me/InsureVN/AGENTS.md)
still applies, but when source-specific guidance is needed, follow this file.

## Purpose

- Keep runtime code in `src/` production-grade, observable, and easy to review.
- Favor repository patterns that already exist over introducing new local styles.
- Preserve InsureVN's agent boundaries, evidence rules, and operational safety.

## Architecture Boundaries

- Keep `src/services/` stateless. Services should transform, retrieve, merge, or validate data; they should not own long-lived workflow state.
- Agents own LLM instances, tool binding, workflow state, and orchestration decisions.
- Prefer LangChain, LangGraph, and Deep Agents primitives before writing custom orchestration code.
- Preserve evidence lineage whenever code touches retrieval, validation, or answer generation. Do not drop citation metadata casually.
- If code touches high-risk claim, payout, rejection, appeal, or fraud-suspicion flows, preserve verifier checks, evidence sufficiency checks, and human review gates.
- If a change blurs service vs agent responsibility, stop and simplify the boundary before adding more code.

## Core Python Rules

- Target Python `3.12`.
- Keep code `ruff`-clean and use `ruff format` for formatting.
- Add type hints to every function and method signature.
- Add Google-style docstrings to public functions and public classes.
- Keep imports at the top of the file, grouped `stdlib -> third-party -> local`.
- Use descriptive names. Avoid generic names like `agent`, `llm`, `data`, `result`, or `handler` when a domain-specific name would be clearer.
- Keep functions cohesive. Prefer small functions with one clear responsibility over large, tangled procedures.
- Keep files focused. If a file is collecting unrelated helpers, move them into a clearer module before the file becomes hard to navigate.
- Prefer straightforward Python over clever abstractions. Do not add indirection unless the code is already paying for repeated complexity.
- Prefer side-effect-light transformations when practical. Avoid mutating shared state unless mutation is the clearest option.

## File Structure In `src/`

Each source file should have one clear purpose. Prefer this order when applicable:

1. module docstring when the file needs one
2. imports
3. constants, type aliases, and small configuration values local to the module
4. data models, protocols, or lightweight helper types
5. private helper functions
6. public functions or classes

Do not mix unrelated responsibilities in the same file, such as:

- API routing plus retrieval logic
- configuration loading plus business logic
- agent orchestration plus generic utility helpers
- runtime code plus temporary debugging scripts

If a file starts needing "misc" sections or unrelated helper clusters, it already wants to be split.

## File Size And Function Size Guidance

These are guidance thresholds, not hard parser limits.

- Good target for a normal `src/` file: `150-300` lines
- Review the structure once a file passes `400` lines
- Strongly prefer splitting once a file passes `600` lines unless the shape is still unusually clear
- Treat `800+` lines as an exception that needs a strong reason

For functions:

- Good target: `15-40` lines
- Review once a function passes `60` lines
- Strongly prefer splitting once a function passes `80` lines unless it is a very clear orchestration wrapper

Length alone is not the rule. The real rule is clarity. A shorter tangled file is still worse than a slightly longer but well-bounded one.

## Folder-Specific Responsibilities

Use the existing `src/` structure intentionally.

- `src/agents/`
  - agent assembly, prompt/tool/LLM wiring, orchestration boundaries, workflow-facing behavior
  - do not bury large stateless transformation logic here when it belongs in a service
- `src/services/`
  - stateless retrieval, merge, validation, formatting, graph, and evidence operations
  - should be reusable without owning workflow state
- `src/api/`
  - route definitions, request/response handling, API-boundary validation, dependency wiring
  - do not place heavy business logic directly in route handlers
- `src/core/`
  - shared infrastructure such as config, logging, database connections, common utilities
  - keep this layer generic and stable
- `src/tools/`
  - wrappers and bindings for tool integrations
  - keep tool-specific side effects and tracing at this boundary
- `src/models/`
  - schemas, DTOs, evidence models, and other typed data structures

When adding a new capability, choose the folder based on responsibility, not convenience.

## Naming Rules

Names must describe function and domain, not just type or framework.

- Prefer `[domain/context] + [role]` naming.
- Module names should describe the main responsibility, for example `evidence_merger.py`, `sqlite_evidence.py`, or `qdrant_retriever.py`.
- Function names should describe the job being done, for example `merge_claim_evidence`, `build_qdrant_filters`, or `format_citation_metadata`.
- Class names should describe the domain object or role, for example `EvidenceMerger`, `ClaimDecisionDraft`, or `QdrantRetriever`.
- Important variables should describe what they hold, not just that they exist.

Prefer names like:

- `claim_evidence`
- `policy_citation_metadata`
- `database_agent_llm`
- `search_agent_tools`
- `retrieval_timeout_seconds`

Avoid names like:

- `data`
- `result`
- `handler`
- `manager`
- `agent`
- `llm`
- `tmp`

Short local names are acceptable only when they are obvious and low-risk, such as `i` in a tiny loop or `db` in a very small database-scoped block. Public-facing names and important locals should still be domain-specific.

## When To Create A New File

Create a new file when the new functionality has its own responsibility and would make the current file less clear if kept inline.

Bias toward a new file when:

- the new logic can be understood and tested as its own unit
- the new logic introduces a new domain concept
- the new logic would create a second major responsibility in the current file
- the current file is already trending large or hard to scan
- the new capability may be reused by more than one caller

Keep logic in the current file when:

- it is a very small helper tightly coupled to the file's existing responsibility
- extracting it would create a worse "one-function file" with no meaningful boundary
- the logic is private glue code that exists only to support one public function or class

Good examples:

- new evidence merge strategy -> new service file
- new API request model set -> new model file
- new tracing decorator or logger helper -> `core/`
- new provider adapter -> new service or tool file based on responsibility

Bad examples:

- adding graph traversal utilities into an API route file because "it was convenient"
- putting citation formatting, retrieval, and HTTP response shaping into one file
- growing a generic `utils.py` or `helpers.py` as a dumping ground

## Validation At Boundaries

- Validate data at system boundaries:
  - API input
  - tool input
  - MCP payloads
  - provider responses
  - file/document-derived data
  - database or graph query parameters
- Prefer typed models, schema validation, or explicit guard code over ad hoc assumptions.
- Never trust external data by default, even if it came from a "known" provider.
- Fail fast when inputs are invalid, ambiguous, or incomplete.
- Return or raise errors that make the failure mode reviewable.

Use this style:

```python
def load_plan(plan_name: str) -> Plan:
    if not plan_name.strip():
        raise ValueError("plan_name must not be empty")
    ...
```

Avoid this style:

```python
def load_plan(plan_name):
    ...
```

## Error Handling

- Handle errors explicitly. Do not silently swallow exceptions.
- Log meaningful context before re-raising or returning an error result.
- Use error handling that matches realistic failure modes. Do not add defensive branches for impossible scenarios just to look "robust".
- Keep fallback behavior explicit. If code falls back to another provider, prompt, parser, or data source, log that decision.
- If partial failure is acceptable, log what failed, what was skipped, and why execution continued.

Use this style:

```python
try:
    payload = client.fetch(query)
except Exception:
    logger.error("Provider fetch failed", extra={"query": query}, exc_info=True)
    raise
```

Avoid this style:

```python
try:
    payload = client.fetch(query)
except Exception:
    return {}
```

## Observability And Logging

Observability is the default for meaningful runtime work in `src/`.

- Any function, tool, service, workflow step, or background task with side effects or operational value must be reviewable from logs and traces.
- Use `src.core.logger.get_logger()` for structured logs. Do not use `print()` for runtime diagnostics.
- For meaningful operations, log at least:
  - start
  - success
  - failure
- On failure, log with `exc_info=True`.
- Log sanitized summaries of inputs and outputs. Do not log raw secrets, credentials, tokens, or unnecessary sensitive payloads.
- Long-running or batched work must emit progress logs so an operator can follow the run without attaching a debugger.
- If a process should remain inspectable after the terminal session ends, prefer a file-backed logger pattern under `log/`.
- Design logs so a reviewer can answer:
  - what started
  - what succeeded
  - what failed
  - how far the operation got

Use this style:

```python
logger = get_logger(__name__)

logger.info("Starting evidence merge", extra={"claim_id": claim_id})
...
logger.info("Evidence merge completed", extra={"claim_id": claim_id, "count": count})
```

Avoid this style:

```python
print("starting merge")
```

## Langfuse And Trace Boundaries

Langfuse is expected at the right boundaries, not on every helper.

- For service-layer operations, prefer `service_observe(...)`.
- For agent, tool, workflow, or other LLM-facing boundaries, prefer `@observe(...)` or the repository's existing tracing patterns.
- Attach useful trace metadata when it helps later review, for example:
  - component
  - operation
  - company
  - document
  - retrieval counts
  - duration
  - fallback used
- Do not instrument every tiny pure helper just because it is public.
- Pure transformation helpers with no operational value do not need traces unless they are central to a debugging hotspot.

Use this style:

```python
@service_observe(name="merge-evidence", component="evidence_merger")
def merge_evidence(...) -> MergedEvidence:
    ...
```

## Configuration And Hardcoding

- Do not read environment variables directly from business logic, agents, or services.
- Do not call `os.getenv`, `load_dotenv`, or read raw config files outside the centralized config layer unless there is an established local exception that clearly belongs there.
- New agent-specific settings must be typed and prefixed by agent identity in the configuration layer.
- Avoid hardcoded operational values when a named constant or typed config field is more appropriate.
- Never hardcode secrets, provider keys, or private endpoints.

## Testing Expectations For Source Changes

Testing expectations in `src/` are moderate but real.

- If a source change alters behavior, add or update tests that prove the intended behavior.
- If the task is a bugfix, add a regression test that would fail without the fix when practical.
- If you add boundary validation, add negative tests for invalid input when practical.
- If observability behavior is part of the contract, verify it with `caplog` or similar test helpers when practical.
- You do not need a separate test for every tiny pure helper, but meaningful logic changes should not ship untested.
- Keep tests aligned with the current repo setup: `pytest`, async markers, and the existing test folder structure.

## Review Checklist

Before considering `src/` work complete, check:

- Does this code respect service vs agent boundaries?
- Are inputs validated at the right boundary?
- Are failures explicit and reviewable?
- Can an operator understand the run from logs and traces?
- Did I preserve evidence and citation metadata where required?
- Did I avoid direct env access and hardcoded operational values?
- Is there test coverage for the behavior change or a clear reason it was not added?

## Anti-Patterns

Do not do these in `src/`:

- Add `print()` debugging to runtime code.
- Swallow exceptions and return empty data structures without explanation.
- Scatter `os.getenv(...)` across business logic.
- Put imports inside runtime branches without a real need.
- Let services accumulate workflow state.
- Drop citation metadata because it is inconvenient to thread through.
- Introduce a new abstraction before confirming existing patterns are insufficient.
- Log raw secrets, raw tokens, or oversized sensitive payloads.

## Default Bias

- Choose the simpler design when two options are equally correct.
- Choose the more observable design when two options are equally simple.
- Match existing repo conventions before introducing a new local pattern.
