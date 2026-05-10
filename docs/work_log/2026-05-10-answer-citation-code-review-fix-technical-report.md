# 2026-05-10 - Báo cáo kỹ thuật review/fix answer + citation evaluator

## 1. Tóm tắt điều hành

Đã thực hiện code review cho runner đánh giá answer/citation và sửa các lỗi ảnh hưởng trực tiếp đến độ tin cậy của metric. Lỗi nghiêm trọng nhất là evaluator có thể cho `success=True` với answer dùng citation không tồn tại như `[S99]`.

Sau khi sửa, `success` chỉ pass khi đạt đủ các điều kiện:

- `answer_quality_score >= 0.65`
- `valid_citation_rate == 1.0`
- `citation_coverage == 1.0`
- nếu benchmark có `must_cite_source=True`, answer phải cite đúng expected source

Full eval đã được chạy lại. Kết quả cuối là `success_rate = 0.7640`, thấp hơn bản trước review `0.7978` vì các case cite sai source không còn được tính pass. Đây là kết quả đáng tin hơn.

## 2. Mục tiêu và phạm vi

Mục tiêu:

1. Review tính đúng của evaluator sau bước answer/citation evaluation.
2. Fix các lỗi làm metric bị lạc quan giả.
3. Chạy lại full eval và cập nhật report.
4. Xóa artifact report lỗi thời để tránh nhầm lẫn.

Phạm vi:

- Data pipeline phase: `Training & Eval`
- System tier: `Core Services`
- Evidence foundation: `Qdrant`
- Script chính: `scripts/05_training_eval/run_answer_citation_eval.py`
- Test chính: `tests/unit/test_answer_citation_eval.py`
- Report liên quan:
  - `docs/work_log/2026-05-10-answer-citation-evaluation-technical-report.md`
  - `docs/eval_results/2026-05-10-answer-citation-evaluation-full-results.md`

## 3. Bối cảnh

Trước review, dự án đã chốt retrieval stack:

```text
Qwen/Qwen3-Embedding-8B
  -> HYBRID retrieval
  -> hard filters
  -> namdp-ptit/ViRanker rerank
```

Bước answer/citation eval được thêm để đo readiness sau retrieval/rerank. Runner dùng persisted retrieval artifact từ:

```text
data/eval_runs/20260510_qwen_full_folder_filtered_rerank_eval/retrievals.jsonl
```

Runner không gọi production code trong `src/eval` từ `src/` và không chạy lại embedding/Qdrant/ViRanker.

## 4. Triển khai

Các lỗi được reviewer phát hiện:

| Mức độ | Vấn đề | Tác động |
| :--- | :--- | :--- |
| Critical | Answer dùng citation không tồn tại như `[S99]` vẫn có thể pass | Làm evaluator chấp nhận citation sai |
| Important | LLM prompt chứa expected source/gold source | Leak label vào generation, làm nhiễu LLM-mode metric |
| Important | `numeric_claim_support` check số trên toàn bộ top-k context | Có thể pass số liệu dù statement cite sai context |
| Minor | Test chưa khóa format citation trước dấu câu | Có thể tái sinh lỗi `câu. [S1]` |
| Minor | Report ghi test count cũ | Báo cáo không khớp trạng thái code |

Các thay đổi đã thực hiện:

- Bỏ dòng expected source khỏi `build_answer_prompt()`.
- `calculate_citation_coverage()` nhận `valid_citation_ids` và chỉ tính coverage khi citation map được về retrieved context.
- `success` được gate bằng citation hợp lệ, coverage hợp lệ, và expected-source citation khi benchmark yêu cầu.
- `count_unsupported_numeric_claims()` kiểm tra số liệu theo từng statement và theo context được statement đó cite.
- Thêm regression tests cho invalid citation ID, numeric support theo cited context, và citation trước terminal punctuation.
- Cập nhật full-results report và technical report theo metric mới.
- Xóa artifact lỗi thời: `data/eval_runs/20260510_answer_citation_eval_before_fix`.

## 5. Bằng chứng và lệnh đã chạy

Lệnh review/fix/eval chính:

```bash
pytest tests/unit/test_answer_citation_eval.py -q
ruff check scripts/05_training_eval/run_answer_citation_eval.py tests/unit/test_answer_citation_eval.py
ruff format --check scripts/05_training_eval/run_answer_citation_eval.py tests/unit/test_answer_citation_eval.py
python scripts/05_training_eval/run_answer_citation_eval.py \
  --generation-mode extractive \
  --output-dir data/eval_runs/20260510_answer_citation_eval \
  --scenario hybrid_company_filter_rerank \
  --top-contexts 5
pytest tests/unit/test_answer_citation_eval.py \
  tests/unit/test_filtered_hybrid_rerank_retriever.py \
  tests/unit/test_rerank_cross_encoder.py \
  tests/unit/test_huggingface_rerank_cross_encoder.py \
  tests/unit/test_production_qdrant_retrieval_eval.py -q
git diff --check -- scripts/05_training_eval/run_answer_citation_eval.py \
  tests/unit/test_answer_citation_eval.py \
  docs/work_log/2026-05-10-answer-citation-evaluation-technical-report.md \
  docs/eval_results/2026-05-10-answer-citation-evaluation-full-results.md \
  docs/work_log/2026-05-10-opensource-reranker-evaluation-technical-report.md
```

Scan secret/dummy-marker trên file thay đổi:

```bash
rg -n "TO[D]O|FI[X]ME|TB[D]|AIza|sk-|OPENAI_API_KEY|GOOGLE_API_KEY_[0-9]+=|Expected source để đối chiếu" \
  scripts/05_training_eval/run_answer_citation_eval.py \
  tests/unit/test_answer_citation_eval.py \
  docs/work_log/2026-05-10-answer-citation-evaluation-technical-report.md \
  docs/eval_results/2026-05-10-answer-citation-evaluation-full-results.md \
  docs/work_log/2026-05-10-opensource-reranker-evaluation-technical-report.md
```

Xóa artifact lỗi thời:

```bash
rm -rf data/eval_runs/20260510_answer_citation_eval_before_fix
```

## 6. Xác minh

Kết quả verification:

- Focused unit tests: `8 passed`, `6 warnings`
- Regression suite liên quan: `25 passed`, `6 warnings`
- `ruff check`: pass
- `ruff format --check`: pass
- `git diff --check`: pass
- Secret/dummy-marker scan: không phát hiện key/token hoặc marker chưa hoàn thiện trong file thay đổi
- Follow-up code review: không còn Critical/Important/Minor, `Ready to merge: Yes`

Reviewer cũng xác minh trực tiếp case `[S99]`:

```text
valid_citation_rate = 0.0
citation_coverage = 0.0
success = False
```

## 7. Kết quả

Kết quả full eval cuối sau strict gate:

| Metric | Giá trị |
| :--- | ---: |
| `cases` | 89 |
| `success_rate` | 0.7640 |
| `answer_quality_score_mean` | 0.7741 |
| `expected_source_in_context_rate` | 0.9326 |
| `expected_source_cited_rate` | 0.8427 |
| `valid_citation_rate_mean` | 1.0000 |
| `citation_coverage_mean` | 1.0000 |
| `answer_gold_token_recall_mean` | 0.6247 |
| `answer_context_token_precision_mean` | 0.9888 |
| `numeric_claim_support_rate` | 1.0000 |

So sánh trước/sau strict gate:

| Metric | Trước strict gate | Sau strict gate | Nhận định |
| :--- | ---: | ---: | :--- |
| `success_rate` | 0.7978 | 0.7640 | Giảm vì case cite sai expected source không còn được pass |
| `answer_quality_score_mean` | 0.7741 | 0.7741 | Không đổi vì score vẫn là heuristic tổng hợp |
| `expected_source_cited_rate` | 0.8427 | 0.8427 | Không đổi, nhưng giờ được dùng làm hard gate |
| `valid_citation_rate_mean` | 1.0000 | 1.0000 | Extractive baseline dùng citation ID hợp lệ |

Report hiện hành:

- `docs/work_log/2026-05-10-answer-citation-evaluation-technical-report.md`
- `docs/eval_results/2026-05-10-answer-citation-evaluation-full-results.md`
- `docs/work_log/2026-05-10-answer-citation-code-review-fix-technical-report.md`

## 8. Rủi ro và giới hạn

1. Full run vẫn dùng `generation_mode=extractive`, chưa chứng minh LLM answer generator production tự tuân thủ citation.
2. `answer_quality_score` vẫn là heuristic deterministic, không thay thế human/LLM judge cho semantic correctness.
3. Retrieval artifact hiện dùng `content_preview`, chưa phải full chunk text, nên answer eval là proxy readiness.
4. `success_rate = 0.7640` không có nghĩa production answer đã sẵn sàng hoàn toàn; nó cho thấy retrieval + extractive citation baseline đủ ổn để chuyển sang bước LLM answer generator/human judge.

## 9. Việc tiếp theo

1. Xây answer generator production với rule bắt buộc cite từng claim/bullet.
2. Dùng full chunk text thay vì `content_preview` cho answer eval.
3. Chạy diagnostic riêng cho source selection ở `aia.com.vn` và `bic.vn`.
4. Thêm human/LLM judge cho faithfulness, citation correctness và answer helpfulness.
5. Đưa strict citation gate vào readiness check trước khi cho agent trả lời high-risk workflows.
