"""LLM-based schema mapping for insurance data.

Strategy:
  1. Collect unique key-sets from JSON files (321 unique from 644 files)
  2. For each unique key-set, pick a representative file with sample data
  3. Send keys + sample rows + compact DB schema to LLM
  4. LLM returns: target table, key-to-column mapping, plan identification
  5. Save results as JSON (for ingestion) + CSV (for human review)
  6. Uses 10 API keys in parallel (ThreadPoolExecutor + Queue)
"""

import csv
import hashlib
import json
import os
import queue
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

# --- CẤU HÌNH ---
DATA_DIR = Path(
    "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance"
    "/health_insurance_extracted_good_content"
)
OUTPUT_DIR = DATA_DIR / "schema_mapping_results"
CACHE_FILE = OUTPUT_DIR / "schema_mapping.json"
REVIEW_CSV = OUTPUT_DIR / "schema_mapping_review.csv"

COMPANY_MAP: dict[str, str] = {
    "aia.com.vn": "aia",
    "pacific_cross_all_pdfs": "pacific_cross",
    "bic.vn": "bic",
    "libertyinsurance.com.vn": "liberty",
    "baominh.com.vn": "baominh",
    "pti.com.vn": "pti",
}

# Allowed target tables (LLM must pick one of these)
VALID_TABLES = [
    "benefit_items",
    "premium_entries",
    "hospitals",
    "glossary_terms",
    "waiting_periods",
    "claim_payouts",
    "short_term_premiums",
]

# Compact schema to include in prompt (no indexes, no seed data)
COMPACT_SCHEMA = """
DATABASE TABLES (PostgreSQL):

1. source_tables — Mỗi file JSON = 1 row (đã tự tạo, không cần mapping)
   Columns: id, document_id, file_path, table_type, raw_json, keys[], content_type, description

2. plan_types — Mapping plan name → normalized code (auto-created)
   Columns: id, company_id, document_id, raw_name VARCHAR(200), normalized_code VARCHAR(50), plan_level INT

3. benefit_items — Mỗi hàng quyền lợi BH
   Columns: id, source_table_id, document_id, category_id, row_index, raw_row JSONB,
            raw_name VARCHAR(500), normalized_name, applicable_to TEXT, note TEXT
   → Mỗi benefit_item có NHIỀU benefit_values (1 per plan)

4. benefit_values — Giá trị quyền lợi THEO TỪNG PLAN (long format)
   Columns: id, benefit_item_id, plan_type_id, value TEXT, value_numeric NUMERIC,
            value_context VARCHAR(100), limit_type VARCHAR(50), unit VARCHAR(100), is_covered BOOLEAN, note TEXT

5. premium_entries — Phí BH theo tuổi/plan
   Columns: id, source_table_id, document_id, plan_type_id, row_index, raw_row JSONB,
            age_min INT, age_max INT, age_label VARCHAR(50), premium_amount NUMERIC,
            currency VARCHAR(10), period VARCHAR(20), year_label VARCHAR(20)

6. hospitals — Danh sách bệnh viện
   Columns: id, source_table_id, document_id, row_index, raw_row JSONB,
            name_vi VARCHAR(300), name_en VARCHAR(300), address TEXT, city TEXT,
            country VARCHAR(100), phone VARCHAR(100), hospital_type VARCHAR(100),
            gop_supported BOOLEAN, gop_time VARCHAR(100), working_hours VARCHAR(200),
            external_id VARCHAR(50), note TEXT

7. glossary_terms — Thuật ngữ
   Columns: id, source_table_id, document_id, row_index, raw_row JSONB,
            term VARCHAR(300), definition TEXT

8. waiting_periods — Thời gian chờ
   Columns: id, source_table_id, document_id, row_index, raw_row JSONB,
            condition_group VARCHAR(200), condition_detail TEXT,
            waiting_days INT, waiting_text VARCHAR(200)

9. claim_payouts — Tỷ lệ chi trả
   Columns: id, source_table_id, document_id, row_index, raw_row JSONB,
            event VARCHAR(300), payout_rate NUMERIC, payout_text VARCHAR(200)

10. short_term_premiums — Phí ngắn hạn
    Columns: id, source_table_id, document_id, row_index, raw_row JSONB,
             duration_text VARCHAR(200), duration_days INT, premium_rate NUMERIC

11. benefit_categories (reference only):
    Existing codes: inpatient, outpatient, emergency, maternity, dental, cancer,
                    mental_health, accident, life, day_treatment
""".strip()


# ============================================================
# LLM API (reused from 10_classify_with_llm.py)
# ============================================================


def load_api_keys() -> list[dict]:
    """Load API keys from .env file."""
    env_path = Path("/home/quangnhvn34/dev/me/InsureVN/.env")
    if not env_path.exists():
        print("❌ Không tìm thấy file .env")
        return []

    keys: list[dict] = []
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
            else:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    k, v = parts
                else:
                    continue
            k = k.strip().upper()
            v = v.strip()
            if not v:
                continue

            if k.startswith("NVIDIA_NIM_API") or k.startswith("NVIDIA_PAI_KEY"):
                keys.append({
                    "provider": "NVIDIA",
                    "key": v,
                    "model": "google/gemma-3-27b-it",
                    "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
                    "timeout": 1180.0,
                })
            elif k.startswith("OLLAMA_API_KEY"):
                ollama_url = (
                    os.environ.get("OLLAMA_API_URL", "https://ollama.com")
                    + "/api/generate"
                )
                keys.append({
                    "provider": "OLLAMA",
                    "key": v,
                    "model": "gemma4:31b-cloud",
                    "endpoint": ollama_url,
                    "timeout": 1180.0,
                })
    print(f"✅ Loaded {len(keys)} API keys")
    return keys


def call_llm(api_config: dict, prompt: str) -> str:
    """Call LLM API and return text response."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_config['key']}",
        "Accept": "application/json",
    }
    timeout = api_config.get("timeout", 180.0)

    if api_config["provider"] == "OLLAMA":
        data = {
            "model": api_config["model"],
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0},
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(api_config["endpoint"], headers=headers, json=data)
            resp.raise_for_status()
            return resp.json().get("response", "")
    else:
        data = {
            "model": api_config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(api_config["endpoint"], headers=headers, json=data)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


def clean_json_response(text: str) -> str:
    """Clean LLM response to extract JSON."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


# ============================================================
# Key extraction (reused)
# ============================================================


def normalize_key(key: str) -> str:
    """Normalize key for consistent comparison."""
    key = unicodedata.normalize("NFC", key)
    key = key.strip()
    key = re.sub(r"\s+", " ", key)
    return key


def extract_keys_and_sample(data: dict) -> tuple[list[str], list[dict]]:
    """Extract keys and first 2 sample rows from structured_data."""
    structured = data.get("structured_data")
    if structured is None:
        return [], []

    keys: set[str] = set()
    sample_rows: list[dict] = []

    if isinstance(structured, list):
        for i, row in enumerate(structured):
            if isinstance(row, dict):
                keys.update(row.keys())
                if i < 2:
                    sample_rows.append(row)
    elif isinstance(structured, dict):
        keys.update(structured.keys())
        sample_rows.append(structured)

    sorted_keys = sorted(normalize_key(k) for k in keys if k.strip())
    return sorted_keys, sample_rows


def keyset_hash(keys: list[str]) -> str:
    """Generate a short hash for a key-set."""
    joined = " | ".join(sorted(keys))
    return hashlib.md5(joined.encode()).hexdigest()[:12]


def keyset_id(keys: list[str]) -> str:
    """Generate a stable string ID for a key-set."""
    return " | ".join(sorted(keys))


# ============================================================
# Prompt building
# ============================================================


def build_mapping_prompt(
    keys: list[str],
    sample_rows: list[dict],
    file_path: str,
    description: str,
) -> str:
    """Build prompt for LLM to map keys to DB columns."""
    sample_text = json.dumps(sample_rows, ensure_ascii=False, indent=2)
    # Truncate sample if too long
    if len(sample_text) > 2000:
        sample_text = sample_text[:2000] + "\n... (truncated)"

    return f"""You are a data engineer mapping Vietnamese insurance document data to a PostgreSQL database.

{COMPACT_SCHEMA}

TASK:
Given the JSON data below extracted from an insurance document, determine:
1. Which domain table (target_table) this data belongs to
2. How each key maps to a database column

SOURCE FILE: {file_path}
DESCRIPTION: {description}

KEYS in structured_data: {json.dumps(keys, ensure_ascii=False)}

SAMPLE DATA (first 2 rows):
{sample_text}

RULES:
- target_table MUST be one of: {', '.join(VALID_TABLES)}

PLAN LEVEL RULES (CRITICAL — each plan MUST have a UNIQUE level, no duplicates):
  For AIA products:
    Cơ bản / CƠ BẢN       → basic,    plan_level=1
    Nâng cao / NÂNG CAO    → standard, plan_level=2
    Toàn diện / TOÀN DIỆN  → advanced, plan_level=3
    Hoàn hảo / HOÀN HẢO   → premium,  plan_level=4
  For generic columns:
    Mức 1 / Gói 1 / Cột 1 → basic(1), Mức 2 / Gói 2 / Cột 2 → standard(2),
    Mức 3 / Gói 3 / Cột 3 → advanced(3), Mức 4 / Gói 4 / Cột 4 → premium(4)
  For AIA Vitality tiers:
    Đồng → basic(1), Bạc → standard(2), Vàng → advanced(3), Bạch kim/Bạch Kim → premium(4)
  For year-based premiums (PHÍ NĂM 1, PHÍ NĂM 2...):
    Use plan_normalized_code = "year_1", "year_2", etc. with plan_level = 1, 2, 3...
  NEVER assign the same plan_level to two different plan columns.

ROW LABEL RULES:
  - Every benefit_items/premium_entries mapping MUST have exactly ONE key with role "row_label"
  - Typical row label keys: "Quyền lợi bảo hiểm", "Hạng mục", "Nội dung", "Quyền lợi", "Điều trị ung thư"
  - If "Nội dung" exists, it is ALWAYS the row_label (column="raw_name"), never "direct_column"

OTHER ROLES:
  - "direct_column": maps directly to a DB column
  - "metadata": extra info (e.g. "Tần suất" → note, "Áp dụng cho" → applicable_to, "Đơn vị" → unit)
  - "ignore": skip this key (including empty string keys "")
  - description field: provide a brief Vietnamese summary of what this data contains

OUTPUT FORMAT (JSON only, no markdown, no commentary):
{{
  "target_table": "<table_name>",
  "description": "<brief Vietnamese description of the data>",
  "key_roles": {{
    "<key_name>": {{
      "role": "row_label" | "plan_value" | "direct_column" | "metadata" | "ignore",
      "column": "<column_name_in_target_table>",
      "plan_normalized_code": "<code>",
      "plan_level": <int>
    }}
  }}
}}

Only include "column" for row_label, direct_column, metadata roles.
Only include "plan_normalized_code" and "plan_level" for plan_value role.
"""


# ============================================================
# Collect unique key-sets
# ============================================================


def collect_unique_keysets(
    base_dir: Path,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[Path]],
    dict[str, list[dict]],
    dict[str, str],
]:
    """Collect unique key-sets with sample data.

    Returns:
        keyset_map: {keyset_id: [keys]}
        files_map: {keyset_id: [file_paths]}
        samples_map: {keyset_id: [sample_rows]}
        desc_map: {keyset_id: description}
    """
    json_files = [
        f
        for f in sorted(base_dir.rglob("*.json"))
        if "classification_output" not in str(f)
    ]

    keyset_map: dict[str, list[str]] = {}
    files_map: dict[str, list[Path]] = {}
    samples_map: dict[str, list[dict]] = {}
    desc_map: dict[str, str] = {}

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        keys, sample_rows = extract_keys_and_sample(data)
        if not keys:
            continue

        kid = keyset_id(keys)
        if kid not in keyset_map:
            keyset_map[kid] = keys
            files_map[kid] = []
            samples_map[kid] = sample_rows
            desc_map[kid] = data.get("description", "")
        files_map[kid].append(fp)

    return keyset_map, files_map, samples_map, desc_map


# ============================================================
# Parallel LLM processing
# ============================================================


def process_keyset(
    kid: str,
    keys: list[str],
    sample_rows: list[dict],
    description: str,
    sample_file: str,
    idx: int,
    total: int,
    worker_queue: queue.Queue,
    cache: dict,
    cache_lock: threading.Lock,
) -> None:
    """Process a single key-set mapping using an available API worker."""
    prompt = build_mapping_prompt(keys, sample_rows, sample_file, description)

    for attempt in range(3):
        api_config = worker_queue.get()
        worker_id = f"{api_config['provider']}-{api_config['key'][:8]}..."

        try:
            print(
                f"  📡 [{idx}/{total}] hash={keyset_hash(keys)} "
                f"(attempt {attempt + 1}, worker={worker_id})"
            )

            raw = call_llm(api_config, prompt)
            clean = clean_json_response(raw)
            result = json.loads(clean)

            # Validate target_table
            target = result.get("target_table", "")
            if target not in VALID_TABLES:
                print(
                    f"    ⚠️ Invalid target_table '{target}', "
                    f"defaulting to benefit_items"
                )
                result["target_table"] = "benefit_items"

            with cache_lock:
                cache[kid] = result
                # Save after each success
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)

            worker_queue.put(api_config)
            print(
                f"  ✅ [{idx}/{total}] → {result['target_table']} "
                f"({len(result.get('key_roles', {}))} keys mapped)"
            )
            return

        except Exception as e:
            worker_queue.put(api_config)
            print(
                f"    ⚠️ [{idx}/{total}] attempt {attempt + 1} "
                f"failed with {worker_id}: {e}"
            )
            if attempt < 2:
                time.sleep(2)
            else:
                print(
                    f"    ❌ [{idx}/{total}] FAILED after 3 attempts. "
                    f"Will retry on next run."
                )


def run_mapping(
    keyset_map: dict[str, list[str]],
    files_map: dict[str, list[Path]],
    samples_map: dict[str, list[dict]],
    desc_map: dict[str, str],
    api_keys: list[dict],
) -> dict[str, dict]:
    """Run LLM schema mapping for all unique key-sets."""
    # Load cache
    cache: dict[str, dict] = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            print(f"📦 Loaded {len(cache)} cached schema mappings")
        except Exception:
            print("⚠️ Cache file corrupted, starting fresh.")

    # Find uncached
    to_process = {
        kid: keys for kid, keys in keyset_map.items() if kid not in cache
    }

    skipped = len(keyset_map) - len(to_process)
    if skipped > 0:
        print(f"⏩ Skipping {skipped} key-sets already present in cache.")

    if not to_process:
        print("✅ All key-sets already mapped (from cache)")
        return cache

    print(f"🔄 {len(to_process)} key-sets to map via LLM (Parallel Mode)")

    # Setup workers
    worker_queue: queue.Queue = queue.Queue()
    for key in api_keys:
        worker_queue.put(key)

    cache_lock = threading.Lock()
    total = len(to_process)
    num_threads = min(len(api_keys), total)

    print(f"🚀 Processing with {num_threads} parallel workers...")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for i, (kid, keys) in enumerate(to_process.items()):
            sample_file = str(
                files_map[kid][0].relative_to(DATA_DIR)
            ) if files_map[kid] else "unknown"

            futures.append(
                executor.submit(
                    process_keyset,
                    kid,
                    keys,
                    samples_map.get(kid, []),
                    desc_map.get(kid, ""),
                    sample_file,
                    i + 1,
                    total,
                    worker_queue,
                    cache,
                    cache_lock,
                )
            )

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"🔴 Fatal thread error: {e}")

    # Final save
    with cache_lock:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    return cache


# ============================================================
# Generate review outputs
# ============================================================


def generate_review_csv(
    cache: dict[str, dict],
    files_map: dict[str, list[Path]],
    base_dir: Path,
) -> None:
    """Generate CSV for human review of schema mappings."""
    rows: list[dict] = []

    for kid, mapping in cache.items():
        target_table = mapping.get("target_table", "unknown")
        description = mapping.get("description", "")
        key_roles = mapping.get("key_roles", {})
        num_files = len(files_map.get(kid, []))
        sample_file = ""
        if files_map.get(kid):
            sample_file = str(files_map[kid][0].relative_to(base_dir))

        for key_name, role_info in key_roles.items():
            rows.append({
                "keyset_hash": keyset_hash(kid.split(" | ")),
                "target_table": target_table,
                "description": description,
                "key_name": key_name,
                "role": role_info.get("role", ""),
                "column": role_info.get("column", ""),
                "plan_code": role_info.get("plan_normalized_code", ""),
                "plan_level": role_info.get("plan_level", ""),
                "num_files": num_files,
                "sample_file": sample_file,
            })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "keyset_hash",
                "target_table",
                "description",
                "key_name",
                "role",
                "column",
                "plan_code",
                "plan_level",
                "num_files",
                "sample_file",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"📊 Review CSV: file://{REVIEW_CSV.absolute()} ({len(rows)} rows)")


def print_summary(
    cache: dict[str, dict],
    files_map: dict[str, list[Path]],
) -> None:
    """Print summary statistics."""
    from collections import Counter

    table_counts: Counter = Counter()
    total_files = 0

    for kid, mapping in cache.items():
        table = mapping.get("target_table", "unknown")
        n_files = len(files_map.get(kid, []))
        table_counts[table] += n_files
        total_files += n_files

    print(f"\n{'=' * 60}")
    print("📊 SCHEMA MAPPING SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Unique key-sets mapped: {len(cache)}")
    print(f"  Total files covered:    {total_files}")
    print("\n  Files per target table:")
    for table, count in table_counts.most_common():
        pct = count / total_files * 100 if total_files else 0
        print(f"    {table:25s} {count:4d}  ({pct:5.1f}%)")

    print(f"\n✅ Master JSON: file://{CACHE_FILE.absolute()}")
    print(f"📊 Review CSV:  file://{REVIEW_CSV.absolute()}")


# ============================================================
# Main
# ============================================================


def main() -> None:
    """Run LLM schema mapping pipeline."""
    if not DATA_DIR.exists():
        print(f"❌ Thư mục không tồn tại: {DATA_DIR}")
        sys.exit(1)

    # 1. Load API keys
    api_keys = load_api_keys()
    if not api_keys:
        print("❌ Không có API key. Dừng.")
        sys.exit(1)

    # 2. Collect unique key-sets with sample data
    print("📂 Collecting unique key-sets with sample data...")
    keyset_map, files_map, samples_map, desc_map = collect_unique_keysets(DATA_DIR)
    total_files = sum(len(v) for v in files_map.values())
    print(
        f"   Found {len(keyset_map)} unique key-sets "
        f"from {total_files} files"
    )

    # 3. Run LLM mapping (parallel, with caching)
    cache = run_mapping(keyset_map, files_map, samples_map, desc_map, api_keys)

    # 4. Generate review outputs
    print("\n📋 Generating review outputs...")
    generate_review_csv(cache, files_map, DATA_DIR)
    print_summary(cache, files_map)


if __name__ == "__main__":
    main()
