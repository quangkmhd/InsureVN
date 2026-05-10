# 2026-05-10 - Báo cáo kỹ thuật đánh giá answer + citation

## 1. Tóm tắt điều hành

Đã chạy đánh giá answer-level đầu tiên cho pipeline đã chốt `HYBRID + hard filters + ViRanker`. Mục tiêu của run này là kiểm tra liệu top evidence sau retrieval/rerank có đủ sẵn sàng để tạo câu trả lời có citation hay chưa.

Kết quả tổng quan sau review/fix metric trên `89` benchmark cases:

- `success_rate = 0.7640`
- `answer_quality_score_mean = 0.7741`
- `expected_source_in_context_rate = 0.9326`
- `expected_source_cited_rate = 0.8427`
- `answer_has_citation_rate = 1.0000`
- `valid_citation_rate_mean = 1.0000`
- `citation_coverage_mean = 1.0000`
- `answer_gold_token_recall_mean = 0.6247`
- `answer_context_token_precision_mean = 0.9888`
- `numeric_claim_support_rate = 1.0000`

Kết luận: retrieval source đã đủ tốt để bắt đầu answer layer. Sau khi sửa cách đo và cách tạo extractive citation baseline, điểm nghẽn còn lại không phải citation formatting trong baseline nữa mà là `expected_source_cited`/source selection và gold recall, đặc biệt ở `aia.com.vn` và `bic.vn`.

## 2. Mục tiêu và phạm vi

Mục tiêu:

1. Đánh giá bước sau retrieval: tạo answer có citation từ top evidence đã rerank.
2. Không chạy lại embedding, Qdrant indexing, hoặc ViRanker.
3. Tách lỗi answer/citation khỏi lỗi retrieval bằng cách dùng artifact retrieval đã có.
4. Ghi full results để có thể inspect từng case.

Phạm vi:

- Data pipeline phase: `Training & Eval`
- System tier: `Core Services`
- Evidence foundation: `Qdrant`
- Scenario đánh giá: `hybrid_company_filter_rerank`
- Retrieval input: `data/eval_runs/20260510_qwen_full_folder_filtered_rerank_eval`
- Output run: `data/eval_runs/20260510_answer_citation_eval`

## 3. Bối cảnh

Trước run này, dự án đã chốt retrieval production:

```text
Qwen/Qwen3-Embedding-8B
  -> HYBRID retrieval
  -> hard filters
  -> namdp-ptit/ViRanker rerank
```

Retrieval metric trước đó tốt hơn nhiều khi dùng hard filters + rerank, nhưng retrieval tốt chưa đảm bảo câu trả lời cuối cùng tốt. Do đó bước này đo các tín hiệu answer-level:

- citation có đúng source không
- câu trả lời có bám evidence không
- câu trả lời có giữ được số liệu không
- nội dung trả lời có phủ gold/evidence quote không

## 4. Triển khai

Đã thêm runner:

- `scripts/05_training_eval/run_answer_citation_eval.py`

Runner đọc:

- benchmark JSONL từ `data/health_insurance/health_insurance_markdowns_interpreted_cleaned/benchmark`
- retrieval artifact từ `data/eval_runs/20260510_qwen_full_folder_filtered_rerank_eval/retrievals.jsonl`

Runner ghi:

- `answer_eval_rows.csv`
- `answer_eval_rows.jsonl`
- `answer_eval_summary.csv`
- `answer_eval_summary.json`
- `answers.md`
- `answer_citation_eval_report.md`
- `manifest.json`

Đã thêm test:

- `tests/unit/test_answer_citation_eval.py`

Các metric chính:

- `expected_source_in_context`: source vàng có nằm trong top contexts không.
- `expected_source_cited`: answer có cite context đúng source vàng không.
- `answer_has_citation`: answer có citation dạng `[S1]` không.
- `valid_citation_rate`: citation trong answer có map được vào retrieved context không.
- `citation_coverage`: tỷ lệ statement trong answer có citation hợp lệ map được về retrieved context. Sau review, metric này đã được sửa để citation rời như `câu. [S1]` được gắn vào câu trước, và extractive baseline đặt citation trước dấu câu kết thúc theo dạng `câu [S1].`
- `answer_gold_token_recall`: recall token quan trọng giữa gold text và answer.
- `answer_context_token_precision`: token quan trọng của answer có nằm trong context không.
- `numeric_claim_support`: số liệu trong từng statement của answer có xuất hiện trong context được statement đó cite không.
- `answer_quality_score`: weighted score tổng hợp, threshold là `0.65`.
- `success`: chỉ pass khi `answer_quality_score >= 0.65`, citation hợp lệ 100%, coverage hợp lệ 100%, và nếu case yêu cầu source thì citation phải trỏ về đúng expected source.

## 5. Bằng chứng và lệnh đã chạy

Unit test và lint:

```bash
pytest tests/unit/test_answer_citation_eval.py -q
ruff check scripts/05_training_eval/run_answer_citation_eval.py tests/unit/test_answer_citation_eval.py
```

Smoke LLM mode:

```bash
python scripts/05_training_eval/run_answer_citation_eval.py \
  --limit-cases 3 \
  --output-dir data/eval_runs/20260510_answer_citation_eval_smoke \
  --request-timeout-seconds 30 \
  --max-slot-attempts 4
```

Smoke Gemini mode:

```bash
python scripts/05_training_eval/run_answer_citation_eval.py \
  --limit-cases 3 \
  --output-dir data/eval_runs/20260510_answer_citation_eval_smoke_gemini \
  --request-timeout-seconds 30 \
  --max-slot-attempts 5
```

Full run dùng extractive grounded baseline:

```bash
python scripts/05_training_eval/run_answer_citation_eval.py \
  --generation-mode extractive \
  --output-dir data/eval_runs/20260510_answer_citation_eval \
  --scenario hybrid_company_filter_rerank \
  --top-contexts 5
```

## 6. Xác minh

Kết quả xác minh code:

- `pytest tests/unit/test_answer_citation_eval.py -q`: `8 passed`, `6 warnings`
- `ruff check ...`: `All checks passed`

Kết quả full run:

- `case_count = 89`
- `generation_mode = extractive`
- `generation_completed_rate = 1.0000`
- `fallback_rate = 0.0000`
- Output dir: `data/eval_runs/20260510_answer_citation_eval`

Lưu ý: smoke LLM mode không được dùng làm kết quả chính vì provider pool hiện chưa ổn định cho answer generation. Gemini smoke cũng fallback extractive toàn bộ 3/3 cases. Vì vậy full run được chốt là grounded extractive baseline để đo answer/citation readiness không bị nhiễu bởi lỗi provider.

## 7. Kết quả

### 7.1 Tổng quan

| Group | Cases | Success | Quality | Source in context | Source cited | Citation coverage | Gold recall | Context precision | Numeric support |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall:all | 89 | 0.7640 | 0.7741 | 0.9326 | 0.8427 | 1.0000 | 0.6247 | 0.9888 | 1.0000 |

### 7.2 Theo provider

| Provider | Cases | Success | Quality | Source in context | Source cited | Gold recall |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `pti.com.vn` | 66 | 0.8788 | 0.8091 | 1.0000 | 0.9697 | 0.6613 |
| `libertyinsurance.com.vn` | 5 | 0.6000 | 0.7549 | 0.8000 | 0.6000 | 0.6374 |
| `baominh.com.vn` | 5 | 0.6000 | 0.7220 | 1.0000 | 0.6000 | 0.5549 |
| `pacific_cross_all_pdfs` | 1 | 1.0000 | 0.7735 | 1.0000 | 1.0000 | 0.2941 |
| `aia.com.vn` | 6 | 0.3333 | 0.6192 | 0.3333 | 0.3333 | 0.4792 |
| `bic.vn` | 6 | 0.1667 | 0.6044 | 0.8333 | 0.3333 | 0.4692 |

### 7.3 Theo risk

| Risk | Cases | Success | Quality | Source cited | Gold recall |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `high` | 33 | 0.8485 | 0.8129 | 0.8788 | 0.7336 |
| `medium` | 45 | 0.6889 | 0.7512 | 0.8000 | 0.5871 |
| `low` | 11 | 0.8182 | 0.7515 | 0.9091 | 0.4516 |

### 7.4 Nhận định

1. `expected_source_in_context_rate = 0.9326` cho thấy retrieval/rerank đã đưa đúng tài liệu vào top context trong phần lớn cases.
2. `expected_source_cited_rate = 0.8427` thấp hơn source-in-context, nghĩa là answer layer vẫn có thể cite nhầm source dù evidence đúng có mặt.
3. `citation_coverage_mean = 1.0000` sau fix cho thấy formatter baseline đã gắn citation hợp lệ cho từng statement extractive.
4. `numeric_claim_support_rate = 1.0000` là tín hiệu tốt: extractive answer không bịa số liệu mới ngoài context được cite.
5. `aia.com.vn` và `bic.vn` vẫn là hai provider yếu nhất ở answer-level do source selection/retrieval còn yếu, không phải do citation formatter.

### 7.5 Review/fix sau lần chạy đầu

Lần chạy đầu cho `citation_coverage_mean = 0.3506`. Sau review code và sample answers, nguyên nhân không phải toàn bộ do answer thiếu citation, mà có hai lỗi trong baseline/evaluator:

1. Extractive answer chỉ gắn một citation ở cuối toàn đoạn.
2. Metric tách câu theo dấu chấm nên mẫu `câu. [S1]` làm `[S1]` bị tách thành statement riêng, khiến câu trước bị tính là không có citation.

Đã sửa formatter/evaluator lần 1:

- `build_extractive_answer()` gắn citation cho từng statement.
- Citation được đặt trước dấu câu kết thúc theo dạng `câu [S1].`
- `calculate_citation_coverage()` gắn citation-only statement vào statement trước đó.

Tác động sau formatter fix, trước khi siết strict success gate:

| Metric | Trước fix | Sau fix | Delta |
| :--- | ---: | ---: | ---: |
| `success_rate` | 0.5506 | 0.7978 | +0.2472 |
| `answer_quality_score_mean` | 0.6809 | 0.7741 | +0.0932 |
| `citation_coverage_mean` | 0.3506 | 1.0000 | +0.6494 |
| `expected_source_in_context_rate` | 0.9326 | 0.9326 | 0.0000 |
| `expected_source_cited_rate` | 0.8427 | 0.8427 | 0.0000 |

Sau external code review, success gate được siết thêm để không cho pass answer có citation ID không tồn tại hoặc cite sai expected source khi benchmark yêu cầu citation source. Đây mới là kết quả cuối của report này:

| Metric | Trước gate chặt | Sau gate chặt | Delta |
| :--- | ---: | ---: | ---: |
| `success_rate` | 0.7978 | 0.7640 | -0.0338 |
| `answer_quality_score_mean` | 0.7741 | 0.7741 | 0.0000 |
| `expected_source_cited_rate` | 0.8427 | 0.8427 | 0.0000 |
| `valid_citation_rate_mean` | 1.0000 | 1.0000 | 0.0000 |

Các fix bổ sung sau review:

- Loại bỏ `expected_source_path` khỏi prompt LLM để tránh leak gold label vào generation.
- `citation_coverage` trong evaluator chỉ tính statement có citation ID hợp lệ trong retrieved contexts.
- `success` yêu cầu citation hợp lệ 100%, coverage hợp lệ 100%, và đúng source nếu `must_cite_source=True`.
- `numeric_claim_support` kiểm tra số liệu theo context được statement cite, không còn kiểm tra trên toàn bộ top-k context.
- Thêm regression tests cho citation ID không tồn tại, numeric claim cite sai context, và format citation trước dấu câu.

## 8. Rủi ro và giới hạn

1. Full run này dùng `generation_mode=extractive`, chưa phải LLM answer generator production.
2. Retrieval artifact chỉ lưu `content_preview`, không phải toàn bộ chunk text, nên answer eval hiện là lower-bound cho answer generation.
3. `citation_coverage = 1.0000` hiện phản ánh formatter extractive baseline đã cite từng statement bằng citation hợp lệ, không chứng minh LLM generator production sẽ tự làm đúng.
4. `answer_gold_token_recall` là deterministic heuristic, chưa thay thế được human/LLM judge cho tính đúng sai ngữ nghĩa.
5. LLM smoke chưa ổn định vì provider pool/Gemini hiện không đảm bảo trả lời tốt cho prompt answer generation.

## 9. Việc tiếp theo

1. Tạo answer generator production thật với rule: mọi bullet/claim phải có citation.
2. Mở rộng retrieval artifact hoặc answer eval runner để dùng full chunk text thay vì `content_preview`.
3. Chạy provider slice diagnostic cho `aia.com.vn` và `bic.vn`.
4. Sau khi có answer generator ổn định, chạy lại LLM/human judge cho answer faithfulness và citation correctness.
5. Thêm readiness gate: không cho trả lời nếu `expected_source_in_context` hoặc hard filter confidence thấp.
