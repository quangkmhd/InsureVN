---
name: writing-insurevn-technical-reports
description: Use when người dùng yêu cầu tạo báo cáo kỹ thuật, work report, work log, implementation report, hoặc gọi skill này sau công việc coding, evaluation, data pipeline, agent, service, hoặc documentation trong InsureVN.
---

# Ghi Báo Cáo Kỹ Thuật InsureVN

## Tổng Quan

Tạo báo cáo kỹ thuật đầy đủ cho công việc đã hoàn thành trong InsureVN. Đây là tài liệu báo cáo, không phải ghi chú ngắn, và phải đủ bối cảnh để developer hoặc agent sau này hiểu mục tiêu, cách triển khai, bằng chứng, xác minh, kết quả, rủi ro và việc cần làm tiếp.

## Khi Nào Dùng

Chỉ dùng khi người dùng yêu cầu rõ, ví dụ:

- "ghi work log"
- "tạo báo cáo kỹ thuật"
- "write report"
- "create implementation report"
- "summarize this work into a report"
- "$writing-insurevn-technical-reports"

Không tự tạo báo cáo sau mọi thay đổi code nếu người dùng chưa yêu cầu.

## Yêu Cầu Ngôn Ngữ

Báo cáo mới phải viết bằng **tiếng Việt có dấu**. Giữ nguyên tên file, đường dẫn, lệnh terminal, class/function/module name, metric key, API field và trích dẫn kỹ thuật cần chính xác. Không tự dịch nội dung lịch sử đã có nếu việc dịch có thể làm thay đổi ý nghĩa hoặc làm sai số liệu; có thể đặt nội dung đó trong phần "Nội dung gốc được giữ lại".

## Vị Trí Mặc Định

Mỗi task tạo một báo cáo riêng:

```text
docs/work_log/YYYY-MM-DD-<task-name>-technical-report.md
```

Dùng ngày local hiện tại cho `YYYY-MM-DD`. Dùng slug ngắn, lowercase cho `<task-name>`.

## Nguồn Bằng Chứng

Dựa trên tất cả bằng chứng có sẵn:

- context cuộc trò chuyện và thông tin người dùng cung cấp
- `git status --short`
- `git diff --stat`
- `git diff --name-status`
- `git diff` có mục tiêu cho file liên quan
- commit, branch, tag hoặc range nếu người dùng cung cấp
- output test/evaluation trong phiên làm việc
- hiện vật đầu ra và file báo cáo đã tạo

Nếu thiếu bằng chứng, ghi rõ. Không bịa số liệu, lệnh hoặc kết quả.

## Mẫu Báo Cáo

Luôn có các mục dưới đây. Task nhỏ thì viết ngắn trong từng mục; task lớn thì thêm chi tiết, bảng và link hiện vật đầu ra khi hữu ích.

```markdown
# YYYY-MM-DD - Báo cáo kỹ thuật <Tên task>

## 1. Tóm tắt điều hành

## 2. Mục tiêu và phạm vi

## 3. Bối cảnh

## 4. Triển khai

## 5. Bằng chứng và lệnh đã chạy

## 6. Xác minh

## 7. Kết quả

## 8. Rủi ro và giới hạn

## 9. Việc tiếp theo
```

## Phân Loại InsureVN

Khi phù hợp, phân loại công việc trong `Bối cảnh` hoặc `Triển khai` theo mô hình hiện có của dự án:

- Data pipeline phase: Acquisition, Preprocessing & QA, Conversion & Interpretation, Extraction, Training & Eval, hoặc Ingestion
- System tier: Infrastructure & Tools, Core Services, hoặc Intelligent Agents
- Evidence foundation: SQLite, Qdrant, Knowledge Graph, hoặc merged evidence
- Risk lane: Fast Q&A, Verified Advisor, hoặc High-Risk Claim workflow

Không ép phân loại nếu không phù hợp.

## Ranh Giới

- Không update `README.md`, API docs, ADRs, changelogs hoặc runbooks nếu người dùng không yêu cầu cụ thể.
- Nếu công việc có quyết định kiến trúc, ghi "Nên tạo ADR" trong `Việc tiếp theo`; không tự tạo ADR.
- Nếu công việc liên quan release, ghi "Nên tạo changelog" trong `Việc tiếp theo`; không tự tạo release notes.
- Báo cáo phải factual, có bằng chứng.
- Dùng ngày tuyệt đối.

## Xác Minh Trước Khi Trả Lời Cuối

Sau khi viết báo cáo:

```bash
git diff -- docs/work_log
rg -n "TO[D]O|TB[D]|fill[[:space:]]+in|place[[:alpha:]]*holder" docs/work_log || true
```

Final response phải nêu đường dẫn báo cáo và mọi bước xác minh chưa hoàn tất.
