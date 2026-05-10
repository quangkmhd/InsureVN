# Nhật ký Xây dựng Knowledge Graph (KG Construction Log)

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-08-knowledge-graph-construction-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Extraction và Knowledge Graph; workflow xây dựng knowledge graph ở Core Services.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-08-knowledge-graph-construction-technical-report.md`
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

**Thời gian:** 09/05/2026
**Thành phần:** Knowledge Graph Discovery & Building Pipeline
**Trạng thái:** Hoàn thành thiết kế quy trình 4 bước và ánh xạ mã nguồn thực thi.

---

### 1. Mục tiêu (Objective)

Thiết lập một pipeline tự động hóa để trích xuất tri thức dạng đồ thị (thực thể và quan hệ) từ các tài liệu bảo hiểm sức khỏe, đảm bảo tính nhất quán (Canonicalization) và khả năng truy vết (Lineage) tới tài liệu gốc.

### 2. Chi tiết quy trình đã triển khai (Implemented Pipeline)

Chúng tôi đã hoàn thiện và tài liệu hóa quy trình 4 giai đoạn dựa trên các script trong `scripts/07_knowledge_graph/`:

#### Bước 1: Schema Discovery
*   **Mục tiêu:** Khám phá tự động các loại thực thể và quan hệ phổ biến trong corpus.
*   **Script:** `01_discover_schema.py`
*   **Kết quả:** Xác định được các nhóm thực thể cốt lõi: `Company`, `Plan`, `Benefit`, `Exclusion`, `Condition`, `WaitingPeriod`.

#### Bước 2: Schema Canonicalization
*   **Mục tiêu:** Chuẩn hóa thuật ngữ AI trích xuất được để tránh trùng lặp và nhiễu.
*   **Script:** `02_canonicalize_schema.py`
*   **Hành động:** Sử dụng LLM để merge các label tương đồng và chọn lọc các quan hệ có giá trị nghiệp vụ cao nhất.

#### Bước 3: Schema Contract (V1)
*   **Mục tiêu:** Thiết lập bộ khung Schema chính thức để hướng dẫn quá trình trích xuất hàng loạt.
*   **Script:** `03_select_schema_v1.py`
*   **Sản phẩm:** File `allowed_nodes.csv` và `allowed_relationships.csv` dùng làm "ground truth" cho hệ thống.

#### Bước 4: Graph Building & Quality Validation
*   **Mục tiêu:** Trích xuất thực tế và xây dựng file Graph JSON cuối cùng.
*   **Script:** `04_build_knowledge_graph.py`
*   **Tính năng chính:**
    *   Trích xuất thực thể theo Schema Contract.
    *   Tự động kiểm định chất lượng (Orphan nodes, Lineage check).
    *   Xuất báo cáo chất lượng (`Quality Report`) và file `insurevn_graph.json`.

---

### 3. Tài liệu liên quan (Related Documents)

*   **Kiến trúc chi tiết:** [Knowledge Graph Schema Discovery & Pipeline](../architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md)
*   **Sơ đồ luồng:** `asset/Defining Entities-Relationships.png`
*   **Blueprint gốc:** [Phase 03: Knowledge Graph Foundation](../blueprints/phase_03_knowledge_graph_foundation.md)

---

### 4. Ghi chú kỹ thuật (Technical Notes)

*   Pipeline này là một phần của **Giai đoạn 6 (Ingestion)** trong quy trình xử lý dữ liệu tổng thể của InsureVN.
*   Đồ thị được xây dựng dưới dạng NetworkX (JSON) trước khi được nạp vào Neo4j để đảm bảo tính linh hoạt trong quá trình phát triển và kiểm thử.
