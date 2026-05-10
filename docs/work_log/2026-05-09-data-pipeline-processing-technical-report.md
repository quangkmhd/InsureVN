# Nhật ký Phát triển Hệ thống InsureVN

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-data-pipeline-processing-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Index tiến độ data pipeline liên pha, bao phủ acquisition, ingestion và knowledge graph work.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-data-pipeline-processing-technical-report.md`
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

- Giữ index này đồng bộ khi có báo cáo kỹ thuật mới theo ngày trong `docs/work_log/`.
- Đưa bằng chứng chi tiết vào report riêng của từng task thay vì mở rộng index này quá dài.

## 10. Nội dung gốc được giữ lại

**Thời gian cập nhật:** 09/05/2026
**Trạng thái hệ thống:** Đã hoàn thiện pipeline chunking, embedding, Qdrant, eval retrieval/LLM judge và benchmark v2 theo context cho bảo hiểm sức khỏe. Chiến lược chunking mặc định đã được chuyển sang `hierarchical_header_recursive`; full vector/graph run cần cấu hình lại quota embedding và KG model để hoàn tất. Nhật ký mã nguồn `src/` được tách riêng.

---

### 1. Quy trình Xử lý Dữ liệu (Data Pipeline Flow)

Hệ thống được xây dựng trên một quy trình 6 giai đoạn nghiêm ngặt để đảm bảo dữ liệu thô từ PDF trở thành tri thức chính xác 99%.

#### Giai đoạn 1: Thu thập dữ liệu (Acquisition)
- **Mục tiêu:** Thu thập tài liệu PDF và dữ liệu web từ các công ty bảo hiểm lớn.
- **Thành tựu:** Tự động hóa việc xây dựng kho dữ liệu thô từ 9+ nguồn lớn (AIA, Bao Viet, PVI...).

#### Giai đoạn 2: Tiền xử lý & Kiểm soát chất lượng (Preprocessing & QA)
- **Mục tiêu:** Phân loại và lọc bỏ dữ liệu rác bằng AI.
- **Thành tựu:** Đảm bảo dữ liệu đầu vào sạch, lọc bỏ hoàn toàn các tài liệu không liên quan đến bảo hiểm sức khỏe.

#### Giai đoạn 3: Chuyển đổi & Diễn giải (Conversion & Interpretation)
- **Mục tiêu:** Chuyển PDF sang Markdown và diễn giải bảng biểu.
- **Thành tựu:** Sử dụng kỹ thuật **Table-to-Narrative** để biến bảng phí/quyền lợi phức tạp thành văn bản diễn giải tự nhiên cho AI.

#### Giai đoạn 4: Trích xuất tri thức & Lọc Good/Trash (Extraction)
- **Mục tiêu:** Trích xuất JSON có cấu trúc và lọc nội dung giá trị.
- **Thành tựu:** Sử dụng LLM phân loại file Tốt/Rác (Good/Trash) và tự động ánh xạ key JSON vào Schema SQL.

#### Giai đoạn 5: Huấn luyện & Đánh giá (Training & Eval)
- **Mục tiêu:** Tối ưu hóa model Vision (Gemma4) cho bảo hiểm Việt Nam.
- **Thành tựu:** Fine-tune thành công mô hình để nhận diện và trích xuất dữ liệu bảo hiểm với độ chính xác cao.

#### Giai đoạn 6: Đưa dữ liệu vào Database (Ingestion)
- **Mục tiêu:** Đẩy dữ liệu đồng bộ vào SQL, Vector DB và Graph DB.
- **Thành tựu:** Xây dựng nền tảng **Hybrid RAG** mạnh mẽ, tạo sự liên kết giữa SQL, Vector (Qdrant) và Graph (Neo4j).

#### Giai đoạn 7: Xây dựng Knowledge Graph (Knowledge Graph)
- **Mục tiêu:** Khám phá schema, chuẩn hóa và xây dựng đồ thị tri thức từ tài liệu.
- **Thành tựu:** Tự động hóa việc khám phá schema thực tế từ dữ liệu, giúp xây dựng Knowledge Graph chính xác và có thể mở rộng.

---

### 2. Liên kết Nhật ký Mã nguồn

Nhật ký này chỉ ghi tiến độ xử lý dữ liệu theo 6 giai đoạn pipeline. Danh mục chi tiết toàn bộ mã nguồn `src/` đã được tách sang file riêng:

- [`2026-05-09-src-code-inventory-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-09-src-code-inventory-technical-report.md)

---

### 3. Các thành tựu cốt lõi đã giải quyết (Core Achievements)

1.  **Độ chính xác 99%:** QA đa lớp cho toàn bộ quy trình.
2.  **Lọc Good/Trash:** Làm sạch dữ liệu tự động, loại bỏ rác hiệu quả.
3.  **Tự động Mapping Schema:** AI tự động hiểu và map dữ liệu vào SQL Database.
4.  **Agentic Observability:** Giám sát toàn bộ luồng suy luận của Agent qua Langfuse.

---

### 4. Danh mục Script Chi tiết (scripts/)

#### 4.1. Thu thập & Tiền xử lý
| Script | Công dụng |
| :--- | :--- |
| `01_acquisition/01_scrape_insurance_pdfs.py` | Crawler chính tải PDF. |
| `02_preprocessing/01_classify_pdfs_ollama.py` | AI phân loại PDF bảo hiểm. |

#### 4.2. Chuyển đổi & Trích xuất
| Script | Công dụng |
| :--- | :--- |
| `03_conversion/04_convert_tables_to_text.py` | Biến bảng biểu thành văn bản LLM. |
| `04_extraction/04_extract_images_multi_provider.py` | Trích xuất Ảnh/Bảng đa nguồn AI. |
| `04_extraction/08_classify_content_good_trash.py` | Lọc dữ liệu Tốt/Rác trước khi vào DB. |
| `04_extraction/11_llm_schema_mapping.py` | Tự động ánh xạ JSON sang Schema SQL. |

#### 4.3. Ingestion & Training
| Script | Công dụng |
| :--- | :--- |
| `05_training_eval/02_train_gemma4.py` | Huấn luyện mô hình Gemma4. |
| `05_training_eval/06_generate_health_rag_context_benchmark_v2.py` | Sinh benchmark v2 gồm 100 câu hỏi RAG theo context 1/2/3 chunk và table context, dùng 21 provider slots song song và không fallback deterministic. |
| `05_training_eval/run_llm_retrieval_judge_eval.py` | Chấm AI cho kết quả retrieval đã có, dùng provider pool không OpenAI và có resume khi provider timeout/rate-limit. |
| `05_training_eval/run_streaming_chunking_embedding_qdrant.py` | Chạy streaming chunking + embedding + Qdrant, có cache chunk boundary để không phải gọi lại LLM chunking. |
| `06_db_ingestion/02_ingest_with_mapping.py` | Đẩy dữ liệu vào SQL dựa trên mapping AI. |
| `06_db_ingestion/09_index_all_markdowns.py` | Pipeline đẩy dữ liệu đồng thời vào Vector & Graph. |
| `06_db_ingestion/04_index_qdrant_documents.py` | Index tài liệu vào Qdrant. |

#### 4.3.1. Báo cáo Eval / Vector Ingestion
| Ngày | Báo cáo | Nội dung |
| :--- | :--- | :--- |
| 2026-05-08 | [`2026-05-08-llm-chunking-cache-qdrant-run-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-08-llm-chunking-cache-qdrant-run-technical-report.md) | Hoàn tất 2 chiến lược LLM chunking trên 86 expected-source files, lưu chunk boundary cache và Qdrant per-strategy. |
| 2026-05-08 | [`2026-05-08-health-rag-context-benchmark-v2-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-08-health-rag-context-benchmark-v2-technical-report.md) | Tạo benchmark v2 riêng gồm 100 case: 30 single-context, 30 two-context, 30 three-context, 10 table-context; verify nguồn và quote line span đạt 0 lỗi. |
| 2026-05-09 | [`2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md) | Đánh giá 9 kỹ thuật chunking trên benchmark v2 mới, 100 case, 42 source files; `hierarchical_header_recursive` đứng đầu required-source recall@5 và line-overlap recall@5. |
| 2026-05-09 | [`2026-05-09-final-chunking-900-150-vs-512-50-decision-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-09-final-chunking-900-150-vs-512-50-decision-technical-report.md) | Kết luận không merge nhánh table-aware; `DEFAULT_CHUNK_SIZE=900` và `DEFAULT_CHUNK_OVERLAP=150` tốt hơn `512/50` trong benchmark hiện tại, và `hierarchical_header_recursive` tốt hơn phương pháp kết hợp về source recall tổng. |
| 2026-05-09 | [`2026-05-09-hierarchical-default-chunking-indexing-run-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-09-hierarchical-default-chunking-indexing-run-technical-report.md) | Chuyển default chunking sang `hierarchical_header_recursive`, thêm metadata QA, dry-run 107 tài liệu/9933 chunks không thiếu/rỗng/null metadata; full Qdrant/Graph run bị chặn bởi Gemini embedding quota và KG model default chưa authorized. |
| 2026-05-08 | [`2026-05-08-all-techniques-full-retrieval-eval-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-08-all-techniques-full-retrieval-eval-technical-report.md) | Đánh giá retrieval top-k=5 cho toàn bộ 9 kỹ thuật chunking trên 150 benchmark cases. |
| 2026-05-08 | [`2026-05-08-all-techniques-full-llm-judge-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-08-all-techniques-full-llm-judge-technical-report.md) | Chấm AI toàn bộ 1350 strategy-case retrieval rows, dùng Gemini/NVIDIA/Ollama provider pool, 1350/1350 completed. |
| 2026-05-09 | [`2026-05-09-knowledge-graph-schema-discovery-pipeline.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md) | Tài liệu kiến trúc chi tiết quy trình 4 giai đoạn (Discover, Clean, Select, Build) cho Knowledge Graph Swarm. |

#### 4.4. Knowledge Graph Discovery & Build
| Script | Công dụng |
| :--- | :--- |
| `07_knowledge_graph/01_discover_schema.py` | Khám phá candidate schema từ Markdown. |
| `07_knowledge_graph/02_canonicalize_schema.py` | Chuẩn hóa schema labels bằng AI. |
| `07_knowledge_graph/03_select_schema_v1.py` | Tổng hợp và chọn lọc Schema V1 chính thức. |
| `07_knowledge_graph/04_build_knowledge_graph.py` | Script chính xây dựng đồ thị từ dữ liệu. |


---

### 5. Kết luận
Dự án đã hoàn thiện cả về hạ tầng dữ liệu và khung kiến trúc Agent, đảm bảo tính quy trình và độ tin cậy cao.
