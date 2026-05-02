# Database Agent & MCP Integration Design

## 1. Mục đích (Purpose)
Tích hợp server MCP SQLite hiện có (`src/mcp_servers/sqlite/server.py`) vào kiến trúc Multi-Agent của InsureVN bằng LangChain và LangGraph. Đảm bảo nguyên tắc Single Responsibility (Mỗi agent một nhiệm vụ) và tránh hiện tượng "Tool Bloat" (nhồi nhét quá nhiều công cụ vào một LLM gây ảo giác).

## 2. Kiến trúc tổng quan (Architecture)
Thay vì cấp các công cụ (tools) truy vấn Database cho tất cả các Agents (như RAG, OCR), chúng ta sẽ đóng gói chúng vào một Agent chuyên biệt có tên là **DatabaseAgent**. 

Khi hệ thống vận hành qua LangGraph, nếu các Agent khác cần số liệu hoặc kiểm chứng thông tin, chúng sẽ truyền yêu cầu vào Graph State. `Orchestrator` sẽ điều phối nhiệm vụ này cho `DatabaseAgent`.

### Các thành phần cần phát triển:
1. **`src/tools/mcp_client.py`**
   - Nhiệm vụ: Chứa logic thiết lập kết nối `stdio` (subprocess) tới `server.py` bằng `langchain-mcp-adapters`.
   - Hàm chính: `get_sqlite_mcp_tools()` - hàm bất đồng bộ trả về danh sách các `BaseTool` đã được chuyển đổi để LangChain hiểu.

2. **`src/agents/database_agent.py`**
   - Nhiệm vụ: Một node trong LangGraph (sử dụng kiến trúc ReAct Agent).
   - Được cấp quyền **độc quyền** sử dụng các tools từ `mcp_client.py`.
   - Đầu vào: Yêu cầu trích xuất số liệu bằng ngôn ngữ tự nhiên từ Orchestrator.
   - Đầu ra: Kết quả truy vấn SQL đã được format và diễn giải lại bằng LLM.

## 3. Luồng dữ liệu (Data Flow)
1. **Khởi tạo hệ thống**: Application load `get_sqlite_mcp_tools()` để thiết lập connection pool ngầm với MCP subprocess.
2. **Xử lý yêu cầu (Execution)**:
   - User hỏi: *"Gói bảo hiểm A có chi trả thai sản không và mức phí là bao nhiêu?"*
   - Orchestrator (LangGraph) nhận thấy cần thông tin số liệu $\rightarrow$ Điều hướng context sang `DatabaseAgent`.
   - `DatabaseAgent` đọc State, tự động suy luận cần gọi tool `get_premium_quotes` (với tham số `plan_code="A"`) và `search_benefits`.
   - MCP Server (chạy file `server.py`) thực thi SQL, trả về list dictionaries.
   - `DatabaseAgent` tổng hợp lại thành câu trả lời tự nhiên.
   - Orchestrator gộp kết quả từ `DatabaseAgent` và `PolicyAgent` (RAG) $\rightarrow$ Sinh câu trả lời cuối cùng cho User.

## 4. Quản lý tài nguyên và Xử lý lỗi
- **Graceful Shutdown**: Do giao tiếp qua `stdio`, connection (subprocess) sẽ sống chừng nào ứng dụng còn chạy. Cần cung cấp cơ chế đóng `MultiServerMCPClient` gọn gàng khi FastAPI app ngừng hoạt động.
- **Tool Error**: Nếu LLM truyền sai tham số (ví dụ truyền chuỗi thay vì số nguyên cho tool `limit`), LangGraph ReAct agent sẽ tự động bắt lỗi từ Tool và LLM sẽ thử sửa lại (Self-correction).

## 5. Testing
- Viết integration test cơ bản để đảm bảo `langchain-mcp-adapters` có thể kích hoạt file `server.py` thành công.
- Test LLM (Gemini) của `DatabaseAgent` có khả năng tự map từ câu hỏi "Liệt kê các gói" thành action gọi tool `list_plans`.