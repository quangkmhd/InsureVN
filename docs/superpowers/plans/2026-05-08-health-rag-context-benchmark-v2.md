# Health RAG Context Benchmark V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a separate 100-case context-level Health RAG benchmark v2 for evaluating chunking and RAG retrieval.

**Architecture:** Add a focused generator module under `src/eval` and a thin CLI wrapper under `scripts/05_training_eval`. The module loads all Markdown corpus files, creates 1500-token context chunks with source metadata, samples 30/30/30/10 case candidates, generates Q&A with up to 21 LLM slots in parallel, validates grounding, and writes eval-compatible artifacts.

**Tech Stack:** Python 3.12, dataclasses, `httpx`, `python-dotenv`, existing `src.eval.llm_provider_slots`, pytest, ruff.

---

### Task 1: Context Chunking And Sampling

**Files:**
- Create: `src/eval/context_benchmark_v2.py`
- Create: `tests/unit/test_context_benchmark_v2.py`

- [ ] **Step 1: Write failing tests for context chunking and quotas**

```python
def test_chunk_document_text_tracks_line_ranges_and_tables() -> None:
    text = "a b c d e\n| A | B |\n|---|---|\n| 1 | 2 |\nf g h i j\n"
    chunks = chunk_document_text(
        provider="provider",
        source_path="provider/doc.md",
        text=text,
        target_tokens=5,
        min_tokens=1,
    )
    assert chunks[0].start_line == 1
    assert chunks[0].end_line >= 1
    assert any(chunk.contains_table for chunk in chunks)
```

```python
def test_build_case_candidates_respects_distribution() -> None:
    chunks = make_chunks(non_table_count=12, table_count=3)
    candidates = build_case_candidates(
        chunks,
        distribution={
            "single_context": 3,
            "two_context": 3,
            "three_context": 3,
            "table_context": 1,
        },
        random_seed=7,
    )
    assert [candidate.case_type for candidate in candidates].count("single_context") == 3
    assert [candidate.case_type for candidate in candidates].count("two_context") == 3
    assert [candidate.case_type for candidate in candidates].count("three_context") == 3
    assert [candidate.case_type for candidate in candidates].count("table_context") == 1
    assert all(
        any(chunk.contains_table for chunk in candidate.contexts)
        for candidate in candidates
        if candidate.case_type == "table_context"
    )
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/unit/test_context_benchmark_v2.py -q`

Expected: FAIL because `src.eval.context_benchmark_v2` does not exist.

- [ ] **Step 3: Implement chunking and sampling**

Create dataclasses `ContextChunk` and `CaseCandidate`. Implement:

- `find_markdown_files`
- `chunk_document_text`
- `contains_markdown_table`
- `load_context_chunks`
- `build_case_candidates`

- [ ] **Step 4: Run tests and verify they pass**

Run: `pytest tests/unit/test_context_benchmark_v2.py -q`

Expected: PASS.

### Task 2: LLM Calls, Retry, Validation, And Serialization

**Files:**
- Modify: `src/eval/context_benchmark_v2.py`
- Modify: `tests/unit/test_context_benchmark_v2.py`

- [ ] **Step 1: Write failing tests for retry and schema serialization**

```python
def test_generate_case_retries_twice_then_accepts_valid_payload() -> None:
    attempts = 0

    def fake_call(_slot, _prompt, _timeout_seconds):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return {
            "question": "Quyền lợi được nêu thế nào?",
            "gold_answer": "Quyền lợi A được chi trả.",
            "evidence_quotes": [{"chunk_id": "chunk-1", "quote": "Quyền lợi A được chi trả."}],
            "task_type": "coverage",
            "risk_level": "medium",
        }

    case = generate_case_for_candidate(
        candidate=make_candidate(),
        case_index=1,
        slot=make_slot(),
        call_llm=fake_call,
        timeout_seconds=1,
        max_retries=2,
    )
    assert attempts == 3
    assert case["id"] == "hrag_ctx_v2_00001"
    assert case["expected_sources"][0]["evidence_quote"] == "Quyền lợi A được chi trả."
```

```python
def test_generate_case_fails_after_two_retries() -> None:
    def fake_call(_slot, _prompt, _timeout_seconds):
        raise RuntimeError("temporary")

    with pytest.raises(CaseGenerationError):
        generate_case_for_candidate(
            candidate=make_candidate(),
            case_index=1,
            slot=make_slot(),
            call_llm=fake_call,
            timeout_seconds=1,
            max_retries=2,
        )
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/unit/test_context_benchmark_v2.py -q`

Expected: FAIL because retry/generation functions do not exist.

- [ ] **Step 3: Implement LLM, validation, and artifact writers**

Implement:

- `build_generation_prompt`
- `call_llm_slot`
- `generate_case_for_candidate`
- `run_context_benchmark_generation`
- `write_benchmark_outputs`
- `write_readme`
- `write_manifest`

Use `ThreadPoolExecutor(max_workers=min(21, len(slots)))` and round-robin slot
assignment. Do not generate deterministic fallback cases.

- [ ] **Step 4: Run unit tests**

Run: `pytest tests/unit/test_context_benchmark_v2.py -q`

Expected: PASS.

### Task 3: CLI And Real Run

**Files:**
- Create: `scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py`
- Create: `docs/work_log/2026-05-08-health-rag-context-benchmark-v2-report.md`

- [ ] **Step 1: Add CLI wrapper**

Create a CLI that loads `.env`, collects provider slots, and calls
`run_context_benchmark_generation` with defaults:

- `--max-workers 21`
- `--max-retries 2`
- `--target-tokens 1500`
- `--random-seed 20260508`
- `--output-dir data/benchmark/health_rag_context_benchmark_v2`

- [ ] **Step 2: Run focused tests and ruff**

Run:

```bash
pytest tests/unit/test_context_benchmark_v2.py -q
ruff check src/eval/context_benchmark_v2.py scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py tests/unit/test_context_benchmark_v2.py
```

Expected: PASS and no ruff errors.

- [ ] **Step 3: Run generator**

Run:

```bash
python scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py \
  --max-workers 21 \
  --max-retries 2 \
  --target-tokens 1500
```

Expected: writes exactly 100 accepted cases unless provider/API failures exhaust
candidate attempts.

- [ ] **Step 4: Verify generated artifacts**

Run:

```bash
wc -l data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl
python scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py --verify-only
```

Expected: JSONL has 100 lines and verification reports 30/30/30/10 distribution.

- [ ] **Step 5: Write report**

Write `docs/work_log/2026-05-08-health-rag-context-benchmark-v2-report.md`
with command, counts, paths, failures, and verification results.
