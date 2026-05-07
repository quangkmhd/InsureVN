"""Demo LLM-guided chunk boundaries over one Markdown policy document.

The script keeps source text exact. RecursiveCharacterTextSplitter creates
baseline chunks and splits oversized atomic units; the LLM only chooses
contiguous unit ranges inside Python-computed size bands.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ollama import Client
from pydantic import BaseModel, Field, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DOCUMENT_PATH = (
    PROJECT_ROOT
    / "data/health_insurance/health_insurance_markdowns_interpreted_cleaned"
    / "aia.com.vn/2601-TCB-BH-SucKhoeTronDoi-brochure"
    / "2601-TCB-BH-SucKhoeTronDoi-brochure.md"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports/chunking_llm_boundary_demo"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
TOKEN_CHARS = 4


@dataclass(frozen=True)
class SourceUnit:
    """Atomic source unit exposed to the LLM for boundary planning."""

    unit_id: int
    start: int
    end: int
    chars: int
    tokens: int
    unit_type: str
    heading_path: str
    text: str


@dataclass(frozen=True)
class BoundaryOption:
    """Python-computed valid cut choices for a possible chunk start."""

    start_unit: int
    valid_end_units: list[int]
    preferred_end_units: list[int]
    hard_end_unit: int


@dataclass(frozen=True)
class ChunkView:
    """One output chunk with validation metadata."""

    chunk_id: str
    method: str
    start: int
    end: int
    chars: int
    tokens: int
    start_unit: int | None
    end_unit: int | None
    issues: list[str]
    text: str


@dataclass(frozen=True)
class PlannerWindow:
    """One bounded unit window sent to a single LLM planning call."""

    window_id: int
    start_unit: int
    end_unit: int
    source_chars: int
    prompt_chars: int
    status: str


class LLMBoundary(BaseModel):
    """One contiguous source-unit range selected by the LLM."""

    start_unit: int = Field(ge=1)
    end_unit: int = Field(ge=1)
    reason: str = Field(default="")


class LLMBoundaryPlan(BaseModel):
    """Structured LLM output for boundary planning."""

    chunks: list[LLMBoundary] = Field(min_length=1)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT_PATH)
    parser.add_argument("--env-path", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ollama-host", default="https://ollama.com")
    parser.add_argument("--model", default="gemma4:31b-cloud")
    parser.add_argument("--min-tokens", type=int, default=300)
    parser.add_argument("--target-tokens", type=int, default=456)
    parser.add_argument("--preferred-max-tokens", type=int, default=512)
    parser.add_argument("--hard-max-tokens", type=int, default=612)
    parser.add_argument("--max-unit-tokens", type=int, default=220)
    parser.add_argument("--planner-window-chars", type=int, default=11000)
    parser.add_argument("--max-input-chars", type=int, default=52000)
    parser.add_argument("--skip-llm", action="store_true")
    return parser.parse_args()


def estimate_tokens(text: str) -> int:
    """Estimate tokens using the benchmark's char/token heuristic."""
    return max(1, math.ceil(len(text) / TOKEN_CHARS))


def classify_unit(text: str) -> str:
    """Classify a Markdown source unit."""
    stripped = text.strip()
    if re.match(r"^#{1,6}\s+", stripped):
        return "heading"
    if "|" in stripped and "\n" in stripped:
        return "table"
    if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", stripped):
        return "list"
    return "paragraph"


def heading_title(text: str) -> str | None:
    """Return Markdown heading title if text is a heading unit."""
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", text.strip())
    if match is None:
        return None
    return match.group(2).strip()


def build_source_units(text: str, *, max_unit_tokens: int) -> list[SourceUnit]:
    """Split source text into paragraph/table units with source offsets."""
    max_unit_chars = max_unit_tokens * TOKEN_CHARS
    units: list[SourceUnit] = []
    heading_stack: dict[int, str] = {}
    paragraph_re = re.compile(r"\S[\s\S]*?(?=\n\s*\n|\Z)")

    for match in paragraph_re.finditer(text):
        block_start, block_end = match.start(), match.end()
        block_text = text[block_start:block_end].strip()
        if not block_text:
            continue

        for start, end in split_oversized_unit(
            text,
            start=block_start,
            end=block_end,
            max_unit_chars=max_unit_chars,
        ):
            unit_text = text[start:end].strip()
            if not unit_text:
                continue
            title = heading_title(unit_text)
            if title is not None:
                level = len(unit_text.lstrip().split(" ", maxsplit=1)[0])
                heading_stack[level] = title
                for stale_level in list(heading_stack):
                    if stale_level > level:
                        heading_stack.pop(stale_level, None)
            heading_path = " > ".join(
                heading_stack[level] for level in sorted(heading_stack)
            )
            units.append(
                SourceUnit(
                    unit_id=len(units) + 1,
                    start=start,
                    end=end,
                    chars=len(unit_text),
                    tokens=estimate_tokens(unit_text),
                    unit_type=classify_unit(unit_text),
                    heading_path=heading_path or "document",
                    text=unit_text,
                )
            )

    if not units and text.strip():
        units.append(
            SourceUnit(
                unit_id=1,
                start=0,
                end=len(text),
                chars=len(text.strip()),
                tokens=estimate_tokens(text),
                unit_type=classify_unit(text),
                heading_path="document",
                text=text.strip(),
            )
        )
    return units


def split_oversized_unit(
    source_text: str,
    *,
    start: int,
    end: int,
    max_unit_chars: int,
) -> list[tuple[int, int]]:
    """Split oversized blocks with RecursiveCharacterTextSplitter."""
    block_text = source_text[start:end].strip()
    if len(block_text) <= max_unit_chars:
        leading = len(source_text[start:end]) - len(source_text[start:end].lstrip())
        trailing = len(source_text[start:end]) - len(source_text[start:end].rstrip())
        return [(start + leading, end - trailing)]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_unit_chars,
        chunk_overlap=0,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    parts = [part.strip() for part in splitter.split_text(block_text) if part.strip()]
    spans: list[tuple[int, int]] = []
    cursor = start
    for part in parts:
        part_start = source_text.find(part, cursor, end)
        if part_start < 0:
            part_start = source_text.find(part, start, end)
        if part_start < 0:
            continue
        part_end = part_start + len(part)
        spans.append((part_start, part_end))
        cursor = part_end
    return spans or [(start, end)]


def build_boundary_options(
    units: list[SourceUnit],
    *,
    min_tokens: int,
    target_tokens: int,
    preferred_max_tokens: int,
    hard_max_tokens: int,
) -> list[BoundaryOption]:
    """Compute valid and preferred cut bands for every possible start unit."""
    options: list[BoundaryOption] = []
    by_index = {unit.unit_id: index for index, unit in enumerate(units)}
    for unit in units:
        start_index = by_index[unit.unit_id]
        running_tokens = 0
        valid_end_units: list[int] = []
        preferred_end_units: list[int] = []
        hard_end_unit = unit.unit_id

        for candidate in units[start_index:]:
            running_tokens += candidate.tokens
            if running_tokens <= hard_max_tokens:
                hard_end_unit = candidate.unit_id
            if min_tokens <= running_tokens <= hard_max_tokens:
                valid_end_units.append(candidate.unit_id)
            if target_tokens <= running_tokens <= preferred_max_tokens:
                preferred_end_units.append(candidate.unit_id)
            if running_tokens > hard_max_tokens:
                break

        if not valid_end_units:
            valid_end_units.append(hard_end_unit)
        if not preferred_end_units:
            preferred_end_units = list(valid_end_units)
        options.append(
            BoundaryOption(
                start_unit=unit.unit_id,
                valid_end_units=valid_end_units,
                preferred_end_units=preferred_end_units,
                hard_end_unit=hard_end_unit,
            )
        )
    return options


def build_planner_windows(
    units: list[SourceUnit],
    *,
    planner_window_chars: int,
) -> list[list[SourceUnit]]:
    """Group source units into bounded LLM planning windows."""
    windows: list[list[SourceUnit]] = []
    current_units: list[SourceUnit] = []
    current_chars = 0
    for unit in units:
        starts_major_heading = unit.unit_type == "heading" and unit.text.startswith(
            ("# ", "## ")
        )
        should_start_new_window = (
            current_units
            and current_chars + unit.chars > planner_window_chars
            and starts_major_heading
        )
        must_start_new_window = (
            current_units and current_chars + unit.chars > planner_window_chars * 1.25
        )
        if should_start_new_window or must_start_new_window:
            windows.append(current_units)
            current_units = []
            current_chars = 0

        current_units.append(unit)
        current_chars += unit.chars

    if current_units:
        windows.append(current_units)
    return windows


def build_prompt(
    *,
    units: list[SourceUnit],
    options: list[BoundaryOption],
    min_tokens: int,
    target_tokens: int,
    preferred_max_tokens: int,
    hard_max_tokens: int,
) -> str:
    """Build a source-unit boundary planning prompt."""
    unit_payload = [
        {
            "unit_id": unit.unit_id,
            "type": unit.unit_type,
            "chars": unit.chars,
            "tokens": unit.tokens,
            "heading_path": unit.heading_path,
            "text": unit.text,
        }
        for unit in units
    ]
    option_payload = [
        {
            "start_unit": option.start_unit,
            "valid_end_units": option.valid_end_units,
            "preferred_end_units": option.preferred_end_units,
            "hard_end_unit": option.hard_end_unit,
        }
        for option in options
    ]
    return (
        "You choose retrieval chunk boundaries for Vietnamese insurance Markdown.\n"
        "Return only JSON matching the schema. Do not copy or rewrite source text.\n"
        "Rules:\n"
        "- Output contiguous ranges: chunk 1 starts at unit 1, "
        "next starts at previous end + 1.\n"
        "- Cover every unit exactly once, with no gaps and no overlap.\n"
        f"- Each chunk should be {min_tokens}-{hard_max_tokens} estimated tokens.\n"
        f"- Prefer {target_tokens}-{preferred_max_tokens} estimated tokens "
        "when the text allows it.\n"
        "- Prefer end_unit values listed in preferred_end_units for that start_unit.\n"
        "- Use valid_end_units when preferred boundaries would split a topic badly.\n"
        "- Keep headings with their body, keep tables with nearby explanation text.\n"
        "- If a single unit is large, choose that unit alone.\n\n"
        "<boundary_options_json>\n"
        f"{json.dumps(option_payload, ensure_ascii=False)}\n"
        "</boundary_options_json>\n\n"
        "<source_units_json>\n"
        f"{json.dumps(unit_payload, ensure_ascii=False)}\n"
        "</source_units_json>"
    )


def ollama_boundary_plan(
    *,
    prompt: str,
    env_path: Path,
    host: str,
    model: str,
) -> tuple[LLMBoundaryPlan, str]:
    """Call Ollama with structured output and return the parsed boundary plan."""
    env = dotenv_values(env_path)
    api_key = (
        os.getenv("OLLAMA_API_KEY")
        or env.get("OLLAMA_API_KEY")
        or first_csv_value(env.get("KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS"))
        or env.get("KG_SCHEMA_DISCOVERY_OLLAMA_API_KEY_1")
        or env.get("LLM_API_KEY")
    )
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    client = Client(host=host, headers=headers)
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format=LLMBoundaryPlan.model_json_schema(),
        options={
            "temperature": 0,
            "num_ctx": 65536,
            "num_predict": 4096,
        },
    )
    response_text = response.message.content
    return parse_boundary_plan_response(response_text), response_text


def parse_boundary_plan_response(response_text: str) -> LLMBoundaryPlan:
    """Parse robust JSON boundary output from an LLM response."""
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        payload = parse_first_json_value(response_text)

    if isinstance(payload, list):
        payload = {"chunks": payload}
    if not isinstance(payload, dict):
        raise ValueError("LLM boundary response must be a JSON object or list.")

    chunks = payload.get("chunks")
    if isinstance(chunks, list):
        normalized_chunks: list[dict[str, Any]] = []
        for item in chunks:
            if not isinstance(item, dict):
                raise ValueError("LLM boundary chunk item must be an object.")
            normalized_chunks.append(
                {
                    "start_unit": item.get("start_unit", item.get("start")),
                    "end_unit": item.get("end_unit", item.get("end")),
                    "reason": item.get("reason", ""),
                }
            )
        payload = {"chunks": normalized_chunks}
    return LLMBoundaryPlan.model_validate(payload)


def parse_first_json_value(response_text: str) -> Any:
    """Parse the first JSON object or array embedded in response text."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", response_text):
        try:
            value, _end = decoder.raw_decode(response_text[match.start() :])
        except json.JSONDecodeError:
            continue
        return value
    raise ValueError("LLM boundary response did not contain JSON.")


def first_csv_value(value: str | None) -> str | None:
    """Return the first non-empty CSV entry."""
    if not value:
        return None
    for item in value.split(","):
        stripped = item.strip()
        if stripped:
            return stripped
    return None


def chunks_from_plan(
    *,
    source_text: str,
    units: list[SourceUnit],
    options: list[BoundaryOption],
    plan: LLMBoundaryPlan,
    min_tokens: int,
    preferred_max_tokens: int,
    hard_max_tokens: int,
) -> list[ChunkView]:
    """Validate LLM ranges and convert them to exact source chunks."""
    units_by_id = {unit.unit_id: unit for unit in units}
    options_by_start = {option.start_unit: option for option in options}
    chunks: list[ChunkView] = []
    expected_start_unit = units[0].unit_id

    for index, boundary in enumerate(plan.chunks):
        issues: list[str] = []
        if boundary.start_unit != expected_start_unit:
            raise ValueError(
                f"Chunk {index} must start at unit {expected_start_unit}, "
                f"got {boundary.start_unit}."
            )
        if boundary.end_unit < boundary.start_unit:
            raise ValueError(f"Chunk {index} has end before start.")
        if (
            boundary.start_unit not in units_by_id
            or boundary.end_unit not in units_by_id
        ):
            raise ValueError(f"Chunk {index} references an unknown unit.")

        start_unit = units_by_id[boundary.start_unit]
        end_unit = units_by_id[boundary.end_unit]
        option = options_by_start[boundary.start_unit]
        if boundary.end_unit not in option.valid_end_units:
            issues.append("outside_python_valid_band")
        if boundary.reason.startswith("snapped_to_valid_band"):
            issues.append("snapped_to_valid_band")
        if boundary.reason.startswith("optimized_to_valid_band"):
            issues.append("optimized_to_valid_band")
        text = source_text[start_unit.start : end_unit.end].strip()
        tokens = estimate_tokens(text)
        if tokens < min_tokens and boundary.end_unit != units[-1].unit_id:
            issues.append("below_min_tokens")
        if tokens > preferred_max_tokens:
            issues.append("above_preferred_max")
        if tokens > hard_max_tokens:
            issues.append("above_hard_max")

        chunks.append(
            ChunkView(
                chunk_id=f"llm-boundary:{index}",
                method="llm_boundary",
                start=start_unit.start,
                end=end_unit.end,
                chars=len(text),
                tokens=tokens,
                start_unit=boundary.start_unit,
                end_unit=boundary.end_unit,
                issues=issues,
                text=text,
            )
        )
        expected_start_unit = boundary.end_unit + 1

    if expected_start_unit <= units[-1].unit_id:
        raise ValueError(f"LLM plan omitted unit {expected_start_unit} and later.")
    return chunks


def snap_plan_to_valid_options(
    *,
    plan: LLMBoundaryPlan,
    units: list[SourceUnit],
    options: list[BoundaryOption],
    min_tokens: int,
    target_tokens: int,
    preferred_max_tokens: int,
    hard_max_tokens: int,
) -> LLMBoundaryPlan:
    """Force LLM boundaries onto an optimized valid-cut path."""
    options_by_start = {option.start_unit: option for option in options}
    requested_by_start = {
        boundary.start_unit: boundary.end_unit for boundary in plan.chunks
    }
    unit_ids = [unit.unit_id for unit in units]
    id_to_position = {unit.unit_id: index for index, unit in enumerate(units)}
    token_prefix = [0]
    for unit in units:
        token_prefix.append(token_prefix[-1] + unit.tokens)
    final_unit = units[-1].unit_id

    def range_tokens(start_unit: int, end_unit: int) -> int:
        start_position = id_to_position[start_unit]
        end_position = id_to_position[end_unit]
        return token_prefix[end_position + 1] - token_prefix[start_position]

    memo: dict[int, tuple[float, list[LLMBoundary]]] = {}

    def best_path(start_unit: int) -> tuple[float, list[LLMBoundary]]:
        if start_unit > final_unit:
            return 0.0, []
        if start_unit in memo:
            return memo[start_unit]

        option = options_by_start[start_unit]
        requested_end = requested_by_start.get(start_unit)
        best_cost = float("inf")
        best_boundaries: list[LLMBoundary] = []

        for end_unit in option.valid_end_units:
            next_start = end_unit + 1
            if next_start <= final_unit and next_start not in options_by_start:
                continue
            chunk_tokens = range_tokens(start_unit, end_unit)
            size_cost = boundary_size_cost(
                tokens=chunk_tokens,
                min_tokens=min_tokens,
                target_tokens=target_tokens,
                preferred_max_tokens=preferred_max_tokens,
                hard_max_tokens=hard_max_tokens,
            )
            semantic_cost = 0.0
            reason = "filled_missing_boundary_from_valid_band"
            if requested_end is not None:
                if requested_end == end_unit:
                    reason = "llm boundary inside valid band"
                    semantic_cost = -0.5
                else:
                    reason = "optimized_to_valid_band"
                    semantic_cost = min(abs(end_unit - requested_end), 20) * 0.25

            rest_cost, rest_boundaries = best_path(next_start)
            total_cost = size_cost + semantic_cost + rest_cost + 0.01
            if total_cost < best_cost:
                best_cost = total_cost
                best_boundaries = [
                    LLMBoundary(
                        start_unit=start_unit,
                        end_unit=end_unit,
                        reason=reason,
                    ),
                    *rest_boundaries,
                ]

        memo[start_unit] = best_cost, best_boundaries
        return memo[start_unit]

    _cost, boundaries = best_path(unit_ids[0])
    if not boundaries:
        return deterministic_band_plan(units, options)

    return LLMBoundaryPlan(chunks=boundaries)


def boundary_size_cost(
    *,
    tokens: int,
    min_tokens: int,
    target_tokens: int,
    preferred_max_tokens: int,
    hard_max_tokens: int,
) -> float:
    """Score a valid boundary by closeness to the preferred size band."""
    if tokens < min_tokens:
        return float((min_tokens - tokens) * 20)
    if tokens > hard_max_tokens:
        return float((tokens - hard_max_tokens) * 20)
    if target_tokens <= tokens <= preferred_max_tokens:
        return 0.0
    if tokens < target_tokens:
        return (target_tokens - tokens) / 20
    return (tokens - preferred_max_tokens) / 20


def merge_short_chunks(
    *,
    source_text: str,
    chunks: list[ChunkView],
    min_tokens: int,
    hard_max_tokens: int,
) -> list[ChunkView]:
    """Merge below-min chunks across planner-window seams when possible."""
    repaired: list[ChunkView] = []
    index = 0
    while index < len(chunks):
        current = chunks[index]
        if current.tokens >= min_tokens or index == len(chunks) - 1:
            repaired.append(current)
            index += 1
            continue

        next_chunk = chunks[index + 1]
        merged_text = source_text[current.start : next_chunk.end].strip()
        merged_tokens = estimate_tokens(merged_text)
        if merged_tokens <= hard_max_tokens:
            repaired.append(
                ChunkView(
                    chunk_id=f"llm-boundary-repaired:{len(repaired)}",
                    method="llm_boundary",
                    start=current.start,
                    end=next_chunk.end,
                    chars=len(merged_text),
                    tokens=merged_tokens,
                    start_unit=current.start_unit,
                    end_unit=next_chunk.end_unit,
                    issues=sorted(
                        {
                            *current.issues,
                            *next_chunk.issues,
                            "merged_below_min_with_next",
                        }
                    ),
                    text=merged_text,
                )
            )
            index += 2
            continue

        repaired.append(current)
        index += 1

    return [
        ChunkView(
            chunk_id=f"llm-boundary:{index}",
            method=chunk.method,
            start=chunk.start,
            end=chunk.end,
            chars=chunk.chars,
            tokens=chunk.tokens,
            start_unit=chunk.start_unit,
            end_unit=chunk.end_unit,
            issues=chunk.issues,
            text=chunk.text,
        )
        for index, chunk in enumerate(repaired)
    ]


def recursive_baseline_chunks(
    *,
    source_text: str,
    target_tokens: int,
    overlap_tokens: int = 0,
) -> list[ChunkView]:
    """Split source with RecursiveCharacterTextSplitter as a baseline."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=target_tokens * TOKEN_CHARS,
        chunk_overlap=overlap_tokens * TOKEN_CHARS,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    parts = [part.strip() for part in splitter.split_text(source_text) if part.strip()]
    chunks: list[ChunkView] = []
    cursor = 0
    for index, part in enumerate(parts):
        start = source_text.find(part, cursor)
        if start < 0:
            start = source_text.find(part)
        if start < 0:
            start = cursor
        end = start + len(part)
        cursor = max(cursor, end)
        chunks.append(
            ChunkView(
                chunk_id=f"recursive:{index}",
                method="recursive",
                start=start,
                end=end,
                chars=len(part),
                tokens=estimate_tokens(part),
                start_unit=None,
                end_unit=None,
                issues=[],
                text=part,
            )
        )
    return chunks


def deterministic_band_plan(
    units: list[SourceUnit],
    options: list[BoundaryOption],
) -> LLMBoundaryPlan:
    """Fallback plan using the middle preferred cut for each start unit."""
    options_by_start = {option.start_unit: option for option in options}
    boundaries: list[LLMBoundary] = []
    start_unit = units[0].unit_id
    while start_unit <= units[-1].unit_id:
        option = options_by_start[start_unit]
        candidate_units = option.preferred_end_units or option.valid_end_units
        end_unit = candidate_units[len(candidate_units) // 2]
        boundaries.append(
            LLMBoundary(
                start_unit=start_unit,
                end_unit=end_unit,
                reason="deterministic fallback picked the middle preferred cut",
            )
        )
        start_unit = end_unit + 1
    return LLMBoundaryPlan(chunks=boundaries)


def summarize_chunks(chunks: list[ChunkView]) -> dict[str, Any]:
    """Return aggregate chunk statistics."""
    tokens = [chunk.tokens for chunk in chunks]
    if not tokens:
        return {
            "chunk_count": 0,
            "avg_tokens": 0,
            "median_tokens": 0,
            "min_tokens": 0,
            "max_tokens": 0,
            "issue_count": 0,
        }
    return {
        "chunk_count": len(chunks),
        "avg_tokens": round(sum(tokens) / len(tokens), 2),
        "median_tokens": round(statistics.median(tokens), 2),
        "min_tokens": min(tokens),
        "max_tokens": max(tokens),
        "issue_count": sum(1 for chunk in chunks if chunk.issues),
    }


def write_outputs(
    *,
    output_dir: Path,
    document_path: Path,
    units: list[SourceUnit],
    options: list[BoundaryOption],
    planner_windows: list[PlannerWindow],
    recursive_chunks: list[ChunkView],
    llm_chunks: list[ChunkView],
    llm_raw_responses: list[str],
    llm_status: str,
    settings: dict[str, Any],
) -> tuple[Path, Path]:
    """Write JSON and Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "aia_2601_llm_boundary_chunks.json"
    markdown_path = output_dir / "aia_2601_llm_boundary_chunks.md"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "document_path": str(document_path),
        "settings": settings,
        "llm_status": llm_status,
        "unit_count": len(units),
        "planner_windows": [asdict(window) for window in planner_windows],
        "boundary_options": [asdict(option) for option in options],
        "summaries": {
            "recursive": summarize_chunks(recursive_chunks),
            "llm_boundary": summarize_chunks(llm_chunks),
        },
        "units": [asdict(unit) for unit in units],
        "chunks": {
            "recursive": [asdict(chunk) for chunk in recursive_chunks],
            "llm_boundary": [asdict(chunk) for chunk in llm_chunks],
        },
        "llm_raw_responses": llm_raw_responses,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    markdown_path.write_text(render_markdown_report(payload), "utf-8")
    return json_path, markdown_path


def render_markdown_report(payload: dict[str, Any]) -> str:
    """Render a compact human-readable report."""
    settings = payload["settings"]
    recursive_summary = payload["summaries"]["recursive"]
    llm_summary = payload["summaries"]["llm_boundary"]
    lines = [
        "# AIA LLM Boundary Chunking Demo",
        "",
        f"- Document: `{payload['document_path']}`",
        f"- LLM status: `{payload['llm_status']}`",
        f"- Units exposed to planner: `{payload['unit_count']}`",
        f"- Planner windows: `{len(payload['planner_windows'])}`",
        (
            f"- Target band: `{settings['min_tokens']}-"
            f"{settings['hard_max_tokens']}` estimated tokens"
        ),
        (
            f"- Preferred band: `{settings['target_tokens']}-"
            f"{settings['preferred_max_tokens']}` estimated tokens"
        ),
        "- Token estimate: `ceil(chars / 4)`",
        "",
        "## Summary",
        "",
        "| Method | Chunks | Avg tok | Median tok | Min tok | Max tok | Issue chunks |",
        "|---|---:|---:|---:|---:|---:|---:|",
        summary_row("RecursiveCharacterTextSplitter", recursive_summary),
        summary_row("LLM boundary planner", llm_summary),
        "",
        "## First LLM Boundary Chunks",
        "",
        "| # | Units | Chars | Tokens | Issues | Preview |",
        "|---:|---|---:|---:|---|---|",
    ]
    for index, chunk in enumerate(payload["chunks"]["llm_boundary"][:30], start=1):
        preview = preview_text(chunk["text"], 160)
        issues = ", ".join(chunk["issues"]) if chunk["issues"] else "-"
        lines.append(
            "| "
            f"{index} | {chunk['start_unit']}-{chunk['end_unit']} | "
            f"{chunk['chars']} | {chunk['tokens']} | {issues} | {preview} |"
        )
    lines.extend(
        [
            "",
            "## How To Read This",
            "",
            "- Recursive baseline cuts by size/separators only.",
            (
                "- LLM boundary planner receives source units plus "
                "Python-computed valid cut bands."
            ),
            (
                "- The LLM returns unit ranges only; final chunk text is sliced "
                "from the original Markdown."
            ),
            (
                "- `outside_python_valid_band`, `below_min_tokens`, or "
                "`above_hard_max` mean the validator caught a boundary problem."
            ),
            "",
            "## Command",
            "",
            "```bash",
            "python scripts/08_chunking_compare/llm_boundary_chunking_demo.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def summary_row(name: str, summary: dict[str, Any]) -> str:
    """Format one summary table row."""
    return (
        f"| {name} | {summary['chunk_count']} | {summary['avg_tokens']} | "
        f"{summary['median_tokens']} | {summary['min_tokens']} | "
        f"{summary['max_tokens']} | {summary['issue_count']} |"
    )


def preview_text(text: str, limit: int) -> str:
    """Return Markdown-table-safe preview text."""
    preview = re.sub(r"\s+", " ", text).strip()
    preview = preview.replace("|", "\\|")
    if len(preview) > limit:
        return preview[: limit - 3] + "..."
    return preview


def main() -> None:
    """Run the demo and write reports."""
    args = parse_args()
    started = time.perf_counter()
    source_text = args.document.read_text(encoding="utf-8")
    units = build_source_units(source_text, max_unit_tokens=args.max_unit_tokens)
    unit_windows = build_planner_windows(
        units,
        planner_window_chars=args.planner_window_chars,
    )
    all_options: list[BoundaryOption] = []
    planner_windows: list[PlannerWindow] = []
    llm_raw_responses: list[str] = []
    llm_chunks: list[ChunkView] = []
    fallback_windows = 0

    for window_index, window_units in enumerate(unit_windows):
        options = build_boundary_options(
            window_units,
            min_tokens=args.min_tokens,
            target_tokens=args.target_tokens,
            preferred_max_tokens=args.preferred_max_tokens,
            hard_max_tokens=args.hard_max_tokens,
        )
        prompt = build_prompt(
            units=window_units,
            options=options,
            min_tokens=args.min_tokens,
            target_tokens=args.target_tokens,
            preferred_max_tokens=args.preferred_max_tokens,
            hard_max_tokens=args.hard_max_tokens,
        )
        all_options.extend(options)
        status = "ollama"
        try:
            if args.skip_llm:
                raise RuntimeError("--skip-llm requested")
            if len(prompt) > args.max_input_chars:
                raise ValueError(
                    f"Prompt is {len(prompt)} chars, above {args.max_input_chars}."
                )
            plan, llm_raw_response = ollama_boundary_plan(
                prompt=prompt,
                env_path=args.env_path,
                host=args.ollama_host,
                model=args.model,
            )
        except (RuntimeError, ValidationError, ValueError, Exception) as exc:
            fallback_windows += 1
            status = f"fallback:{type(exc).__name__}:{str(exc)[:140]}"
            plan = deterministic_band_plan(window_units, options)
            llm_raw_response = plan.model_dump_json()

        plan = snap_plan_to_valid_options(
            plan=plan,
            units=window_units,
            options=options,
            min_tokens=args.min_tokens,
            target_tokens=args.target_tokens,
            preferred_max_tokens=args.preferred_max_tokens,
            hard_max_tokens=args.hard_max_tokens,
        )

        llm_raw_responses.append(llm_raw_response)
        planner_windows.append(
            PlannerWindow(
                window_id=window_index + 1,
                start_unit=window_units[0].unit_id,
                end_unit=window_units[-1].unit_id,
                source_chars=sum(unit.chars for unit in window_units),
                prompt_chars=len(prompt),
                status=status,
            )
        )
        llm_chunks.extend(
            chunks_from_plan(
                source_text=source_text,
                units=window_units,
                options=options,
                plan=plan,
                min_tokens=args.min_tokens,
                preferred_max_tokens=args.preferred_max_tokens,
                hard_max_tokens=args.hard_max_tokens,
            )
        )

    llm_chunks = merge_short_chunks(
        source_text=source_text,
        chunks=llm_chunks,
        min_tokens=args.min_tokens,
        hard_max_tokens=args.hard_max_tokens,
    )
    recursive_chunks = recursive_baseline_chunks(
        source_text=source_text,
        target_tokens=args.target_tokens,
        overlap_tokens=0,
    )
    settings = {
        "model": args.model,
        "ollama_host": args.ollama_host,
        "min_tokens": args.min_tokens,
        "target_tokens": args.target_tokens,
        "preferred_max_tokens": args.preferred_max_tokens,
        "hard_max_tokens": args.hard_max_tokens,
        "max_unit_tokens": args.max_unit_tokens,
        "planner_window_chars": args.planner_window_chars,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    llm_status = (
        f"windows={len(unit_windows)} "
        f"ollama_windows={len(unit_windows) - fallback_windows} "
        f"fallback_windows={fallback_windows}"
    )
    json_path, markdown_path = write_outputs(
        output_dir=args.output_dir,
        document_path=args.document,
        units=units,
        options=all_options,
        planner_windows=planner_windows,
        recursive_chunks=recursive_chunks,
        llm_chunks=llm_chunks,
        llm_raw_responses=llm_raw_responses,
        llm_status=llm_status,
        settings=settings,
    )
    print(
        json.dumps({"json": str(json_path), "markdown": str(markdown_path)}, indent=2)
    )


if __name__ == "__main__":
    main()
