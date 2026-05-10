---
name: multi-provider-apikey-router
description: Use when the user explicitly mentions multi-provider-apikey-router and wants code that distributes work across multiple providers, API keys, and models while following the repo's existing stack.
---

# Multi Provider APIKey Router

Implement the smallest useful solution for the current task. Do not force every task into a full router service.

## Workflow

1. Inspect the repo first and follow the existing stack, patterns, and framework.
2. Read `.env` or related config safely. Summarize names and structure only; never print raw secrets.
3. Detect provider groups, models, API keys, and base URLs.
4. Prefer these config names:
   - `PROVIDER_API_KEY_1..N`
   - `PROVIDER_LLM_MODEL_1..N`
   - `PROVIDER_BASE_URL`
5. Normalize inconsistent names when needed, for example `OllAMA_API_Key_1` to `OLLAMA_API_KEY_1`.
6. Treat each provider as:
   - one provider name
   - one shared key pool
   - one shared model list
   - one optional base URL
7. Default expansion rule:
   - all models in the same provider share all keys of that provider
   - logical targets are `provider x model x api_key`
8. Example:
   - `GOOGLE_LLM_MODEL_1`
   - `GOOGLE_LLM_MODEL_2`
   - `GOOGLE_API_KEY_1..5`
   - this means 10 logical targets by default
9. Implement only what the task needs:
   - helper module
   - batch runner
   - queue worker
   - CLI
   - HTTP service

## Parallel and Retry Rules

- Run requests in parallel across logical targets as appropriate for the task.
- Retry each failed request up to `2` times.
- Record successes immediately.
- Do not stop the whole run because one request fails.
- After the first pass completes, rerun only the failed items.
- Report final success, final failure, and rerun results clearly.

## Implementation Rules

- If the task mentions a framework, SDK, API, CLI, or cloud service, fetch current docs before coding.
- Keep code minimal and aligned with the current repo.
- Preserve provider-specific caveats when relevant.
- Do not assume that more API keys always mean more real upstream quota.
- If the user asks for stricter per-model key mapping, override the default shared-key behavior.

## Output

State:

- detected stack
- detected providers, model groups, and key groups
- what was added or changed
- what succeeded
- what failed after retries
- what was rerun
