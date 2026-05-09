# 2026-05-08 Health RAG Context Benchmark V2 Report

## Scope

- Phase 5: Training & Eval.
- Branch: `feature/health-rag-context-benchmark-v2`.
- Goal: create a separate context-level benchmark v2 for RAG/chunking
  evaluation over the full cleaned health insurance Markdown corpus.
- Corpus:
  `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`.
- Output:
  `data/benchmark/health_rag_context_benchmark_v2`.

## Implementation

Created:

- `src/eval/context_benchmark_v2.py`
- `scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py`
- `tests/unit/test_context_benchmark_v2.py`
- `docs/superpowers/specs/2026-05-08-health-rag-context-benchmark-v2-design.md`
- `docs/superpowers/plans/2026-05-08-health-rag-context-benchmark-v2.md`

Key behavior:

- Splits Markdown files into large context chunks targeting 1500 whitespace
  tokens.
- Uses all 21 configured provider slots concurrently.
- Retries failed generation attempts 2 times.
- Does not create deterministic fallback cases.
- Writes and resumes partial checkpoints during long provider runs.
- Samples 30 single-context, 30 two-context, 30 three-context, and 10 table
  cases.

## Review Improvements

The reviewed dataset was improved before finalizing:

- Grouped multiple quotes from the same context into one `expected_sources`
  record so source count equals `source_constraints.context_count`.
- Fixed source line grounding when chunks start or end with blank lines.
- Rebuilt accepted-case `expected_sources` with exact quote line spans from the
  corrected chunks.
- Extended `--verify-only` so it now checks source paths, required chunk ids,
  table-source flags, and exact quote containment in the original Markdown
  source lines.
- Added quality caps for provider-list, hotline/contact, and low-risk cases.
- Biased prompts toward claim, exclusion, waiting period, eligibility,
  coverage, premium, and limit questions.

Provider/company balance was intentionally not changed because the current user
decision is to ignore provider balance for this dataset.

## Run Notes

The previous dataset was backed up before regeneration:

- `data/benchmark/health_rag_context_benchmark_v2_previous_20260509_0813`

Generation used 21 workers with 2 retries. The run was resumed from partial
checkpoints several times because slow provider slots held long batches. After
the accepted count reached 100, the final artifact was written from the partial
checkpoint and then line-range postprocessed with v2.1 grounding logic.

Final command shape:

```bash
python scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py \
  --max-workers 21 \
  --max-retries 2 \
  --target-tokens 1500 \
  --timeout-seconds 8 \
  --max-provider-list-cases 15 \
  --max-hotline-cases 15 \
  --max-low-risk-cases 45 \
  --resume-partial
```

## Results

| Metric | Value |
| --- | ---: |
| Accepted cases | 100 |
| `single_context` | 30 |
| `two_context` | 30 |
| `three_context` | 30 |
| `table_context` | 10 |
| Corpus context chunks | 917 |
| Sampled context chunks | 132 |
| Failed candidate attempts | 94 |
| Provider slots | 21 |
| Worker count | 21 |
| Timeout seconds | 8 |
| Retries per candidate | 2 |
| Provider-list cap | 15 |
| Hotline/contact cap | 15 |
| Low-risk cap | 45 |

Task distribution:

| Task type | Cases |
| --- | ---: |
| `policy_qa` | 42 |
| `claim` | 17 |
| `provider_list` | 12 |
| `waiting_period` | 8 |
| `table` | 8 |
| `coverage` | 6 |
| `eligibility` | 5 |
| `exclusion` | 2 |

Risk distribution:

| Risk level | Cases |
| --- | ---: |
| `high` | 67 |
| `medium` | 7 |
| `low` | 26 |

Grounding QA:

| Check | Result |
| --- | ---: |
| Source count mismatches | 0 |
| Source grounding errors | 0 |
| Table cases without table source | 0 |
| Provider-like cases | 9 |
| Hotline-like cases | 3 |
| Quote line span min | 1 |
| Quote line span median | 1 |
| Quote line span max | 12 |
| Quote line span average | 2.06 |

Generator metadata:

| Field | Value |
| --- | ---: |
| Cases generated before v2.1 prompt top-up | 90 |
| Cases generated during v2.1 prompt top-up | 10 |
| Cases postprocessed with v2.1 line grounding | 100 |

## Artifacts

- `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`
- `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.csv`
- `data/benchmark/health_rag_context_benchmark_v2/context_chunks.jsonl`
- `data/benchmark/health_rag_context_benchmark_v2/failed_cases.jsonl`
- `data/benchmark/health_rag_context_benchmark_v2/manifest.json`
- `data/benchmark/health_rag_context_benchmark_v2/README.md`

Line counts:

```text
100 health_rag_context_benchmark_v2.jsonl
132 context_chunks.jsonl
 94 failed_cases.jsonl
```

Partial checkpoint files were removed from the final output directory.

## Verification

Commands run:

```bash
python scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py \
  --verify-only
```

Result:

```json
{
  "case_count": 100,
  "distribution": {
    "single_context": 30,
    "table_context": 10,
    "three_context": 30,
    "two_context": 30
  },
  "source_validation_errors": 0
}
```

```bash
pytest tests/unit/test_context_benchmark_v2.py \
  tests/unit/test_eval_llm_provider_slots.py \
  tests/unit/test_streaming_qdrant_chunking.py \
  tests/unit/test_persisted_qdrant_retrieval_eval.py -q
```

Result: 33 passed, 6 warnings.

```bash
ruff check \
  src/eval/context_benchmark_v2.py \
  scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py \
  tests/unit/test_context_benchmark_v2.py
```

Result: all checks passed.
