# Technical Reference: InsureVN Database MCP Server (`insurevn-db`)

## 1. Overview
The `insurevn-db` MCP server is a standalone Model Context Protocol server built with **FastMCP**. It provides a bridge between AI agents (via LangChain/LangGraph) and the InsureVN SQLite database, exposing specialized tools to solve insurance-related queries.

- **Source Code:** `src/mcp_servers/sqlite/server.py`
- **Standard Protocol:** MCP (Model Context Protocol)
- **Transport:** `stdio` (Standard I/O)

---

## 2. Server Architecture
The server is designed to handle read-only database operations with a focus on high-level domain specific tools rather than raw SQL execution.

### Internal Helpers
- `_rows_to_dicts`: Converts SQLite rows into standard Python dictionaries for MCP compatibility.
- `_limit`: Enforces safe pagination limits (default 50, max 200).
- `_like`: Wraps strings in `%` for fuzzy SQL `LIKE` searches.
- `_placeholders`: Generates `?, ?, ?` strings for safe SQL `IN` clauses.

---

## 3. Tool Reference

### 3.1. Infrastructure & Discovery Tools
Tools for exploring the database structure, data volume, and source documentation.

| Tool Name | Description |
| :--- | :--- |
| `list_tables` | Returns all table names in the database. |
| `get_schema` | Returns DDL (`CREATE TABLE`) for specified tables. |
| `execute_query` | Executes a raw read-only SQL query (SELECT/PRAGMA/EXPLAIN only). |
| `database_summary` | Returns row counts for all major insurance domain tables. |
| `list_documents` | Returns source PDF documents with optional insurer, document type, and keyword filters. |
| `list_source_tables` | Returns extracted JSON table metadata (page, type, etc.) without raw_json payload. |

### 3.2. Insurance Domain Tools (Business Logic)
Specialized tools designed to answer the "100 Customer Intent Scenarios".

#### Product & Company Discovery
- **`list_companies`**: Returns available insurers with document and plan counts.
- **`list_plans`**: Returns plan types (Basic, Gold, etc.) filtered by insurer.
- **`search_plans`**: Fuzzy searches across plan aliases, raw names, and normalized plan codes.

#### Benefits & Comparisons
- **`search_benefits`**: Fuzzy searches across benefit names, notes, and values. Essential for "Does this plan cover X?" questions.
- **`compare_benefits`**: Side-by-side comparison of benefits across multiple companies/plans for a specific keyword.
- **`get_benefit_matrix`**: Returns a full matrix of benefit items and plan-specific values for a document/company/category.
- **`list_benefit_categories`**: Returns the benefit category taxonomy (e.g., Inpatient, Outpatient).

#### Pricing (Premium)
- **`get_premium_quotes`**: Returns premium rates based on `age`, `company`, `plan`, and `max_premium`. Handles age-range logic automatically.
- **`get_short_term_premiums`**: Returns short-term (non-annual) premium rates and duration rules.

#### Networks & Geography
- **`search_hospitals`**: Finds hospitals/clinics by name, city, or insurer. Supports filtering by "Bảo lãnh viện phí" (`gop_supported`).

#### Rules & Terms
- **`search_waiting_periods`**: Tra cứu thời gian chờ cho các bệnh lý/điều kiện.
- **`search_claim_payouts`**: Tra cứu tỷ lệ chi trả cho các sự kiện bảo hiểm.
- **`search_glossary_terms`**: Giải thích thuật ngữ bảo hiểm (Bệnh có sẵn, Đồng chi trả...).
- **`search_exclusions`**: Tìm kiếm tổng hợp các điều khoản loại trừ từ cả bảng `benefit_items` and `glossary_terms`.

### 3.3. Lineage & Debugging
- **`get_raw_source`**: Returns the full raw extracted JSON (including `raw_json` payload) and file path for a specific `source_table_id`. Allows the Agent to verify data against the source PDF.

---

## 4. Security
- **Read-Only Enforcement:** `execute_query` strictly validates that the query starts with `SELECT`, `PRAGMA`, or `EXPLAIN`.
- **Parameterization:** All tools use SQL parameterization (`?`) to prevent SQL injection.

---

## 5. Mapping to Customer Intents (Examples)

| Scenario Group | Tool Used | Example Query |
| :--- | :--- | :--- |
| **So sánh & Lựa chọn** | `compare_benefits` | Keyword: "Ung thư", Companies: ["aia", "liberty"] |
| **Sử dụng & Khám bệnh** | `search_hospitals` | City: "Hà Nội", GOP: True |
| **Claim & Payout** | `search_claim_payouts` | Keyword: "Gãy xương" |
| **Thời gian chờ** | `search_waiting_periods` | Keyword: "Bệnh đặc biệt" |
| **Giá cả** | `get_premium_quotes` | Age: 30, Company: "baominh" |
