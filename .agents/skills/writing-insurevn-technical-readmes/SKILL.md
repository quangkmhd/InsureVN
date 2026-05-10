---
name: writing-insurevn-technical-readmes
description: Use when creating, reviewing, or updating README.md files in InsureVN, including root README, module README, technical showcase, show tech, portfolio-style technical summary, setup docs, architecture summary, benchmark summary, or README cleanup.
---

# Viết README Kỹ Thuật Cho InsureVN

## Tổng Quan

README của InsureVN phải là **technical showcase**: cho người đọc thấy hệ thống đã làm gì, làm bằng kỹ thuật nào, trạng thái thật tới đâu, bằng chứng nằm ở đâu, và chạy/kiểm tra như thế nào. README không phải landing page marketing, không phải work log hằng ngày, và không thay thế tài liệu kiến trúc chi tiết.

Nguyên tắc cốt lõi: **đọc codebase và docs thật trước, rồi mới viết README**. README tốt phải trả lời đúng câu hỏi của người đọc, không chỉ liệt kê mọi thứ dự án có.

## Khi Nào Dùng

Dùng skill này khi người dùng yêu cầu:

- tạo hoặc sửa `README.md`
- review README
- làm README gọn lại, bớt lộn xộn
- viết README kiểu show kỹ thuật, show tech, portfolio kỹ thuật
- cập nhật phần architecture, tech stack, benchmark, roadmap, setup hoặc project status trong README

## Bước 1: Xác Định Task Và Audience

Trước khi sửa README, phân loại yêu cầu:

| Task | Cách xử lý |
| :--- | :--- |
| `Create` | Tạo README mới từ codebase, docs, setup và mục tiêu kỹ thuật. |
| `Update` | Đọc README hiện có, xác định phần stale, chỉ sửa phần cần thiết. |
| `Review` | So README với repo thật, báo claim sai, thiếu setup, thiếu bằng chứng, trùng docs. |
| `Restructure` | Giữ nội dung đúng, đổi cấu trúc để dễ đọc và có thứ tự kỹ thuật. |

Audience mặc định của InsureVN:

- developer mới vào dự án
- người review kỹ thuật/portfolio
- agent sau này cần hiểu repo nhanh
- chính maintainer khi quay lại dự án sau một thời gian

Không mặc định README là brochure cho người dùng cuối.

## Ngôn Ngữ Và Giọng Văn

- Viết bằng **tiếng Việt có dấu** cho README tiếng Việt.
- Giữ nguyên tên file, đường dẫn, lệnh terminal, class/function/module name, metric key và thuật ngữ kỹ thuật cần chính xác.
- Văn phong kỹ thuật, rõ ràng, có bằng chứng; tránh khẩu hiệu lớn nếu không có dữ liệu hỗ trợ.
- Không dùng emoji làm cấu trúc chính. Nếu file đang dùng emoji, có thể giữ vừa phải nhưng không thêm dày đặc.
- Ưu tiên câu trực tiếp, ngắn, có dữ kiện. Tránh văn phong AI/phóng đại như “đột phá”, “tối ưu tuyệt đối”, “production-ready” nếu chưa có bằng chứng vận hành.

## Bước 2: Đọc Bằng Chứng Trước Khi Viết

Tối thiểu đọc các nguồn phù hợp:

- `README.md` hiện tại nếu có
- `AGENTS.md` để nắm project conventions
- `pyproject.toml`, `requirements.txt`, `src/main.py`, `src/`, `scripts/`, `tests/`
- architecture docs canonical trong `docs/architecture/`
- `docs/README.md`, `docs/pipeline/`, `docs/database/`
- work log liên quan trong `docs/work_log/`
- asset diagram trong `asset/`

Với mỗi claim lớn trong README, cần có một trong các bằng chứng: file code, docs, work log, command output, metric report hoặc diagram.

## Cấu Trúc Root README Khuyến Nghị

README root nên có các phần theo thứ tự này, có thể rút gọn nếu task nhỏ:

1. **Project identity**: tên, mô tả 1-2 câu, logo/badge nếu đã có.
2. **Technical snapshot**: bảng ngắn gồm stack, trạng thái, dữ liệu, retrieval, agents, observability, test/eval.
3. **What is implemented**: các năng lực đã có, mỗi dòng kèm link bằng chứng hoặc file liên quan.
4. **Architecture**: mô tả ngắn, link diagram và tài liệu kiến trúc canonical.
5. **Data and evidence foundation**: SQLite, Qdrant, Knowledge Graph, citation/evidence model.
6. **Pipeline**: các phase xử lý dữ liệu, output chính, link runbook/work log.
7. **Evaluation and benchmarks**: chỉ giữ metric quan trọng nhất; link báo cáo chi tiết thay vì copy toàn bộ bảng dài.
8. **How to run**: prerequisites, environment, commands chạy app/test/eval phổ biến.
9. **Project structure**: cây thư mục ngắn, chỉ các folder người mới cần biết.
10. **Current status and next work**: completed/ongoing/planned, không biến thành changelog dài.
11. **Documentation map**: link tới architecture, pipeline docs, work logs, database docs.

README module hoặc package con có thể ngắn hơn: mô tả scope, entry point, cách chạy, API/commands chính, test, gotchas và link về root README.

## Quy Tắc Nội Dung

- Mỗi claim kỹ thuật quan trọng phải có bằng chứng: file code, docs, work log, command output, metric report hoặc asset.
- Nếu trạng thái chưa hoàn tất, ghi rõ `Design`, `Implemented`, `Evaluated`, `Blocked`, hoặc `Planned`.
- Không copy nguyên nội dung dài từ `docs/work_log`; README chỉ tóm tắt và link sang report.
- Không nhồi timeline “tin tức mới” dài. Nếu cần, giữ tối đa 3 mốc gần nhất hoặc chuyển sang changelog/work log.
- Không ghi “production-ready” nếu chưa có test, deployment, monitoring và operational evidence tương ứng.
- Không trộn nội dung người dùng cuối, nhà tuyển dụng, developer onboarding và vận hành vào cùng một đoạn dài; tách bằng heading/bảng.
- Không thêm README con nếu root README hoặc docs index đã đủ; tránh tạo nhiều nơi cập nhật cùng một sự thật.
- Với README dài trên khoảng 200 dòng, thêm mục lục ngắn, tối đa 2 cấp.
- Command phải copy-paste được và khớp tooling thật của repo.
- Bảng phù hợp cho tech stack, capability/status/evidence, env vars, scripts và benchmark summary.

## Cách Review README Hiện Có

Khi review hoặc chỉnh README:

1. Đọc `README.md`, `docs/README.md`, `AGENTS.md`, các architecture docs canonical và work log liên quan.
2. Lập danh sách claim lớn trong README: agents, retrieval, data scale, benchmark, production infrastructure, roadmap.
3. Đối chiếu từng claim với bằng chứng trong repo.
4. Gắn nhãn từng claim:
   - `Keep`: đúng, có bằng chứng, hữu ích.
   - `Trim`: đúng nhưng quá dài hoặc trùng docs khác.
   - `Move`: nên chuyển sang docs/work_log/changelog.
   - `Fix`: sai, mơ hồ hoặc vượt quá trạng thái thật.
5. Sửa README theo hướng ngắn hơn, nhiều link hơn, ít phóng đại hơn.

## Mẫu Technical Showcase

Root README cho InsureVN nên kết hợp hai kiểu:

- **Internal README**: setup, architecture, key files, troubleshooting, related docs.
- **Portfolio README**: tech stack, how it works, interesting technical decisions, evaluation result.

Không dùng README kiểu OSS package thuần nếu repo là product/platform phức tạp; phần API reference chi tiết nên nằm ở docs riêng.

## Template Ngắn

````markdown
# InsureVN

Mô tả 1-2 câu về hệ thống và mục tiêu kỹ thuật.

## Technical Snapshot

| Area | Current state | Evidence |
| :--- | :--- | :--- |
| Runtime | FastAPI, Python 3.12 | `src/main.py`, `pyproject.toml` |
| Retrieval | Quad retrieval: vector, sparse, graph, SQL | `docs/architecture/...` |

## Implemented Capabilities

| Capability | Status | Evidence |
| :--- | :--- | :--- |
| Evidence model | Implemented | `src/models/evidence.py` |

## Architecture

Tóm tắt ngắn. Link diagram và docs canonical.

## Data Pipeline

Tóm tắt 6 phase. Link runbook/report thay vì copy chi tiết.

## Evaluation

Metric chính, ngày chạy, link report.

## Running Locally

```bash
...
```

## Documentation Map

- Architecture: ...
- Work logs: ...
````

## Xác Minh Trước Khi Kết Luận

Sau khi sửa README:

```bash
rg -n "TODO|TBD|production-ready|Latest News|Tin tức mới" README.md docs/README.md || true
git diff -- README.md docs/README.md
git diff --check -- README.md docs/README.md
```

Nếu README có link tới file local đã đổi tên, kiểm tra link tồn tại bằng `test -e` hoặc script kiểm tra markdown link phù hợp.
