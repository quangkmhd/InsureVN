# Streaming Chunking + Embedding + Qdrant Report

Date: 2026-05-08

Run directory:
`data/eval_runs/20260508_162320_streaming_chunking_embedding_qdrant`

Scope:
- 10 benchmark source files from `data/benchmark/health_rag_benchmark`
- Chunking + embedding only
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Device: CUDA
- Embedding batch size: 2
- Processing mode: strategy -> file -> chunk -> embed -> Qdrant upsert
- Qdrant mode: incremental upsert per file
- Qdrant indexes kept for later retrieval evaluation

Safety controls:
- Process pinned to one CPU core with `taskset -c 0`
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

| Strategy | Status | Files | Qdrant points |
| --- | --- | ---: | ---: |
| semantic_embedding | completed | 10 | 667 |
| heading_level_table_safe | completed | 10 | 651 |
| markdown_header_recursive_table | completed | 10 | 6711 |
| insurance_contract_hybrid_late | completed | 10 | 6860 |
| markdown_then_semantic | completed | 10 | 1287 |
| table_as_one_hybrid | completed | 10 | 6529 |
| hierarchical_header_recursive | completed | 10 | 3478 |

Qdrant directory sizes:

| Strategy | Size |
| --- | ---: |
| heading_level_table_safe | 5.7M |
| semantic_embedding | 5.5M |
| markdown_then_semantic | 8.4M |
| hierarchical_header_recursive | 19M |
| table_as_one_hybrid | 34M |
| markdown_header_recursive_table | 36M |
| insurance_contract_hybrid_late | 43M |

Notes:
- `embedding_cache.sqlite` is not the retrieval database. It only caches encoded
  text vectors so repeated runs do not recompute the same embeddings.
- The persisted retrieval indexes are the Qdrant directories under `qdrant/`.
- The run directory size after completion was about 455M, mostly from the
  embedding cache.
