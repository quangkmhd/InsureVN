# All Expected Source Streaming Chunking + Embedding + Qdrant Report

Date: 2026-05-08

Phase: Phase 5 - Training & Eval, Phase 6 - Qdrant vector ingestion artifact.

Run directory:
`data/eval_runs/20260508_164948_all_expected_sources_streaming_chunking_embedding_qdrant`

Scope:
- Benchmark directory:
  `data/benchmark/health_rag_benchmark`
- Benchmark JSONL cases: 150
- Unique primary source paths: 20
- Unique expected source paths: 86
- Processed source selection: all 86 expected source paths found in the corpus
- Strategies: 7
- Per-file rows: 602

Runtime configuration:
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Device: CUDA
- Embedding batch size: 2
- Processing mode: strategy -> file -> chunk -> embed -> Qdrant upsert
- Qdrant mode: incremental upsert per file
- Qdrant indexes kept for later retrieval evaluation
- LLM calls: not used in this run

Safety controls:
- Pinned to one CPU core with `taskset -c 0`
- Thread fan-out limited with `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`
- Resource guard enabled with CPU threshold 85% and minimum available memory 3000 MiB
- No resource guard abort marker was produced

Outputs:
- Manifest: `out/manifest.json`
- Per-file stats: `out/streaming_file_results.csv`
- Per-strategy stats: `out/streaming_strategy_results.csv`
- Qdrant indexes: `qdrant/<strategy>/`
- Embedding cache: `embedding_cache.sqlite`

Strategy summary:

| Strategy | Status | Files | Qdrant Points |
| --- | --- | ---: | ---: |
| semantic_embedding | completed | 86 | 2232 |
| heading_level_table_safe | completed | 86 | 3816 |
| markdown_header_recursive_table | completed | 86 | 16358 |
| insurance_contract_hybrid_late | completed | 86 | 17566 |
| markdown_then_semantic | completed | 86 | 6759 |
| table_as_one_hybrid | completed | 86 | 15129 |
| hierarchical_header_recursive | completed | 86 | 11673 |

Notes:
- `embedding_cache.sqlite` only caches encoded text vectors. It is not the
  retrieval database.
- Persisted retrieval indexes are the Qdrant directories under `qdrant/`.
- The run directory size after completion was about 1.3G.
- After completion, RAM available was about 8.8 GiB and GPU memory returned to
  about 284 MiB.
