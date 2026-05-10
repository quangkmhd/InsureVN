# 2026-05-09 - Báo cáo quyết định cuối cùng cho chunking 900/150 so với 512/50

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-final-chunking-900-150-vs-512-50-decision-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval; report quyết định kỹ thuật cho cấu hình chunking mặc định.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-final-chunking-900-150-vs-512-50-decision-technical-report.md`
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

- Nên tạo ADR nếu lựa chọn chunking trở thành chính sách kiến trúc dài hạn.
- Chạy lại benchmark khi tài liệu nguồn, embedding model hoặc tham số retrieval thay đổi.

## 10. Nội dung gốc được giữ lại

### Scope

- Phase 5: Training & Eval.
- Benchmark:
  `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`.
- Cases: 100.
- Retrieval eval: persisted Qdrant, dense retrieval, no LLM judge.
- Branch decision: `feat/hierarchical-table-chunking` was **not merged** and
  was deleted after evaluation.

### Decision

Keep the eval baseline configuration:

- `DEFAULT_CHUNK_SIZE = 900`
- `DEFAULT_CHUNK_OVERLAP = 150`

Do **not** replace the baseline with `512/50`.

Keep `hierarchical_header_recursive` as the preferred benchmark winner. Do
**not** replace it with the combined
`hierarchical_header_recursive_table_aware` approach for the current retrieval
benchmark.

### Evidence

#### Top-K=5

| Param | Strategy | Points | MRR@5 | Source recall@5 | Line overlap@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| 900/150 | `hierarchical_header_recursive` | 9,518 | 0.3973 | 0.6200 | 0.2183 |
| 900/150 | `table_as_one_hybrid` | 13,222 | 0.4222 | 0.6000 | 0.1900 |
| pre-512 combined | `hierarchical_header_recursive_table_aware` | 12,105 | 0.3818 | 0.5800 | 0.1817 |
| 512/50 | `hierarchical_header_recursive` | 16,354 | 0.3668 | 0.5300 | 0.1600 |
| 512/50 | `table_as_one_hybrid` | 19,454 | 0.3625 | 0.5400 | 0.1467 |
| 512/50 | `hierarchical_header_recursive_table_aware` | 16,266 | 0.3588 | 0.5300 | 0.1750 |

At top-k=5, `hierarchical_header_recursive` with `900/150` is the best broad
retrieval choice:

- It beats `hierarchical_header_recursive` with `512/50` by `+0.0900`
  source recall and `+0.0583` line overlap.
- It beats the combined table-aware method at `512/50` by `+0.0900`
  source recall and `+0.0433` line overlap.
- It beats the best pre-512 combined table-aware run by `+0.0400`
  source recall and `+0.0366` line overlap.

#### Top-K=10

| Param | Strategy | Points | MRR@10 | Source recall@10 | Line overlap@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| 900/150 | `hierarchical_header_recursive` | 9,518 | 0.4126 | 0.7300 | 0.2533 |
| 900/150 | `table_as_one_hybrid` | 13,222 | 0.4373 | 0.7100 | 0.2650 |
| pre-512 combined | `hierarchical_header_recursive_table_aware` | 12,105 | 0.3936 | 0.6700 | 0.2317 |
| 512/50 | `hierarchical_header_recursive` | 16,354 | 0.3881 | 0.7000 | 0.1967 |
| 512/50 | `table_as_one_hybrid` | 19,454 | 0.3812 | 0.6800 | 0.1917 |
| 512/50 | `hierarchical_header_recursive_table_aware` | 16,266 | 0.3721 | 0.6300 | 0.2400 |

At top-k=10, increasing retrieval depth helps smaller chunks, but it does not
change the main decision:

- `hierarchical_header_recursive` with `900/150` still has the best source
  recall among the three method families: `0.7300`.
- `table_as_one_hybrid` with `900/150` has the best MRR and line overlap, but
  its source recall remains below `hierarchical_header_recursive`.
- The combined table-aware method with `512/50` improves table locality, but
  its total source recall is only `0.6300`, below `hierarchical_header_recursive`
  at both `900/150` and `512/50`.

### Why 900/150 Beats 512/50

The benchmark questions were generated from larger source contexts, while
retrieval is scored over final Qdrant chunks. `512/50` fragments evidence more
aggressively:

- `hierarchical_header_recursive` grows from `9,518` points at `900/150` to
  `16,354` points at `512/50`.
- More points means more near-candidates compete for the same top-k budget.
- Multi-context questions need evidence from multiple contexts; smaller chunks
  consume more top-k slots to cover the same answer.
- The embedding model ranks chunk text only. Metadata is stored as payload and
  does not help dense vector ranking.

So `512/50` can improve locality in some cases, but it lowers broad retrieval
recall under raw dense top-k scoring.

### Why Hierarchical Beats The Combined Method

The combined method was intended as:

`hierarchical_header_recursive + table_as_one_hybrid`

But in practice it is not a simple additive merge. It creates a new chunk space:

- Table chunks, row-group chunks, repeated headers, and interpretation chunks
  compete with normal prose chunks.
- The current evaluator retrieves raw chunks. It does not expand by
  `table_group_id`, fetch linked `table_interpretation`, or collapse table
  groups before scoring.
- Benchmark v2 has only 10 table cases out of 100. Table-specific gains cannot
  compensate for lower broad recall across non-table cases.
- The combined method changes chunk boundaries around sections containing
  tables and interpretations, so it does not preserve the exact
  `hierarchical_header_recursive` non-table behavior.

The combined method is useful as a production evidence-lineage idea, but the
current benchmark rewards direct top-k source recall. For that benchmark,
`hierarchical_header_recursive` remains better.

### Final Recommendation

Use this as the current benchmark default:

```python
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 150
strategy = "hierarchical_header_recursive"
```

Do not adopt `512/50` as the eval default based on the current evidence. Do not
merge the combined table-aware branch into main.

If table-aware chunking is revisited later, evaluate it with a group-aware
retrieval pipeline:

1. Dense prefetch top 20-50.
2. Expand table chunks by `table_group_id`.
3. Attach linked `table_interpretation`.
4. Rerank or collapse evidence groups.
5. Score final evidence groups, not only raw chunks.

### Artifacts

- Baseline top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval`
- Baseline top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval_top10`
- HHR 512/50 top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_hhr_512_retrieval_eval`
- HHR 512/50 top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_hhr_512_retrieval_eval_top10`
- table-as-one 512/50 top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_table_as_one_512_retrieval_eval_top5`
- table-as-one 512/50 top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_table_as_one_512_retrieval_eval_top10`
- combined table-aware 512/50 top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_hhrr_table_aware_512_retrieval_eval`
- combined table-aware 512/50 top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_hhrr_table_aware_512_retrieval_eval_top10`

### Verification

- Removed worktree:
  `/home/quangnhvn34/dev/me/InsureVN/.worktrees/hierarchical-table-chunking`
- Deleted branch:
  `feat/hierarchical-table-chunking`
- Verified only `main` remains in `git worktree list`.
- Ran top-k=5 retrieval eval for `table_as_one_hybrid` at `512/50` to complete
  the comparison matrix.

Note: retrieval commands emitted the existing torchao compatibility warning for
Torch `2.6.0+cu124` and torchao `0.15.0`; it did not stop evaluation.
