# Chuyển Đổi Tài Liệu Và Làm Sạch Markdown

## Mục tiêu

Nhóm script này chuyển PDF đã lọc sang Markdown có thể chunk, search và trích
evidence. Sau conversion, bảng biểu được diễn giải thành text tiếng Việt và các
nhiễu ảnh/caption do OCR sinh ra được loại bỏ.

Pipeline tương ứng phase 3 trong
[`../work_log/2026-05-09-data-pipeline-processing-technical-report.md`](../work_log/2026-05-09-data-pipeline-processing-technical-report.md).

## Năng lực chính

### PDF sang Markdown

- [`../../scripts/03_conversion/01_convert_pdfs_marker.py`](../../scripts/03_conversion/01_convert_pdfs_marker.py)
  chạy Marker batch conversion, tối ưu cho máy VRAM thấp, có option tắt LLM và
  xử lý lỗi rate limit/OOM.
- [`../../scripts/03_conversion/02_convert_pdfs_datalab_api.py`](../../scripts/03_conversion/02_convert_pdfs_datalab_api.py)
  dùng hosted Datalab API, hỗ trợ nhiều API key qua `.env`.
- [`../../scripts/03_conversion/03_convert_pdfs_datalab_key.py`](../../scripts/03_conversion/03_convert_pdfs_datalab_key.py)
  chạy Marker với Datalab key trực tiếp.

Tài liệu thiết kế đã có:
[`../superpowers/specs/2026-04-27-marker-batch-conversion-design.md`](../superpowers/specs/2026-04-27-marker-batch-conversion-design.md)
và
[`../superpowers/plans/2026-04-27-marker-batch-conversion-plan.md`](../superpowers/plans/2026-04-27-marker-batch-conversion-plan.md).

### Diễn giải bảng Markdown

- [`../../scripts/03_conversion/04_convert_tables_to_text.py`](../../scripts/03_conversion/04_convert_tables_to_text.py)
  tìm bảng Markdown và dùng worker LLM để chuyển bảng sang đoạn giải thích
  tiếng Việt, giữ nội dung bảng ở dạng dễ retrieval hơn.

Tài liệu thiết kế đã có:
[`../superpowers/specs/2026-05-02-table-to-text-conversion-design.md`](../superpowers/specs/2026-05-02-table-to-text-conversion-design.md)
và
[`../superpowers/plans/2026-05-02-table-to-text-conversion.md`](../superpowers/plans/2026-05-02-table-to-text-conversion.md).

### Làm sạch nhiễu Markdown

- [`../../scripts/03_conversion/05_clean_markdown_image_noise.py`](../../scripts/03_conversion/05_clean_markdown_image_noise.py)
  xóa local image links, caption tiếng Anh ngắn, QR/logo noise và các dòng ảnh
  không hữu ích cho retrieval.

## Luồng chạy đề xuất

1. Chuyển PDF đã lọc sang Markdown:

```bash
python scripts/03_conversion/01_convert_pdfs_marker.py \
  --input data/health_insurance_pdfs \
  --output data/processed/marker_markdowns
```

2. Nếu cần conversion qua hosted API:

```bash
python scripts/03_conversion/02_convert_pdfs_datalab_api.py \
  --input data/health_insurance_pdfs \
  --output data/datalab_hosted_markdowns \
  --use-llm
```

3. Diễn giải bảng thành text:

```bash
python scripts/03_conversion/04_convert_tables_to_text.py
```

4. Làm sạch image noise:

```bash
python scripts/03_conversion/05_clean_markdown_image_noise.py \
  data/health_insurance/health_insurance_markdowns_interpreted \
  --output-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned
```

## Input và output

- Input: PDF đã lọc hoặc Markdown thô từ Marker/Datalab.
- Output: Markdown gốc, Markdown đã diễn giải bảng, Markdown đã làm sạch.
- Output sạch là nguồn khuyến nghị cho chunking, benchmark generation, Qdrant
  indexing và graph ingestion.

## Kiểm tra chất lượng

- Kiểm tra số file Markdown output bằng với số PDF kỳ vọng.
- Mở một vài file có bảng phức tạp để xác nhận bảng không bị mất header, quyền
  lợi, mức phí, giới hạn, thời gian chờ.
- Chạy cleaner ở chế độ dry-run trước nếu input là corpus mới:

```bash
python scripts/03_conversion/05_clean_markdown_image_noise.py \
  data/health_insurance/health_insurance_markdowns_interpreted \
  --dry-run
```

