# Python Test Rules

Apply these rules when editing files under `tests/`.

## Framework

- Use `pytest`.
- Keep tests in the existing `unit`, `integration`, and `e2e` structure.
- Use `pytest.mark.asyncio` for async tests.
- Reproduce a bug with a failing test before fixing it when the task is a bugfix.

## Test design

- Prefer focused tests with one clear behavior under assertion.
- Prefer fixtures, mocks, and stubs over real network or provider calls.
- Use `unittest.mock` or existing pytest fixtures for isolation.
- Add or update regression coverage for every behavior change.

## Markers and external dependencies

- Reserve `real_api` for tests that genuinely call external providers.
- Gate external tests with `skipif` or equivalent checks so local runs remain reliable without credentials.
- Do not silently convert unit tests into integration tests.

## Verification

- Run targeted tests for the files you changed first, then broaden when needed.
- **MANDATORY**: Perform real execution testing (manual verification or E2E tests with real dependencies) to confirm the final result before concluding the task. Never rely solely on mocks or unit tests for final sign-off.
- Keep tests compatible with the repo's `pytest` and `pyright` configuration.
- Prefer deterministic assertions over timing-sensitive or order-sensitive checks.
- When observability is part of the intended behavior, add assertions for emitted logs, metadata, or trace-facing summaries with `caplog` or equivalent test helpers.
