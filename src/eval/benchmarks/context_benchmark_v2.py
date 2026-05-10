"""Generate context-level Health RAG benchmark v2 cases."""

from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import random
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from src.eval.io import ensure_directory
from src.eval.llm_provider_slots import EvalLLMProviderSlot, provider_slot_counts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "health_insurance"
    / "health_insurance_markdowns_interpreted_cleaned"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "benchmark" / "health_rag_context_benchmark_v2"
)
DEFAULT_DISTRIBUTION = {
    "single_context": 30,
    "two_context": 30,
    "three_context": 30,
    "table_context": 10,
}
CASE_CONTEXT_COUNTS = {
    "single_context": 1,
    "two_context": 2,
    "three_context": 3,
    "table_context": 1,
}
EXCLUDED_PATH_MARKERS = ("benchmark", "sample", "test")
TOKEN_PATTERN = re.compile(r"\S+")
TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)

JsonDict = dict[str, Any]
LLMCall = Callable[[EvalLLMProviderSlot, str, float], JsonDict]


@dataclass(frozen=True)
class ContextChunk:
    """A large source context chunk with line and table metadata."""

    chunk_id: str
    provider: str
    source_path: str
    text: str
    start_line: int
    end_line: int
    token_count: int
    contains_table: bool
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class CaseCandidate:
    """One sampled prompt candidate for LLM benchmark generation."""

    candidate_id: str
    case_type: str
    contexts: tuple[ContextChunk, ...]


@dataclass(frozen=True)
class ContextBenchmarkV2Config:
    """Runtime configuration for context benchmark v2 generation."""

    input_dir: Path = DEFAULT_INPUT_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    target_tokens: int = 1500
    min_tokens: int = 80
    distribution: Mapping[str, int] = field(
        default_factory=lambda: dict(DEFAULT_DISTRIBUTION)
    )
    random_seed: int = 20260508
    max_workers: int = 21
    max_retries: int = 2
    timeout_seconds: float = 120.0
    max_rounds: int = 25
    progress_every: int = 5
    resume_partial: bool = False
    max_provider_list_cases: int = 15
    max_hotline_cases: int = 15
    max_low_risk_cases: int = 45


@dataclass(frozen=True)
class GenerationRunResult:
    """Summary of a completed benchmark generation run."""

    output_dir: Path
    accepted_count: int
    failed_count: int
    distribution: dict[str, int]
    context_chunk_count: int
    sampled_context_chunk_count: int
    provider_slot_count: int
    worker_count: int
    elapsed_seconds: float


class CaseGenerationError(RuntimeError):
    """Raised when an LLM case cannot be generated or validated."""


def find_markdown_files(input_dir: Path) -> list[Path]:
    """Find source Markdown files under the corpus directory."""

    files: list[Path] = []
    for path in input_dir.rglob("*.md"):
        rel_path = path.relative_to(input_dir)
        lower_parts = tuple(part.lower() for part in rel_path.parts)
        if any(
            marker in part
            for marker in EXCLUDED_PATH_MARKERS
            for part in lower_parts
        ):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(input_dir).as_posix())


def chunk_document_text(
    *,
    provider: str,
    source_path: str,
    text: str,
    target_tokens: int = 1500,
    min_tokens: int = 80,
) -> list[ContextChunk]:
    """Split one source document into large context chunks."""

    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive.")
    if min_tokens <= 0:
        raise ValueError("min_tokens must be positive.")

    chunks: list[ContextChunk] = []
    current_lines: list[str] = []
    current_start_line = 1
    current_token_count = 0
    lines = text.splitlines()
    for line_index, line in enumerate(lines):
        line_number = line_index + 1
        next_line = lines[line_index + 1] if line_index + 1 < len(lines) else ""
        if not current_lines:
            current_start_line = line_number
        current_lines.append(line)
        current_token_count += count_tokens(line)
        if current_token_count >= target_tokens and not should_delay_chunk_flush(
            line,
            next_line,
        ):
            append_context_chunk(
                chunks=chunks,
                provider=provider,
                source_path=source_path,
                lines=current_lines,
                start_line=current_start_line,
                token_count=current_token_count,
            )
            current_lines = []
            current_token_count = 0

    if current_lines:
        if chunks and current_token_count < min_tokens:
            trimmed_lines, _, trimmed_end_line = trim_blank_edge_lines(
                current_lines,
                current_start_line,
            )
            if trimmed_lines:
                previous = chunks.pop()
                merged_text = previous.text + "\n" + "\n".join(trimmed_lines)
                chunks.append(
                    ContextChunk(
                        chunk_id=previous.chunk_id,
                        provider=previous.provider,
                        source_path=previous.source_path,
                        text=merged_text,
                        start_line=previous.start_line,
                        end_line=trimmed_end_line,
                        token_count=previous.token_count + current_token_count,
                        contains_table=previous.contains_table
                        or contains_markdown_table(merged_text),
                        metadata=previous.metadata,
                    )
                )
        elif current_token_count >= min_tokens or not chunks:
            append_context_chunk(
                chunks=chunks,
                provider=provider,
                source_path=source_path,
                lines=current_lines,
                start_line=current_start_line,
                token_count=current_token_count,
            )
    return chunks


def append_context_chunk(
    *,
    chunks: list[ContextChunk],
    provider: str,
    source_path: str,
    lines: Sequence[str],
    start_line: int,
    token_count: int,
) -> None:
    """Append one normalized context chunk."""

    trimmed_lines, trimmed_start_line, trimmed_end_line = trim_blank_edge_lines(
        lines,
        start_line,
    )
    text = "\n".join(trimmed_lines)
    if not text:
        return
    chunk_index = len(chunks)
    chunks.append(
        ContextChunk(
            chunk_id=build_chunk_id(source_path, chunk_index),
            provider=provider,
            source_path=source_path,
            text=text,
            start_line=trimmed_start_line,
            end_line=trimmed_end_line,
            token_count=token_count,
            contains_table=contains_markdown_table(text),
            metadata={"chunk_index": chunk_index},
        )
    )


def trim_blank_edge_lines(
    lines: Sequence[str],
    start_line: int,
) -> tuple[list[str], int, int]:
    """Trim blank edge lines while preserving source line numbering."""

    first_index = 0
    last_index = len(lines) - 1
    while first_index <= last_index and not lines[first_index].strip():
        first_index += 1
    while last_index >= first_index and not lines[last_index].strip():
        last_index -= 1
    if first_index > last_index:
        return [], start_line, start_line - 1
    return (
        list(lines[first_index : last_index + 1]),
        start_line + first_index,
        start_line + last_index,
    )


def load_context_chunks(
    input_dir: Path,
    *,
    target_tokens: int = 1500,
    min_tokens: int = 80,
) -> list[ContextChunk]:
    """Load all corpus Markdown files and split them into context chunks."""

    chunks: list[ContextChunk] = []
    for path in find_markdown_files(input_dir):
        rel_path = path.relative_to(input_dir).as_posix()
        provider = Path(rel_path).parts[0]
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(
            chunk_document_text(
                provider=provider,
                source_path=rel_path,
                text=text,
                target_tokens=target_tokens,
                min_tokens=min_tokens,
            )
        )
    return chunks


def count_tokens(text: str) -> int:
    """Return an approximate whitespace-token count."""

    return len(TOKEN_PATTERN.findall(text))


def contains_markdown_table(text: str) -> bool:
    """Return whether text contains a Markdown table."""

    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        if line.count("|") < 2:
            continue
        if TABLE_SEPARATOR_PATTERN.match(lines[index + 1]):
            return True
    return False


def should_delay_chunk_flush(current_line: str, next_line: str) -> bool:
    """Return whether a chunk boundary should wait for a table block."""

    return is_tableish_line(current_line) or is_tableish_line(next_line)


def is_tableish_line(line: str) -> bool:
    """Return whether a line looks like part of a Markdown table."""

    stripped = line.strip()
    return stripped.count("|") >= 2 or bool(TABLE_SEPARATOR_PATTERN.match(stripped))


def build_case_candidates(
    chunks: Sequence[ContextChunk],
    *,
    distribution: Mapping[str, int],
    random_seed: int,
) -> list[CaseCandidate]:
    """Sample case candidates with the requested distribution."""

    if not chunks:
        raise ValueError("Cannot build candidates without context chunks.")

    rng = random.Random(random_seed)
    non_table_chunks = [chunk for chunk in chunks if not chunk.contains_table]
    table_chunks = [chunk for chunk in chunks if chunk.contains_table]
    text_pool = non_table_chunks or list(chunks)
    source_groups = grouped_chunks_by_source(text_pool)
    candidates: list[CaseCandidate] = []
    for case_type, count in distribution.items():
        if count < 0:
            raise ValueError(f"Negative count for {case_type}.")
        context_count = CASE_CONTEXT_COUNTS.get(case_type)
        if context_count is None:
            raise ValueError(f"Unsupported case type: {case_type}")
        for index in range(count):
            contexts = sample_candidate_contexts(
                case_type=case_type,
                context_count=context_count,
                text_pool=text_pool,
                source_groups=source_groups,
                table_chunks=table_chunks,
                rng=rng,
            )
            candidates.append(
                CaseCandidate(
                    candidate_id=f"{case_type}_{index + 1:05d}",
                    case_type=case_type,
                    contexts=tuple(contexts),
                )
            )
    return candidates


def sample_candidate_contexts(
    *,
    case_type: str,
    context_count: int,
    text_pool: Sequence[ContextChunk],
    source_groups: Sequence[Sequence[ContextChunk]],
    table_chunks: Sequence[ContextChunk],
    rng: random.Random,
) -> list[ContextChunk]:
    """Sample contexts for one case candidate."""

    if case_type == "table_context":
        if not table_chunks:
            raise ValueError("No table chunks are available for table_context cases.")
        return [rng.choice(table_chunks)]
    if len(text_pool) < context_count:
        raise ValueError(
            f"Need at least {context_count} text chunks for {case_type}; "
            f"found {len(text_pool)}."
        )
    if context_count > 1:
        eligible_groups = [
            group for group in source_groups if len(group) >= context_count
        ]
        if eligible_groups:
            group = list(rng.choice(eligible_groups))
            start_index = rng.randint(0, len(group) - context_count)
            return group[start_index : start_index + context_count]
    return rng.sample(list(text_pool), context_count)


def grouped_chunks_by_source(
    chunks: Sequence[ContextChunk],
) -> list[tuple[ContextChunk, ...]]:
    """Group chunks by source path while preserving source order."""

    groups: dict[str, list[ContextChunk]] = {}
    for chunk in chunks:
        groups.setdefault(chunk.source_path, []).append(chunk)
    return [
        tuple(sorted(group, key=lambda chunk: chunk.metadata.get("chunk_index", 0)))
        for group in groups.values()
    ]


def build_generation_prompt(candidate: CaseCandidate) -> str:
    """Build the LLM prompt for one benchmark candidate."""

    context_blocks = []
    for index, chunk in enumerate(candidate.contexts, start=1):
        context_blocks.append(
            "\n".join(
                [
                    f"[CONTEXT {index}]",
                    f"chunk_id: {chunk.chunk_id}",
                    f"provider: {chunk.provider}",
                    f"source_path: {chunk.source_path}",
                    f"line_range: {chunk.start_line}-{chunk.end_line}",
                    f"contains_table: {str(chunk.contains_table).lower()}",
                    "text:",
                    chunk.text,
                ]
            )
        )
    context_count = len(candidate.contexts)
    all_context_rule = (
        "Câu hỏi và câu trả lời phải cần thông tin từ TẤT CẢ context. "
        "Với 2 hoặc 3 context, hãy tạo câu hỏi so sánh/tổng hợp dạng: "
        "'ở context 1..., context 2..., context 3... thì quy định thế nào?'. "
        "Câu trả lời nên có từng ý ngắn cho mỗi context."
        if context_count > 1
        else "Câu hỏi và câu trả lời phải bám vào context duy nhất."
    )
    table_rule = (
        "Đây là table_context: câu hỏi phải hỏi về dữ liệu trong bảng Markdown."
        if candidate.case_type == "table_context"
        else "Không tạo câu hỏi chỉ dựa vào bảng nếu context không có bảng."
    )
    return f"""
Bạn là chuyên gia tạo benchmark RAG cho bảo hiểm sức khỏe Việt Nam.
Dựa duy nhất vào các context bên dưới, tạo đúng 1 JSON object.
Không dùng kiến thức ngoài context. Không thêm markdown fence.

Yêu cầu:
- {all_context_rule}
- {table_rule}
- evidence_quotes phải copy nguyên văn từ context.
- Với case nhiều context, evidence_quotes phải có ít nhất 1 quote cho mỗi chunk_id.
- Với case nhiều context, chọn quote ngắn 1-2 câu hoặc 1 dòng bảng từ từng context;
  không tóm tắt quote, không nối nhiều đoạn xa nhau thành một quote.
- Câu hỏi phải tự nhiên, bằng tiếng Việt, có thể nêu provider/sản phẩm nếu context có.
- Câu trả lời ngắn gọn nhưng đủ thông tin để làm ground truth.
- Ưu tiên câu hỏi về bồi thường, loại trừ, thời gian chờ, điều kiện tham gia,
  quyền lợi, phí hoặc hạn mức. Tránh câu hỏi chỉ hỏi hotline/liên hệ nếu context
  còn nội dung bảo hiểm khác.
- task_type dùng một trong các nhãn: coverage, exclusion, claim,
  waiting_period, eligibility, premium, provider_list, table, policy_qa.
- risk_level đặt là high cho claim, từ chối/loại trừ, tranh chấp bồi thường,
  quyền lợi có khả năng ảnh hưởng quyết định chi trả.

Schema:
{{
  "question": "câu hỏi tiếng Việt",
  "gold_answer": "câu trả lời ground truth",
  "evidence_quotes": [
    {{"chunk_id": "chunk_id trong context", "quote": "trích dẫn nguyên văn"}}
  ],
  "task_type": "policy_qa",
  "risk_level": "low|medium|high"
}}

case_type: {candidate.case_type}
context_count: {context_count}

{chr(10).join(context_blocks)}
""".strip()


def call_llm_slot(
    slot: EvalLLMProviderSlot,
    prompt: str,
    timeout_seconds: float,
) -> JsonDict:
    """Call one configured LLM slot and return parsed JSON."""

    headers = {"Content-Type": "application/json"}
    provider = slot.provider.strip().lower()
    if provider == "gemini":
        content = call_gemini_slot(slot, prompt, timeout_seconds, headers)
    elif provider == "ollama":
        content = call_ollama_slot(slot, prompt, timeout_seconds, headers)
    else:
        content = call_openai_compatible_slot(slot, prompt, timeout_seconds, headers)
    payload = json.loads(clean_json_response(content))
    if not isinstance(payload, dict):
        raise ValueError("LLM returned non-object JSON.")
    return payload


def call_gemini_slot(
    slot: EvalLLMProviderSlot,
    prompt: str,
    timeout_seconds: float,
    headers: dict[str, str],
) -> str:
    """Call a Gemini generateContent endpoint."""

    url = (
        f"{slot.base_url.rstrip('/')}/models/{slot.model}:generateContent"
        f"?key={slot.api_key}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)
    raise_for_status_with_body(response)
    data = response.json()
    return str(data["candidates"][0]["content"]["parts"][0]["text"])


def call_ollama_slot(
    slot: EvalLLMProviderSlot,
    prompt: str,
    timeout_seconds: float,
    headers: dict[str, str],
) -> str:
    """Call an Ollama chat endpoint."""

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
    raise_for_status_with_body(response)
    data = response.json()
    return str(data.get("message", {}).get("content", "{}"))


def call_openai_compatible_slot(
    slot: EvalLLMProviderSlot,
    prompt: str,
    timeout_seconds: float,
    headers: dict[str, str],
) -> str:
    """Call an OpenAI-compatible chat/completions endpoint."""

    if slot.api_key:
        headers["Authorization"] = f"Bearer {slot.api_key}"
    payload = {
        "model": slot.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(slot.base_url, json=payload, headers=headers)
    raise_for_status_with_body(response)
    data = response.json()
    return str(data["choices"][0]["message"]["content"])


def raise_for_status_with_body(response: httpx.Response) -> None:
    """Raise HTTP errors while preserving response body context."""

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = response.text[:500]
        raise httpx.HTTPStatusError(
            f"{exc}; response body: {body}",
            request=exc.request,
            response=exc.response,
        ) from exc


def clean_json_response(text: str) -> str:
    """Extract a JSON object from an LLM response."""

    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
    stripped = re.sub(r"```$", "", stripped).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


def generate_case_for_candidate(
    *,
    candidate: CaseCandidate,
    case_index: int,
    slot: EvalLLMProviderSlot,
    call_llm: LLMCall = call_llm_slot,
    timeout_seconds: float,
    max_retries: int,
) -> JsonDict:
    """Generate and validate one benchmark case for a candidate."""

    prompt = build_generation_prompt(candidate)
    errors: list[str] = []
    for attempt in range(max_retries + 1):
        try:
            payload = call_llm(slot, prompt, timeout_seconds)
            return build_case_payload(
                candidate=candidate,
                payload=payload,
                case_index=case_index,
                slot=slot,
                attempt_count=attempt + 1,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"attempt {attempt + 1}: {type(exc).__name__}: {exc}")
    raise CaseGenerationError("; ".join(errors))


def build_case_payload(
    *,
    candidate: CaseCandidate,
    payload: JsonDict,
    case_index: int,
    slot: EvalLLMProviderSlot,
    attempt_count: int,
) -> JsonDict:
    """Validate LLM JSON and convert it to benchmark schema."""

    question = str(payload.get("question") or "").strip()
    gold_answer = str(payload.get("gold_answer") or payload.get("answer") or "").strip()
    if not question:
        raise ValueError("LLM payload missing question.")
    if not gold_answer:
        raise ValueError("LLM payload missing gold_answer.")
    evidence_items = normalize_evidence_items(payload.get("evidence_quotes"))
    if not evidence_items:
        raise ValueError("LLM payload missing evidence_quotes.")

    matched_sources = match_evidence_sources(candidate, evidence_items, gold_answer)
    required_chunk_ids = {chunk.chunk_id for chunk in candidate.contexts}
    matched_chunk_ids = {source["chunk_id"] for source in matched_sources}
    if len(candidate.contexts) > 1 and matched_chunk_ids != required_chunk_ids:
        missing = sorted(required_chunk_ids - matched_chunk_ids)
        raise ValueError(f"Missing evidence quotes for chunk ids: {missing}")
    if candidate.case_type == "table_context" and not any(
        chunk.contains_table for chunk in candidate.contexts
    ):
        raise ValueError("table_context candidate has no table context.")

    task_type = str(payload.get("task_type") or "policy_qa")
    risk_level = normalize_case_risk_level(
        task_type,
        str(payload.get("risk_level") or "medium"),
    )
    case_id = f"hrag_ctx_v2_{case_index:05d}"
    return {
        "id": case_id,
        "financebench_id": case_id,
        "case_type": candidate.case_type,
        "task_type": task_type,
        "risk_level": risk_level,
        "question": question,
        "gold_answer": gold_answer,
        "expected_behavior": expected_behavior_for_candidate(candidate),
        "expected_sources": matched_sources,
        "source_constraints": {
            "case_type": candidate.case_type,
            "context_count": len(candidate.contexts),
            "required_chunk_ids": sorted(required_chunk_ids),
            "required_source_paths": [
                chunk.source_path for chunk in candidate.contexts
            ],
            "must_use_all_contexts": len(candidate.contexts) > 1,
            "must_include_table_evidence": candidate.case_type == "table_context",
        },
        "scoring": {
            "max_score": 10,
            "pass_threshold": 8,
            "criteria": {
                "retrieves_all_required_contexts": 3,
                "retrieves_evidence_quotes": 2,
                "answer_faithful_to_context": 3,
                "cites_sources_correctly": 1,
                "does_not_use_outside_knowledge": 1,
            },
            "required_source_paths": [
                chunk.source_path for chunk in candidate.contexts
            ],
            "required_evidence_quotes": [
                evidence_quote["evidence_quote"]
                for source in matched_sources
                for evidence_quote in source["evidence_quotes"]
            ],
        },
        "generator": {
            "name": "health_rag_context_benchmark_v2",
            "version": "v2.1",
            "candidate_id": candidate.candidate_id,
            "slot_id": slot.slot_id,
            "provider": slot.provider,
            "model": slot.model,
            "attempt_count": attempt_count,
            "context_target_tokens": 1500,
            "llm_fallback": False,
        },
    }


def normalize_evidence_items(value: object) -> list[JsonDict]:
    """Normalize LLM evidence quote payloads to dictionaries."""

    if not isinstance(value, list):
        return []
    items: list[JsonDict] = []
    for item in value:
        if isinstance(item, str):
            items.append({"chunk_id": "", "quote": item})
        elif isinstance(item, dict):
            items.append(
                {
                    "chunk_id": str(item.get("chunk_id") or "").strip(),
                    "quote": str(item.get("quote") or item.get("evidence_quote") or "")
                    .strip(),
                }
            )
    return [item for item in items if item["quote"]]


def match_evidence_sources(
    candidate: CaseCandidate,
    evidence_items: Sequence[JsonDict],
    gold_answer: str,
) -> list[JsonDict]:
    """Match evidence quotes to source context chunks."""

    matches: list[JsonDict] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence_items:
        quote = str(item["quote"]).strip()
        match = find_quote_match(candidate.contexts, quote, str(item.get("chunk_id")))
        if match is None:
            raise ValueError(f"Evidence quote is not grounded in context: {quote[:80]}")
        chunk, grounded_quote, quote_line_start, quote_line_end = match
        key = (chunk.chunk_id, normalize_whitespace(grounded_quote))
        if key in seen:
            continue
        seen.add(key)
        matches.append(
            {
                "provider": chunk.provider,
                "source_path": chunk.source_path,
                "evidence_quote": grounded_quote,
                "line_start": quote_line_start,
                "line_end": quote_line_end,
                "chunk_id": chunk.chunk_id,
                "context_token_count": chunk.token_count,
                "contains_table": chunk.contains_table,
            }
        )
    return group_evidence_matches_by_context(matches, gold_answer)


def group_evidence_matches_by_context(
    matches: Sequence[JsonDict],
    gold_answer: str,
) -> list[JsonDict]:
    """Group evidence quotes so each expected source maps to one context."""

    grouped: dict[str, list[JsonDict]] = {}
    for match in matches:
        grouped.setdefault(str(match["chunk_id"]), []).append(match)

    sources: list[JsonDict] = []
    for chunk_id, chunk_matches in grouped.items():
        first_match = chunk_matches[0]
        evidence_quotes = [
            {
                "evidence_quote": match["evidence_quote"],
                "line_start": match["line_start"],
                "line_end": match["line_end"],
            }
            for match in chunk_matches
        ]
        sources.append(
            {
                "provider": first_match["provider"],
                "source_path": first_match["source_path"],
                "line_start": min(match["line_start"] for match in chunk_matches),
                "line_end": max(match["line_end"] for match in chunk_matches),
                "answer": gold_answer,
                "evidence_quote": first_match["evidence_quote"],
                "evidence_quotes": evidence_quotes,
                "relationship": "primary" if not sources else "supporting_context",
                "chunk_id": chunk_id,
                "context_token_count": first_match["context_token_count"],
                "contains_table": first_match["contains_table"],
            }
        )
    return sources


def find_quote_match(
    chunks: Sequence[ContextChunk],
    quote: str,
    preferred_chunk_id: str,
) -> tuple[ContextChunk, str, int, int] | None:
    """Find the context chunk and source-grounded text for an evidence quote."""

    normalized_quote = normalize_whitespace(quote)
    preferred_chunks = [
        chunk
        for chunk in chunks
        if preferred_chunk_id and chunk.chunk_id == preferred_chunk_id
    ]
    for chunk in [*preferred_chunks, *chunks]:
        if normalized_quote in normalize_whitespace(chunk.text):
            line_start, line_end = find_grounded_quote_line_range(chunk, quote)
            return chunk, quote, line_start, line_end
        snapped_match = snap_quote_to_chunk(chunk, quote)
        if snapped_match:
            snapped_quote, line_start, line_end = snapped_match
            return chunk, snapped_quote, line_start, line_end
    return None


def snap_quote_to_chunk(chunk: ContextChunk, quote: str) -> tuple[str, int, int] | None:
    """Snap a near quote to an exact source line/window from a context chunk."""

    quote_tokens = lexical_tokens(quote)
    if len(quote_tokens) < 4:
        return None
    best_score = 0.0
    best_candidate = ""
    best_line_start = chunk.start_line
    best_line_end = chunk.end_line
    for candidate, relative_start, relative_end in quote_snap_candidates(chunk.text):
        candidate_tokens = lexical_tokens(candidate)
        if not candidate_tokens:
            continue
        overlap = len(set(quote_tokens) & set(candidate_tokens))
        quote_coverage = overlap / max(1, len(set(quote_tokens)))
        candidate_coverage = overlap / max(1, len(set(candidate_tokens)))
        score = (quote_coverage * 0.7) + (candidate_coverage * 0.3)
        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_line_start = chunk.start_line + relative_start - 1
            best_line_end = chunk.start_line + relative_end - 1
    if best_score >= 0.58:
        return best_candidate.strip(), best_line_start, best_line_end
    return None


def quote_snap_candidates(text: str) -> list[tuple[str, int, int]]:
    """Return source text windows used for near-quote snapping."""

    lines = [
        (line_number, line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    candidates = [
        (line, line_number, line_number) for line_number, line in lines
    ]
    for window_size in (2, 3):
        for index in range(0, max(0, len(lines) - window_size + 1)):
            window = lines[index : index + window_size]
            candidates.append(
                (
                    " ".join(line for _, line in window),
                    window[0][0],
                    window[-1][0],
                )
            )
    return candidates


def find_grounded_quote_line_range(
    chunk: ContextChunk,
    quote: str,
) -> tuple[int, int]:
    """Find the shortest source line range containing an exact quote."""

    lines = chunk.text.splitlines()
    normalized_quote = normalize_whitespace(quote)
    for window_size in range(1, min(20, len(lines)) + 1):
        for index in range(0, len(lines) - window_size + 1):
            window_text = "\n".join(lines[index : index + window_size])
            if normalized_quote in normalize_whitespace(window_text):
                return (
                    chunk.start_line + index,
                    chunk.start_line + index + window_size - 1,
                )
    return chunk.start_line, chunk.end_line


def normalize_case_risk_level(task_type: str, risk_level: str) -> str:
    """Normalize generated risk labels for high-risk insurance tasks."""

    normalized_task_type = task_type.strip().lower()
    normalized_risk_level = risk_level.strip().lower()
    if normalized_task_type in {"claim", "exclusion"}:
        return "high"
    if normalized_task_type in {"waiting_period", "eligibility", "premium"}:
        return "medium" if normalized_risk_level == "low" else normalized_risk_level
    if normalized_risk_level in {"low", "medium", "high"}:
        return normalized_risk_level
    return "medium"


def lexical_tokens(text: str) -> list[str]:
    """Return lowercase lexical tokens for Vietnamese text matching."""

    normalized = re.sub(r"[^\wÀ-ỹ]+", " ", text.lower())
    return [token for token in normalized.split() if len(token) >= 2]


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for exact quote containment checks."""

    return re.sub(r"\s+", " ", text).strip()


def expected_behavior_for_candidate(candidate: CaseCandidate) -> str:
    """Return expected answer behavior for a case candidate."""

    if candidate.case_type == "table_context":
        return "Trả lời dựa trên dữ liệu bảng trong context và trích dẫn nguồn."
    if len(candidate.contexts) > 1:
        return "Trả lời bằng cách kết hợp đầy đủ tất cả context được yêu cầu."
    return "Trả lời đúng theo context duy nhất và trích dẫn evidence."


def run_context_benchmark_generation(
    *,
    config: ContextBenchmarkV2Config,
    slots: Sequence[EvalLLMProviderSlot],
    call_llm: LLMCall = call_llm_slot,
) -> GenerationRunResult:
    """Generate the context benchmark v2 dataset."""

    started_at = time.monotonic()
    if not slots:
        raise ValueError("At least one LLM provider slot is required.")
    ensure_directory(config.output_dir)
    chunks = load_context_chunks(
        config.input_dir,
        target_tokens=config.target_tokens,
        min_tokens=config.min_tokens,
    )
    if not chunks:
        raise ValueError(f"No context chunks found under {config.input_dir}")

    accepted_cases: list[JsonDict] = []
    failed_cases: list[JsonDict] = []
    if config.resume_partial:
        accepted_cases = read_optional_jsonl(
            config.output_dir / "health_rag_context_benchmark_v2.partial.jsonl"
        )
        failed_cases = read_optional_jsonl(
            config.output_dir / "failed_cases.partial.jsonl"
        )
    accepted_counts = dict.fromkeys(config.distribution, 0)
    accepted_counts.update(count_case_types(accepted_cases))
    submitted_count = len(accepted_cases) + len(failed_cases)
    worker_count = min(config.max_workers, len(slots))
    for round_index in range(config.max_rounds):
        remaining = {
            case_type: target_count - accepted_counts.get(case_type, 0)
            for case_type, target_count in config.distribution.items()
            if target_count - accepted_counts.get(case_type, 0) > 0
        }
        if not remaining:
            break
        candidate_distribution = oversampled_distribution(
            remaining,
            worker_count=worker_count,
        )
        candidates = build_case_candidates(
            chunks,
            distribution=candidate_distribution,
            random_seed=config.random_seed + round_index,
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures: dict[
                concurrent.futures.Future[JsonDict],
                tuple[CaseCandidate, EvalLLMProviderSlot, int],
            ] = {}
            for candidate in candidates:
                submitted_count += 1
                slot = slots[(submitted_count - 1) % len(slots)]
                future = pool.submit(
                    generate_case_for_candidate,
                    candidate=candidate,
                    case_index=submitted_count,
                    slot=slot,
                    call_llm=call_llm,
                    timeout_seconds=config.timeout_seconds,
                    max_retries=config.max_retries,
                )
                futures[future] = (candidate, slot, submitted_count)
            for future in concurrent.futures.as_completed(futures):
                candidate, slot, candidate_index = futures[future]
                try:
                    case = future.result()
                except Exception as exc:  # noqa: BLE001
                    failed_cases.append(
                        failed_case_record(candidate, slot, candidate_index, exc)
                    )
                    continue
                if not case_passes_quality_caps(
                    case,
                    accepted_cases,
                    max_provider_list_cases=config.max_provider_list_cases,
                    max_hotline_cases=config.max_hotline_cases,
                    max_low_risk_cases=config.max_low_risk_cases,
                ):
                    failed_cases.append(
                        quality_gate_failed_record(
                            candidate,
                            slot,
                            candidate_index,
                            case,
                        )
                    )
                    continue
                if accepted_counts[case["case_type"]] >= config.distribution[
                    case["case_type"]
                ]:
                    continue
                accepted_counts[case["case_type"]] += 1
                accepted_cases.append(case)
                if (
                    config.progress_every
                    and len(accepted_cases) % config.progress_every == 0
                ):
                    write_generation_checkpoint(
                        config.output_dir,
                        accepted_cases,
                        failed_cases,
                    )
                    print(
                        json.dumps(
                            {
                                "event": "case_accepted",
                                "accepted": len(accepted_cases),
                                "distribution": accepted_counts,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
            write_generation_checkpoint(config.output_dir, accepted_cases, failed_cases)

    if accepted_counts != dict(config.distribution):
        failed_cases.append(
            {
                "error": "distribution_incomplete",
                "accepted_distribution": accepted_counts,
                "target_distribution": dict(config.distribution),
            }
        )

    accepted_cases = renumber_cases(sort_cases(accepted_cases))
    sampled_chunks = sampled_context_chunks(accepted_cases, chunks)
    manifest = build_manifest(
        config=config,
        chunks=chunks,
        sampled_chunks=sampled_chunks,
        accepted_cases=accepted_cases,
        failed_cases=failed_cases,
        slots=slots,
        worker_count=worker_count,
        elapsed_seconds=time.monotonic() - started_at,
    )
    write_benchmark_outputs(
        output_dir=config.output_dir,
        cases=accepted_cases,
        sampled_chunks=sampled_chunks,
        failed_cases=failed_cases,
        manifest=manifest,
    )
    return GenerationRunResult(
        output_dir=config.output_dir,
        accepted_count=len(accepted_cases),
        failed_count=len(failed_cases),
        distribution=count_case_types(accepted_cases),
        context_chunk_count=len(chunks),
        sampled_context_chunk_count=len(sampled_chunks),
        provider_slot_count=len(slots),
        worker_count=worker_count,
        elapsed_seconds=manifest["elapsed_seconds"],
    )


def failed_case_record(
    candidate: CaseCandidate,
    slot: EvalLLMProviderSlot,
    candidate_index: int,
    exc: Exception,
) -> JsonDict:
    """Build a serializable failed candidate record."""

    return {
        "candidate_index": candidate_index,
        "candidate_id": candidate.candidate_id,
        "case_type": candidate.case_type,
        "slot_id": slot.slot_id,
        "provider": slot.provider,
        "model": slot.model,
        "error": f"{type(exc).__name__}: {exc}",
        "contexts": [
            {
                "chunk_id": chunk.chunk_id,
                "source_path": chunk.source_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "contains_table": chunk.contains_table,
            }
            for chunk in candidate.contexts
        ],
    }


def quality_gate_failed_record(
    candidate: CaseCandidate,
    slot: EvalLLMProviderSlot,
    candidate_index: int,
    case: JsonDict,
) -> JsonDict:
    """Build a failed candidate record for quality-gate rejections."""

    return {
        "candidate_index": candidate_index,
        "candidate_id": candidate.candidate_id,
        "case_type": candidate.case_type,
        "slot_id": slot.slot_id,
        "provider": slot.provider,
        "model": slot.model,
        "error": "quality_gate_rejected",
        "generated_task_type": case.get("task_type", ""),
        "generated_risk_level": case.get("risk_level", ""),
        "question": case.get("question", ""),
    }


def case_passes_quality_caps(
    case: JsonDict,
    accepted_cases: Sequence[JsonDict],
    *,
    max_provider_list_cases: int = 15,
    max_hotline_cases: int = 15,
    max_low_risk_cases: int = 45,
) -> bool:
    """Return whether a generated case fits dataset-level quality caps."""

    if (
        str(case.get("task_type") or "") == "provider_list"
        and count_matching_cases(accepted_cases, is_provider_list_case)
        >= max_provider_list_cases
    ):
        return False
    if (
        is_hotline_case(case)
        and count_matching_cases(accepted_cases, is_hotline_case)
        >= max_hotline_cases
    ):
        return False
    return not (
        str(case.get("risk_level") or "") == "low"
        and count_matching_cases(accepted_cases, is_low_risk_case)
        >= max_low_risk_cases
    )


def count_matching_cases(
    cases: Sequence[JsonDict],
    predicate: Callable[[JsonDict], bool],
) -> int:
    """Count accepted cases matching a predicate."""

    return sum(1 for case in cases if predicate(case))


def is_provider_list_case(case: JsonDict) -> bool:
    """Return whether a case is provider-list oriented."""

    return str(case.get("task_type") or "") == "provider_list"


def is_low_risk_case(case: JsonDict) -> bool:
    """Return whether a case is low risk."""

    return str(case.get("risk_level") or "") == "low"


def is_hotline_case(case: JsonDict) -> bool:
    """Return whether a case is mainly hotline/contact oriented."""

    text = f"{case.get('question', '')} {case.get('gold_answer', '')}".lower()
    hotline_terms = (
        "hotline",
        "assistance@",
        "liên hệ",
        "email",
        "số điện thoại",
        "3821-6699",
    )
    return any(term in text for term in hotline_terms)


def oversampled_distribution(
    remaining: Mapping[str, int],
    *,
    worker_count: int,
) -> dict[str, int]:
    """Return a candidate distribution that keeps workers busy during top-up."""

    return {
        case_type: remaining_count
        if remaining_count >= worker_count
        else worker_count
        for case_type, remaining_count in remaining.items()
    }


def sort_cases(cases: Sequence[JsonDict]) -> list[JsonDict]:
    """Sort cases by configured distribution order."""

    case_order = {
        case_type: index for index, case_type in enumerate(DEFAULT_DISTRIBUTION)
    }
    return sorted(
        cases,
        key=lambda case: (
            case_order.get(str(case.get("case_type")), 999),
            str(case.get("id")),
        ),
    )


def renumber_cases(cases: Sequence[JsonDict]) -> list[JsonDict]:
    """Renumber accepted cases so output IDs are contiguous."""

    renumbered: list[JsonDict] = []
    for index, case in enumerate(cases, start=1):
        case_id = f"hrag_ctx_v2_{index:05d}"
        updated = dict(case)
        updated["id"] = case_id
        updated["financebench_id"] = case_id
        renumbered.append(updated)
    return renumbered


def sampled_context_chunks(
    cases: Sequence[JsonDict],
    chunks: Sequence[ContextChunk],
) -> list[JsonDict]:
    """Return unique context chunks referenced by accepted cases."""

    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    required_ids: list[str] = []
    for case in cases:
        constraints = case.get("source_constraints", {})
        if not isinstance(constraints, dict):
            continue
        for chunk_id in constraints.get("required_chunk_ids", []):
            if chunk_id not in required_ids:
                required_ids.append(str(chunk_id))
    sampled: list[JsonDict] = []
    for chunk_id in required_ids:
        chunk = chunk_by_id.get(chunk_id)
        if chunk is None:
            continue
        sampled.append(asdict(chunk))
    return sampled


def build_manifest(
    *,
    config: ContextBenchmarkV2Config,
    chunks: Sequence[ContextChunk],
    sampled_chunks: Sequence[JsonDict],
    accepted_cases: Sequence[JsonDict],
    failed_cases: Sequence[JsonDict],
    slots: Sequence[EvalLLMProviderSlot],
    worker_count: int,
    elapsed_seconds: float,
) -> JsonDict:
    """Build a generation manifest."""

    return {
        "version": "health_rag_context_benchmark_v2",
        "input_dir": str(config.input_dir),
        "output_dir": str(config.output_dir),
        "target_tokens": config.target_tokens,
        "min_tokens": config.min_tokens,
        "random_seed": config.random_seed,
        "max_workers": config.max_workers,
        "worker_count": worker_count,
        "max_retries": config.max_retries,
        "timeout_seconds": config.timeout_seconds,
        "max_provider_list_cases": config.max_provider_list_cases,
        "max_hotline_cases": config.max_hotline_cases,
        "max_low_risk_cases": config.max_low_risk_cases,
        "target_distribution": dict(config.distribution),
        "case_count": len(accepted_cases),
        "failed_count": len(failed_cases),
        "case_distribution": count_case_types(accepted_cases),
        "context_chunk_count": len(chunks),
        "sampled_context_chunk_count": len(sampled_chunks),
        "table_context_chunk_count": sum(1 for chunk in chunks if chunk.contains_table),
        "provider_slot_count": len(slots),
        "provider_slot_counts": provider_slot_counts(slots),
        "provider_slots": [
            {"slot_id": slot.slot_id, "provider": slot.provider, "model": slot.model}
            for slot in slots
        ],
        "elapsed_seconds": round(elapsed_seconds, 3),
    }


def write_benchmark_outputs(
    *,
    output_dir: Path,
    cases: Sequence[JsonDict],
    sampled_chunks: Sequence[JsonDict],
    failed_cases: Sequence[JsonDict],
    manifest: JsonDict,
) -> None:
    """Write JSONL, CSV, manifest, and README artifacts."""

    ensure_directory(output_dir)
    write_jsonl(output_dir / "health_rag_context_benchmark_v2.jsonl", cases)
    write_jsonl(output_dir / "context_chunks.jsonl", sampled_chunks)
    write_jsonl(output_dir / "failed_cases.jsonl", failed_cases)
    write_cases_csv(output_dir / "health_rag_context_benchmark_v2.csv", cases)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_readme(output_dir, manifest)


def write_generation_checkpoint(
    output_dir: Path,
    accepted_cases: Sequence[JsonDict],
    failed_cases: Sequence[JsonDict],
) -> None:
    """Write partial generation outputs for long-running provider calls."""

    ensure_directory(output_dir)
    write_jsonl(
        output_dir / "health_rag_context_benchmark_v2.partial.jsonl",
        renumber_cases(sort_cases(accepted_cases)),
    )
    write_jsonl(output_dir / "failed_cases.partial.jsonl", failed_cases)


def write_jsonl(path: Path, rows: Sequence[JsonDict]) -> None:
    """Write dictionary rows to JSONL."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            row_json = json.dumps(row, ensure_ascii=False, sort_keys=True)
            output_file.write(row_json + "\n")


def write_cases_csv(path: Path, cases: Sequence[JsonDict]) -> None:
    """Write a spreadsheet-friendly case CSV."""

    ensure_directory(path.parent)
    fieldnames = [
        "id",
        "case_type",
        "task_type",
        "risk_level",
        "question",
        "gold_answer",
        "expected_sources",
        "source_constraints",
        "scoring",
        "generator",
    ]
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for case in cases:
            row = {field: case.get(field, "") for field in fieldnames}
            for field in (
                "expected_sources",
                "source_constraints",
                "scoring",
                "generator",
            ):
                row[field] = json.dumps(row[field], ensure_ascii=False)
            writer.writerow(row)


def write_readme(output_dir: Path, manifest: JsonDict) -> None:
    """Write a short README for generated benchmark artifacts."""

    readme = f"""# Health RAG Context Benchmark V2

This dataset contains LLM-generated Vietnamese RAG benchmark cases grounded in
large source contexts from the InsureVN health insurance Markdown corpus.

## Counts

- Cases: {manifest["case_count"]}
- Failed candidates: {manifest["failed_count"]}
- Context chunks in corpus: {manifest["context_chunk_count"]}
- Sampled context chunks: {manifest["sampled_context_chunk_count"]}
- Distribution: {json.dumps(manifest["case_distribution"], ensure_ascii=False)}

## Files

- `health_rag_context_benchmark_v2.jsonl`: canonical eval-compatible benchmark.
- `health_rag_context_benchmark_v2.csv`: spreadsheet copy.
- `context_chunks.jsonl`: unique source contexts used by accepted cases.
- `failed_cases.jsonl`: candidates that failed after configured retries.
- `manifest.json`: run configuration and provider-slot summary.

All accepted cases are generated from context chunks only. Deterministic fallback
case generation is disabled.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def verify_benchmark_output(
    output_dir: Path,
    *,
    expected_distribution: Mapping[str, int] = DEFAULT_DISTRIBUTION,
    input_dir: Path = DEFAULT_INPUT_DIR,
) -> JsonDict:
    """Verify generated benchmark artifacts and return counts."""

    benchmark_path = output_dir / "health_rag_context_benchmark_v2.jsonl"
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Missing benchmark JSONL: {benchmark_path}")
    cases = read_jsonl(benchmark_path)
    distribution = count_case_types(cases)
    errors: list[str] = []
    if distribution != dict(expected_distribution):
        errors.append(
            f"distribution mismatch: expected {dict(expected_distribution)}, "
            f"found {distribution}"
        )
    for case in cases:
        if not str(case.get("question") or "").strip():
            errors.append(f"{case.get('id')}: empty question")
        if not str(case.get("gold_answer") or "").strip():
            errors.append(f"{case.get('id')}: empty gold_answer")
        sources = case.get("expected_sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{case.get('id')}: missing expected_sources")
            continue
        errors.extend(verify_case_sources(case, sources, input_dir))
    if errors:
        raise ValueError("Benchmark verification failed:\n" + "\n".join(errors[:20]))
    return {
        "case_count": len(cases),
        "distribution": distribution,
        "path": str(benchmark_path),
        "source_validation_errors": 0,
    }


def verify_case_sources(
    case: JsonDict,
    sources: Sequence[object],
    input_dir: Path,
) -> list[str]:
    """Verify source count, chunk ids, table flags, and evidence quote spans."""

    errors: list[str] = []
    case_id = str(case.get("id") or "<missing_id>")
    constraints = case.get("source_constraints")
    if isinstance(constraints, dict):
        context_count = constraints.get("context_count")
        if isinstance(context_count, int) and len(sources) != context_count:
            errors.append(
                f"{case_id}: expected_sources count {len(sources)} does not "
                f"match context_count {context_count}"
            )
        required_chunk_ids = {
            str(chunk_id) for chunk_id in constraints.get("required_chunk_ids", [])
        }
        source_chunk_ids = {
            str(source.get("chunk_id"))
            for source in sources
            if isinstance(source, dict) and source.get("chunk_id")
        }
        if required_chunk_ids and source_chunk_ids != required_chunk_ids:
            errors.append(
                f"{case_id}: expected source chunk ids {sorted(source_chunk_ids)} "
                f"do not match required chunk ids {sorted(required_chunk_ids)}"
            )
        if constraints.get("must_include_table_evidence") and not any(
            isinstance(source, dict) and source.get("contains_table")
            for source in sources
        ):
            errors.append(f"{case_id}: table case has no table source")

    for source in sources:
        if not isinstance(source, dict):
            errors.append(f"{case_id}: malformed expected source")
            continue
        errors.extend(verify_expected_source_quotes(case_id, source, input_dir))
    return errors


def verify_expected_source_quotes(
    case_id: str,
    source: JsonDict,
    input_dir: Path,
) -> list[str]:
    """Verify evidence quotes for one expected source."""

    errors: list[str] = []
    source_path = str(source.get("source_path") or "")
    if not source_path:
        return [f"{case_id}: expected source missing source_path"]
    full_source_path = input_dir / source_path
    if not full_source_path.exists():
        return [f"{case_id}: source path does not exist: {source_path}"]
    source_lines = full_source_path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()
    for quote_item in evidence_quote_items(source):
        quote = str(quote_item.get("evidence_quote") or "")
        line_start = quote_item.get("line_start")
        line_end = quote_item.get("line_end")
        if not quote.strip():
            errors.append(f"{case_id}: empty evidence quote in {source_path}")
            continue
        if not source_line_range_is_valid(source_lines, line_start, line_end):
            errors.append(
                f"{case_id}: invalid quote line range "
                f"{line_start}-{line_end} in {source_path}"
            )
            continue
        span = "\n".join(source_lines[int(line_start) - 1 : int(line_end)])
        if normalize_whitespace(quote) not in normalize_whitespace(span):
            errors.append(
                f"{case_id}: quote not found in source lines "
                f"{line_start}-{line_end} of {source_path}"
            )
    return errors


def evidence_quote_items(source: JsonDict) -> list[JsonDict]:
    """Return nested evidence quote records for a source."""

    value = source.get("evidence_quotes")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return [
        {
            "evidence_quote": source.get("evidence_quote", ""),
            "line_start": source.get("line_start"),
            "line_end": source.get("line_end"),
        }
    ]


def source_line_range_is_valid(
    source_lines: Sequence[str],
    line_start: object,
    line_end: object,
) -> bool:
    """Return whether a line range is valid for source lines."""

    return (
        isinstance(line_start, int)
        and isinstance(line_end, int)
        and line_start >= 1
        and line_end >= line_start
        and line_end <= len(source_lines)
    )


def read_jsonl(path: Path) -> list[JsonDict]:
    """Read JSONL dictionary rows."""

    rows: list[JsonDict] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object row in {path}")
            rows.append(payload)
    return rows


def read_optional_jsonl(path: Path) -> list[JsonDict]:
    """Read JSONL rows if a checkpoint exists."""

    if not path.exists():
        return []
    return read_jsonl(path)


def count_case_types(cases: Sequence[JsonDict]) -> dict[str, int]:
    """Count case types in stable configured order."""

    counts = dict.fromkeys(DEFAULT_DISTRIBUTION, 0)
    for case in cases:
        case_type = str(case.get("case_type") or "")
        counts[case_type] = counts.get(case_type, 0) + 1
    return {case_type: count for case_type, count in counts.items() if count}


def build_chunk_id(source_path: str, chunk_index: int) -> str:
    """Build a stable chunk id for a source path and chunk index."""

    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]
    return f"{digest}:ctx:{chunk_index:04d}"
