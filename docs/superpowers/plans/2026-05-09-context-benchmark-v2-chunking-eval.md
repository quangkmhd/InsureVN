# Context Benchmark V2 Chunking Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate all active chunking strategies against the new 100-case Health RAG Context Benchmark V2.

**Architecture:** Reuse the existing streaming chunking + Qdrant indexing pipeline and persisted Qdrant retrieval evaluator. Add only the missing CLI plumbing so the streaming runner can receive the v2 benchmark path and corpus dir from the command line.

**Tech Stack:** Python, pytest, ruff, local Qdrant, sentence-transformers MiniLM embeddings, existing InsureVN chunking strategies.

---

### Task 1: Add Benchmark Path CLI Plumbing

**Files:**
- Modify: `scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py`
- Test: `tests/unit/test_streaming_qdrant_cli.py`

- [ ] Write a failing CLI parser test that passes `--benchmark-path` and `--corpus-dir` and asserts the parsed `Path` values.
- [ ] Update `parse_args` to accept an optional argv list for testability.
- [ ] Add `--benchmark-path` and `--corpus-dir` parser options.
- [ ] Pass those values into `StreamingChunkEmbeddingConfig`.
- [ ] Run the focused CLI test and the existing streaming tests.

### Task 2: Build New Qdrant Indexes

**Files:**
- Output only: `data/eval_runs/20260509_context_benchmark_v2_all_chunking_qdrant`

- [ ] Run streaming chunking for the v2 benchmark with `--source-selection expected`, `--limit-documents 0`, and all 9 strategies.
- [ ] Keep Qdrant directories for retrieval evaluation.
- [ ] Verify the manifest points to `health_rag_context_benchmark_v2.jsonl` and contains 42 expected source files.

### Task 3: Run Retrieval Eval

**Files:**
- Output only: `data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval`

- [ ] Run persisted Qdrant retrieval eval at top-k 5 over the new Qdrant run.
- [ ] Verify all 9 strategies complete and produce 900 case metric rows.
- [ ] Sort the strategy summary by required-source recall, primary hit, MRR, and line overlap.

### Task 4: Report Results

**Files:**
- Create: `docs/work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md`
- Modify: `docs/work_log/2026-05-09-data-pipeline-processing-technical-report.md`

- [ ] Write a compact report with run paths, strategy rankings, and verification commands.
- [ ] Add the report link to the Phase 5 eval report table.
- [ ] Run pytest, ruff, and final artifact sanity checks before reporting completion.
