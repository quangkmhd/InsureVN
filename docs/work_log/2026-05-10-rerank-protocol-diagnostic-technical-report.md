# 2026-05-10 - Báo cáo kỹ thuật rerank protocol diagnostic

## 1. Tóm tắt điều hành

Đã sửa protocol đánh giá rerank để tách rõ candidate retrieval và final rerank: baseline vẫn đánh giá top 10, rerank scenario dùng `retrieve_top_k=30` rồi rerank về `rerank_top_k=10`. Đã bổ sung logging pre-rerank/post-rerank để giải thích chính xác trường hợp rerank tốt hơn hay kém hơn.

Kết quả thực nghiệm: rerank có ích khi đi kèm hard filters. Cấu hình tốt nhất là `HYBRID + hard filters + namdp-ptit/ViRanker`, đạt `source@10=0.9551`, `MRR@10=0.8725`, `quote@10=0.9221`. Nếu không hard filter, `HYBRID + rerank` giảm exact `source@10` từ `0.8427` xuống `0.8090` trên cùng candidate set.

## 2. Mục tiêu và phạm vi

Mục tiêu là kiểm tra lại nhận định rerank có vẻ kém hơn không rerank, sửa sai lệch trong benchmark, chạy lại trên dữ liệu thật, và tạo báo cáo kết quả đầy đủ.

Phạm vi thuộc `Training & Eval` và `Qdrant evidence foundation`. Code chính thức không import hoặc phụ thuộc `src/eval`; runner benchmark nằm trong `scripts/05_training_eval`.

## 3. Bối cảnh

Trước khi sửa, benchmark dùng cùng một `top_k` cho cả retrieval và rerank. Với `retrieve_top_k == rerank_top_k == 10`, reranker gần như chỉ reorder cùng top 10 nên không đo được lợi ích phổ biến của rerank là lấy candidate rộng hơn rồi chọn lại top kết quả.

Một sai lệch nữa là evaluator match quote bằng `Evidence.content + metadata['text']`, nhưng production reranker trước đó chỉ score `Evidence.content`. Với Qdrant payload, phần text dài có thể nằm trong metadata, vì vậy reranker thiếu ngữ cảnh so với evaluator.

## 4. Triển khai

Đã cập nhật `scripts/05_training_eval/run_production_qdrant_retrieval_eval.py`:

- Thêm CLI `--retrieve-top-k` và `--rerank-top-k`.
- Non-rerank scenarios vẫn retrieve `--top-k` để giữ baseline cũ.
- Rerank scenarios retrieve candidate theo `--retrieve-top-k`, sau đó rerank về `--rerank-top-k`.
- Case metrics thêm `pre_rerank_*`, `candidate_retrieved_count`, `source_rank_delta_after_rerank`, `quote_rank_delta_after_rerank`.
- Retrieval rows thêm `stage=pre_rerank|final` để audit cùng một candidate set.
- Summary rows thêm pre-rerank aggregate và delta final-minus-pre cho rerank scenarios.

Đã cập nhật `src/services/evidence/evidence_merger.py`:

- `_evidence_to_document()` dùng `_evidence_rerank_text()` để score cả `Evidence.content` và `metadata['text']` khi có payload text.
- Giữ nguyên metadata/citation khi trả evidence sau rerank.

Đã thêm test regression:

- `tests/unit/test_production_qdrant_retrieval_eval.py`: xác nhận rerank nhận 30 candidates, trả 10 final, và log pre/post metrics.
- `tests/unit/test_evidence_merger.py`: xác nhận reranker có thể score Qdrant payload text nằm trong metadata.

## 5. Bằng chứng và lệnh đã chạy

Test đỏ đã được xác nhận trước khi sửa:

```bash
pytest tests/unit/test_production_qdrant_retrieval_eval.py::test_rerank_scenario_records_pre_and_post_rerank_metrics -q
# FAIL: evaluate_case() got an unexpected keyword argument 'retrieve_top_k'

pytest tests/unit/test_evidence_merger.py::test_evidence_reranker_scores_qdrant_metadata_text_payload -q
# FAIL: expected metadata payload evidence to rank first
```

Xác minh sau sửa:

```bash
ruff check scripts/05_training_eval/run_production_qdrant_retrieval_eval.py src/services/evidence/evidence_merger.py tests/unit/test_evidence_merger.py tests/unit/test_production_qdrant_retrieval_eval.py
# All checks passed!

pytest tests/unit/test_evidence_merger.py tests/unit/test_production_qdrant_retrieval_eval.py tests/unit/test_huggingface_rerank_cross_encoder.py tests/unit/test_rerank_cross_encoder.py tests/unit/test_config.py -q
# 28 passed, 6 warnings
```

Lệnh benchmark thật:

```bash
RAG_RERANK_PROVIDER=HUGGINGFACE RAG_RERANK_MODEL='namdp-ptit/ViRanker' RAG_RERANK_DEVICE='cuda' RAG_RERANK_BATCH_SIZE=8 RAG_RERANK_MAX_LENGTH=1024 RAG_RERANK_TRUST_REMOTE_CODE=false RAG_RERANK_BACKEND=torch python scripts/05_training_eval/run_production_qdrant_retrieval_eval.py --corpus-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned --benchmark-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned/benchmark --output-dir data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic --collection-name insurevn_qwen_prod_eval_20260510_full --top-k 10 --retrieve-top-k 30 --rerank-top-k 10 --scenarios hybrid,hybrid_rerank,hybrid_company_filter,hybrid_company_filter_rerank
# Completed: data/eval_runs/20260510_viranker_retrieve30_rerank10_diagnostic
```

## 6. Xác minh

Benchmark artifact:

- `manifest.json`: collection `insurevn_qwen_prod_eval_20260510_full`, `9933` points.
- `retrieval_case_metrics.jsonl`: 356 rows.
- `retrieval_summary.jsonl`: 16 rows.
- `retrieval_provider_summary.jsonl`: 24 rows.
- `retrievals.jsonl`: 8.900 rows.

Tất cả scenario có `success_case_count=89` trong overall summary.

## 7. Kết quả

Overall summary quan trọng:

| scenario_name | case_count | success_case_count | source_hit_rate_at_5 | source_hit_rate_at_10 | mrr_at_5 | mrr_at_10 | quote_hit_rate_at_5 | quote_hit_rate_at_10 | evidence_phrase_recall_at_5 | evidence_phrase_recall_at_10 | latency_ms_avg | rerank_latency_ms_avg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid | 89 | 89 | 0.7528 | 0.8539 | 0.503 | 0.5157 | 0.5455 | 0.6883 | 0.4427 | 0.5208 | 653.032 | 0.0 |
| hybrid_company_filter | 89 | 89 | 0.9326 | 0.9438 | 0.8434 | 0.8453 | 0.8571 | 0.9091 | 0.5729 | 0.5924 | 362.706 | 0.0 |
| hybrid_company_filter_rerank | 89 | 89 | 0.9326 | 0.9551 | 0.8697 | 0.8725 | 0.9091 | 0.9221 | 0.569 | 0.5846 | 1210.526 | 805.161 |
| hybrid_rerank | 89 | 89 | 0.7079 | 0.809 | 0.524 | 0.537 | 0.6364 | 0.7273 | 0.4896 | 0.5208 | 1230.44 | 867.501 |


Rerank pre/post trên cùng candidate set:

| scenario_name | pre_rerank_source_hit_rate_at_5 | source_hit_rate_at_5 | source_hit_rate_at_5_delta_vs_pre_rerank | pre_rerank_source_hit_rate_at_10 | source_hit_rate_at_10 | source_hit_rate_at_10_delta_vs_pre_rerank | pre_rerank_mrr_at_10 | mrr_at_10 | mrr_at_10_delta_vs_pre_rerank | pre_rerank_quote_hit_rate_at_10 | quote_hit_rate_at_10 | quote_hit_rate_at_10_delta_vs_pre_rerank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid_company_filter_rerank | 0.9326 | 0.9326 | 0.0 | 0.9438 | 0.9551 | 0.0112 | 0.8434 | 0.8725 | 0.029 | 0.9091 | 0.9221 | 0.013 |
| hybrid_rerank | 0.7528 | 0.7079 | -0.0449 | 0.8427 | 0.809 | -0.0337 | 0.5025 | 0.537 | 0.0346 | 0.6623 | 0.7273 | 0.0649 |


Audit theo case:

| scenario_name | case_count | rank_improved | rank_worsened | rank_same | missing_rank_pair | brought_into_top10 | lost_from_top10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid_rerank | 89 | 30 | 20 | 22 | 17 | 7 | 10 |
| hybrid_company_filter_rerank | 89 | 11 | 7 | 67 | 4 | 2 | 1 |


Kết luận kỹ thuật: rerank không phải vô dụng. Nó cải thiện ranking nội bộ và quote matching, nhưng nếu không hard filter thì exact `source_path` bị nhiễu bởi tài liệu khác công ty hoặc khác file nhưng cùng chủ đề. Với hard filters, nhiễu này giảm mạnh và rerank tạo cải thiện rõ ở `MRR@10` và `quote@10`, đồng thời tăng nhẹ `source@10`.

## 8. Rủi ro và giới hạn

Metric `source_path` là exact file match, nên có thể phạt những tài liệu cùng công ty/cùng điều khoản nhưng khác file. Đây là đúng cho benchmark hiện tại, nhưng cần thêm metric `company_hit`, `document_family_hit`, hoặc LLM judge để phân biệt sai thật với alternate valid evidence.

Benchmark mới chỉ chạy với `namdp-ptit/ViRanker` sau khi đã chọn model local tốt nhất trước đó. Nếu đổi reranker model hoặc max length, cần chạy lại cùng protocol.

Latency tăng đáng kể khi bật rerank: `hybrid_company_filter_rerank` trung bình `1210.526 ms`, trong đó rerank `805.161 ms`; baseline hard filter là `362.706 ms`.

## 9. Việc tiếp theo

Nên chốt production retrieval policy là: chỉ bật rerank sau khi có hard filters đáng tin cậy cho company/document/product; nếu không có hard filter thì dùng HYBRID raw top 10 hoặc bổ sung filter extraction trước.

Nên tạo thêm metric `document_family_hit` để đánh giá đúng hơn các trường hợp cùng sản phẩm/cùng bộ quy tắc nhưng khác file markdown.

Nên tạo ADR nếu quyết định đưa `HYBRID + hard filters + ViRanker retrieve30/rerank10` thành strategy production mặc định.
