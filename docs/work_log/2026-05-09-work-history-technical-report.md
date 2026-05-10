# Nhật ký Công việc Phát triển Hệ thống InsureVN

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-work-history-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Tổng hợp lịch sử công việc theo các phase data pipeline của InsureVN và utilities hỗ trợ.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-work-history-technical-report.md`
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

Tài liệu này tổng hợp các công việc đã thực hiện trong quá trình xây dựng hệ thống AI cho ngành bảo hiểm Việt Nam (InsureVN), dựa trên các kịch bản (scripts) đã triển khai. Quy trình được thực hiện theo luồng xử lý dữ liệu từ đầu đến cuối.

---

### 1. Giai đoạn 1: Thu thập dữ liệu (Acquisition)

**Mục tiêu:** Thu thập các tài liệu bảo hiểm từ nhiều nguồn khác nhau (web, PDF).

* **Scraping PDF Bảo hiểm:** Triển khai kịch bản `01_scrape_insurance_pdfs.py` để tự động thu thập tệp PDF từ các trang web bảo hiểm lớn tại Việt Nam (Bảo Việt, Bảo Minh, BIC, VBI, Liberty, Generali, PTI, AIA, PVI).
* **Sử dụng Firecrawl:** Áp dụng công nghệ Firecrawl (`02_scrape_multi_firecrawl.py`, `05_scrape_pacific_firecrawl.py`) để thu thập dữ liệu thô từ web một cách hiệu quả, đặc biệt là dữ liệu từ Pacific Cross.
* **Tìm kiếm chuyên sâu:** Thực hiện tìm kiếm và thu thập dữ liệu sâu (`04_scrape_pacific_deep.py`) để đảm bảo không bỏ sót thông tin quan trọng.

### 2. Giai đoạn 2: Tiền xử lý (Preprocessing)

**Mục tiêu:** Phân loại và tổ chức dữ liệu thô để chuẩn bị cho việc chuyển đổi.

* **Phân loại tài liệu bằng LLM:** Sử dụng Ollama (`01_classify_pdfs_ollama.py`) để tự động phân loại các tệp PDF đã thu thập được.
* **Lọc dữ liệu bảo hiểm sức khỏe:** Chuyên biệt hóa việc tìm kiếm và lọc các tài liệu liên quan đến bảo hiểm sức khỏe (`02_find_health_insurance_pdfs.py`).
* **Tổ chức thư mục:** Tự động hóa việc sắp xếp các tệp PDF và thư mục trích xuất (`03_organize_pdfs.py`, `04_organize_extracted_folders.py`) để quản lý dữ liệu ngăn nắp.

### 3. Giai đoạn 3: Chuyển đổi định dạng (Conversion)

**Mục tiêu:** Chuyển đổi PDF sang Markdown để máy có thể hiểu và xử lý tốt hơn.

* **Chuyển đổi bằng Marker:** Sử dụng công cụ Marker (`01_convert_pdfs_marker.py`) với sự hỗ trợ của GPU (CUDA) và Gemini API để chuyển đổi PDF sang Markdown chất lượng cao.
* **Sử dụng Datalab API:** Thử nghiệm và triển khai chuyển đổi qua Datalab (`02_convert_pdfs_datalab_api.py`, `03_convert_pdfs_datalab_key.py`).
* **Xử lý bảng và làm sạch:** Chuyển đổi các bảng trong tài liệu thành văn bản (`04_convert_tables_to_text.py`) và loại bỏ nhiễu hình ảnh trong tệp Markdown (`05_clean_markdown_image_noise.py`).

### 4. Giai đoạn 4: Trích xuất và Xây dựng Knowledge Graph (Extraction & KG)

**Mục tiêu:** Trích xuất thông tin cấu trúc và xây dựng mạng lưới tri thức.

* **Trích xuất cấu trúc tài liệu:** Tự động nhận diện cấu trúc văn bản (`01_extract_doc_structures.py`).
* **Trích xuất bảng và hình ảnh:** Sử dụng các mô hình LLM mạnh mẽ (Ollama, Gemini, VLM) để trích xuất dữ liệu từ bảng và hình ảnh một cách chính xác (`02_extract_tables_ollama.py`, `03_extract_images_ollama_robust.py`, `04_extract_images_multi_provider.py`).
* **Xây dựng Knowledge Graph:** Thiết kế và triển khai quy trình xây dựng đồ thị tri thức từ tài liệu (`05_build_knowledge_graph.py`), bao gồm cả việc khám phá và chuẩn hóa schema (`06_discover_knowledge_graph_schema.py`, `07_canonicalize_knowledge_graph_schema.py`).
* **Phân loại nội dung:** Tự động lọc bỏ các nội dung không giá trị ("trash") và giữ lại nội dung tốt (`08_classify_content_good_trash.py`, `08_cleanup_good_content.py`).

### 5. Giai đoạn 5: Huấn luyện và Đánh giá (Training & Evaluation)

**Mục tiêu:** Tinh chỉnh mô hình (Fine-tuning) để tối ưu hóa cho lĩnh vực bảo hiểm.

* **Chuẩn bị dữ liệu VLM:** Tạo tập dữ liệu cho mô hình Vision-Language (VLM) bằng Oumi (`01_prepare_oumi_vlm_dataset.py`).
* **Huấn luyện mô hình Gemma4:** Triển khai các kịch bản huấn luyện và xuất mô hình Gemma4 (`02_train_gemma4.py`, `04_export_gemma4.py`, `05_start_training.sh`).
* **Đánh giá:** Thực hiện đánh giá hiệu năng của mô hình sau huấn luyện (`03_eval_gemma4.py`, `run_vlm_inference.py`).

### 6. Giai đoạn 6: Nạp dữ liệu vào Database (DB Ingestion)

**Mục tiêu:** Đưa dữ liệu vào hệ thống lưu trữ để phục vụ RAG.

* **Nạp dữ liệu vào Qdrant:** Triển khai kịch bản nạp và lập chỉ mục (index) các đoạn văn bản vào Qdrant Vector Database (`04_index_qdrant_documents.py`, `09_index_all_markdowns.py`).
* **Ánh xạ dữ liệu:** Tạo và xác minh logic ánh xạ bảng (`07_generate_table_mapping.py`, `08_verify_mapping_logic.py`).
* **Nạp dữ liệu vào Neo4j:** Tích hợp việc nạp dữ liệu vào đồ thị tri thức Neo4j đồng thời với Qdrant.

### 7. Các công cụ hỗ trợ khác (Utilities)

* **Sơ đồ kiến trúc:** Tự động tạo các sơ đồ kiến trúc hệ thống (`create_diagrams.py`).
* **Truy vết (Tracing):** Công cụ hỗ trợ lấy thông tin truy vết từ Langfuse để phục vụ debug và giám sát (`fetch_langfuse_trace.py`, `debug_agent_trace.py`).
* **Công cụ Review:** Hỗ trợ kiểm soát chất lượng dữ liệu và mã nguồn (`review_tool.py`).

### Note

- Chunking: với ## là Parent, còn các content bên trong là childrent, và index kèm theo các thông tin như company name, file name, tên bảo hiểm,...
- So sánh 6 loại chunking khác nhau để tìm ra loại chunking phù hợp nhất, và thông số phù hợp nhất scripts/08_chunking_compare/00_chunking_compare.html,
- tính toán Token
- CI/CD, cost tracking, logging, human approval,eval, guardrails, monitoring, retries
- Maintenance nightmare: AI stack thay đổi cực nhanh: model update, API change,framework breaking change
- vector DB,queue,caching,observability,secrets,deployment,scaling, telemetry,eval,pipeline,throughput, latency, cost, accuracy, reliability
- thứ khó nhất không phải prompt, mà là production infrastructure
- https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/ bài nghiên cứu về:

  - Chunking strategy nào tốt nhất cho hệ thống RAG
  - Ảnh hưởng của kích thước chunk đến retrieval và chất lượng answer
  - So sánh thực nghiệm giữa nhiều kiểu chunking khác nhau trên nhiều dataset thực tế
- [Adaptive Chunking: Optimizing Chunking-Method Selection for RAG](https://arxiv.org/pdf/2603.25333) , [ekimetrics/adaptive-chunking: Adaptive Chunking: automatically select the best chunking method per document for RAG. Accepted at LREC 2026.](https://github.com/ekimetrics/adaptive-chunking)
- docs/work_log/2026-05-07-health-chunking-benchmark-end-to-end-process-technical-report.md tạo grounf truth tự động mà không cần gán nhãn tay: cắt theo các đầu mục như H1, H2 -> chọn các bock > 200 kí tự, cắt các block lớn hơn 400 kí tự. -> Tạo query = H1/H2 + **`[Top 10 Keywords]`** chính trong đoạn đó -> Ground: doc id + strat + end chính đoạn đó -> vecor lên bằng thư viện TfidfVectorizer -> tính toán Retrieval score-> Chấm Chất Lượng Chunk -> Retrieval score + Chất Lượng Chunk = overal
