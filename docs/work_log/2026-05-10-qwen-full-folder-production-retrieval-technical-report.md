# 2026-05-10 - Báo cáo kỹ thuật đánh giá retrieval production Qwen trên full folder

## 1. Tóm tắt điều hành

Ngày 10 tháng 5 năm 2026, tôi đã chạy một vòng đánh giá retrieval production-style cho `Qwen/Qwen3-Embedding-8B` trên toàn bộ folder `/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned`, thay vì chỉ trên benchmark-subset index. Run này index `107` markdown documents thành `9,933` Qdrant points trong collection riêng `insurevn_qwen_prod_eval_20260510_full`, sau đó chạy benchmark `89` câu hỏi trên cả `VECTOR` và `HYBRID`.

Kết quả chính là `HYBRID` vượt `VECTOR` khá rõ trên toàn cục. `source_hit@10` tăng từ `63/89` lên `77/89`, `quote_hit@10` tăng từ `37/77` lên `53/77`, và `MRR@10` tăng từ `0.4426` lên `0.5257`. Trên benchmark `v3_multifile`, `HYBRID` không cải thiện `source_hit@10` so với `VECTOR`, nhưng cải thiện `source_hit@5` và `quote_hit@10`, cho thấy hybrid hữu ích chủ yếu ở việc kéo đúng evidence lên cao hơn trong ranking.

## 2. Mục tiêu và phạm vi

Mục tiêu của run này là xác minh retrieval quality của stack production hiện tại sau khi dự án đã chốt dense embedding production sang `Qwen/Qwen3-Embedding-8B`. Phạm vi được giữ ở retrieval-only:

- không sinh answer
- không chấm citation generation của LLM
- không dùng `src/eval` pipeline cũ để tránh lệch khỏi production path

Phạm vi benchmark:

- full-folder corpus under `health_insurance_markdowns_interpreted_cleaned`
- `vector` mode
- `hybrid` mode
- `top_k = 10`
- không áp hard filters để tạo bài test full-corpus khó hơn

## 3. Bối cảnh

Run này thuộc phase `Training & Eval` nhưng bám trực tiếp vào production retrieval stack của Evidence Foundation `Qdrant`, không dùng evaluator dense-only cũ trong `src/eval`. Điều này quan trọng vì production code hiện tại đã:

- dùng `Qwen/Qwen3-Embedding-8B`
- dùng `Qdrant/bm25` cho hybrid
- dùng chunking config production `hierarchical_header_recursive` với `1200/150`

Do đó, kết quả trong báo cáo này phản ánh hành vi retrieval gần production hơn benchmark embedding/chunking lịch sử.

## 4. Triển khai

### 4.1 Index full-folder vào collection riêng

Tôi tạo một collection benchmark riêng `insurevn_qwen_prod_eval_20260510_full` để không đụng collection mặc định của app. Index run được thực hiện qua script production ingestion:

```bash
RAG_QDRANT_COLLECTION=insurevn_qwen_prod_eval_20260510_full \
python scripts/06_db_ingestion/09_index_all_markdowns.py \
  --markdown-dir /home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned \
  --table-mapping-json /home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns/table_mapping.json \
  --ingestion-version qwen_full_folder_eval_20260510 \
  --recreate-qdrant \
  --skip-neo4j \
  --skip-chunk-export \
  --skip-graph-json
```

Để xác định tổng chunk count kỳ vọng, tôi còn chạy một dry-run chỉ chunking, không Qdrant, không Neo4j. Kết quả dry-run cho thấy:

- `document_count = 107`
- `chunk_count = 9933`

### 4.2 Thêm runner benchmark production-style

Vì benchmark JSONL trong folder này không cùng schema với evaluator cũ, tôi thêm runner mới:

- `scripts/05_training_eval/run_production_qdrant_retrieval_eval.py`

Runner này:

- parse trực tiếp benchmark JSONL
- build `QdrantRetriever` từ production path
- chạy cả `VECTOR` và `HYBRID`
- lưu `manifest`, `summary`, `provider summary`, `case metrics`, và `retrievals`

### 4.3 Chạy retrieval benchmark

Sau khi index xong full `9,933` points, watcher tự động bắt đầu benchmark:

```bash
/usr/bin/time -f '{"elapsed_seconds":%e,"max_rss_kb":%M}' \
  -o data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_eval_runtime.txt \
  python scripts/05_training_eval/run_production_qdrant_retrieval_eval.py \
    --corpus-dir /home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned \
    --benchmark-dir /home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned/benchmark \
    --output-dir /home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval \
    --collection-name insurevn_qwen_prod_eval_20260510_full \
    --top-k 10
```

## 5. Bằng chứng và lệnh đã chạy

Các lệnh và bằng chứng chính:

- đếm markdown files trong corpus: `107`
- kiểm tra provider distribution của corpus
- kiểm tra benchmark distribution:
  - `v1 = 12`
  - `v2 = 52`
  - `v3_multifile = 25`
- dry-run chunk-only để lấy `chunk_count = 9933`
- `nvidia-smi` xác nhận runtime local:
  - `NVIDIA GeForce RTX 4060`
  - `7015 MiB / 8188 MiB`
  - `100% GPU utilization` tại thời điểm kiểm tra
- `index_report.json` xác nhận full index thành công
- `retrieval_eval_runtime.txt` xác nhận runtime benchmark `96.02s`

Artifact chính:

- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/index_report.json`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/manifest.json`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_summary.csv`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_provider_summary.csv`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_case_metrics.csv`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrievals.jsonl`

## 6. Xác minh

Các điều kiện xác minh đã đạt:

- collection point count đạt đúng `9,933`
- index process kết thúc sạch
- `index_report.json` có nội dung và báo:
  - `document_count = 107`
  - `chunk_count = 9933`
  - `qdrant_indexed = true`
  - `required_metadata_valid = true`
- retrieval benchmark kết thúc sạch và sinh đầy đủ artifact files
- runner benchmark mới đã được:
  - `ruff format`
  - `ruff check`

Runtime benchmark:

- `elapsed_seconds = 96.02`
- `max_rss_kb = 5768668`

## 7. Kết quả

### 7.1 Kết quả tổng thể

`HYBRID` là winner rõ ràng trên toàn bộ benchmark:

- `source_hit@10`: `77/89` so với `63/89`
- `source_hit@5`: `67/89` so với `57/89`
- `quote_hit@10`: `53/77` so với `37/77`
- `MRR@10`: `0.5257` so với `0.4426`

Ở góc nhìn case-level:

- `HYBRID-only hits@10`: `16` cases
- `VECTOR-only hits@10`: `2` cases
- `both_hit@10`: `61` cases
- `both_miss@10`: `10` cases

### 7.2 Theo benchmark

`v1`:

- `VECTOR`: `9/12` hit ở `@10`
- `HYBRID`: `11/12` hit ở `@10`

`v2`:

- `VECTOR`: `34/52` hit ở `@10`
- `HYBRID`: `46/52` hit ở `@10`

`v3_multifile`:

- `VECTOR`: `20/25` hit ở `@10`
- `HYBRID`: `20/25` hit ở `@10`
- `HYBRID` tăng `source_hit@5` từ `16/25` lên `20/25`
- `HYBRID` tăng `quote_hit@10` từ `0.56` lên `0.68`

Kết luận cho `v3_multifile` là hybrid không tăng recall tuyệt đối ở `@10`, nhưng tăng ranking quality ở top positions.

### 7.3 Theo provider

Provider khó nhất là `aia.com.vn`:

- aggregate all benchmarks:
  - `VECTOR source_hit@10 = 0.3333`
  - `HYBRID source_hit@10 = 0.3333`
- riêng `v3_multifile`:
  - `VECTOR source_hit@10 = 0.4`
  - `HYBRID source_hit@10 = 0.4`

Provider mạnh:

- `baominh.com.vn`: `HYBRID source_hit@10 = 1.0`
- `pti.com.vn`: `HYBRID source_hit@10 = 0.9091`
- `bic.vn`: `HYBRID source_hit@10 = 0.8333`

Một điểm cần lưu ý là aggregate provider summary bị skew mạnh bởi `pti.com.vn` vì PTI chiếm `66` benchmark cases.

### 7.4 Latency

Steady-state query latency thực tế của cả hai mode khá gần nhau:

- `HYBRID latency_ms_avg = 319.617`
- `HYBRID latency_ms_p95 = 340.346`
- `VECTOR latency_ms_p95 = 341.134`

`VECTOR latency_ms_avg = 674.554` không phản ánh steady-state vì bị kéo lên bởi cold-start query đầu tiên:

- max latency vector: `32081.771 ms`
- nếu loại outlier cold-start này, `VECTOR avg ≈ 317.654 ms`

Điều này cho thấy steady-state retrieval cost của `Qwen + Qdrant` trong local environment này là khoảng `0.31s` mỗi query retrieval, còn cold-start model load là một chi phí riêng cần ghi nhận.

## 8. Rủi ro và giới hạn

- Run này không dùng hard filters. Trong production, supervisor có thể cung cấp filter theo `company_code`, `document_id`, hoặc `section_type`, nên kết quả ở đây có thể đang bi quan hơn production filtered path.
- Benchmark này là retrieval-only. Nó chưa đánh giá answer correctness hay citation formatting của LLM agent.
- Metric `line_overlap` chưa được đo trong run production-style này vì chunk payload production hiện không mang line span. Do đó tôi dùng `source_hit` và `quote_hit` làm metric grounded retrieval thay thế.
- `v1` và `v2` skew mạnh về PTI; cross-provider fairness chủ yếu nên nhìn ở `v3_multifile`.
- `VECTOR avg latency` bị méo bởi cold start của query đầu tiên; cần nhìn thêm `p95` và steady-state interpretation.

## 9. Việc tiếp theo

- Chạy thêm một vòng `HYBRID` với hard filters theo provider để đo upper-bound retrieval khi supervisor route/filter đúng.
- Đánh giá reranker trên shortlist hiện tại, bắt đầu từ `HYBRID + Qwen`.
- Thực hiện answer-level evaluation sau khi retrieval path đã đủ ổn định.
- Nếu muốn tiếp tục dùng `line_overlap`, cần mở rộng production chunk payload để lưu line-span metadata.
- Nên tạo ADR nếu dự án muốn chốt `HYBRID` là retrieval mode mặc định cho production Qwen path.
