"""Generate a grounded multi-source RAG benchmark for health insurance markdowns."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = (
    REPO_ROOT
    / "data/health_insurance/health_insurance_markdowns_interpreted_cleaned"
)
FALLBACK_INPUT_DIR = Path(
    "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/"
    "health_insurance_markdowns_interpreted_cleaned"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/health_insurance/benchmark/health_rag_benchmark"

KEYWORD_PATTERN = re.compile(
    r"bảo hiểm|quyền lợi|chi trả|bồi thường|loại trừ|thời gian chờ|"
    r"nội trú|ngoại trú|thai sản|hồ sơ|phí bảo hiểm|số tiền bảo hiểm|"
    r"người được bảo hiểm|điều kiện|thời hạn|tử vong|thương tật",
    re.IGNORECASE,
)
LOW_VALUE_EVIDENCE_PATTERN = re.compile(
    r"ban hành kèm|căn cứ giấy phép|trên cơ sở người được bảo hiểm|"
    r"là tổ chức được thành lập|chọn có hoặc không|tôi đồng ý cho phép",
    re.IGNORECASE,
)
QUESTION_PREFIX_BY_KEYWORD = [
    ("thời gian chờ", "Theo {provider}, quy định về thời gian chờ trong đoạn này là gì?"),
    ("loại trừ", "Theo {provider}, trường hợp nào bị loại trừ hoặc không được áp dụng?"),
    ("bồi thường", "Theo {provider}, yêu cầu hoặc thời hạn bồi thường được quy định như thế nào?"),
    ("hồ sơ", "Theo {provider}, hồ sơ hoặc chứng từ cần có là gì?"),
    ("thai sản", "Theo {provider}, quyền lợi hoặc điều kiện thai sản được nêu như thế nào?"),
    ("nội trú", "Theo {provider}, quyền lợi hoặc điều kiện điều trị nội trú là gì?"),
    ("ngoại trú", "Theo {provider}, quyền lợi hoặc điều kiện điều trị ngoại trú là gì?"),
    ("số tiền bảo hiểm", "Theo {provider}, số tiền bảo hiểm hoặc giới hạn được quy định ra sao?"),
]


@dataclass(frozen=True)
class ProviderSlot:
    """One API key/model slot usable by the generator."""

    slot_id: str
    provider: str
    api_key: str
    model: str
    base_url: str


@dataclass
class EvidenceSource:
    """A grounded source span for one benchmark answer."""

    provider: str
    source_path: str
    line_start: int
    line_end: int
    answer: str
    evidence_quote: str
    relationship: str = "primary"


@dataclass
class BenchmarkCase:
    """One RAG benchmark case."""

    id: str
    financebench_id: str
    case_type: str
    task_type: str
    risk_level: str
    question: str
    gold_answer: str
    expected_behavior: str
    expected_sources: list[EvidenceSource]
    source_constraints: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    generator: dict[str, Any] = field(default_factory=dict)


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse .env while tolerating malformed KEY value lines."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        else:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            key, value = parts
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            values[key] = value
    return values


def split_keys(value: str) -> list[str]:
    """Split comma/semicolon/newline separated API keys."""
    return [part.strip() for part in re.split(r"[,;\s]+", value) if part.strip()]


def build_provider_slots(env_path: Path) -> list[ProviderSlot]:
    """Build provider slots from all supported API keys in .env."""
    env = parse_env_file(env_path)
    slots: list[ProviderSlot] = []

    def add_slots(prefix: str, provider: str, model: str, base_url: str) -> None:
        keys: list[str] = []
        for key, value in env.items():
            if key.upper().startswith(prefix):
                keys.extend(split_keys(value))
        for idx, api_key in enumerate(dict.fromkeys(keys), start=1):
            digest = hashlib.sha1(api_key.encode()).hexdigest()[:8]
            slots.append(
                ProviderSlot(
                    slot_id=f"{provider}_{idx}_{digest}",
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                )
            )

    add_slots(
        "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS",
        "gemini",
        env.get("KG_SCHEMA_DISCOVERY_GEMINI_MODEL", "gemini-2.5-flash"),
        env.get(
            "KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ),
    )
    add_slots(
        "GEMINI_API_KEY",
        "gemini",
        env.get("KG_SCHEMA_DISCOVERY_GEMINI_MODEL", "gemini-2.5-flash"),
        env.get(
            "KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ),
    )
    add_slots(
        "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS",
        "openrouter",
        env.get("KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        env.get(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
    )
    add_slots(
        "OPENROUTER_API_KEY",
        "openrouter",
        env.get("KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        env.get(
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
    )
    add_slots(
        "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS",
        "nvidia",
        env.get("KG_SCHEMA_DISCOVERY_NVIDIA_MODEL", "google/gemma-4-31b-it"),
        env.get(
            "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        ),
    )
    add_slots(
        "NVIDIA",
        "nvidia",
        env.get("KG_SCHEMA_DISCOVERY_NVIDIA_MODEL", "google/gemma-4-31b-it"),
        env.get(
            "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        ),
    )
    add_slots(
        "OLLAMA_API_KEY",
        "ollama",
        env.get("KG_SCHEMA_DISCOVERY_OLLAMA_MODEL", "gemma4:31b-cloud"),
        env.get("KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    deduped_slots: list[ProviderSlot] = []
    seen_slot_keys: set[tuple[str, str, str]] = set()
    for slot in slots:
        slot_key = (slot.provider, slot.api_key, slot.model)
        if slot_key in seen_slot_keys:
            continue
        seen_slot_keys.add(slot_key)
        deduped_slots.append(slot)
    return deduped_slots


def find_markdown_files(input_dir: Path, limit_files: int | None) -> list[Path]:
    """Find markdown files, excluding generated benchmark folders."""
    files = [
        path
        for path in input_dir.rglob("*.md")
        if "benchmark" not in path.relative_to(input_dir).parts
        and not any(
            "test" in part.lower() or "sample" in part.lower()
            for part in path.relative_to(input_dir).parts
        )
    ]
    files.sort(key=lambda path: (path.relative_to(input_dir).parts[0], str(path)))
    if limit_files:
        return files[:limit_files]
    return files


def infer_document_type(path: Path) -> str:
    """Infer a coarse document type from the filename."""
    text = path.as_posix().lower()
    if "bieu-phi" in text or "premium" in text or "phi" in text:
        return "premium"
    if "provider-list" in text or "co-so-y-te" in text or "benh-vien" in text:
        return "provider_list"
    if "brochure" in text or "gioi-thieu" in text:
        return "brochure"
    if "tom-tat" in text or "summary" in text:
        return "summary"
    if "quy-tac" in text or "policy-wording" in text or "dieu-khoan" in text:
        return "policy_wording"
    return "other"


def iter_candidate_lines(path: Path, input_dir: Path) -> list[dict[str, Any]]:
    """Extract candidate benchmark evidence lines from a markdown file."""
    rel_path = path.relative_to(input_dir).as_posix()
    provider = Path(rel_path).parts[0]
    candidates: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line_number, line in enumerate(lines, start=1):
        quote = line.strip()
        if not (80 <= len(quote) <= 900):
            continue
        if quote.startswith("|"):
            continue
        if not KEYWORD_PATTERN.search(quote):
            continue
        if LOW_VALUE_EVIDENCE_PATTERN.search(quote):
            continue
        candidates.append(
            {
                "provider": provider,
                "source_path": rel_path,
                "document_type": infer_document_type(Path(rel_path)),
                "line_start": line_number,
                "line_end": line_number,
                "quote": quote,
            }
        )
    return candidates


def readable_document_name(source_path: str) -> str:
    """Build a short readable document name from a source path."""
    stem = Path(source_path).stem.replace("-", " ").replace("_", " ")
    stem = re.sub(r"\b\d{4,}\b", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem[:80] or Path(source_path).parent.name[:80]


def quote_topic(quote: str) -> str:
    """Extract a short topic phrase so generated questions are not duplicated."""
    text = re.sub(r"^[#\-*>|\d\.\)\s]+", "", quote).strip()
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\s+", " ", text)
    for pattern in [
        r"(?:quy định|quyền lợi|điều khoản|nội dung|hồ sơ|thời gian chờ)\s+(?:về|cho|của)?\s*([^.;:]{12,120})",
        r"(?:trường hợp|chi phí|dịch vụ|bệnh|tai nạn|thai sản)\s+([^.;:]{12,120})",
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ,;:-")[:90]
    words = text.split()
    return " ".join(words[:14]).strip(" ,;:-")[:90]


def deterministic_question(candidate: dict[str, Any]) -> tuple[str, str, str]:
    """Create a grounded fallback question/task/risk from a quote."""
    provider = candidate["provider"]
    quote = candidate["quote"]
    document_name = readable_document_name(candidate["source_path"])
    topic = quote_topic(quote)
    lowered = quote.lower()
    for keyword, template in QUESTION_PREFIX_BY_KEYWORD:
        if keyword in lowered:
            task_type = keyword.replace(" ", "_")
            risk = "high" if keyword in {"loại trừ", "bồi thường", "thai sản"} else "medium"
            question = (
                f"Trong tài liệu {document_name} của {provider}, nội dung về {topic} "
                "được quy định như thế nào?"
            )
            return question, task_type, risk
    return (
        f"Trong tài liệu {document_name} của {provider}, {topic} được nêu như thế nào?",
        "policy_qa",
        "medium",
    )


def clean_json_response(text: str) -> str:
    """Extract a JSON array/object from an LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    starts = [idx for idx in [text.find("["), text.find("{")] if idx >= 0]
    if starts:
        start = min(starts)
        end = max(text.rfind("]"), text.rfind("}"))
        if end > start:
            return text[start : end + 1]
    return text


def llm_prompt(candidate: dict[str, Any]) -> str:
    """Build prompt for one grounded Q&A generation request."""
    return f"""
Bạn là chuyên gia tạo benchmark RAG bảo hiểm Việt Nam.
Dựa duy nhất vào evidence_quote bên dưới, hãy tạo đúng 1 JSON object.
Không dùng kiến thức ngoài quote. Không thêm markdown fence.

Schema:
{{
  "question": "câu hỏi tiếng Việt, nên nêu provider/sản phẩm nếu có",
  "answer": "câu trả lời ngắn, trung thành với quote",
  "task_type": "definition|coverage|exclusion|claim|waiting_period|eligibility|premium|provider_list|policy_qa",
  "risk_level": "low|medium|high"
}}

Metadata:
provider: {candidate['provider']}
document_type: {candidate['document_type']}
source_path: {candidate['source_path']}
line: {candidate['line_start']}

evidence_quote:
{candidate['quote']}
""".strip()


def call_provider(slot: ProviderSlot, prompt: str, timeout_seconds: float) -> dict[str, Any]:
    """Call one configured provider slot and return parsed JSON."""
    headers = {"Content-Type": "application/json"}
    if slot.provider == "gemini":
        url = (
            f"{slot.base_url.rstrip('/')}/models/{slot.model}:generateContent"
            f"?key={slot.api_key}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]
    elif slot.provider == "ollama":
        url = f"{slot.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": slot.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        if slot.api_key:
            headers["Authorization"] = f"Bearer {slot.api_key}"
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data.get("message", {}).get("content", "{}")
    else:
        headers["Authorization"] = f"Bearer {slot.api_key}"
        payload = {
            "model": slot.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(slot.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
    parsed = json.loads(clean_json_response(content))
    if not isinstance(parsed, dict):
        raise ValueError("Provider returned non-object JSON")
    return parsed


def generate_case_payload(
    candidate: dict[str, Any],
    slots: list[ProviderSlot],
    index: int,
    timeout_seconds: float,
    use_llm: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate one Q&A payload, falling back to deterministic generation."""
    provider_info = {"mode": "deterministic", "slot_id": "", "error": ""}
    if use_llm and slots:
        slot = slots[index % len(slots)]
        try:
            payload = call_provider(slot, llm_prompt(candidate), timeout_seconds)
            if not str(payload.get("question") or "").strip():
                raise ValueError("Provider returned an empty question")
            if not str(payload.get("answer") or "").strip():
                raise ValueError("Provider returned an empty answer")
            provider_info = {"mode": "llm", "slot_id": slot.slot_id, "error": ""}
            return payload, provider_info
        except Exception as exc:  # noqa: BLE001
            provider_info = {
                "mode": "deterministic_fallback",
                "slot_id": slot.slot_id,
                "error": str(exc)[:300],
            }
    question, task_type, risk = deterministic_question(candidate)
    return {
        "question": question,
        "answer": candidate["quote"],
        "task_type": task_type,
        "risk_level": risk,
    }, provider_info


def source_similarity_key(quote: str) -> set[str]:
    """Return normalized tokens used for cross-source matching."""
    text = re.sub(r"[^\w\sÀ-ỹ]", " ", quote.lower())
    tokens = {token for token in text.split() if len(token) >= 5}
    return tokens


def expand_sources(
    primary: dict[str, Any], all_candidates: list[dict[str, Any]], max_sources: int
) -> list[EvidenceSource]:
    """Find other sources whose evidence appears to answer the same theme."""
    primary_tokens = source_similarity_key(primary["quote"])
    sources = [
        EvidenceSource(
            provider=primary["provider"],
            source_path=primary["source_path"],
            line_start=primary["line_start"],
            line_end=primary["line_end"],
            answer=primary["quote"],
            evidence_quote=primary["quote"],
            relationship="primary",
        )
    ]
    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate in all_candidates:
        if candidate["source_path"] == primary["source_path"]:
            continue
        tokens = source_similarity_key(candidate["quote"])
        if not tokens:
            continue
        overlap = len(primary_tokens & tokens) / max(1, len(primary_tokens | tokens))
        same_theme = bool(KEYWORD_PATTERN.search(candidate["quote"]))
        if overlap >= 0.12 and same_theme:
            scored.append((overlap, candidate))
    for _, candidate in sorted(scored, key=lambda item: item[0], reverse=True)[: max_sources - 1]:
        sources.append(
            EvidenceSource(
                provider=candidate["provider"],
                source_path=candidate["source_path"],
                line_start=candidate["line_start"],
                line_end=candidate["line_end"],
                answer=candidate["quote"],
                evidence_quote=candidate["quote"],
                relationship="related_source",
            )
        )
    return sources


def interleave_candidates_by_provider(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Interleave candidates so primary benchmark cases cover multiple providers."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate["provider"], []).append(candidate)
    ordered_providers = sorted(grouped, key=lambda provider: (-len(grouped[provider]), provider))
    interleaved: list[dict[str, Any]] = []
    while ordered_providers:
        next_round: list[str] = []
        for provider in ordered_providers:
            provider_candidates = grouped[provider]
            if provider_candidates:
                interleaved.append(provider_candidates.pop(0))
            if provider_candidates:
                next_round.append(provider)
        ordered_providers = next_round
    return interleaved


def build_cases(
    candidates: list[dict[str, Any]],
    slots: list[ProviderSlot],
    args: argparse.Namespace,
) -> list[BenchmarkCase]:
    """Generate benchmark cases from candidate evidence."""
    selected = interleave_candidates_by_provider(candidates)[: max(args.max_cases, args.max_cases * 4)]
    cases: list[BenchmarkCase] = []
    seen_questions: set[str] = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrency) as executor:
        futures = {
            executor.submit(
                generate_case_payload,
                candidate,
                slots,
                index,
                args.timeout_seconds,
                args.use_llm,
            ): (index, candidate)
            for index, candidate in enumerate(selected)
        }
        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            index, candidate = futures[future]
            payload, generator = future.result()
            completed += 1
            if args.progress_every and completed % args.progress_every == 0:
                print(
                    json.dumps(
                        {
                            "event": "case_generated",
                            "completed": completed,
                            "total": total,
                            "mode": generator.get("mode"),
                            "slot_id": generator.get("slot_id"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            sources = expand_sources(candidate, candidates, args.max_sources_per_case)
            case_type = "multi_source_answer" if len(sources) > 1 else "single_source_answer"
            case_id = f"hi_rag_bench_{index + 1:05d}"
            expected_behavior = (
                "Trả lời theo từng provider/source, không gộp thành một điều khoản chung."
                if case_type == "multi_source_answer"
                else "Trả lời đúng theo nguồn duy nhất và trích dẫn evidence."
            )
            question = str(payload.get("question") or "").strip()
            normalized_question = re.sub(r"\s+", " ", question.lower())
            if not question or normalized_question in seen_questions:
                continue
            seen_questions.add(normalized_question)
            cases.append(
                BenchmarkCase(
                    id=case_id,
                    financebench_id=case_id,
                    case_type=case_type,
                    task_type=str(payload.get("task_type") or "policy_qa"),
                    risk_level=str(payload.get("risk_level") or "medium"),
                    question=question,
                    gold_answer=str(payload.get("answer") or candidate["quote"]),
                    expected_behavior=expected_behavior,
                    expected_sources=sources,
                    source_constraints={
                        "primary_provider": candidate["provider"],
                        "primary_source_path": candidate["source_path"],
                        "must_include_primary_source": True,
                        "must_match_primary_provider": case_type == "single_source_answer",
                        "allow_related_sources": case_type == "multi_source_answer",
                        "must_group_by_source": case_type == "multi_source_answer",
                        "must_cite_each_source": True,
                        "expected_source_count": len(sources),
                        "expected_provider_count": len({source.provider for source in sources}),
                    },
                    scoring={
                        "max_score": 10,
                        "pass_threshold": 8,
                        "criteria": {
                            "retrieves_primary_source": 2,
                            "retrieves_required_evidence_quote": 2,
                            "answer_faithful_to_evidence": 3,
                            "cites_sources_correctly": 1,
                            "groups_multi_source_answers": 1,
                            "does_not_overgeneralize": 1,
                        },
                        "min_sources_required": min(len(sources), 2),
                        "required_source_paths": [source.source_path for source in sources],
                        "required_evidence_quotes": [source.evidence_quote for source in sources],
                    },
                    generator={
                        **generator,
                        "name": "health_rag_benchmark_generator",
                        "version": "v1.1",
                        "question_strategy": "deterministic_topic_from_evidence",
                        "cross_source_strategy": "token_overlap_related_sources",
                        "llm_requested": args.use_llm,
                        "llm_used": generator.get("mode") == "llm",
                    },
                )
            )
            if len(cases) >= args.max_cases:
                break
    return sorted(cases, key=lambda case: case.id)


def write_outputs(cases: list[BenchmarkCase], output_dir: Path, manifest: dict[str, Any]) -> None:
    """Write JSONL, CSV, manifest, and README outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "health_insurance_rag_benchmark.jsonl"
    csv_path = output_dir / "health_insurance_rag_benchmark.csv"
    manifest_path = output_dir / "manifest.json"
    readme_path = output_dir / "README.md"

    rows = [asdict(case) for case in cases]
    jsonl_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    flat_rows = []
    for row in rows:
        flat = dict(row)
        flat["expected_sources"] = json.dumps(flat["expected_sources"], ensure_ascii=False)
        flat["source_constraints"] = json.dumps(flat["source_constraints"], ensure_ascii=False)
        flat["scoring"] = json.dumps(flat["scoring"], ensure_ascii=False)
        flat["generator"] = json.dumps(flat["generator"], ensure_ascii=False)
        flat_rows.append(flat)
    with csv_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"""# Health Insurance RAG Benchmark\n\nGenerated benchmark inspired by FinanceBench-style JSONL outputs, adapted for Vietnamese health insurance RAG.\n\n## Files\n\n- `health_insurance_rag_benchmark.jsonl`: canonical benchmark cases.\n- `health_insurance_rag_benchmark.csv`: spreadsheet-friendly copy.\n- `manifest.json`: generation settings and provider-slot summary.\n\n## Schema Highlights\n\n- `question`, `gold_answer`: FinanceBench-like fields for evaluation.\n- `case_type`: `single_source_answer` or `multi_source_answer`.\n- `expected_sources`: list of grounded sources with `source_path`, `line_start`, `line_end`, `evidence_quote`.\n- `scoring`: retrieval, evidence, answer faithfulness, and citation rubric.\n\n## Counts\n\n- Cases: {len(cases)}\n- Multi-source cases: {sum(1 for case in cases if case.case_type == 'multi_source_answer')}\n- Single-source cases: {sum(1 for case in cases if case.case_type == 'single_source_answer')}\n\nFor multi-source questions, the target RAG behavior is to return separate answers grouped by provider/source rather than one universal insurance rule.\n""",
        encoding="utf-8",
    )


def verify_cases(cases: list[BenchmarkCase], input_dir: Path) -> list[str]:
    """Verify source paths, lines, and evidence quotes."""
    errors: list[str] = []
    for case in cases:
        if not case.question.strip():
            errors.append(f"{case.id}: empty question")
        for source in case.expected_sources:
            path = input_dir / source.source_path
            if not path.exists():
                errors.append(f"{case.id}: missing source {source.source_path}")
                continue
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if source.line_start < 1 or source.line_start > len(lines):
                errors.append(f"{case.id}: bad line {source.line_start}")
                continue
            if lines[source.line_start - 1].strip() != source.evidence_quote:
                errors.append(f"{case.id}: evidence quote mismatch")
    return errors


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--env-path", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--limit-files", type=int, default=80)
    parser.add_argument("--max-cases", type=int, default=100)
    parser.add_argument("--max-candidates-per-file", type=int, default=8)
    parser.add_argument("--max-sources-per-case", type=int, default=4)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir
    if not input_dir.exists() and FALLBACK_INPUT_DIR.exists():
        input_dir = FALLBACK_INPUT_DIR

    started = time.time()
    slots = build_provider_slots(args.env_path)
    markdown_files = find_markdown_files(input_dir, args.limit_files)
    candidates: list[dict[str, Any]] = []
    for path in markdown_files:
        candidates.extend(iter_candidate_lines(path, input_dir)[: args.max_candidates_per_file])
    if not candidates:
        raise ValueError(f"No benchmark candidates found under {input_dir}")
    cases = build_cases(candidates, slots, args)
    errors = verify_cases(cases, input_dir)
    if errors:
        raise ValueError("Verification failed:\n" + "\n".join(errors[:20]))

    manifest = {
        "version": "health_insurance_rag_benchmark_v1_generated",
        "input_dir": str(input_dir),
        "output_dir": str(args.output_dir),
        "file_count": len(markdown_files),
        "candidate_count": len(candidates),
        "case_count": len(cases),
        "provider_slot_count": len(slots),
        "provider_slots": [
            {"slot_id": slot.slot_id, "provider": slot.provider, "model": slot.model}
            for slot in slots
        ],
        "use_llm": args.use_llm,
        "elapsed_seconds": round(time.time() - started, 2),
    }
    write_outputs(cases, args.output_dir, manifest)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
