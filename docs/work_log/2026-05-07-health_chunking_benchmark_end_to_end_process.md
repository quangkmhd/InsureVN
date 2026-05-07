# Quy Trình Đánh Giá Benchmark Chunking Từ Đầu Đến Cuối

**Ngày:** 2026-05-07
**Mục tiêu:** Chọn phương pháp chunking tốt hơn cho retrieval trong RAG, không cần gán nhãn tay và không ghi vào database.

Sơ đồ tổng quan:

![Flow tổng quát đánh giá benchmark chunking](../assets/health_chunking_benchmark_evaluation_flow.png)

---

## 1. Chuẩn Bị Dữ Liệu

Input là bộ Markdown bảo hiểm sức khỏe:

- `103` file Markdown.
- `7,442,006` ký tự nguồn.
- Dữ liệu chỉ được đọc để benchmark, không ghi vào database/vector store.

Mục tiêu của bước này là có corpus gốc để tất cả phương pháp chunking chạy trên cùng một dữ liệu.

---

## 2. Tạo Ground Truth Tự Động

Benchmark tự tạo bộ test retrieval từ chính Markdown, không cần người gán nhãn.

Quy trình:

1. Chia tài liệu theo heading Markdown và các mục pháp lý như `Điều`, `Mục`, `Chương`, `Phần`.
2. Lấy các đoạn evidence đủ dài, tối thiểu khoảng `180` ký tự.
3. Nếu evidence quá dài, tách thành span khoảng `220-1,400` ký tự.
4. Tạo query synthetic bằng công thức:

```text
query = heading + top keywords trong evidence
```

Mỗi case giữ lại:

```text
doc_id, start, end, evidence_text, case_type
```

Nhờ có `start/end`, benchmark biết chính xác đoạn nào trong source là bằng chứng đúng.

Kết quả bước này: `900` synthetic retrieval cases.

---

## 3. Chạy Các Phương Pháp Chunking

Mỗi phương pháp nhận cùng một corpus và tạo ra danh sách chunks riêng.

Các phương pháp hiện được chấm:

1. Fixed-size
2. Recursive
3. Sentence
4. Markdown
5. Regex
6. Semantic
7. Project Chunker
8. Hybrid Recursive+Semantic
9. Hierarchical Parent-Child
10. Late Chunking
11. LLM Chunking

Mỗi chunk giữ:

```text
chunk_id, method, doc_id, text, start, end, tokens
```

`start/end` của chunk được dùng để đo overlap với evidence gốc.

---

## 4. Chấm Retrieval

Mỗi method được chấm riêng.

Quy trình:

1. Fit `TfidfVectorizer` trên toàn bộ chunks của method đó.
2. Transform `900` synthetic queries.
3. Với mỗi query, lấy top `5` chunks.
4. Một chunk được xem là đúng nếu:

```text
chunk.doc_id == case.doc_id
AND overlap(chunk, evidence) / evidence_length >= 0.20
```

Các metric chính:

- `Hit@1`: top 1 có chunk đúng không.
- `Hit@3`: top 3 có chunk đúng không.
- `Hit@5`: top 5 có chunk đúng không.
- `MRR@5`: chunk đúng đứng càng cao điểm càng tốt.
- `Evidence Coverage@5`: top 5 bao phủ evidence tốt đến đâu.

Retrieval score:

```text
retrieval_score = 100 * (
  0.30 * Hit@1
  + 0.20 * Hit@3
  + 0.15 * Hit@5
  + 0.20 * MRR@5
  + 0.15 * EvidenceCoverage@5
)
```

---

## 5. Chấm Chất Lượng Chunk

Bước này không dùng query. Nó chỉ kiểm tra hình dạng chunk có tốt cho RAG/citation không.

Các lỗi bị phạt:

- Chunk quá nhỏ.
- Chunk quá lớn.
- Cắt giữa từ.
- Cắt giữa câu.
- Heading bị đứng một mình, thiếu nội dung theo sau.
- Table bị mất header.
- Redundancy quá cao do overlap/context lặp lại nhiều.

Quality score bắt đầu từ `100`, sau đó trừ điểm theo các lỗi trên.

---

## 6. Tính Điểm Tổng

Điểm tổng ưu tiên retrieval nhưng vẫn giữ ràng buộc chất lượng chunk:

```text
overall_score = 0.78 * retrieval_score + 0.22 * quality_score
```

Ý nghĩa:

- `78%` cho retrieval vì chunking chủ yếu phục vụ tìm đúng evidence.
- `22%` cho chất lượng chunk để tránh chọn method retrieve tốt nhưng chunk xấu, khó đọc hoặc khó citation.

---

## 7. Xuất Report

Benchmark xuất 3 định dạng:

```text
health_chunking_benchmark.md
health_chunking_benchmark.json
health_chunking_benchmark.csv
```

Report chứa:

- số document,
- tổng ký tự nguồn,
- số synthetic cases,
- phân bố case type,
- điểm từng method,
- ranking cuối cùng.

---

## 8. Kết Quả Hiện Tại

Top kết quả sau khi chấm `11` method:

| Rank | Method | Overall | Retrieval | Quality |
| ---: | --- | ---: | ---: | ---: |
| 1 | Late Chunking | 49.80 | 37.63 | 92.94 |
| 2 | LLM Chunking | 49.73 | 38.90 | 88.12 |
| 3 | Hierarchical Parent-Child | 43.74 | 30.03 | 92.32 |

Kết luận ngắn:

- `Late Chunking` đang đứng đầu overall.
- `LLM Chunking` có retrieval score cao nhất trong top 2, nhưng quality thấp hơn Late Chunking.
- Nên lấy top `2-3` method để chạy tiếp embedding retrieval, rerank và answer evaluation.

---

## 9. Cần Nhớ

Benchmark này dùng để chọn chunking candidate, không phải để kết luận chatbot production đã tốt.

Sau bước này cần đánh giá tiếp:

1. Retrieval bằng embedding production.
2. Rerank benchmark.
3. Answer correctness.
4. Citation correctness.
5. Human review trên query thật.
