# 2026-05-10 - Báo cáo kỹ thuật so sánh hard filters và ViRanker rerank

## 1. Tóm tắt điều hành

Báo cáo này giải thích `hard filters` trong retrieval pipeline và so sánh trực tiếp hai cấu hình trên cùng benchmark health insurance:

- `HYBRID + hard filters`
- `HYBRID + hard filters + namdp-ptit/ViRanker rerank`

Kết luận: `HYBRID + hard filters + ViRanker rerank` tốt hơn về `source@10`, `MRR@10`, `quote@5`, và `quote@10`, nhưng latency tăng đáng kể. Nếu ưu tiên chất lượng evidence, có thể dùng rerank sau hard filters. Nếu ưu tiên tốc độ, `HYBRID + hard filters` đã đủ mạnh và rẻ hơn nhiều.

## 2. Mục tiêu và phạm vi

Mục tiêu là làm rõ `hard filters` là gì, vì sao nó quan trọng với retrieval dữ liệu bảo hiểm tiếng Việt, và lượng hóa việc thêm ViRanker rerank có đáng dùng hay không.

Phạm vi thuộc `Training & Eval`, `Qdrant evidence foundation`, và retrieval path cho Fast Q&A / Verified Advisor. Báo cáo này không thay đổi code và không chạy benchmark mới; nó dùng artifact đã tạo tại:

```text
data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic
```

## 3. Bối cảnh

`hard filters` là bước lọc cứng metadata trước khi ranking. Trong benchmark này, filter chính là `company_code`, được suy ra từ `provider` của benchmark case.

Ví dụ:

- Case thuộc `pti.com.vn` thì chỉ retrieve các chunk có `company_code=PTI`.
- Case thuộc `bic.vn` thì chỉ retrieve các chunk có `company_code=BIC`.
- Case thuộc `aia.com.vn` thì chỉ retrieve các chunk có `company_code=AIA`.

Điểm khác biệt so với rerank:

- `hard filters` loại bỏ tài liệu sai phạm vi ngay từ đầu.
- `HYBRID` xếp hạng bằng vector + sparse/BM25 trong candidate đã lọc.
- `ViRanker rerank` nhận candidate đã retrieve, chấm lại mức liên quan query-document, rồi reorder top kết quả.

Trong dữ liệu bảo hiểm, nhiều công ty có điều khoản giống nhau như nội trú, ngoại trú, loại trừ, thời gian chờ, quyền lợi nha khoa. Nếu không lọc cứng theo công ty, reranker có thể kéo một chunk rất giống ngữ nghĩa nhưng sai công ty lên cao. Điều đó làm giảm metric exact `source_path`, dù nội dung nhìn có vẻ liên quan.

## 4. Triển khai

Benchmark được chạy với collection:

```text
insurevn_qwen_prod_eval_20260510_full
```

Cấu hình chính:

| Trường | Giá trị |
| --- | --- |
| Embedding model | `Qwen/Qwen3-Embedding-8B` |
| Dense vector size | `4096` |
| Reranker | `namdp-ptit/ViRanker` |
| Collection point count | `9933` |
| Benchmark cases | `89` |
| Baseline top_k | `10` |
| Rerank protocol | `retrieve_top_k=30 -> rerank_top_k=10` |

Hai cấu hình so sánh:

| Cấu hình | Mô tả |
| --- | --- |
| `HYBRID + hard filters` | Retrieve top 10 bằng hybrid vector + sparse/BM25, có lọc cứng `company_code`. |
| `HYBRID + hard filters + ViRanker rerank` | Retrieve 30 candidate bằng hybrid có lọc cứng `company_code`, sau đó ViRanker rerank về top 10. |

## 5. Bằng chứng và lệnh đã chạy

Nguồn số liệu:

```text
data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic/retrieval_summary.csv
data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic/retrieval_provider_summary.csv
data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic/retrieval_case_metrics.csv
```

Artifact đầy đủ đã có:

```text
data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic/manifest.json
data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic/retrievals.jsonl
docs/eval_results/2026-05-10-viranker-retrieve30-rerank10-diagnostic-full-results.md
docs/work_log/2026-05-10-rerank-protocol-diagnostic-technical-report.md
```

Lệnh benchmark gốc đã chạy trong phiên trước:

```bash
RAG_RERANK_PROVIDER=HUGGINGFACE RAG_RERANK_MODEL='namdp-ptit/ViRanker' RAG_RERANK_DEVICE='cuda' RAG_RERANK_BATCH_SIZE=8 RAG_RERANK_MAX_LENGTH=1024 RAG_RERANK_TRUST_REMOTE_CODE=false RAG_RERANK_BACKEND=torch python scripts/05_training_eval/run_production_qdrant_retrieval_eval.py --corpus-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned --benchmark-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned/benchmark --output-dir data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic --collection-name insurevn_qwen_prod_eval_20260510_full --top-k 10 --retrieve-top-k 30 --rerank-top-k 10 --scenarios hybrid,hybrid_rerank,hybrid_company_filter,hybrid_company_filter_rerank
```

## 6. Xác minh

Benchmark có `89/89` case thành công cho cả hai cấu hình được so sánh.

Artifact row counts từ run:

| File | Số dòng |
| --- | ---: |
| `retrievals.jsonl` | `8900` |
| `retrieval_case_metrics.jsonl` | `356` |
| `retrieval_summary.jsonl` | `16` |
| `retrieval_provider_summary.jsonl` | `24` |

Xác minh code liên quan từ phiên trước:

```bash
ruff check scripts/05_training_eval/run_production_qdrant_retrieval_eval.py src/services/evidence/evidence_merger.py tests/unit/test_evidence_merger.py tests/unit/test_production_qdrant_retrieval_eval.py
# All checks passed!

pytest tests/unit/test_evidence_merger.py tests/unit/test_production_qdrant_retrieval_eval.py tests/unit/test_huggingface_rerank_cross_encoder.py tests/unit/test_rerank_cross_encoder.py tests/unit/test_config.py -q
# 28 passed, 6 warnings
```

## 7. Kết quả

### 7.1 Overall comparison

| Metric | `HYBRID + hard filters` | `HYBRID + hard filters + ViRanker rerank` | Delta |
| --- | ---: | ---: | ---: |
| `source_hit_rate_at_5` | `0.9326` | `0.9326` | `+0.0000` |
| `source_hit_rate_at_10` | `0.9438` | `0.9551` | `+0.0113` |
| `mrr_at_5` | `0.8434` | `0.8697` | `+0.0263` |
| `mrr_at_10` | `0.8453` | `0.8725` | `+0.0272` |
| `quote_hit_rate_at_5` | `0.8571` | `0.9091` | `+0.0520` |
| `quote_hit_rate_at_10` | `0.9091` | `0.9221` | `+0.0130` |
| `evidence_phrase_recall_at_5` | `0.5729` | `0.5690` | `-0.0039` |
| `evidence_phrase_recall_at_10` | `0.5924` | `0.5846` | `-0.0078` |
| `latency_ms_avg` | `362.706` | `1210.526` | `+847.820 ms` |
| `latency_ms_p95` | `414.525` | `1418.852` | `+1004.327 ms` |

### 7.2 Pre-rerank vs post-rerank trong cùng candidate set

Trong scenario rerank có hard filters, hệ thống retrieve 30 candidate rồi ViRanker chọn lại top 10. Vì vậy có thể so sánh pre/post trên cùng candidate set.

| Metric | Pre-rerank top 30 candidate | Post-rerank top 10 | Delta |
| --- | ---: | ---: | ---: |
| `source_hit_rate_at_5` | `0.9326` | `0.9326` | `+0.0000` |
| `source_hit_rate_at_10` | `0.9438` | `0.9551` | `+0.0112` |
| `mrr_at_5` | `0.8416` | `0.8697` | `+0.0281` |
| `mrr_at_10` | `0.8434` | `0.8725` | `+0.0290` |
| `quote_hit_rate_at_5` | `0.8701` | `0.9091` | `+0.0390` |
| `quote_hit_rate_at_10` | `0.9091` | `0.9221` | `+0.0130` |
| `evidence_phrase_recall_at_5` | `0.5677` | `0.5690` | `+0.0013` |
| `evidence_phrase_recall_at_10` | `0.5807` | `0.5846` | `+0.0039` |

### 7.3 Case movement audit

| Scenario | Case count | Rank improved | Rank worsened | Rank same | Missing rank pair | Brought into top 10 | Lost from top 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid_company_filter_rerank` | `89` | `11` | `7` | `67` | `4` | `2` | `1` |

Diễn giải:

- `67/89` cases giữ nguyên exact source rank hoặc không bị ảnh hưởng đáng kể.
- `11` cases được đẩy source đúng lên cao hơn.
- `7` cases bị đẩy source đúng xuống thấp hơn.
- `2` cases trước rerank không nằm trong top 10 nhưng sau rerank vào top 10.
- `1` case trước rerank nằm trong top 10 nhưng sau rerank rơi khỏi top 10.

### 7.4 Provider-level comparison

| Provider | `HYBRID + hard filters` source@10 | `HYBRID + hard filters + rerank` source@10 | Delta source@10 | Baseline MRR@10 | Rerank MRR@10 | Baseline quote@10 | Rerank quote@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `aia.com.vn` | `0.3333` | `0.5000` | `+0.1667` | `0.1167` | `0.2708` | `0.8000` | `0.6000` |
| `baominh.com.vn` | `1.0000` | `1.0000` | `+0.0000` | `0.6000` | `0.5467` | `1.0000` | `1.0000` |
| `bic.vn` | `1.0000` | `0.8333` | `-0.1667` | `0.5889` | `0.5764` | `0.3333` | `0.5000` |
| `libertyinsurance.com.vn` | `0.8000` | `1.0000` | `+0.2000` | `0.8000` | `0.8667` | `0.8000` | `0.8000` |
| `pacific_cross_all_pdfs` | `1.0000` | `1.0000` | `+0.0000` | `1.0000` | `1.0000` | `0.0000` | `0.0000` |
| `pti.com.vn` | `1.0000` | `1.0000` | `+0.0000` | `0.9545` | `0.9773` | `0.9821` | `1.0000` |

Provider-level có số case không đều, nên không nên dùng riêng từng provider để quyết định toàn hệ thống. Tuy nhiên bảng này cho thấy rerank giúp AIA, Liberty, PTI, nhưng làm giảm exact source@10 ở BIC trong benchmark này.

## 8. Rủi ro và giới hạn

`source_path` là exact-match metric. Nếu reranker chọn tài liệu cùng công ty/cùng điều khoản nhưng khác file markdown, benchmark vẫn tính là sai. Đây là metric nghiêm khắc và hữu ích cho citation, nhưng có thể đánh giá thấp các alternate evidence hợp lệ.

Latency là trade-off lớn nhất. Rerank tăng average latency từ `362.706 ms` lên `1210.526 ms`. Nếu dùng trong production, nên bật rerank có điều kiện thay vì luôn bật.

Hard filters hiện dựa vào việc nhận diện đúng company/provider. Nếu query thực tế không rõ công ty, cần agent hoặc retrieval planner extract company trước; nếu không extract được, bật rerank có thể kéo tài liệu sai công ty lên cao.

## 9. Việc tiếp theo

Khuyến nghị production hiện tại:

- Dùng `HYBRID + hard filters` làm baseline chính khi có company/document/product filter.
- Bật `ViRanker rerank` cho luồng cần chất lượng evidence cao, đặc biệt Verified Advisor hoặc claim-related retrieval.
- Không bật rerank mặc định khi chưa có hard filters đáng tin cậy.
- Thêm metric `company_hit`, `document_family_hit`, hoặc `valid_alternate_evidence` để phân biệt sai exact source với evidence thay thế hợp lệ.

Nếu quyết định đưa `HYBRID + hard filters + ViRanker rerank` thành retrieval strategy chính thức, nên tạo ADR để ghi rõ trade-off chất lượng và latency.
