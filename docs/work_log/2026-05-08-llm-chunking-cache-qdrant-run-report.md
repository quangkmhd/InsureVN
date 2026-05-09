# 2026-05-08 LLM Chunking Cache + Qdrant Run Report

## Scope

- Phase 5: Training & Eval - run LLM chunking comparison for the health RAG benchmark corpus.
- Phase 6: Ingestion - embed chunks and persist them into per-strategy local Qdrant stores.
- Source set: 86 expected-source Markdown files from `data/benchmark/health_rag_benchmark`.
- Strategies: `llm_markdown_optimal`, `llamaindex_markdown_element`.

## Runtime Configuration

- Run directory: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed`
- Chunk cache: `data/eval_chunk_cache/chunk_boundaries`
- Chunk records: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_chunk_records.jsonl`
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Embedding device: `cuda`
- Embedding mode: batch size 2, file-by-file, then incremental Qdrant upsert.
- LLM provider pool: 21 slots total: Gemini 5, Ollama 5, OpenRouter 6, NVIDIA 5.
- LLM worker setting: `--markdown-element-num-workers 0`, resolved to 21 workers.
- Provider failover limit: 4 slot attempts per prompt, 15 second timeout per slot attempt.
- CPU/RAM guard: enabled, CPU abort threshold 85%, minimum available memory 2048 MiB.

## Results

| Strategy | Files | Status | Chunks / Qdrant points | Cache hits | LLM fallback chunks | Duration |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: |
| `llm_markdown_optimal` | 86 | completed | 6,315 | 86 | 5,145 | 86.600s |
| `llamaindex_markdown_element` | 86 | completed | 3,850 | 8 | 3,542 | 541.340s |

Total file-strategy rows: 172/172 completed.

Total failed rows: 0.

Total cached chunk boundary files after the run: 172.

Final run size: 158 MiB. Chunk cache size: 32 MiB.

## Important Notes

- `llm_markdown_optimal` used cached chunk boundaries from the earlier interrupted run, so the final fixed run did not call LLM again for those 86 files.
- `llamaindex_markdown_element` originally failed on many files due LlamaIndex nested async and provider errors. The wrapper was changed to use LlamaIndex async entrypoint and to fall back to deterministic table-safe chunking when table-summary LLM calls fail.
- `llamaindex_markdown_element` completed all files, but 70 files used full fallback chunks because provider slots returned rate limits, timeouts, or server errors. These are marked by `llm_fallback=True` and `llamaindex_fallback=True` in chunk metadata.
- `llm_markdown_optimal` had 3 fully fallback files, 82 partially fallback files, and 1 file with no fallback chunks. Segment-level fallback is recorded in each chunk metadata.
- Each chunk record includes `start_char`, `end_char`, `start_line`, `end_line`, chunk text, metadata, source hash, and cache path. This allows later embedding/Qdrant rebuilds without re-running LLM chunking.

## Verification

- `ruff check` passed for changed evaluation files.
- Unit tests passed: `tests/unit/test_streaming_qdrant_chunking.py` and `tests/unit/test_eval_llm_provider_slots.py`.
- Smoke checks verified:
  - cached boundaries are reused with `chunk_cache_hit=True` and near-zero chunk time;
  - `llamaindex_markdown_element` no longer emits failed rows when provider calls fail; it records deterministic fallback chunks instead.

## Output Artifacts

- File-level CSV: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_file_results.csv`
- Strategy CSV: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_strategy_results.csv`
- Per-chunk records: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_chunk_records.jsonl`
- Qdrant `llm_markdown_optimal`: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/qdrant/llm_markdown_optimal`
- Qdrant `llamaindex_markdown_element`: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/qdrant/llamaindex_markdown_element`
