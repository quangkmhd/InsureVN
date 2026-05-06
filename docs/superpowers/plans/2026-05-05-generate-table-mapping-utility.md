# Generate Table Mapping Utility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a utility script to map Markdown documents to their extracted `source_table_id`s in SQLite for metadata indexing.

**Architecture:** The script will walk the `health_insurance_markdowns` directory, extract document identifiers from paths, query the SQLite `source_tables` table, and output a mapping report.

**Tech Stack:** Python 3.12, `sqlite3`, `pathlib`.

---

### Task 1: Create Mapping Script

**Files:**
- Create: `scripts/06_db_ingestion/07_generate_table_mapping.py`

- [ ] **Step 1: Write the script implementation**

```python
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.core.config import settings
from src.core.database import get_db_connection

def generate_mapping():
    markdown_dir = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns"
    output_file = markdown_dir / "table_mapping.json"

    mapping = {}

    # Connect to database
    with get_db_connection(read_only=True) as conn:
        cursor = conn.cursor()

        # Get all markdown files
        md_files = list(markdown_dir.glob("**/*.md"))
        print(f"Found {len(md_files)} markdown documents.")

        for md_path in md_files:
            # Extract folder name (document id)
            # e.g. aia.com.vn/021025-Quy-tac-va-dieu-khoan-Bao-hiem-Suc-khoe-Bung-Gia-Luc/
            doc_folder = md_path.parent.name
            company_folder = md_path.parent.parent.name
            relative_doc_path = f"{company_folder}/{doc_folder}"

            # Query source_tables for this document
            cursor.execute(
                "SELECT id, file_path, table_type, page_number FROM source_tables WHERE file_path LIKE ?",
                (f"%{relative_doc_path}%",)
            )
            rows = cursor.fetchall()

            if not rows:
                continue

            mapping[str(md_path.relative_to(markdown_dir))] = {
                "document_path": relative_doc_path,
                "tables": [
                    {
                        "source_table_id": row["id"],
                        "file_name": Path(row["file_path"]).name,
                        "table_type": row["table_type"],
                        "page_number": row["page_number"]
                    }
                    for row in rows
                ]
            }

    # Save mapping
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"Mapping saved to {output_file}")

if __name__ == "__main__":
    generate_mapping()
```

- [ ] **Step 2: Run the script**

Run: `python scripts/06_db_ingestion/07_generate_table_mapping.py`
Expected: "Mapping saved to .../table_mapping.json"

- [ ] **Step 3: Verify output**

Run: `cat data/health_insurance/health_insurance_markdowns/table_mapping.json | head -n 20`
Expected: JSON content showing md file paths and their associated tables.

- [ ] **Step 4: Commit**

```bash
git add scripts/06_db_ingestion/07_generate_table_mapping.py
git commit -m "feat: add table mapping utility script"
```
