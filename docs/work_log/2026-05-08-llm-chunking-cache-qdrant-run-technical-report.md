# 2026-05-08 - Báo cáo chạy LLM Chunking Cache và Qdrant

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-08-llm-chunking-cache-qdrant-run-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval và Ingestion; report chạy LLM chunking cache và Qdrant.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-08-llm-chunking-cache-qdrant-run-technical-report.md`
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

- Phase 5: Training & Eval - run LLM chunking comparison for the health RAG benchmark corpus.
- Phase 6: Ingestion - embed chunks and persist them into per-strategy local Qdrant stores.
- Source set: 86 expected-source Markdown files from `data/benchmark/health_rag_benchmark`.
- Strategies: `llm_markdown_optimal`, `llamaindex_markdown_element`.

### Runtime Configuration

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

### Results

| Strategy | Files | Status | Chunks / Qdrant points | Cache hits | LLM fallback chunks | Duration |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: |
| `llm_markdown_optimal` | 86 | completed | 6,315 | 86 | 5,145 | 86.600s |
| `llamaindex_markdown_element` | 86 | completed | 3,850 | 8 | 3,542 | 541.340s |

Total file-strategy rows: 172/172 completed.

Total failed rows: 0.

Total cached chunk boundary files after the run: 172.

Final run size: 158 MiB. Chunk cache size: 32 MiB.

### Important Notes

- `llm_markdown_optimal` used cached chunk boundaries from the earlier interrupted run, so the final fixed run did not call LLM again for those 86 files.
- `llamaindex_markdown_element` originally failed on many files due LlamaIndex nested async and provider errors. The wrapper was changed to use LlamaIndex async entrypoint and to fall back to deterministic table-safe chunking when table-summary LLM calls fail.
- `llamaindex_markdown_element` completed all files, but 70 files used full fallback chunks because provider slots returned rate limits, timeouts, or server errors. These are marked by `llm_fallback=True` and `llamaindex_fallback=True` in chunk metadata.
- `llm_markdown_optimal` had 3 fully fallback files, 82 partially fallback files, and 1 file with no fallback chunks. Segment-level fallback is recorded in each chunk metadata.
- Each chunk record includes `start_char`, `end_char`, `start_line`, `end_line`, chunk text, metadata, source hash, and cache path. This allows later embedding/Qdrant rebuilds without re-running LLM chunking.

### Verification

- `ruff check` passed for changed evaluation files.
- Unit tests passed: `tests/unit/test_streaming_qdrant_chunking.py` and `tests/unit/test_eval_llm_provider_slots.py`.
- Smoke checks verified:
  - cached boundaries are reused with `chunk_cache_hit=True` and near-zero chunk time;
  - `llamaindex_markdown_element` no longer emits failed rows when provider calls fail; it records deterministic fallback chunks instead.

### Output Artifacts

- File-level CSV: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_file_results.csv`
- Strategy CSV: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_strategy_results.csv`
- Per-chunk records: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/out/streaming_chunk_records.jsonl`
- Qdrant `llm_markdown_optimal`: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/qdrant/llm_markdown_optimal`
- Qdrant `llamaindex_markdown_element`: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed/qdrant/llamaindex_markdown_element`
