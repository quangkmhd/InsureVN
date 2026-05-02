"""Classify extracted JSON source tables into domain categories.

Step 1 of the ETL pipeline: reads all JSON files, extracts keys from
structured_data, and classifies each file into a table_type using
rule-based matching. Outputs classification results + error audit log.

Categories:
    - benefit_table:       Bảng quyền lợi bảo hiểm theo plan
    - benefit_detail:      Chi tiết quyền lợi (không có plan columns)
    - premium_table:       Bảng phí bảo hiểm theo tuổi/plan
    - hospital_network:    Danh sách cơ sở y tế / bệnh viện
    - glossary:            Thuật ngữ / định nghĩa
    - waiting_period:      Thời gian chờ
    - claim_payout:        Tỷ lệ chi trả / sự kiện bảo hiểm
    - short_term_premium:  Phí ngắn hạn / hoàn phí
    - vitality_tier:       Bảng AIA Vitality (Bạc/Vàng/Bạch Kim)
    - unclassified:        Không xác định được category
"""

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# --- CẤU HÌNH ---
DATA_DIR = Path(
    "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance"
    "/health_insurance_extracted_good_content"
)
OUTPUT_DIR = DATA_DIR / "classification_output"

# Company code → source directory mapping (exhaustive)
COMPANY_MAP: dict[str, str] = {
    "aia.com.vn": "aia",
    "pacific_cross_all_pdfs": "pacific_cross",
    "bic.vn": "bic",
    "libertyinsurance.com.vn": "liberty",
    "baominh.com.vn": "baominh",
    "pti.com.vn": "pti",
}

# ============================================================
# Key normalization
# ============================================================


def normalize_key(key: str) -> str:
    """Normalize a key for comparison.

    - NFC unicode normalization
    - lowercase
    - collapse multiple whitespace to single space
    - strip leading/trailing whitespace
    """
    key = unicodedata.normalize("NFC", key)
    key = key.lower().strip()
    key = re.sub(r"\s+", " ", key)
    return key


# ============================================================
# Classification rules — order matters (first match wins)
# ============================================================

# Keys that indicate hospital/provider listings (Vietnamese)
_HOSPITAL_KEYS_VI = {
    "tên cơ sở y tế",
    "tên cơ sở",
    "điện thoại",
    "tỉnh thành",
    "thời gian làm việc",
    "gop time",
}

# Keys that indicate hospital (English)
_HOSPITAL_KEYS_EN = {
    "hospital",
    "hospital/clinic",
    "hospital name",
    "provider",
    "provider name",
    "facility",
    "facility name",
    "name (en)",
    "phone",
    "address",
    "province/city",
    "gop service",
    "gop time",
    "type of hospital",
    "medical facility name",
    "id",
    "country",
    "city",
    "state",
    "region",
    "city/suburb",
    "au/nz",
    "aus/nz",
    "location/address",
}

# Hospital name keys — require pairing with location/contact keys
_HOSPITAL_NAME_KEYS = {
    "hospital",
    "hospital/clinic",
    "hospital name",
    "provider",
    "provider name",
    "facility",
    "facility name",
    "name (en)",
    "tên cơ sở y tế",
    "tên cơ sở",
    "tên",
}
_HOSPITAL_LOCATION_KEYS = {
    "address",
    "city",
    "country",
    "id",
    "phone",
    "địa chỉ",
    "điện thoại",
    "quốc gia",
}

# BaoMinh hospital: 'Tên cơ sở', 'Địa chỉ', 'Ghi chú'
_HOSPITAL_KEYS_VI_ALT = {"tên cơ sở", "địa chỉ", "ghi chú"}

# Plan-level column keys (indicate benefit_table)
_PLAN_KEYS = {
    # AIA Vietnamese
    "cơ bản",
    "nâng cao",
    "toàn diện",
    "hoàn hảo",
    "hoàn hảo",
    # AIA brochure variants (Gói / Mức)
    "gói 1",
    "gói 2",
    "gói 3",
    "gói 4",
    "mức 1",
    "mức 2",
    "mức 3",
    "mức 4",
    "mức áp dụng 1",
    "mức áp dụng 2",
    "mức áp dụng 3",
    "mức áp dụng 4",
    "cột 1",
    "cột 2",
    "cột 3",
    "cột 4",
    # Pacific Cross
    "hf1",
    "hf2",
    "hf3",
    # Liberty
    "plan classic h1",
    "plan executive h2",
    "plan premier h3",
    "plan h1 classic",
    "plan h2 executive",
    "plan h3 premier",
    "chương trình classic h1",
    "chương trình executive h2",
    "chương trình premier h3",
    # Bao Minh
    "chương trình 1",
    "chương trình 2",
    "chương trình 3",
    "chương trình 4",
    "chương trình cơ bản",
    "chương trình hoàn hảo",
    "chương trình nâng cao",
    "chương trình toàn diện",
}

# Premium/pricing keys
_PREMIUM_KEYS = {
    "tuổi hiện tại của nđbh",
    "tuổi bảo hiểm",
    "phí bảo hiểm",
    "phí năm 1",
    "phí năm 2",
    "phí năm 3",
    "phí năm 4",
    "phí năm 5",
    "premium",
    "ages (last birthday)",
    "age (last birthday)",
    "phí bảo hiểm/người/năm",
}

# Glossary
_GLOSSARY_KEYS = {"thuật ngữ", "định nghĩa"}

# Waiting period
_WAITING_KEYS = {
    "thời gian chờ",
    "thời gian chờ 1",
    "thời gian chờ 2",
    "nhóm bệnh",
}

# Claim payout rates
_PAYOUT_KEYS = {
    "tỷ lệ chi trả",
    "tỷ lệ trả tiền (%)",
    "sự kiện bảo hiểm",
    "tỷ lệ 1",
    "tỷ lệ 2",
    "các trường hợp thương tật",
    "loại thương tật",
    "tỷ lệ chi trả trên số tiền bảo hiểm của quyền lợi tương ứng (%)",
}

# Benefit detail — specific keys indicating benefit content (no plan columns)
_BENEFIT_DETAIL_KEYS = {
    "chi tiết quyền lợi",
    "phạm vi bảo hiểm",
    "cơ sở bồi thường",
    "cơ sở bồi thưởng",
    "nội dung quyền lợi",
    "nội dung trợ cấp",
    "rủi ro được bảo hiểm",
}

# Short-term premium
_SHORT_TERM_KEYS = {
    "mức phí bảo hiểm ngắn hạn",
    "khoảng thời gian trước khi hủy bỏ hợp đồng bảo hiểm",
    "thời hạn bảo hiểm hoặc khoảng thời gian đã bảo hiểm cho người được bảo hiểm trong năm hợp đồng",
}

# AIA Vitality tier
_VITALITY_KEYS = {"bạc", "vàng", "bạch kim", "đồng"}

# Benefit table label keys (the "row header" column)
_BENEFIT_LABEL_KEYS = {
    "quyền lợi bảo hiểm",
    "quyền lợi bảo hiểm",
    "hạng mục",
    "hospital services",
    "điều trị nội trú",
    "quyền lợi",
    "nội dung",
    "quyền lợi nha khoa",
    "quyền lợi điều trị ngoại trú",
    "quyền lợi điều trị trong ngày",
    "chi phí",
    "điều trị ung thư",
    "1. outpatient services",
    "2. dental service (*)",
    "3. maternity care (**)",
    "an tâm trọn đời",
}


# ============================================================
# Helpers
# ============================================================


def extract_company_code(file_path: Path, base_dir: Path) -> str:
    """Extract company code from file path's first directory component.

    Returns a code that exists in COMPANY_MAP values, never 'unknown'.
    Raises ValueError if the directory is not mapped.
    """
    rel = file_path.relative_to(base_dir)
    top_dir = rel.parts[0]
    code = COMPANY_MAP.get(top_dir)
    if code is None:
        raise ValueError(
            f"Unmapped company directory: '{top_dir}'. "
            f"Add it to COMPANY_MAP."
        )
    return code


def extract_document_name(file_path: Path, base_dir: Path) -> str:
    """Extract document folder name (2nd path component)."""
    rel = file_path.relative_to(base_dir)
    if len(rel.parts) >= 2:
        return rel.parts[1]
    return rel.stem


def parse_page_table_index(filename: str) -> tuple[int | None, int | None]:
    """Extract page_number and table_index from filename like 'table_p4_n1.json'."""
    match = re.match(r"(?:table|picture)_p(\d+)_n(\d+)", filename)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def extract_keys(data: dict) -> list[str]:
    """Extract structured_data keys from a parsed JSON file.

    Handles both list[dict] and dict structured_data formats.
    """
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

    # Filter out empty-string keys
    return sorted(k for k in keys if k.strip())


def classify_by_keys(keys: list[str]) -> tuple[str, str]:
    """Classify a file's table_type based on its structured_data keys.

    Uses rule-based matching: first match wins.

    Returns:
        Tuple of (table_type, reason) where reason explains the match.
    """
    if not keys:
        return "unclassified", "no_keys"

    keys_norm = {normalize_key(k) for k in keys}

    # 1. Glossary — very specific, check first
    if _GLOSSARY_KEYS.issubset(keys_norm):
        return "glossary", "keys_match: thuật ngữ + định nghĩa"

    # 2. Hospital/provider network
    hospital_vi_match = len(keys_norm & _HOSPITAL_KEYS_VI) >= 2
    hospital_en_match = len(keys_norm & _HOSPITAL_KEYS_EN) >= 3
    hospital_name_match = bool(keys_norm & _HOSPITAL_NAME_KEYS) and bool(
        keys_norm & _HOSPITAL_LOCATION_KEYS
    )
    hospital_vi_alt = len(keys_norm & _HOSPITAL_KEYS_VI_ALT) >= 2 and (
        "stt" in keys_norm or "tên cơ sở" in keys_norm
    )
    if hospital_vi_match or hospital_en_match or hospital_name_match or hospital_vi_alt:
        matched = keys_norm & (
            _HOSPITAL_KEYS_VI
            | _HOSPITAL_KEYS_EN
            | _HOSPITAL_KEYS_VI_ALT
            | _HOSPITAL_NAME_KEYS
        )
        return "hospital_network", f"hospital_keys: {sorted(matched)[:5]}"

    # 3. Waiting period
    wp_match = keys_norm & _WAITING_KEYS
    if len(wp_match) >= 2:
        return "waiting_period", f"waiting_keys: {sorted(wp_match)}"

    # 4. Claim payout rates
    payout_match = keys_norm & _PAYOUT_KEYS
    has_payout_context = any(
        term in k
        for k in keys_norm
        for term in ["tỷ lệ chi trả", "sự kiện bảo hiểm", "thương tật"]
    )
    if payout_match and has_payout_context:
        return "claim_payout", f"payout_keys: {sorted(payout_match)}"
    if len(payout_match) >= 2:
        return "claim_payout", f"payout_keys_2+: {sorted(payout_match)}"

    # 5. Short-term premium
    stp_match = keys_norm & _SHORT_TERM_KEYS
    if stp_match:
        return "short_term_premium", f"short_term_keys: {sorted(stp_match)}"

    # 6. AIA Vitality tiers (Bạc/Vàng/Bạch Kim/Đồng)
    vitality_match = keys_norm & _VITALITY_KEYS
    has_vitality_context = any("vitality" in k for k in keys_norm)
    has_mat_hieu_luc = any("mất hiệu lực" in k for k in keys_norm)
    has_muc_thay_doi = any("mức thay đổi" in k for k in keys_norm)
    if len(vitality_match) >= 3 and (
        has_vitality_context or has_mat_hieu_luc or has_muc_thay_doi
    ):
        return "vitality_tier", f"vitality_keys: {sorted(vitality_match)}"

    # 7. Premium/pricing table
    premium_match = keys_norm & _PREMIUM_KEYS
    if premium_match:
        return "premium_table", f"premium_keys: {sorted(premium_match)}"
    # Age range pattern: '0-3', '19-25', etc.
    has_tuoi = "tuổi" in keys_norm or "tuổi" in "".join(keys_norm)
    age_ranges = [k for k in keys if re.match(r"^\d+-\d+$", k.strip())]
    if has_tuoi and len(age_ranges) >= 3:
        return "premium_table", f"age_range_pattern: tuổi + {age_ranges[:3]}"

    # 8. Benefit table — has plan-level columns
    plan_match = keys_norm & _PLAN_KEYS
    has_label = bool(keys_norm & _BENEFIT_LABEL_KEYS)
    if len(plan_match) >= 2 and has_label:
        return "benefit_table", f"plan+label: {sorted(plan_match)[:4]}"
    if len(plan_match) >= 2:
        return "benefit_table", f"plan_keys_only: {sorted(plan_match)[:4]}"

    # 9. Benefit detail — specific benefit keys, no plan columns
    bd_match = keys_norm & _BENEFIT_DETAIL_KEYS
    if bd_match:
        return "benefit_detail", f"benefit_detail_keys: {sorted(bd_match)}"
    # Check for keys that ARE benefit-specific (not just containing 'bảo hiểm')
    # Only match if the key itself is a benefit label, not a generic term
    benefit_specific = {
        k
        for k in keys_norm
        if any(
            term in k
            for term in [
                "quyền lợi bảo hiểm",
                "số tiền bảo hiểm",
                "giới hạn bảo hiểm",
                "mức chi trả",
            ]
        )
    }
    if benefit_specific:
        return "benefit_detail", f"benefit_specific: {sorted(benefit_specific)[:3]}"

    return "unclassified", f"no_rule_matched: {sorted(keys_norm)[:5]}"


# ============================================================
# Processing
# ============================================================


def process_file(
    file_path: Path, base_dir: Path
) -> dict:
    """Process a single JSON file and return classification result.

    Always returns a result dict — never None.
    Errors are captured in the result with status='error'.
    """
    rel_path = str(file_path.relative_to(base_dir))

    # Parse JSON
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "file_path": rel_path,
            "status": "error",
            "error_reason": f"json_decode: {e}",
            "table_type": None,
            "classification_reason": None,
        }
    except UnicodeDecodeError as e:
        return {
            "file_path": rel_path,
            "status": "error",
            "error_reason": f"unicode_decode: {e}",
            "table_type": None,
            "classification_reason": None,
        }

    # Extract company
    try:
        company_code = extract_company_code(file_path, base_dir)
    except ValueError as e:
        return {
            "file_path": rel_path,
            "status": "error",
            "error_reason": str(e),
            "table_type": None,
            "classification_reason": None,
        }

    # Extract keys
    keys = extract_keys(data)
    if not keys:
        reason = "no_structured_data" if "structured_data" not in data else "empty_keys"
        return {
            "file_path": rel_path,
            "status": "skipped",
            "error_reason": reason,
            "company_code": company_code,
            "document_name": extract_document_name(file_path, base_dir),
            "table_type": None,
            "classification_reason": reason,
            "content_type": data.get("content_type", "unknown"),
            "has_content": data.get("has_content", False),
        }

    # Classify
    table_type, reason = classify_by_keys(keys)
    page_number, table_index = parse_page_table_index(file_path.name)
    document_name = extract_document_name(file_path, base_dir)

    return {
        "file_path": rel_path,
        "status": "classified",
        "company_code": company_code,
        "document_name": document_name,
        "page_number": page_number,
        "table_index": table_index,
        "keys": keys,
        "table_type": table_type,
        "classification_reason": reason,
        "content_type": data.get("content_type", "unknown"),
        "has_content": data.get("has_content", False),
    }


def main() -> None:
    """Run classification pipeline on all JSON files."""
    base_dir = DATA_DIR
    if not base_dir.exists():
        print(f"❌ Thư mục không tồn tại: {base_dir}")
        sys.exit(1)

    # Collect all JSON files (exclude output dirs)
    json_files = [
        f
        for f in sorted(base_dir.rglob("*.json"))
        if "classification_output" not in str(f)
    ]

    print(f"📂 Tìm thấy {len(json_files)} file JSON")
    print("🔄 Đang classify...")

    all_results: list[dict] = []
    classified_results: list[dict] = []
    error_results: list[dict] = []
    skipped_results: list[dict] = []
    category_counts: Counter = Counter()
    category_files: dict[str, list[str]] = defaultdict(list)

    for file_path in json_files:
        result = process_file(file_path, base_dir)
        all_results.append(result)

        if result["status"] == "error":
            error_results.append(result)
        elif result["status"] == "skipped":
            skipped_results.append(result)
        else:
            classified_results.append(result)
            category_counts[result["table_type"]] += 1
            category_files[result["table_type"]].append(result["file_path"])

    # --- Output ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Full classification results (all files, including errors)
    output_file = OUTPUT_DIR / "classification_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Kết quả chi tiết: file://{output_file.absolute()}")

    # 2. Error/skipped audit log
    if error_results or skipped_results:
        audit_file = OUTPUT_DIR / "classification_audit.json"
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(
                {"errors": error_results, "skipped": skipped_results},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"⚠️  Audit log: file://{audit_file.absolute()}")

    # 3. Per-category file lists
    for category, files in sorted(category_files.items()):
        cat_file = OUTPUT_DIR / f"category_{category}.json"
        with open(cat_file, "w", encoding="utf-8") as f:
            json.dump(files, f, ensure_ascii=False, indent=2)

    # 4. Summary report
    total_processed = len(classified_results)
    summary = {
        "total_files": len(json_files),
        "classified": total_processed,
        "skipped": len(skipped_results),
        "errors": len(error_results),
        "category_distribution": dict(category_counts.most_common()),
        "category_examples": {
            cat: files[:3] for cat, files in category_files.items()
        },
        "skipped_files": [
            {"file": r["file_path"], "reason": r["error_reason"]}
            for r in skipped_results
        ],
        "error_files": [
            {"file": r["file_path"], "reason": r["error_reason"]}
            for r in error_results
        ],
    }
    summary_file = OUTPUT_DIR / "classification_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print("📊 CLASSIFICATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Tổng file:      {len(json_files)}")
    print(f"  Classified:     {total_processed}")
    print(f"  Skipped:        {len(skipped_results)}")
    print(f"  Errors:         {len(error_results)}")
    print("\n  Category distribution:")
    for cat, count in category_counts.most_common():
        pct = count / total_processed * 100 if total_processed else 0
        print(f"    {cat:25s} {count:4d}  ({pct:5.1f}%)")

    if error_results:
        print(f"\n  ⚠️  Errors ({len(error_results)}):")
        for r in error_results[:5]:
            print(f"    {r['file_path']}: {r['error_reason']}")
        if len(error_results) > 5:
            print(f"    ... và {len(error_results) - 5} lỗi khác")

    print(f"\n✅ Summary: file://{summary_file.absolute()}")


if __name__ == "__main__":
    main()
