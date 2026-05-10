# Thu Thập Và Tiền Xử Lý PDF Bảo Hiểm

## Mục tiêu

Nhóm script này tạo raw corpus cho InsureVN: crawl PDF từ website bảo hiểm,
lọc tài liệu liên quan bảo hiểm sức khỏe, phân loại tài liệu theo nhóm nghiệp
vụ và sắp xếp thư mục để các bước chuyển đổi/OCR phía sau dùng được.

Pipeline tương ứng với phase 1 và phase 2 trong
[`../work_log/2026-05-09-data-pipeline-processing-technical-report.md`](../work_log/2026-05-09-data-pipeline-processing-technical-report.md).

## Năng lực chính

### Crawl PDF từ website bảo hiểm

- [`../../scripts/01_acquisition/01_scrape_insurance_pdfs.py`](../../scripts/01_acquisition/01_scrape_insurance_pdfs.py)
  crawl nhiều website bảo hiểm bằng `requests`/`BeautifulSoup`, duyệt BFS trong
  cùng domain, tải PDF vào thư mục theo công ty.
- [`../../scripts/01_acquisition/02_scrape_multi_firecrawl.py`](../../scripts/01_acquisition/02_scrape_multi_firecrawl.py)
  dùng Firecrawl để tìm và tải PDF từ nhiều insurer target.
- [`../../scripts/01_acquisition/03_scrape_pacific_basic.py`](../../scripts/01_acquisition/03_scrape_pacific_basic.py),
  [`../../scripts/01_acquisition/04_scrape_pacific_deep.py`](../../scripts/01_acquisition/04_scrape_pacific_deep.py),
  [`../../scripts/01_acquisition/05_scrape_pacific_firecrawl.py`](../../scripts/01_acquisition/05_scrape_pacific_firecrawl.py)
  là các biến thể riêng cho Pacific Cross.
- [`../../scripts/01_acquisition/06_template_firecrawl.py`](../../scripts/01_acquisition/06_template_firecrawl.py)
  là template để tạo crawler Firecrawl mới.

### Lọc và phân loại PDF

- [`../../scripts/02_preprocessing/01_classify_pdfs_ollama.py`](../../scripts/02_preprocessing/01_classify_pdfs_ollama.py)
  phân loại PDF thô thành các nhóm như quy tắc điều khoản, biểu phí, bảng
  minh họa, tài liệu sản phẩm, báo cáo tài chính, biểu mẫu/hướng dẫn.
- [`../../scripts/02_preprocessing/02_find_health_insurance_pdfs.py`](../../scripts/02_preprocessing/02_find_health_insurance_pdfs.py)
  lọc corpus raw để giữ tài liệu có tín hiệu bảo hiểm sức khỏe.
- [`../../scripts/02_preprocessing/03_organize_pdfs.py`](../../scripts/02_preprocessing/03_organize_pdfs.py)
  sắp xếp PDF Pacific Cross theo keyword trong filename.
- [`../../scripts/02_preprocessing/04_organize_extracted_folders.py`](../../scripts/02_preprocessing/04_organize_extracted_folders.py)
  sắp xếp thư mục đã extract theo loại tài liệu.

## Luồng chạy đề xuất

1. Crawl raw PDFs:

```bash
python scripts/01_acquisition/01_scrape_insurance_pdfs.py
```

2. Bổ sung các nguồn dùng Firecrawl khi cần coverage sâu hơn:

```bash
python scripts/01_acquisition/02_scrape_multi_firecrawl.py
python scripts/01_acquisition/05_scrape_pacific_firecrawl.py
```

3. Lọc tài liệu bảo hiểm sức khỏe:

```bash
python scripts/02_preprocessing/02_find_health_insurance_pdfs.py
```

4. Phân loại và tổ chức lại corpus:

```bash
python scripts/02_preprocessing/01_classify_pdfs_ollama.py
python scripts/02_preprocessing/03_organize_pdfs.py
python scripts/02_preprocessing/04_organize_extracted_folders.py
```

## Input và output

- Input chính: website insurer, `data/raw/`, hoặc thư mục Pacific Cross đã crawl.
- Output chính: raw PDF theo insurer, `data/health_insurance_pdfs/`, các thư mục
  phân loại theo category.
- Output ở phase này chưa phải nguồn evidence canonical. Nó là corpus đầu vào
  cho conversion, OCR và ingestion.

## Lưu ý vận hành

- Giữ raw PDF bất biến sau khi tải. Nếu cần làm sạch hay đổi cấu trúc, tạo thư
  mục output mới để còn truy vết nguồn.
- Một số script preprocessing cũ có cấu hình provider/API nằm trực tiếp trong
  file. Trước khi chạy lại hoặc đưa lên môi trường chung, chuyển credential về
  `.env` và `src/core/config.py`.
- Script Firecrawl multi-site cần kiểm tra lại import/client version trước khi
  chạy, vì API Firecrawl có thể thay đổi theo package.

