# Python Script Rules

Apply these rules when editing files under `scripts/`.

## Core style

- Follow the same Python conventions as `src/`: PEP 8, type hints on function signatures, imports at the top, and `ruff`-clean code.
- Reuse centralized config and project utilities when available instead of introducing standalone env parsing in new script logic.

## File and Directory Structure

- **Naming Conventions**:
    - Use `snake_case` for all filenames and directory names.
    - Scripts should have descriptive names representing their action (e.g., `normalize_vietnamese_text.py`).
- **Creating New Folders**:
    - For data pipeline stages, use the `XX_description` prefix pattern (e.g., `08_new_stage`).
    - Check if the logic fits into an existing numbered directory before creating a new one.
    - If a new stage is necessary, increment the highest existing prefix number.
- **Creating New Files**:
    - Place scripts inside the relevant numbered stage directory whenever possible (e.g., `scripts/04_extraction/custom_extractor.py`).
    - Use the root `scripts/` directory only for cross-cutting utilities, shared tools, or temporary debugging scripts.
    - Avoid creating one-off scripts in the root if they belong to a specific processing lifecycle phase.


## Observability

- Every script that processes files, documents, records, batches, or remote calls must emit structured logs for start, progress, completion, and failure.
- Use the existing logging utilities when practical; otherwise keep logs structured and consistent with `src/core/logger.py`.
- Log counts, filenames, record ids, durations, retry attempts, and output locations where useful for operator review.
- On exceptions, log with stack traces and enough metadata to identify the failed unit of work.
- Do not hide partial failures. If a script continues after an item-level failure, log the failure and the decision to continue.
- Prefer writing long-running job logs to files under `log/` so runs can be reviewed after completion.
- Avoid logging raw secrets or unnecessary full sensitive payloads; prefer summaries and identifiers.

## Execution review

- A human reading the logs should be able to reconstruct the processing timeline without rerunning the job.
- If a script writes derived artifacts, log where they were written and how many items were produced.
- If a script has retries, backoff, skips, or fallback behavior, log those decisions explicitly.
