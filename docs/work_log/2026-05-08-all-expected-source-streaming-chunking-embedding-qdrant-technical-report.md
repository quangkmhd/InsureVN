# Báo cáo streaming chunking, embedding và Qdrant cho toàn bộ expected source

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-08-all-expected-source-streaming-chunking-embedding-qdrant-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval và Ingestion; report về chunking, embedding và Qdrant indexing.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-08-all-expected-source-streaming-chunking-embedding-qdrant-technical-report.md`
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
