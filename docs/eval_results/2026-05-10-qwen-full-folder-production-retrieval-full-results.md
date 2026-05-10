# 2026-05-10 - Kết quả đầy đủ đánh giá retrieval production Qwen trên full folder

## Tóm tắt điều hành

- Đã index full folder `/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned` vào collection `insurevn_qwen_prod_eval_20260510_full` với `107` documents và `9,933` chunks.
- Trên `89` benchmark cases và `178` case-mode evaluations, `HYBRID` là mode tốt nhất tổng thể:
  - `source_hit@10`: `77/89` (`0.8652`) so với `63/89` (`0.7079`) của `VECTOR`
  - `source_hit@5`: `67/89` (`0.7528`) so với `57/89` (`0.6404`)
  - `quote_hit@10`: `53/77` (`0.6883`) so với `37/77` (`0.4805`)
  - `MRR@10`: `0.5257` so với `0.4426`
- Ở benchmark `v3_multifile`, `HYBRID` không tăng `source_hit@10` so với `VECTOR` (`20/25` cho cả hai), nhưng tăng `source_hit@5` từ `16/25` lên `20/25` và tăng `quote_hit@10` từ `14/25` lên `17/25`.
- Provider khó nhất là `aia.com.vn`. Trên `v3_multifile`, cả `VECTOR` và `HYBRID` đều chỉ đạt `source_hit@10 = 0.4` cho AIA.
- `VECTOR latency_ms_avg = 674.554` bị méo bởi cold-start query đầu tiên `32,081.771 ms`. Nếu loại cold start này, `VECTOR steady-state latency` còn khoảng `317.654 ms`, gần với `HYBRID latency_ms_avg = 319.617 ms`.

## Cấu hình run

- Corpus: `/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned`
- Benchmark files:
  - `health_insurance_rag_benchmark_v1.jsonl`: `12` cases
  - `health_insurance_rag_benchmark_v2.jsonl`: `52` cases
  - `health_insurance_rag_benchmark_v3_multifile.jsonl`: `25` cases
- Collection: `insurevn_qwen_prod_eval_20260510_full`
- Dense embedding: `Qwen/Qwen3-Embedding-8B`
- Dense vector size: `4096`
- Sparse model: `Qdrant/bm25`
- Chunking config của production path hiện tại:
  - `chunking_strategy = hierarchical_header_recursive`
  - `child_chunk_chars = 1200`
  - `child_chunk_overlap = 150`
- Retrieval modes đã chạy:
  - `vector`
  - `hybrid`
- `top_k = 10`
- Eval runtime:
  - `elapsed_seconds = 96.02`
  - `max_rss_kb = 5768668`

## Kết quả tổng hợp toàn cục

| Mode | Cases | Source@5 | Source@10 | MRR@5 | MRR@10 | Quote cases | Quote@5 | Quote@10 | Phrase cases | Phrase@5 | Phrase@10 | Latency avg ms | Latency p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid` | 89 | 0.7528 | 0.8652 | 0.5118 | 0.5257 | 77 | 0.5584 | 0.6883 | 64 | 0.4167 | 0.5208 | 319.617 | 340.346 |
| `vector` | 89 | 0.6404 | 0.7079 | 0.4330 | 0.4426 | 77 | 0.4026 | 0.4805 | 64 | 0.3854 | 0.4427 | 674.554 | 341.134 |

Ghi chú:

- `source_hit@10`: `HYBRID 77/89`, `VECTOR 63/89`
- `source_hit@5`: `HYBRID 67/89`, `VECTOR 57/89`
- `quote_hit@10`: `HYBRID 53/77`, `VECTOR 37/77`
- `VECTOR latency_ms_avg` bị đội lên vì query đầu tiên phải load model:
  - worst case: `hi_bench_001` với `32081.771 ms`
  - `VECTOR avg` nếu loại outlier này: `317.654 ms`

## Kết quả theo benchmark file

| Benchmark | Mode | Cases | Source@5 | Source@10 | MRR@5 | MRR@10 | Quote@5 | Quote@10 | Phrase@5 | Phrase@10 | Latency avg ms | Latency p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `health_insurance_rag_benchmark_v1.jsonl` | `hybrid` | 12 | 0.7500 | 0.9167 | 0.5236 | 0.5458 | 0.0000 | 0.0000 | 0.5972 | 0.7361 | 322.706 | 339.274 |
| `health_insurance_rag_benchmark_v1.jsonl` | `vector` | 12 | 0.7500 | 0.7500 | 0.5194 | 0.5194 | 0.0000 | 0.0000 | 0.5972 | 0.7361 | 2974.481 | 342.787 |
| `health_insurance_rag_benchmark_v2.jsonl` | `hybrid` | 52 | 0.7308 | 0.8846 | 0.5106 | 0.5292 | 0.5385 | 0.6923 | 0.3750 | 0.4712 | 319.233 | 340.346 |
| `health_insurance_rag_benchmark_v2.jsonl` | `vector` | 52 | 0.6154 | 0.6538 | 0.4218 | 0.4277 | 0.3846 | 0.4423 | 0.3365 | 0.3750 | 312.371 | 331.946 |
| `health_insurance_rag_benchmark_v3_multifile.jsonl` | `hybrid` | 25 | 0.8000 | 0.8000 | 0.5087 | 0.5087 | 0.6000 | 0.6800 | 0.0000 | 0.0000 | 318.932 | 338.207 |
| `health_insurance_rag_benchmark_v3_multifile.jsonl` | `vector` | 25 | 0.6400 | 0.8000 | 0.4147 | 0.4365 | 0.4400 | 0.5600 | 0.0000 | 0.0000 | 323.929 | 342.838 |

Đếm hit theo benchmark:

- `v1`:
  - `VECTOR`: `9/12` hit ở `@10`
  - `HYBRID`: `11/12` hit ở `@10`
- `v2`:
  - `VECTOR`: `34/52` hit ở `@10`
  - `HYBRID`: `46/52` hit ở `@10`
- `v3_multifile`:
  - `VECTOR`: `20/25` hit ở `@10`
  - `HYBRID`: `20/25` hit ở `@10`
  - `HYBRID` tăng `source_hit@5` từ `16/25` lên `20/25`

## Breakdown theo provider

Ghi chú quan trọng:

- Bảng dưới đây là aggregate trên toàn bộ benchmark files.
- `pti.com.vn` chiếm `66` cases nên kết quả overall bị skew đáng kể theo PTI.

| Provider | Mode | Cases | Source@5 | Source@10 | MRR@5 | MRR@10 | Quote@5 | Quote@10 | Phrase@5 | Phrase@10 | Latency avg ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `aia.com.vn` | `hybrid` | 6 | 0.3333 | 0.3333 | 0.1167 | 0.1167 | 0.6000 | 0.8000 | 0.3333 | 0.3333 | 320.640 |
| `aia.com.vn` | `vector` | 6 | 0.0000 | 0.3333 | 0.0000 | 0.0463 | 0.6000 | 0.8000 | 0.3333 | 0.3333 | 317.839 |
| `baominh.com.vn` | `hybrid` | 5 | 1.0000 | 1.0000 | 0.5067 | 0.5067 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 324.737 |
| `baominh.com.vn` | `vector` | 5 | 0.8000 | 0.8000 | 0.3333 | 0.3333 | 0.4000 | 0.6000 | 0.0000 | 0.0000 | 309.533 |
| `bic.vn` | `hybrid` | 6 | 0.8333 | 0.8333 | 0.7000 | 0.7000 | 0.3333 | 0.3333 | 0.0000 | 0.0000 | 319.397 |
| `bic.vn` | `vector` | 6 | 0.8333 | 0.8333 | 0.6111 | 0.6111 | 0.3333 | 0.3333 | 0.0000 | 0.0000 | 313.945 |
| `libertyinsurance.com.vn` | `hybrid` | 5 | 0.8000 | 0.8000 | 0.5067 | 0.5067 | 0.4000 | 0.6000 | 0.0000 | 0.0000 | 313.502 |
| `libertyinsurance.com.vn` | `vector` | 5 | 0.6000 | 1.0000 | 0.4667 | 0.5202 | 0.2000 | 0.4000 | 0.0000 | 0.0000 | 373.107 |
| `pacific_cross_all_pdfs` | `hybrid` | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.6667 | 0.6667 | 313.945 |
| `pacific_cross_all_pdfs` | `vector` | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.6667 | 0.6667 | 341.134 |
| `pti.com.vn` | `hybrid` | 66 | 0.7576 | 0.9091 | 0.5240 | 0.5427 | 0.5536 | 0.6964 | 0.4140 | 0.5215 | 319.705 |
| `pti.com.vn` | `vector` | 66 | 0.6667 | 0.6970 | 0.4525 | 0.4572 | 0.4107 | 0.4643 | 0.3817 | 0.4409 | 795.307 |

## Breakdown theo provider trên riêng benchmark `v3_multifile`

Bảng này hữu ích hơn cho so sánh cross-provider vì `v3` phân phối case cân bằng hơn.

| Provider | Mode | Cases | Source@10 | Quote@10 | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| `aia.com.vn` | `vector` | 5 | 0.4000 | 0.8000 | 0.0556 |
| `aia.com.vn` | `hybrid` | 5 | 0.4000 | 0.8000 | 0.1400 |
| `baominh.com.vn` | `vector` | 5 | 0.8000 | 0.6000 | 0.3333 |
| `baominh.com.vn` | `hybrid` | 5 | 1.0000 | 1.0000 | 0.5067 |
| `bic.vn` | `vector` | 6 | 0.8333 | 0.3333 | 0.6111 |
| `bic.vn` | `hybrid` | 6 | 0.8333 | 0.3333 | 0.7000 |
| `libertyinsurance.com.vn` | `vector` | 5 | 1.0000 | 0.4000 | 0.5202 |
| `libertyinsurance.com.vn` | `hybrid` | 5 | 0.8000 | 0.6000 | 0.5067 |
| `pti.com.vn` | `vector` | 4 | 1.0000 | 0.7500 | 0.6750 |
| `pti.com.vn` | `hybrid` | 4 | 1.0000 | 0.7500 | 0.6875 |

## So sánh case-level giữa `VECTOR` và `HYBRID`

- `HYBRID` hit được `@10` còn `VECTOR` miss: `16` cases
- `VECTOR` hit được `@10` còn `HYBRID` miss: `2` cases
- Cả hai cùng hit `@10`: `61` cases
- Cả hai cùng miss `@10`: `10` cases

Phân bố `HYBRID-only` theo benchmark:

- `v1`: `2` cases
- `v2`: `12` cases
- `v3_multifile`: `2` cases

Hai case `VECTOR-only`:

- `hi_bench_v3_003` - `aia.com.vn` - "Quyền lợi thai sản của AIA Bùng Gia Lực áp dụng theo phạm vi địa lý nào?"
- `hi_bench_v3_021` - `libertyinsurance.com.vn` - "Điều trị tâm thần trong Liberty bản 2023 áp dụng cho chương trình nào?"

Một số case `HYBRID` vẫn miss ở `@10`:

- `hi_bench_010` - AIA brochure priority
- `hi_bench_v2_005` - điều kiện chi phí y tế thực tế PTI
- `hi_bench_v2_026` - loại trừ điều trị ngoại trú PTI
- `hi_bench_v2_028` - loại trừ khám/xét nghiệm không có kết luận bệnh PTI
- `hi_bench_v2_043` - thời hạn thông báo tổn thất PTI
- `hi_bench_v2_044` - thời hạn nộp hồ sơ bồi thường PTI
- `hi_bench_v2_047` - chứng từ y tế cho nội trú/điều trị trong ngày PTI
- `hi_bench_v3_001` - giới hạn chi trả AIA
- `hi_bench_v3_002` - số tiền bảo hiểm AIA
- `hi_bench_v3_003` - phạm vi địa lý thai sản AIA

## Artifact thô

Artifacts của run này:

- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/index_report.json`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/manifest.json`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_summary.csv`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_summary.jsonl`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_provider_summary.csv`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_provider_summary.jsonl`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_case_metrics.csv`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_case_metrics.jsonl`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrievals.jsonl`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_eval.log`
- `data/eval_runs/20260510_qwen_full_folder_production_retrieval_eval/retrieval_eval_runtime.txt`

Case-level full results nằm trong:

- `retrieval_case_metrics.csv`: `178` rows, mỗi row là một benchmark case ở một retrieval mode
- `retrievals.jsonl`: top-10 retrieval items cho từng case/mode
