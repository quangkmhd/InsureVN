# InsureVN Chunking Evaluation

This package builds one local Qdrant database per chunking strategy and
evaluates retrieval with DeepEval's supported RAG metrics:
`ContextualPrecisionMetric`, `ContextualRecallMetric`, and
`ContextualRelevancyMetric`.

Default command:

```bash
python -m src.eval run \
  --benchmark-path data/benchmark/health_rag_benchmark/health_insurance_rag_benchmark.jsonl \
  --corpus-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned
```

By default the runner uses `--limit-documents 10` and selects those files from
benchmark primary sources, not alphabetic corpus order. Benchmark cases are
then filtered to cases whose primary source is among the loaded files, so
chunking, embedding, retrieval, and evaluation use the same 10-file corpus.
Use `--limit-documents 0` to run the full corpus.

Smoke test without LLM judge:

```bash
python -m src.eval run \
  --strategies markdown_header_recursive_table,table_as_one_hybrid \
  --limit-documents 1 \
  --limit-cases 1 \
  --output-dir /tmp/insurevn_chunking_eval \
  --skip-deepeval
```

Default insurance benchmark strategies:

- `semantic_embedding`: semantic breakpoints with configured embeddings.
- `heading_level_table_safe`: analyzes the loaded corpus heading structure,
  chooses a cut level, merges tiny sections, recursively refines large sections,
  and never cuts through Markdown tables.
- `markdown_header_recursive_table`: Markdown headers plus recursive prose and
  table-aware chunking.
- `insurance_contract_hybrid_late`: definitions, LLM table summaries, parent
  sections, child chunks, and MiniLM retrieval embeddings.
- `llm_markdown_optimal`: sends heading-safe segments to the configured LLM with
  strict JSON output and validates that tables remain intact; invalid LLM output
  falls back to deterministic table-safe chunks.
- `markdown_then_semantic`: Markdown structure first, semantic breakpoints
  inside sections.
- `table_as_one_hybrid`: preserve important tables when possible.
- `llamaindex_markdown_element`: LlamaIndex table-aware parser with Gemini.
- `hierarchical_header_recursive`: header hierarchy metadata plus recursive
  children.

Active strategy files:

- `semantic.py`: `SemanticChunker` with configured semantic embeddings.
- `heading_level_table_safe.py`: corpus-selected heading split level with
  merge/split guards and table row grouping for long tables.
- `markdown_header_recursive_table.py`: Markdown headers, recursive prose
  chunks, and table chunks handled separately.
- `insurance_contract_hybrid_late.py`: insurance-contract pipeline with
  definition context, LLM table summaries, Markdown parent sections, child
  chunks, parent-child retrieval metadata, and MiniLM retrieval embeddings.
- `llm_markdown_optimal.py`: LLM-guided Markdown chunking with deterministic
  validation that tables are not cut or rewritten.
- `markdown_then_semantic.py`: Markdown section split, then semantic split.
- `table_as_one_hybrid.py`: keep short tables as one chunk, split long tables
  by row groups.
- `llamaindex_markdown_element.py`: LlamaIndex `MarkdownElementNodeParser`;
  uses the configured Gemini LLM for table summaries.
- `hierarchical_header_recursive.py`: header path metadata plus recursive children.
- `table_utils.py`: shared Markdown table helpers used by active strategies.

Not registered as fake techniques:

- Fake late chunking, neural chunking, and query-aware chunking are not exposed
  here unless implemented with their real runtime semantics. In this runner each
  strategy has a static database, so query-dependent chunking is a retrieval-time
  technique rather than a per-strategy static index.

Embedding model:

The fast local profile uses one multilingual MiniLM model for every embedding
path, including Qdrant indexing/query, semantic breakpoint chunking, and the
hybrid insurance strategy:

```bash
CHUNKING_EVAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
CHUNKING_EVAL_EMBEDDING_DEVICE=cuda
SEMANTIC_CHUNKING_EMBEDDING_PROVIDER=sentence_transformers
SEMANTIC_CHUNKING_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
SEMANTIC_CHUNKING_EMBEDDING_DEVICE=cuda
LATE_CHUNKING_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

When `insurance_contract_hybrid_late` is selected, the runner requires
`CHUNKING_EVAL_EMBEDDING_MODEL` and `LATE_CHUNKING_EMBEDDING_MODEL` to point at
the same model name. It does not coerce vector dimensions.

`semantic_embedding` and `markdown_then_semantic` use the configured semantic
embeddings for both breakpoint detection and Qdrant indexing/query. The Ollama
base URL is ignored when `SEMANTIC_CHUNKING_EMBEDDING_PROVIDER` is
`sentence_transformers`.

```bash
SEMANTIC_CHUNKING_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

The deterministic strategies still use `CHUNKING_EVAL_EMBEDDING_MODEL` unless a
strategy provides precomputed vectors. `insurance_contract_hybrid_late` keeps
the same strategy name for comparison continuity, but in this fast profile it
does not run heavy late span-pooling; Qdrant embeds its emitted chunks with
MiniLM.

Embedding cache:

Embeddings are cached in SQLite and shared across strategies/runs when the exact
provider, model, purpose, config hash, and text hash match. The cache validates
stored vector dimensions. It does not pad, truncate, or project vectors from one
embedding space into another.

```bash
CHUNKING_EVAL_EMBEDDING_CACHE_ENABLED=true
CHUNKING_EVAL_EMBEDDING_CACHE_PATH=src/eval/generated/embedding_cache/cache.sqlite
```

CLI overrides:

```bash
python -m src.eval run --embedding-cache-path /tmp/insurevn_embeddings.sqlite
python -m src.eval run --disable-embedding-cache
python -m src.eval run --embedding-model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 --late-chunking-embedding-model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Cache stats are written to `manifest.json` under `embedding_cache`.

Retry and resume:

Each strategy is retried independently. `--strategy-retries 2` means one initial
attempt plus two retries after failures. Use a stable `--run-id` to resume the
same report directory; successful strategies from a compatible prior run are
loaded from JSONL artifacts and skipped, while missing or failed strategies run
again.

LLM scoring has its own cache. When the same strategy, benchmark case,
DeepEval metric config, and retrieved contexts match a previous run in the same
`--run-id`, old `deepeval_scores.jsonl` rows are reused instead of calling the
LLM judge again. Disable this with `--disable-llm-scoring-cache`.

```bash
python -m src.eval run \
  --run-id chunking_minilm_10_files \
  --strategy-retries 2

python -m src.eval run \
  --run-id chunking_minilm_10_files \
  --no-resume \
  --disable-llm-scoring-cache
```

Resume only activates when the stored `resume_signature` matches the current
benchmark/corpus/model/chunking/evaluation settings, so changing those settings
forces a fresh run for the selected strategies.

Heading analysis:

`heading_level_table_safe` and `llm_markdown_optimal` share corpus-level heading
analysis. The selected cut level and per-level statistics are written to
`manifest.json`.

```bash
CHUNKING_EVAL_HEADING_CUT_LEVEL=0
CHUNKING_EVAL_HEADING_MAX_CHARS=6000
CHUNKING_EVAL_HEADING_MIN_CHARS=300
CHUNKING_EVAL_HEADING_MAX_TABLE_ROWS=50
```

`0` means auto-select the best heading level from the 10 loaded files. Long
tables are split by row groups with the header repeated; shorter tables are kept
whole.

Markdown element parser LLM:

LLM-dependent strategies use a multi-provider slot pool by default. Slots are
collected from Gemini Studio, Ollama, OpenRouter, and NVIDIA NIM keys in `.env`.
Each prompt is sent once to one available slot. Independent prompts run
concurrently across all available slots; if a slot returns an error or
rate-limit response, that prompt retries on the next slot.

```bash
MARKDOWN_ELEMENT_LLM_PROVIDER=multi
MARKDOWN_ELEMENT_LLM_PROVIDER_ORDER=gemini,ollama,openrouter,nvidia
MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS=120
MARKDOWN_ELEMENT_NUM_WORKERS=32
```

`manifest.json` records the number of configured LLM slots by provider, never
the API keys.

Hybrid insurance strategy:

`insurance_contract_hybrid_late` prepares definitions, parent context, child
chunks, and table summaries. For fast local evaluation, it no longer loads a
long-context Hugging Face embedding model or stores precomputed late vectors.
The default embedding model remains MiniLM:

```bash
LATE_CHUNKING_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
LATE_CHUNKING_MAX_TOKENS=8192
```
