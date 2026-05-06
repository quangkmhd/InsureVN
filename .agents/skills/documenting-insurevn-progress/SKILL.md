---
name: documenting-insurevn-progress
description: Use when completing data processing tasks, implementing new agents, or updating project documentation in InsureVN to ensure standardized work logging following the established 6-phase flow.
---

# Documenting InsureVN Progress

## Overview

This skill enforces a standardized, **process-driven** approach to logging development milestones in InsureVN. It strictly follows the 6-phase data pipeline flow and the 3-tier system architecture.

## When to Use

- After any development activity in `scripts/` or `src/`.
- When asked to "summarize work", "write log", or "update progress".

## Core Principles: The Flow

All documentation MUST be categorized according to the established project phases:

### 1. Data Pipeline Phases (Mandatory)
- **Phase 1: Acquisition** (Scraping, crawling)
- **Phase 2: Preprocessing & QA** (AI classification, filtering)
- **Phase 3: Conversion & Interpretation** (PDF to MD, Table-to-Narrative)
- **Phase 4: Extraction** (JSON extraction, Good/Trash filtering, SQL Mapping)
- **Phase 5: Training & Eval** (Fine-tuning VLM, evaluation)
- **Phase 6: Ingestion** (SQL, Vector, Graph DB storage)

### 2. Core System Architecture
- **Tier 1: Infrastructure & Tools** (DB, MCP Servers, Search tools)
- **Tier 2: Core Services** (Chunking, Evidence Merging, Observability)
- **Tier 3: Intelligent Agents** (DatabaseAgent, Orchestrator)

## Implementation Rules

### 1. Maintain the "Flow" Section
Section 1 of the log MUST remain a detailed summary of these 6 phases. Do NOT simplify it into generic categories.

### 2. Standard Log Location
- Master Log: `/home/quangnhvn34/dev/me/InsureVN/docs/work_log/data_pipeline_processing_log.md`

### 3. Achievement Highlighting
Call out significant milestones like "99% Accuracy" or "Automated Mapping" using dedicated headers.

## Rationalization Table

| Excuse | Reality |
| :--- | :--- |
| "Quy trình 6 giai đoạn quá dài" | Đây là khung xương của dự án, giúp bất kỳ ai cũng có thể hiểu luồng dữ liệu ngay lập tức. |
| "Tóm tắt ngắn gọn cho nhanh" | Tóm tắt ngắn làm mất đi tính minh bạch của quy trình và các thành tựu kỹ thuật cụ thể. |
| "Chỉ cần ghi script là đủ" | Script chỉ là công cụ, quy trình (Phase) mới là cái giải thích TẠI SAO script đó tồn tại. |

## Red Flags - STOP and Correct
- Ghi log mà phá vỡ cấu trúc 6 giai đoạn của Pipeline.
- Quên phân loại script mới vào đúng giai đoạn (Phase) tương ứng.
- Link file không sử dụng giao thức `file:///`.

## Success Criteria
- Nhật ký thể hiện rõ ràng tiến độ theo từng giai đoạn (Flow-based).
- Các thành phần trong `src/` được đặt đúng vị trí trong kiến trúc hệ thống.
- Báo cáo vừa có cái nhìn tổng quan (Flow) vừa có chi tiết (Scripts).
