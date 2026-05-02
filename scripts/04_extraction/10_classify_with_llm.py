"""Classify extracted JSON key-sets using LLM.

Strategy:
  1. Extract all UNIQUE key-sets from 644 JSON files (→ ~321 unique)
  2. Batch them and send to LLM for classification
  3. LLM returns category for each key-set
  4. Save mapping → apply to all files

Only ~321 unique key-sets → ~16 API calls at 20/batch. Very efficient.
"""

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import httpx

# --- CẤU HÌNH ---
DATA_DIR = Path(
    "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance"
    "/health_insurance_extracted_good_content"
)
OUTPUT_DIR = DATA_DIR / "classification_output"
CACHE_FILE = OUTPUT_DIR / "llm_keyset_mapping.json"
BATCH_SIZE = 10  # key-sets per LLM call

COMPANY_MAP: dict[str, str] = {
    "aia.com.vn": "aia",
    "pacific_cross_all_pdfs": "pacific_cross",
    "bic.vn": "bic",
    "libertyinsurance.com.vn": "liberty",
    "baominh.com.vn": "baominh",
    "pti.com.vn": "pti",
}

CATEGORIES = [
    "benefit_table",       # Bảng quyền lợi BH theo plan (Cơ bản/Nâng cao/...)
    "benefit_detail",      # Chi tiết quyền lợi (không có plan columns)
    "premium_table",       # Bảng phí BH theo tuổi/plan
    "hospital_network",    # Danh sách bệnh viện / cơ sở y tế
    "glossary",            # Thuật ngữ / định nghĩa
    "waiting_period",      # Thời gian chờ
    "claim_payout",        # Tỷ lệ chi trả / sự kiện BH
    "short_term_premium",  # Phí ngắn hạn / hoàn phí
    "vitality_tier",       # AIA Vitality tier (Bạc/Vàng/Bạch Kim)
    "misc",                # Không thuộc nhóm nào ở trên (app screenshots, etc.)
]


# ============================================================
# LLM API
# ============================================================


def load_api_keys() -> list[dict]:
    """Load API keys from .env file, same as extraction script."""
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
                    "timeout": 180.0,
                })
            elif k.startswith("OLLAMA_API_KEY"):
                ollama_url = os.environ.get("OLLAMA_API_URL", "https://ollama.com") + "/api/generate"
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
        "Accept": "application/json"
    }
    
    timeout = api_config.get("timeout", 180.0)

    if api_config["provider"] == "OLLAMA":
        data = {
            "model": api_config["model"],
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(api_config["endpoint"], headers=headers, json=data)
            resp.raise_for_status()
            return resp.json().get("response", "")
    else: # NVIDIA (OpenAI compatible)
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


def build_classification_prompt(batch: list[tuple[str, list[str]]]) -> str:
    """Build prompt for classifying a batch of key-sets."""
    categories_desc = """
Categories (pick exactly one per item):
- benefit_table: Bảng quyền lợi bảo hiểm THEO PLAN (có cột plan: Cơ bản, Nâng cao, Toàn diện, Hoàn hảo, HF1/HF2/HF3, Plan H1/H2/H3, Mức 1/2/3/4, Gói 1/2/3/4, Cột 1/2/3/4, etc.)
- benefit_detail: Chi tiết quyền lợi BH nhưng KHÔNG có cột plan (Mức chi trả, Nội dung, Quyền lợi BH, Cơ sở bồi thường, etc.)
- premium_table: Bảng PHÍ bảo hiểm theo tuổi/plan (Tuổi, Phí bảo hiểm, Age, Premium, PHÍ NĂM 1/2/3, etc.)
- hospital_network: Danh sách bệnh viện / cơ sở y tế (Hospital, Address, Phone, Tên cơ sở y tế, Điện thoại, etc.)
- glossary: Thuật ngữ + Định nghĩa
- waiting_period: Thời gian chờ + Nhóm bệnh
- claim_payout: Tỷ lệ chi trả / Sự kiện bảo hiểm / Thương tật
- short_term_premium: Phí ngắn hạn / Khoảng thời gian trước khi hủy bỏ
- vitality_tier: AIA Vitality tier table (Bạc, Vàng, Bạch Kim, Đồng)
- misc: Không thuộc nhóm nào (app screenshots, misc info, navigation guides, etc.)
"""
    items_text = ""
    for idx, (key_id, keys) in enumerate(batch):
        items_text += f"\n{idx}. ID={key_id}\n   Keys: {json.dumps(keys, ensure_ascii=False)}\n"

    return f"""You are classifying Vietnamese insurance document tables based on their column keys.

{categories_desc}

For each item below, return a JSON array where each element is:
{{"id": "<key_id>", "category": "<category_name>", "reason": "<brief reason in Vietnamese>"}}

Return ONLY the JSON array, no markdown blocks, no commentary.

Items to classify:
{items_text}
"""


def clean_json_response(text: str) -> str:
    """Clean LLM response to extract JSON."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


# ============================================================
# Key extraction
# ============================================================


def normalize_key(key: str) -> str:
    """Normalize key for consistent comparison."""
    key = unicodedata.normalize("NFC", key)
    key = key.strip()
    key = re.sub(r"\s+", " ", key)
    return key


def extract_keys(data: dict) -> list[str]:
    """Extract structured_data keys. Handles both list and dict."""
    structured = data.get("structured_data")
    if structured is None:
        return []
    keys: set[str] = set()
    if isinstance(structured, list):
        for row in structured:
            if isinstance(row, dict):
                keys.update(row.keys())
    elif isinstance(structured, dict):
        keys.update(structured.keys())
    return sorted(normalize_key(k) for k in keys if k.strip())


def keyset_id(keys: list[str]) -> str:
    """Generate a stable ID for a key-set (sorted, joined)."""
    return " | ".join(sorted(keys))


def parse_page_table_index(filename: str) -> tuple[int | None, int | None]:
    """Extract page_number and table_index from filename."""
    match = re.match(r"(?:table|picture)_p(\d+)_n(\d+)", filename)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


# ============================================================
# Main pipeline
# ============================================================


def collect_unique_keysets(
    base_dir: Path,
) -> tuple[dict[str, list[str]], dict[str, list[Path]]]:
    """Collect all unique key-sets and map them to files.

    Returns:
        keyset_map: {keyset_id: [keys]}
        files_map: {keyset_id: [file_paths]}
    """
    json_files = [
        f
        for f in sorted(base_dir.rglob("*.json"))
        if "classification_output" not in str(f)
    ]

    keyset_map: dict[str, list[str]] = {}
    files_map: dict[str, list[Path]] = {}

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        keys = extract_keys(data)
        if not keys:
            continue

        kid = keyset_id(keys)
        if kid not in keyset_map:
            keyset_map[kid] = keys
            files_map[kid] = []
        files_map[kid].append(fp)

    return keyset_map, files_map


import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# Parallel processing helpers
# ============================================================

def process_batch_parallel(
    batch: list[tuple[str, list[str]]],
    batch_num: int,
    total_batches: int,
    worker_queue: queue.Queue,
    cache: dict,
    cache_lock: threading.Lock,
) -> None:
    """Process a single batch using an available API worker."""
    prompt = build_classification_prompt(batch)
    
    # Try up to 3 times, potentially with different workers
    for attempt in range(3):
        # Get a worker from the queue (wait if necessary)
        api_config = worker_queue.get()
        worker_id = f"{api_config['provider']}-{api_config['key'][:8]}..."
        
        try:
            print(f"  📡 Batch {batch_num}/{total_batches} (Attempt {attempt+1}, worker={worker_id})")
            
            raw = call_llm(api_config, prompt)
            clean = clean_json_response(raw)
            results = json.loads(clean)

            with cache_lock:
                for item in results:
                    kid = item["id"]
                    cat = item["category"]
                    reason = item.get("reason", "")
                    if cat not in CATEGORIES:
                        cat = "misc"
                    cache[kid] = {"category": cat, "reason": reason}

                # Save cache after each successful batch
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
            
            # Return worker to queue
            worker_queue.put(api_config)
            print(f"  ✅ Batch {batch_num}/{total_batches} success.")
            return # Success!

        except Exception as e:
            # Return worker to queue even on failure
            worker_queue.put(api_config)
            print(f"    ⚠️ Batch {batch_num} attempt {attempt+1} failed with {worker_id}: {e}")
            if attempt < 2:
                time.sleep(2)
            else:
                print(f"    ❌ Batch {batch_num} FAILED after 3 attempts. Will retry on next run.")

def classify_with_llm(
    keyset_map: dict[str, list[str]],
    api_keys: list[dict],
) -> dict[str, dict]:
    """Classify all key-sets using LLM in parallel batches."""
    # Load cache
    cache: dict[str, dict] = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            print(f"📦 Loaded {len(cache)} cached classifications")
        except Exception:
            print("⚠️ Cache file corrupted, starting fresh.")

    # Find uncached
    to_classify = {
        kid: keys
        for kid, keys in keyset_map.items()
        if kid not in cache
    }

    if not to_classify:
        print("✅ All key-sets already classified (from cache)")
        return cache

    print(f"🔄 {len(to_classify)} key-sets to classify via LLM (Parallel Mode)")

    # Prepare batches
    items = list(to_classify.items())
    batches = []
    for i in range(0, len(items), BATCH_SIZE):
        batches.append(items[i : i + BATCH_SIZE])

    # Setup workers and locks
    worker_queue = queue.Queue()
    for key in api_keys:
        worker_queue.put(key)
    
    cache_lock = threading.Lock()
    total_batches = len(batches)
    num_threads = min(len(api_keys), total_batches)

    print(f"🚀 Processing with {num_threads} parallel workers...")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for i, batch in enumerate(batches):
            futures.append(
                executor.submit(
                    process_batch_parallel,
                    batch, i + 1, total_batches,
                    worker_queue, cache, cache_lock
                )
            )
        
        # Wait for all to complete
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


def apply_classification(
    base_dir: Path,
    keyset_map: dict[str, list[str]],
    files_map: dict[str, list[Path]],
    classification: dict[str, dict],
) -> None:
    """Apply LLM classification to all files and output results."""
    from collections import Counter, defaultdict

    all_results: list[dict] = []
    category_counts: Counter = Counter()
    category_files: dict[str, list[str]] = defaultdict(list)
    errors: list[dict] = []

    # Process all JSON files (including ones without structured_data)
    json_files = [
        f
        for f in sorted(base_dir.rglob("*.json"))
        if "classification_output" not in str(f)
    ]

    for fp in json_files:
        rel_path = str(fp.relative_to(base_dir))

        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append({"file_path": rel_path, "error": str(e)})
            continue

        keys = extract_keys(data)
        if not keys:
            reason = (
                "no_structured_data"
                if "structured_data" not in data
                else "empty_keys"
            )
            errors.append({"file_path": rel_path, "error": reason})
            continue

        kid = keyset_id(keys)
        clf = classification.get(kid, {"category": "misc", "reason": "not_in_cache"})

        # Extract metadata
        rel = fp.relative_to(base_dir)
        top_dir = rel.parts[0]
        company_code = COMPANY_MAP.get(top_dir, "unknown")
        doc_name = rel.parts[1] if len(rel.parts) >= 2 else rel.stem
        page_num, table_idx = parse_page_table_index(fp.name)

        result = {
            "file_path": rel_path,
            "company_code": company_code,
            "document_name": doc_name,
            "page_number": page_num,
            "table_index": table_idx,
            "keys": keys,
            "table_type": clf["category"],
            "classification_reason": clf["reason"],
            "classification_method": "llm",
            "content_type": data.get("content_type", "unknown"),
            "has_content": data.get("has_content", False),
        }
        all_results.append(result)
        category_counts[clf["category"]] += 1
        category_files[clf["category"]].append(rel_path)

    # --- Output ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Full results
    out = OUTPUT_DIR / "classification_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 2. Audit log
    if errors:
        audit = OUTPUT_DIR / "classification_audit.json"
        with open(audit, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    # 3. Per-category files
    for cat, files in sorted(category_files.items()):
        with open(OUTPUT_DIR / f"category_{cat}.json", "w", encoding="utf-8") as f:
            json.dump(files, f, ensure_ascii=False, indent=2)

    # 4. Summary
    summary = {
        "total_files": len(json_files),
        "classified": len(all_results),
        "errors": len(errors),
        "unique_keysets": len(keyset_map),
        "classification_method": "llm",
        "category_distribution": dict(category_counts.most_common()),
    }
    with open(OUTPUT_DIR / "classification_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Print
    total = len(all_results)
    print(f"\n{'='*60}")
    print("📊 CLASSIFICATION SUMMARY (LLM)")
    print(f"{'='*60}")
    print(f"  Total files:    {len(json_files)}")
    print(f"  Classified:     {total}")
    print(f"  Errors/Skip:    {len(errors)}")
    print(f"  Unique keysets: {len(keyset_map)}")
    print("\n  Category distribution:")
    for cat, count in category_counts.most_common():
        pct = count / total * 100 if total else 0
        print(f"    {cat:25s} {count:4d}  ({pct:5.1f}%)")

    print(f"\n✅ Results: file://{out.absolute()}")


def main() -> None:
    """Run LLM-based classification pipeline."""
    base_dir = DATA_DIR
    if not base_dir.exists():
        print(f"❌ Thư mục không tồn tại: {base_dir}")
        sys.exit(1)

    # 1. Load API keys
    api_keys = load_api_keys()
    if not api_keys:
        print("❌ Không có API key. Dừng.")
        sys.exit(1)

    # 2. Collect unique key-sets
    print("📂 Collecting unique key-sets...")
    keyset_map, files_map = collect_unique_keysets(base_dir)
    print(f"   Found {len(keyset_map)} unique key-sets from {sum(len(v) for v in files_map.values())} files")

    # 3. Classify via LLM (with caching)
    classification = classify_with_llm(keyset_map, api_keys)

    # 4. Apply to all files
    print("\n📋 Applying classification to all files...")
    apply_classification(base_dir, keyset_map, files_map, classification)


if __name__ == "__main__":
    main()
