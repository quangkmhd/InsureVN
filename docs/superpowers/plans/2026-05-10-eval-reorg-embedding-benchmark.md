# Eval Reorg And Embedding Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `src/eval` into clearer subpackages, add provider-aware embedding adapters for evaluation, then run an embedding benchmark on the InsureVN retrieval baseline and produce a report.

**Architecture:** Keep existing public entrypoints stable while moving implementation modules behind clearer package boundaries. Extend the eval embedding layer with a provider-based factory so retrieval, persisted Qdrant eval, and streaming chunk/index runs can benchmark both local sentence-transformer models and Google Gemini embeddings with the same metric pipeline.

**Tech Stack:** Python 3.12, pytest, sentence-transformers, langchain-google-genai, Qdrant local mode, DeepEval-free deterministic retrieval metrics, ruff.

---

### Task 1: Plan And Boundary Lock

**Files:**
- Create: `docs/superpowers/plans/2026-05-10-eval-reorg-embedding-benchmark.md`
- Inspect: `src/eval/`, `tests/unit/test_*eval*`

- [ ] Confirm the move boundaries for `benchmarks`, `embeddings`, `llms`, `pipelines`, and `retrieval`.
- [ ] Preserve old import paths with thin wrappers or updated imports so scripts and tests do not break unexpectedly.
- [ ] Keep chunking strategy modules in `src/eval/chunking/` unchanged unless an import path requires a surgical edit.

### Task 2: Reorganize `src/eval`

**Files:**
- Create: `src/eval/benchmarks/__init__.py`
- Create: `src/eval/embeddings/__init__.py`
- Create: `src/eval/llms/__init__.py`
- Create: `src/eval/pipelines/__init__.py`
- Create: `src/eval/retrieval/__init__.py`
- Move: `src/eval/context_benchmark_v2.py`
- Move: `src/eval/embedding_cache.py`
- Move: `src/eval/embeddings.py`
- Move: `src/eval/llamaindex_llms.py`
- Move: `src/eval/llm_provider_slots.py`
- Move: `src/eval/runner.py`
- Move: `src/eval/streaming_qdrant_chunking.py`
- Move: `src/eval/vector_database.py`
- Move: `src/eval/persisted_qdrant_retrieval_eval.py`
- Move: `src/eval/llm_retrieval_judge_eval.py`

- [ ] Create package directories and `__init__.py` files.
- [ ] Move implementation modules into the new package layout.
- [ ] Replace old root modules with compatibility shims that re-export the moved symbols.
- [ ] Update internal imports to use the new package locations where it improves clarity without broad churn.

### Task 3: Add Provider-Aware Embedding Adapters

**Files:**
- Modify: `src/eval/config.py`
- Modify: `src/eval/embeddings/adapters.py`
- Modify: `src/eval/pipelines/runner.py`
- Modify: `src/eval/pipelines/streaming_qdrant_chunking.py`
- Modify: `src/eval/retrieval/persisted_qdrant_retrieval_eval.py`
- Test: `tests/unit/test_eval_strategy_embeddings.py`
- Test: `tests/unit/test_persisted_qdrant_retrieval_eval.py`

- [ ] Add eval config fields for embedding provider, Google API key, and Google output dimensionality.
- [ ] Generalize the eval embedding factory so retrieval/index code can build either sentence-transformers or Google Gemini embeddings.
- [ ] Keep semantic chunking embeddings on the existing local sentence-transformer path unless explicitly configured otherwise.
- [ ] Ensure persisted retrieval eval reads the embedding provider from the run manifest or CLI overrides.

### Task 4: Verify Reorg And Adapter Behavior

**Files:**
- Test: `tests/unit/test_streaming_qdrant_chunking.py`
- Test: `tests/unit/test_streaming_qdrant_cli.py`
- Test: `tests/unit/test_context_benchmark_v2.py`
- Test: `tests/unit/test_eval_llm_provider_slots.py`
- Test: `tests/unit/test_eval_strategy_embeddings.py`
- Test: `tests/unit/test_persisted_qdrant_retrieval_eval.py`

- [ ] Run the focused eval unit tests and fix import or config regressions.
- [ ] Run a smoke command for the streaming and persisted retrieval CLIs if unit tests are not enough to prove entrypoint stability.

### Task 5: Run Embedding Benchmark

**Files:**
- Create artifacts under: `data/eval_runs/`
- Read benchmark: `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`

- [ ] Freeze the retrieval baseline at `hierarchical_header_recursive`, `chunk_size=900`, `chunk_overlap=150`.
- [ ] Build one persisted Qdrant run per embedding model/provider candidate.
- [ ] Run deterministic retrieval evaluation for each candidate with the same corpus, benchmark cases, and top-k values.
- [ ] Monitor long-running commands until all requested runs complete or fail with a concrete blocker.

### Task 6: Write The Technical Report

**Files:**
- Create: `docs/work_log/2026-05-10-eval-reorg-embedding-benchmark-technical-report.md`

- [ ] Record the reorg scope, compatibility notes, commands run, benchmark artifact paths, and retrieval metrics.
- [ ] Summarize which embedding model performed best for the current Vietnamese insurance benchmark and note remaining limitations such as dense-only versus hybrid gaps.
