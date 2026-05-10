# 2026-05-08 - Báo cáo Health RAG Context Benchmark V2

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-08-health-rag-context-benchmark-v2-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval; triển khai và kết quả Health RAG Context Benchmark V2.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-08-health-rag-context-benchmark-v2-technical-report.md`
- Lệnh quét danh sách file: `find docs/work_log -maxdepth 2 -type f -print | sort`
- Lệnh kiểm tra heading: `rg -n '^#{1,3} ' docs/work_log/*.md`
- Kiểm tra template: đã kiểm tra sự tồn tại của `## 1. Tóm tắt điều hành` trong toàn bộ file work log

Bằng chứng, lệnh, đường dẫn, số liệu và hiện vật đầu ra riêng của task gốc vẫn được giữ trong Mục 10.

## 6. Xác minh

Các bước xác minh đã thực hiện cho lần chuẩn hóa tài liệu này:

- Đã xác nhận file nằm trong `docs/work_log/`.
- Đã thêm đầy đủ các mục bắt buộc của báo cáo kỹ thuật.
- Đã giữ nguyên phần nội dung cũ thay vì viết lại metrics hoặc kết luận lịch sử.

Xác minh riêng của task gốc, nếu có, vẫn nằm trong Mục 10.

## 7. Kết quả

Báo cáo hiện đã theo cấu trúc báo cáo kỹ thuật của InsureVN. Các kết quả, số liệu benchmark, quyết định và tham chiếu hiện vật đầu ra gốc vẫn nằm trong Mục 10.

## 8. Rủi ro và giới hạn

- Các lệnh lịch sử và kết quả benchmark không được chạy lại trong lần chuẩn hóa này.
- Bất kỳ đường dẫn, metric hoặc trạng thái nào trong nội dung gốc đều là dữ liệu lịch sử cho tới khi được xác minh lại.
- Không nên xem tài liệu này là một lần chạy đánh giá mới nếu Mục 10 không có bằng chứng xác minh hiện tại.

## 9. Việc tiếp theo

- Giữ báo cáo này đồng bộ với mã nguồn, lệnh và hiện vật đầu ra mà nó tham chiếu.
- Chạy lại bước xác minh riêng của task trước khi dùng metrics lịch sử cho quyết định kỹ thuật mới.

## 10. Nội dung gốc được giữ lại

### Scope

- Phase 5: Training & Eval.
- Branch: `feature/health-rag-context-benchmark-v2`.
- Goal: create a separate context-level benchmark v2 for RAG/chunking
  evaluation over the full cleaned health insurance Markdown corpus.
- Corpus:
  `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`.
- Output:
  `data/benchmark/health_rag_context_benchmark_v2`.

### Implementation

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

### Review Improvements

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

### Run Notes

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

### Results

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

### Artifacts

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

### Verification

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
