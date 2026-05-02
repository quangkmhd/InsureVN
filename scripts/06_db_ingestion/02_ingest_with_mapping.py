"""Ingest JSON data into SQLite using LLM-generated schema mapping.

Data-driven ingestion: reads schema_mapping.json to know which table/column
each key maps to. No hardcoded heuristics.

Usage:
    python scripts/06_db_ingestion/02_ingest_with_mapping.py
    python scripts/06_db_ingestion/02_ingest_with_mapping.py --dry-run
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.core.database import get_db_connection, execute_sql_file

# --- CONFIG ---
DATA_DIR = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_extracted_good_content"
MAPPING_FILE = DATA_DIR / "schema_mapping_results" / "schema_mapping.json"
SCHEMA_FILE = PROJECT_ROOT / "src" / "models" / "schema.sql"

COMPANY_MAP: dict[str, str] = {
    "aia.com.vn": "aia",
    "pacific_cross_all_pdfs": "pacific_cross",
    "bic.vn": "bic",
    "libertyinsurance.com.vn": "liberty",
    "baominh.com.vn": "baominh",
    "pti.com.vn": "pti",
}

DRY_RUN = False


# ============================================================
# Helpers
# ============================================================

def truncate(val: str | None, max_len: int) -> str | None:
    """Truncate string to max_len."""
    if val is None:
        return None
    return val[:max_len] if len(val) > max_len else val


def normalize_key(key: str) -> str:
    """Normalize key for keyset lookup."""
    key = unicodedata.normalize("NFC", key)
    key = key.strip()
    key = re.sub(r"\s+", " ", key)
    return key


def extract_keyset_id(data: dict) -> str | None:
    """Extract keyset_id from structured_data for mapping lookup."""
    structured = data.get("structured_data")
    if structured is None:
        return None
    keys: set[str] = set()
    if isinstance(structured, list):
        for row in structured:
            if isinstance(row, dict):
                keys.update(row.keys())
    elif isinstance(structured, dict):
        keys.update(structured.keys())
    sorted_keys = sorted(normalize_key(k) for k in keys if k.strip())
    if not sorted_keys:
        return None
    return " | ".join(sorted_keys)


def parse_numeric(val: Any) -> int | None:
    """Try to parse a Vietnamese-formatted number."""
    if val is None:
        return None
    clean = str(val).replace(".", "").replace(",", "").strip()
    if clean.isdigit():
        return int(clean)
    return None


def parse_age_range(label: str) -> tuple[int | None, int | None]:
    """Extract age_min, age_max from age label text."""
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)", str(label))
    if match:
        return int(match.group(1)), int(match.group(2))
    if "dưới" in str(label).lower():
        m = re.search(r"(\d+)", str(label))
        return (None, int(m.group(1))) if m else (None, None)
    if "trên" in str(label).lower() or "từ" in str(label).lower():
        m = re.search(r"(\d+)", str(label))
        return (int(m.group(1)), None) if m else (None, None)
    m = re.search(r"(\d+)", str(label))
    if m:
        v = int(m.group(1))
        return v, v
    return None, None


def get_company_code(file_path: str) -> str | None:
    """Extract company code from file path."""
    for folder, code in COMPANY_MAP.items():
        if folder in file_path:
            return code
    return None


def get_doc_name(file_path: str) -> str:
    """Extract document folder name from file path."""
    parts = Path(file_path).parts
    # path: company_folder/doc_folder/table_pX_nY.json
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else "unknown"


# ============================================================
# DB Helpers
# ============================================================

def clear_all_data(cur: Any) -> None:
    """Delete all data from domain tables (reverse dependency order)."""
    tables = [
        "benefit_values", "benefit_items", "premium_entries",
        "hospitals", "glossary_terms", "waiting_periods",
        "claim_payouts", "short_term_premiums",
        "source_tables", "plan_types", "documents",
    ]
    for t in tables:
        cur.execute(f"DELETE FROM {t}")
        print(f"  🗑️  Cleared {t}")


def get_or_create_doc(
    cur: Any, company_id: int, company_code: str, doc_name: str,
    doc_cache: dict[str, int],
) -> int:
    """Get or create document, return document ID."""
    source_path = f"{company_code}/{doc_name}"
    if source_path in doc_cache:
        return doc_cache[source_path]
    cur.execute(
        "INSERT INTO documents (company_id, source_path, document_name) "
        "VALUES (?, ?, ?) RETURNING id",
        (company_id, source_path, doc_name),
    )
    doc_id = cur.fetchone()[0]
    doc_cache[source_path] = doc_id
    return doc_id


def get_or_create_plan(
    cur: Any, company_id: int, doc_id: int,
    raw_name: str, normalized_code: str, plan_level: int,
    plan_cache: dict[str, int],
) -> int:
    """Get or create plan_type, return plan ID."""
    cache_key = f"{doc_id}:{raw_name}"
    if cache_key in plan_cache:
        return plan_cache[cache_key]
    cur.execute(
        "SELECT id FROM plan_types WHERE document_id = ? AND raw_name = ?",
        (doc_id, raw_name),
    )
    row = cur.fetchone()
    if row:
        plan_cache[cache_key] = row[0]
        return row[0]
    cur.execute(
        "INSERT INTO plan_types (company_id, document_id, raw_name, normalized_code, plan_level) "
        "VALUES (?, ?, ?, ?, ?) RETURNING id",
        (company_id, doc_id, raw_name, normalized_code, plan_level),
    )
    plan_id = cur.fetchone()[0]
    plan_cache[cache_key] = plan_id
    return plan_id


def create_source_table(
    cur: Any, doc_id: int, file_path: str, table_type: str,
    description: str, raw_json: dict, keys: list[str],
    content_type: str, page_number: int | None, table_index: int | None,
) -> int:
    """Create source_table entry, return ID."""
    cur.execute(
        """INSERT INTO source_tables
        (document_id, file_path, table_type, classification_reason,
         page_number, table_index, raw_json, keys, content_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (file_path) DO UPDATE SET
            table_type = EXCLUDED.table_type,
            raw_json = EXCLUDED.raw_json,
            keys = EXCLUDED.keys
        RETURNING id""",
        (doc_id, file_path, table_type, description,
         page_number, table_index, json.dumps(raw_json),
         json.dumps(keys), content_type),
    )
    return cur.fetchone()[0]


# ============================================================
# Domain Ingestors (data-driven via mapping)
# ============================================================

def ingest_benefit(
    cur: Any, st_id: int, doc_id: int, company_id: int,
    structured: list[dict], mapping: dict, plan_cache: dict[str, int],
) -> int:
    """Ingest benefit_items + benefit_values using mapping."""
    key_roles = mapping.get("key_roles", {})

    # Find row_label key
    row_label_key = None
    plan_keys: list[tuple[str, str, int]] = []  # (raw_name, code, level)
    meta_map: dict[str, str] = {}  # key -> column

    for k, info in key_roles.items():
        role = info.get("role", "")
        if role == "row_label":
            row_label_key = k
        elif role == "plan_value":
            plan_keys.append((k, info.get("plan_normalized_code", "other"), info.get("plan_level", 9)))
        elif role in ("direct_column", "metadata"):
            col = info.get("column", "")
            if col:
                meta_map[k] = col

    # Create plan_types
    plan_id_map: dict[str, int] = {}
    for raw_name, code, level in plan_keys:
        plan_id_map[raw_name] = get_or_create_plan(
            cur, company_id, doc_id, raw_name, code, level, plan_cache,
        )

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        raw_name = row.get(row_label_key, "") if row_label_key else ""
        if not raw_name and row_label_key:
            # Try first non-plan key as fallback
            for k in row:
                if k not in [pk[0] for pk in plan_keys] and k not in meta_map and row[k]:
                    raw_name = str(k)
                    break
        if not raw_name:
            continue

        applicable_to = row.get(meta_map.get("applicable_to", "___"), None) if "applicable_to" in meta_map.values() else None
        note_key = next((k for k, v in meta_map.items() if v == "note"), None)
        note = row.get(note_key) if note_key else None
        unit_key = next((k for k, v in meta_map.items() if v == "unit"), None)

        cur.execute(
            """INSERT INTO benefit_items
            (source_table_id, document_id, row_index, raw_row, raw_name, applicable_to, note)
            VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (st_id, doc_id, idx, json.dumps(row),
             truncate(str(raw_name), 500),
             truncate(str(applicable_to), 500) if applicable_to else None,
             note),
        )
        item_id = cur.fetchone()[0]

        for raw_plan, code, level in plan_keys:
            val = row.get(raw_plan)
            if val is None:
                continue
            plan_id = plan_id_map[raw_plan]
            unit = row.get(unit_key) if unit_key else None
            cur.execute(
                """INSERT INTO benefit_values
                (benefit_item_id, plan_type_id, value, value_numeric, unit)
                VALUES (?, ?, ?, ?, ?)""",
                (item_id, plan_id, str(val), parse_numeric(val),
                 truncate(str(unit), 100) if unit else None),
            )
        count += 1
    return count


def ingest_premium(
    cur: Any, st_id: int, doc_id: int, company_id: int,
    structured: list[dict], mapping: dict, plan_cache: dict[str, int],
) -> int:
    """Ingest premium_entries using mapping."""
    key_roles = mapping.get("key_roles", {})

    row_label_key = None
    plan_keys: list[tuple[str, str, int]] = []

    for k, info in key_roles.items():
        role = info.get("role", "")
        if role == "row_label":
            row_label_key = k
        elif role == "plan_value":
            plan_keys.append((k, info.get("plan_normalized_code", "other"), info.get("plan_level", 9)))

    plan_id_map: dict[str, int] = {}
    for raw_name, code, level in plan_keys:
        plan_id_map[raw_name] = get_or_create_plan(
            cur, company_id, doc_id, raw_name, code, level, plan_cache,
        )

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        age_label = row.get(row_label_key, "") if row_label_key else ""
        if not age_label:
            continue
        age_min, age_max = parse_age_range(str(age_label))

        for raw_plan, code, level in plan_keys:
            val = row.get(raw_plan)
            if val is None:
                continue
            plan_id = plan_id_map[raw_plan]
            cur.execute(
                """INSERT INTO premium_entries
                (source_table_id, document_id, plan_type_id, row_index, raw_row,
                 age_min, age_max, age_label, premium_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (st_id, doc_id, plan_id, idx, json.dumps(row),
                 age_min, age_max, truncate(str(age_label), 50), parse_numeric(val)),
            )
        count += 1
    return count


def ingest_hospital(
    cur: Any, st_id: int, doc_id: int,
    structured: list[dict], mapping: dict,
) -> int:
    """Ingest hospitals using mapping."""
    key_roles = mapping.get("key_roles", {})
    col_map: dict[str, str] = {}
    for k, info in key_roles.items():
        role = info.get("role", "")
        col = info.get("column", "")
        if role in ("row_label", "direct_column", "metadata") and col:
            col_map[k] = col

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        vals: dict[str, Any] = {}
        for json_key, db_col in col_map.items():
            v = row.get(json_key)
            if v is not None:
                vals[db_col] = v

        name_vi = vals.get("name_vi")
        name_en = vals.get("name_en")
        if not name_vi and not name_en:
            continue

        cur.execute(
            """INSERT INTO hospitals
            (source_table_id, document_id, row_index, raw_row,
             name_vi, name_en, address, city, phone, hospital_type,
             external_id, note, country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (st_id, doc_id, idx, json.dumps(row),
             truncate(str(name_vi), 300) if name_vi else None,
             truncate(str(name_en), 300) if name_en else None,
             vals.get("address"), vals.get("city"),
             truncate(str(vals.get("phone", "")), 100) if vals.get("phone") else None,
             vals.get("hospital_type"),
             truncate(str(vals.get("external_id", "")), 50) if vals.get("external_id") else None,
             vals.get("note"),
             vals.get("country", "VN")),
        )
        count += 1
    return count


def ingest_glossary(
    cur: Any, st_id: int, doc_id: int,
    structured: list[dict], mapping: dict,
) -> int:
    """Ingest glossary_terms using mapping."""
    key_roles = mapping.get("key_roles", {})
    term_key = None
    def_key = None
    for k, info in key_roles.items():
        col = info.get("column", "")
        if col == "term":
            term_key = k
        elif col == "definition":
            def_key = k

    if not term_key or not def_key:
        return 0

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        term = row.get(term_key)
        definition = row.get(def_key)
        if not term or not definition:
            continue
        cur.execute(
            """INSERT INTO glossary_terms
            (source_table_id, document_id, row_index, raw_row, term, definition)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (st_id, doc_id, idx, json.dumps(row),
             truncate(str(term), 300), str(definition)),
        )
        count += 1
    return count


def ingest_waiting_period(
    cur: Any, st_id: int, doc_id: int,
    structured: list[dict], mapping: dict,
) -> int:
    """Ingest waiting_periods using mapping."""
    key_roles = mapping.get("key_roles", {})
    col_map: dict[str, str] = {}
    for k, info in key_roles.items():
        col = info.get("column", "")
        if col:
            col_map[k] = col

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        vals: dict[str, Any] = {}
        for json_key, db_col in col_map.items():
            v = row.get(json_key)
            if v is not None:
                vals[db_col] = v

        cur.execute(
            """INSERT INTO waiting_periods
            (source_table_id, document_id, row_index, raw_row,
             condition_group, condition_detail, waiting_days, waiting_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (st_id, doc_id, idx, json.dumps(row),
             truncate(str(vals.get("condition_group", "")), 200) if vals.get("condition_group") else None,
             vals.get("condition_detail"),
             parse_numeric(vals.get("waiting_days")) if vals.get("waiting_days") else None,
             truncate(str(vals.get("waiting_text", "")), 200) if vals.get("waiting_text") else None),
        )
        count += 1
    return count


def ingest_claim_payout(
    cur: Any, st_id: int, doc_id: int,
    structured: list[dict], mapping: dict,
) -> int:
    """Ingest claim_payouts using mapping."""
    key_roles = mapping.get("key_roles", {})
    col_map: dict[str, str] = {}
    for k, info in key_roles.items():
        col = info.get("column", "")
        if col:
            col_map[k] = col

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        vals: dict[str, Any] = {}
        for json_key, db_col in col_map.items():
            v = row.get(json_key)
            if v is not None:
                vals[db_col] = v

        cur.execute(
            """INSERT INTO claim_payouts
            (source_table_id, document_id, row_index, raw_row,
             event, payout_rate, payout_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (st_id, doc_id, idx, json.dumps(row),
             truncate(str(vals.get("event", "")), 300) if vals.get("event") else None,
             parse_numeric(vals.get("payout_rate")),
             truncate(str(vals.get("payout_text", "")), 200) if vals.get("payout_text") else None),
        )
        count += 1
    return count


def ingest_short_term_premium(
    cur: Any, st_id: int, doc_id: int,
    structured: list[dict], mapping: dict,
) -> int:
    """Ingest short_term_premiums using mapping."""
    key_roles = mapping.get("key_roles", {})
    col_map: dict[str, str] = {}
    for k, info in key_roles.items():
        col = info.get("column", "")
        if col:
            col_map[k] = col

    count = 0
    for idx, row in enumerate(structured):
        if not isinstance(row, dict):
            continue
        vals: dict[str, Any] = {}
        for json_key, db_col in col_map.items():
            v = row.get(json_key)
            if v is not None:
                vals[db_col] = v

        cur.execute(
            """INSERT INTO short_term_premiums
            (source_table_id, document_id, row_index, raw_row,
             duration_text, duration_days, premium_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (st_id, doc_id, idx, json.dumps(row),
             truncate(str(vals.get("duration_text", "")), 200) if vals.get("duration_text") else None,
             parse_numeric(vals.get("duration_days")),
             parse_numeric(vals.get("premium_rate"))),
        )
        count += 1
    return count


# ============================================================
# Main ingestion
# ============================================================

INGESTOR_MAP = {
    "benefit_items": ingest_benefit,
    "premium_entries": ingest_premium,
    "hospitals": ingest_hospital,
    "glossary_terms": ingest_glossary,
    "waiting_periods": ingest_waiting_period,
    "claim_payouts": ingest_claim_payout,
    "short_term_premiums": ingest_short_term_premium,
}


def extract_page_info(filename: str) -> tuple[int | None, int | None]:
    """Extract page number and table index from filename like table_p6_n1.json."""
    m = re.match(r"table_p(\d+)_n(\d+)", filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def ingest_all() -> None:
    """Main ingestion pipeline."""
    if not MAPPING_FILE.exists():
        print(f"❌ Mapping file not found: {MAPPING_FILE}")
        sys.exit(1)

    schema_mapping: dict = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    print(f"📦 Loaded {len(schema_mapping)} schema mappings")

    # Collect all JSON files
    json_files = sorted(
        f for f in DATA_DIR.rglob("*.json")
        if "classification_output" not in str(f) and "schema_mapping" not in str(f)
    )
    print(f"📂 Found {len(json_files)} JSON files")

    if DRY_RUN:
        print("🔍 DRY RUN — no database changes will be made")
        return

    # Init DB
    print("🔄 Initializing schema...")
    execute_sql_file(str(SCHEMA_FILE))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Clear all existing data
        print("🗑️  Clearing all existing data...")
        clear_all_data(cur)
        conn.commit()

        # Load company map
        cur.execute("SELECT code, id FROM companies")
        company_db_map: dict[str, int] = {code: cid for code, cid in cur.fetchall()}

        doc_cache: dict[str, int] = {}
        plan_cache: dict[str, int] = {}

        from collections import Counter
        stats = Counter()
        errors: list[str] = []

        for i, fp in enumerate(json_files):
            rel_path = str(fp.relative_to(DATA_DIR))
            company_code = get_company_code(rel_path)
            if not company_code or company_code not in company_db_map:
                stats["skipped_no_company"] += 1
                continue

            try:
                raw_json = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                stats["skipped_bad_json"] += 1
                continue

            keyset_id = extract_keyset_id(raw_json)
            if not keyset_id or keyset_id not in schema_mapping:
                stats["skipped_no_mapping"] += 1
                continue

            mapping = schema_mapping[keyset_id]
            table_type = mapping.get("target_table", "unknown")
            description = mapping.get("description", "")

            if table_type not in INGESTOR_MAP:
                stats["skipped_unknown_table"] += 1
                continue

            company_id = company_db_map[company_code]
            doc_name = get_doc_name(rel_path)
            page_num, table_idx = extract_page_info(fp.name)

            try:
                pass # SQLite handled by transaction context

                doc_id = get_or_create_doc(cur, company_id, company_code, doc_name, doc_cache)

                structured = raw_json.get("structured_data", [])
                if isinstance(structured, dict):
                    structured = [structured]
                if not structured:
                    pass # SQLite handled by transaction context
                    stats["skipped_empty"] += 1
                    continue

                keys = sorted(set(
                    normalize_key(k) for row in structured
                    if isinstance(row, dict) for k in row.keys() if k.strip()
                ))
                content_type = raw_json.get("content_type", "table")

                st_id = create_source_table(
                    cur, doc_id, rel_path, table_type, description,
                    raw_json, keys, content_type, page_num, table_idx,
                )

                ingestor = INGESTOR_MAP[table_type]
                if table_type in ("benefit_items", "premium_entries"):
                    row_count = ingestor(cur, st_id, doc_id, company_id, structured, mapping, plan_cache)
                else:
                    row_count = ingestor(cur, st_id, doc_id, structured, mapping)

                pass # SQLite handled by transaction context
                stats[table_type] += row_count
                stats["files_ok"] += 1

                if (i + 1) % 100 == 0:
                    conn.commit()
                    print(f"  ✅ {i + 1}/{len(json_files)} files processed...")

            except Exception as e:
                errors.append(f"{rel_path}: {e}")
                stats["errors"] += 1

        conn.commit()

        # Print summary
        print(f"\n{'=' * 60}")
        print("📊 INGESTION SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Files processed OK:   {stats['files_ok']}")
        print(f"  Errors:               {stats['errors']}")
        print(f"  Skipped (no company): {stats['skipped_no_company']}")
        print(f"  Skipped (no mapping): {stats['skipped_no_mapping']}")
        print(f"  Skipped (empty):      {stats['skipped_empty']}")
        print(f"\n  Rows inserted per table:")
        for table in INGESTOR_MAP:
            if stats[table] > 0:
                print(f"    {table:25s} {stats[table]:6d}")

        if errors:
            print(f"\n  ⚠️ First 10 errors:")
            for e in errors[:10]:
                print(f"    ❌ {e}")

    finally:
        cur.close()
        conn.close()

    print("\n✅ Ingestion complete!")

    # Export CSVs for review
    if not DRY_RUN:
        export_review_csvs()


def export_review_csvs() -> None:
    """Export all domain tables to CSV for human review."""
    import csv

    out_dir = DATA_DIR / "schema_mapping_results" / "db_review"
    out_dir.mkdir(parents=True, exist_ok=True)

    queries = {
        "benefit_items": """
            SELECT bi.id, c.code AS company, d.document_name,
                   bi.raw_name, bi.applicable_to, bi.note,
                   st.table_type, st.file_path
            FROM benefit_items bi
            JOIN documents d ON bi.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            JOIN source_tables st ON bi.source_table_id = st.id
            ORDER BY c.code, d.document_name, bi.row_index
        """,
        "benefit_values": """
            SELECT bv.id, c.code AS company, d.document_name,
                   bi.raw_name AS benefit_name,
                   pt.raw_name AS plan_name, pt.normalized_code AS plan_code,
                   pt.plan_level, bv.value, bv.value_numeric, bv.unit
            FROM benefit_values bv
            JOIN benefit_items bi ON bv.benefit_item_id = bi.id
            JOIN plan_types pt ON bv.plan_type_id = pt.id
            JOIN documents d ON bi.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            ORDER BY c.code, d.document_name, bi.row_index, pt.plan_level
        """,
        "premium_entries": """
            SELECT pe.id, c.code AS company, d.document_name,
                   pt.raw_name AS plan_name, pt.normalized_code AS plan_code,
                   pe.age_label, pe.age_min, pe.age_max, pe.premium_amount,
                   st.file_path
            FROM premium_entries pe
            JOIN documents d ON pe.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            JOIN source_tables st ON pe.source_table_id = st.id
            LEFT JOIN plan_types pt ON pe.plan_type_id = pt.id
            ORDER BY c.code, d.document_name, pe.row_index
        """,
        "hospitals": """
            SELECT h.id, c.code AS company, d.document_name,
                   h.name_vi, h.name_en, h.address, h.city, h.country,
                   h.phone, h.hospital_type
            FROM hospitals h
            JOIN documents d ON h.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            ORDER BY c.code, h.city, h.name_vi
        """,
        "glossary_terms": """
            SELECT g.id, c.code AS company, d.document_name,
                   g.term, g.definition
            FROM glossary_terms g
            JOIN documents d ON g.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            ORDER BY c.code, g.term
        """,
        "waiting_periods": """
            SELECT w.id, c.code AS company, d.document_name,
                   w.condition_group, w.condition_detail,
                   w.waiting_days, w.waiting_text
            FROM waiting_periods w
            JOIN documents d ON w.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            ORDER BY c.code, w.condition_group
        """,
        "claim_payouts": """
            SELECT cp.id, c.code AS company, d.document_name,
                   cp.event, cp.payout_rate, cp.payout_text
            FROM claim_payouts cp
            JOIN documents d ON cp.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            ORDER BY c.code, cp.event
        """,
        "short_term_premiums": """
            SELECT stp.id, c.code AS company, d.document_name,
                   stp.duration_text, stp.duration_days, stp.premium_rate
            FROM short_term_premiums stp
            JOIN documents d ON stp.document_id = d.id
            JOIN companies c ON d.company_id = c.id
            ORDER BY c.code
        """,
    }

    print("\n📊 Exporting review CSVs...")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        for table_name, query in queries.items():
            cur.execute(query)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

            csv_path = out_dir / f"{table_name}.csv"
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)

            print(f"  📄 {table_name}.csv — {len(rows)} rows")
    finally:
        cur.close()
        conn.close()

    print(f"\n✅ CSVs exported to: {out_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    DRY_RUN = args.dry_run
    ingest_all()
