# Công Cụ Vận Hành, Review Và Debug

## Mục tiêu

Nhóm script này không trực tiếp tạo corpus hay index, nhưng giúp vận hành dự
án: tạo diagram, review output extraction, debug trace Langfuse và smoke-test
search tool.

## Năng lực chính

### Tạo diagram kiến trúc

- [`../../scripts/create_diagrams.py`](../../scripts/create_diagrams.py)
  tạo ba SVG trong `output/`: `arch1.svg`, `arch2.svg`, `arch_master.svg`.
  Nội dung gồm core multi-agent architecture, quad-retrieval RAG và master flow.

Chạy:

```bash
python scripts/create_diagrams.py
```

Diagram canonical hiện tại của dự án vẫn là
[`../../asset/insurevn-Architecture.svg`](../../asset/insurevn-Architecture.svg).
Script này dùng để tái tạo/thử nghiệm sơ đồ, không tự thay thế asset canonical.

### Review UI cho output ảnh và Markdown

- [`../../scripts/review_tool.py`](../../scripts/review_tool.py)
  khởi chạy FastAPI UI tại port `8000`, hiển thị danh sách cặp `.md`/`.png` và
  cho review side-by-side.

Chạy:

```bash
python scripts/review_tool.py
```

Lưu ý: `DATA_DIR` đang hard-code vào một thư mục AIA cụ thể. Trước khi review
corpus khác, đổi `DATA_DIR` hoặc refactor thành tham số CLI.

### Debug DatabaseAgent và Langfuse trace

- [`../../scripts/debug_agent_trace.py`](../../scripts/debug_agent_trace.py)
  tạo `DatabaseAgent`, chạy một query tiếng Việt và đọc log JSON gần nhất trong
  `log/mcp_database.log` để kiểm tra trace/tool call.
- [`../../scripts/fetch_langfuse_trace.py`](../../scripts/fetch_langfuse_trace.py)
  gọi Langfuse API để lấy trace gần nhất, in generation input/output và tool
  observations.

Chạy:

```bash
python scripts/debug_agent_trace.py
python scripts/fetch_langfuse_trace.py
```

Yêu cầu: `.env` cần có `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` và
`LANGFUSE_HOST` nếu không dùng default local host.

### Smoke-test Search Tool

- [`../../scripts/run_search_tool.py`](../../scripts/run_search_tool.py)
  gọi `src.tools.search_tool.search_web` với query mẫu để kiểm tra Tavily/live
  search tool.

Chạy:

```bash
python scripts/run_search_tool.py
```

## Lưu ý vận hành

- Trace và search output có thể chứa prompt, query, tool output hoặc dữ liệu
  nhạy cảm. Không paste log thô vào tài liệu công khai nếu chưa scrub.
- Các script debug thêm project root vào `sys.path` để chạy trực tiếp từ repo.
  Đây là tiện ích local, không phải API production.
- Review UI hiện chưa lưu trạng thái approve/reject; nút Done chỉ chuyển sang
  item tiếp theo.

