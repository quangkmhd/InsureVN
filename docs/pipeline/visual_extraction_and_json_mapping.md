# Trích Xuất Ảnh/Bảng Và Ánh Xạ JSON

## Mục tiêu

Nhóm script này xử lý phần dữ liệu không đọc tốt bằng Markdown thuần: cấu trúc
tài liệu, bảng/ảnh crop từ PDF, OCR/VLM extraction, phân loại output tốt/xấu,
phân tích key JSON và ánh xạ schema để nạp SQLite.

Pipeline tương ứng phase 4 trong
[`../work_log/2026-05-09-data-pipeline-processing-technical-report.md`](../work_log/2026-05-09-data-pipeline-processing-technical-report.md).

## Năng lực chính

### Trích cấu trúc và crop vùng ảnh/bảng

- [`../../scripts/04_extraction/01_extract_doc_structures.py`](../../scripts/04_extraction/01_extract_doc_structures.py)
  dùng Docling để xuất cấu trúc tài liệu: element label, text, page, bbox và
  table Markdown.
- [`../../scripts/04_extraction/05_crop_from_json.py`](../../scripts/04_extraction/05_crop_from_json.py)
  dùng PyMuPDF crop vùng table/picture từ PDF gốc dựa trên bbox trong JSON cấu
  trúc.

### VLM/OCR output sang Markdown và JSON

- [`../../scripts/04_extraction/02_extract_tables_ollama.py`](../../scripts/04_extraction/02_extract_tables_ollama.py)
  extract ảnh bảng bằng Ollama vision model.
- [`../../scripts/04_extraction/03_extract_images_ollama_robust.py`](../../scripts/04_extraction/03_extract_images_ollama_robust.py)
  biến thể robust có retry và output JSON/Markdown.
- [`../../scripts/04_extraction/04_extract_images_multi_provider.py`](../../scripts/04_extraction/04_extract_images_multi_provider.py)
  chạy song song nhiều provider VLM, gồm Ollama và NVIDIA NIM, để extract ảnh
  bảng vào `health_insurance_extracted`.
- [`../../scripts/bak/12_extract_images_ollama_robust_bak.py`](../../scripts/bak/12_extract_images_ollama_robust_bak.py)
  là bản backup cũ, chỉ dùng để tham khảo khi cần khôi phục logic.

### Kiểm tra provider

- [`../../scripts/04_extraction/06_test_nvidia_gemma.py`](../../scripts/04_extraction/06_test_nvidia_gemma.py)
  kiểm tra kết nối NVIDIA Gemma vision.
- [`../../scripts/04_extraction/07_test_openrouter_gemma.py`](../../scripts/04_extraction/07_test_openrouter_gemma.py)
  kiểm tra kết nối OpenRouter vision.

### Lọc chất lượng và chuẩn hóa schema JSON

- [`../../scripts/04_extraction/08_classify_content_good_trash.py`](../../scripts/04_extraction/08_classify_content_good_trash.py)
  phân loại output extraction thành good/trash bằng LLM worker pool.
- [`../../scripts/04_extraction/08_cleanup_good_content.py`](../../scripts/04_extraction/08_cleanup_good_content.py)
  dọn các JSON rỗng trong good content.
- [`../../scripts/04_extraction/08_analyze_json_keys.py`](../../scripts/04_extraction/08_analyze_json_keys.py)
  thống kê key `structured_data` để hiểu schema thực tế trong corpus.
- [`../../scripts/04_extraction/09_classify_and_map_data.py`](../../scripts/04_extraction/09_classify_and_map_data.py)
  phân loại rule-based các JSON table theo nhóm nghiệp vụ như benefit, premium,
  hospital network, glossary, waiting period, claim payout.
- [`../../scripts/04_extraction/10_classify_with_llm.py`](../../scripts/04_extraction/10_classify_with_llm.py)
  phân loại keyset bằng LLM theo batch và cache kết quả.
- [`../../scripts/04_extraction/11_llm_schema_mapping.py`](../../scripts/04_extraction/11_llm_schema_mapping.py)
  map keyset/sample sang bảng SQLite domain như `benefit_items`,
  `premium_entries`, `hospitals`, `glossary_terms`, `waiting_periods`,
  `claim_payouts`, `short_term_premiums`.

Tài liệu schema analysis đã có:
[`../database/json_data_schema_analysis_report.md`](../database/json_data_schema_analysis_report.md).

## Luồng chạy đề xuất

1. Extract cấu trúc PDF:

```bash
python scripts/04_extraction/01_extract_doc_structures.py
```

2. Crop ảnh/bảng từ PDF theo bbox:

```bash
python scripts/04_extraction/05_crop_from_json.py
```

3. Chạy VLM extraction đa provider:

```bash
python scripts/04_extraction/04_extract_images_multi_provider.py
```

4. Lọc good/trash:

```bash
python scripts/04_extraction/08_classify_content_good_trash.py \
  --input data/health_insurance/health_insurance_extracted \
  --good data/health_insurance/good_content \
  --trash data/health_insurance/trash_content
```

5. Phân tích key và map schema:

```bash
python scripts/04_extraction/08_analyze_json_keys.py
python scripts/04_extraction/10_classify_with_llm.py
python scripts/04_extraction/11_llm_schema_mapping.py
```

## Output quan trọng

- JSON cấu trúc tài liệu từ Docling.
- Ảnh crop từng table/picture kèm metadata.
- Markdown/JSON VLM extraction theo từng ảnh.
- `good_content` và `trash_content`.
- `classification_output/` chứa kết quả phân loại keyset/table.
- `schema_mapping_results/schema_mapping.json` dùng cho SQLite ingestion.

## Lưu ý vận hành

- Không coi output VLM là evidence cuối cùng nếu chưa qua lọc chất lượng và
  review sample. VLM có thể hallucinate header, đơn vị tiền, mức phí hoặc giới
  hạn quyền lợi.
- Các test provider dùng ảnh hard-coded; khi đổi corpus cần sửa input path.
- Trước khi chạy các script classification/mapping cũ trên corpus mới, nên
  compile hoặc smoke-test từng file vì một số script thuộc nhóm prototype.

