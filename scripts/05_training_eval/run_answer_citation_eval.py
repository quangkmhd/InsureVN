"""Run answer and citation evaluation over persisted retrieval results."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.eval.config import (
    DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS,
    DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL,
    DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER,
    DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS,
)
from src.eval.llamaindex_llms import build_markdown_element_llm
from src.eval.llm_provider_slots import EvalLLMProviderSlot, provider_slot_counts

DEFAULT_RETRIEVAL_EVAL_DIR = (
    PROJECT_ROOT
    / "data"
    / "eval_runs"
    / "20260510_qwen_full_folder_filtered_rerank_eval"
)
DEFAULT_BENCHMARK_DIR = (
    PROJECT_ROOT
    / "data"
    / "health_insurance"
    / "health_insurance_markdowns_interpreted_cleaned"
    / "benchmark"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "eval_runs" / "20260510_answer_citation_eval"
)
DEFAULT_SCENARIO = "hybrid_company_filter_rerank"
DEFAULT_TOP_CONTEXTS = 5
DEFAULT_MAX_CONTEXT_CHARS_PER_ITEM = 900
DEFAULT_MAX_TOTAL_CONTEXT_CHARS = 4500
DEFAULT_SUCCESS_THRESHOLD = 0.65
GENERIC_EXPECTED_ANSWER_PREFIX = "trả lời dựa trên evidence_quote"
JsonDict = dict[str, Any]


@dataclass(frozen=True)
class AnswerBenchmarkCase:
    """One benchmark case for answer-level evaluation."""

    case_id: str
    benchmark_file: str
    benchmark_version: str
    query: str
    expected_answer: str
    source_path: str
    source_line: int | None
    provider: str
    difficulty: str
    task_type: str
    evidence_quote: str
    expected_evidence: tuple[str, ...]
    must_cite_source: bool
    risk: str


@dataclass(frozen=True)
class RetrievedContext:
    """One retrieved context item exposed to the answer generator."""

    citation_id: str
    rank: int
    source_path: str
    document_id: str
    document_name: str
    section_heading: str
    text: str
    source_match: bool
    quote_match: bool
    score: float | None


@dataclass(frozen=True)
class AnswerEvalConfig:
    """Configuration for answer and citation evaluation."""

    retrieval_eval_dir: Path
    benchmark_dir: Path
    output_dir: Path
    scenario: str = DEFAULT_SCENARIO
    limit_cases: int | None = None
    top_contexts: int = DEFAULT_TOP_CONTEXTS
    max_context_chars_per_item: int = DEFAULT_MAX_CONTEXT_CHARS_PER_ITEM
    max_total_context_chars: int = DEFAULT_MAX_TOTAL_CONTEXT_CHARS
    generation_mode: str = "llm"
    threshold: float = DEFAULT_SUCCESS_THRESHOLD
    llm_provider: str = DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER
    gemini_model: str = DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL
    gemini_api_keys: tuple[str, ...] = DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS
    provider_slots: tuple[EvalLLMProviderSlot, ...] = (
        DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS
    )
    request_timeout_seconds: float = min(
        DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS, 45.0
    )
    max_slot_attempts: int = DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS


@dataclass(frozen=True)
class AnswerEvalResult:
    """One answer-level evaluation result."""

    case_id: str
    benchmark_file: str
    benchmark_version: str
    scenario_name: str
    provider: str
    difficulty: str
    task_type: str
    risk: str
    query: str
    expected_source_path: str
    expected_source_in_context: bool
    expected_source_cited: bool
    answer_has_citation: bool
    valid_citation_rate: float
    citation_coverage: float
    answer_gold_token_recall: float
    expected_evidence_phrase_recall: float | None
    answer_context_token_precision: float
    numeric_claim_support: float
    unsupported_numeric_claim_count: int
    answer_quality_score: float
    success: bool
    threshold: float
    retrieved_context_count: int
    cited_context_ids: str
    generation_mode: str
    generation_status: str
    generation_latency_ms: float
    generation_error: str
    answer: str


def main() -> int:
    """Run answer and citation evaluation and persist artifacts."""

    args = parse_args()
    config = AnswerEvalConfig(
        retrieval_eval_dir=args.retrieval_eval_dir.resolve(),
        benchmark_dir=args.benchmark_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        scenario=args.scenario,
        limit_cases=args.limit_cases if args.limit_cases > 0 else None,
        top_contexts=args.top_contexts,
        max_context_chars_per_item=args.max_context_chars_per_item,
        max_total_context_chars=args.max_total_context_chars,
        generation_mode=args.generation_mode,
        threshold=args.threshold,
        request_timeout_seconds=args.request_timeout_seconds,
        max_slot_attempts=args.max_slot_attempts,
    )
    output_dir = run_answer_citation_eval(config)
    print(output_dir)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retrieval-eval-dir",
        type=Path,
        default=DEFAULT_RETRIEVAL_EVAL_DIR,
    )
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument(
        "--limit-cases",
        type=int,
        default=0,
        help="Limit cases for smoke runs. Use 0 for all.",
    )
    parser.add_argument("--top-contexts", type=int, default=DEFAULT_TOP_CONTEXTS)
    parser.add_argument(
        "--max-context-chars-per-item",
        type=int,
        default=DEFAULT_MAX_CONTEXT_CHARS_PER_ITEM,
    )
    parser.add_argument(
        "--max-total-context-chars",
        type=int,
        default=DEFAULT_MAX_TOTAL_CONTEXT_CHARS,
    )
    parser.add_argument(
        "--generation-mode",
        choices=("llm", "extractive"),
        default="llm",
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_SUCCESS_THRESHOLD)
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=min(DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS, 45.0),
    )
    parser.add_argument(
        "--max-slot-attempts",
        type=int,
        default=DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    )
    args = parser.parse_args()
    for option_name in (
        "top_contexts",
        "max_context_chars_per_item",
        "max_total_context_chars",
    ):
        if getattr(args, option_name) < 1:
            option = option_name.replace("_", "-")
            parser.error(f"--{option} must be greater than zero.")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be in [0, 1].")
    return args


def run_answer_citation_eval(config: AnswerEvalConfig) -> Path:
    """Run answer generation and deterministic answer/citation scoring."""

    config.output_dir.mkdir(parents=True, exist_ok=True)
    cases = load_benchmark_cases(config.benchmark_dir)
    if config.limit_cases is not None:
        cases = cases[: config.limit_cases]
    retrievals_by_case = load_retrieval_contexts(
        retrieval_eval_dir=config.retrieval_eval_dir,
        scenario=config.scenario,
        top_contexts=config.top_contexts,
    )
    answer_llm = build_answer_llm(config)
    results: list[AnswerEvalResult] = []
    for case in cases:
        contexts = retrievals_by_case.get(case.case_id, [])
        answer, status, error, latency_ms, generation_mode = generate_answer(
            config=config,
            answer_llm=answer_llm,
            case=case,
            contexts=contexts,
        )
        result = evaluate_generated_answer(
            case=case,
            scenario_name=config.scenario,
            contexts=contexts,
            answer=answer,
            generation_mode=generation_mode,
            generation_status=status,
            generation_latency_ms=latency_ms,
            generation_error=error,
            threshold=config.threshold,
        )
        results.append(result)
        write_outputs(config, results)
    write_outputs(config, results)
    return config.output_dir


def load_benchmark_cases(benchmark_dir: Path) -> list[AnswerBenchmarkCase]:
    """Load all benchmark JSONL cases from a directory."""

    benchmark_paths = sorted(benchmark_dir.glob("*.jsonl"))
    if not benchmark_paths:
        raise ValueError(f"No benchmark JSONL files found in {benchmark_dir}.")
    cases: list[AnswerBenchmarkCase] = []
    for path in benchmark_paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                case_id = str(payload.get("id") or f"{path.stem}:{line_number}")
                cases.append(
                    AnswerBenchmarkCase(
                        case_id=case_id,
                        benchmark_file=path.name,
                        benchmark_version=str(
                            payload.get("benchmark_version") or path.stem
                        ),
                        query=str(payload.get("query") or "").strip(),
                        expected_answer=str(
                            payload.get("expected_answer") or ""
                        ).strip(),
                        source_path=str(payload.get("source_path") or "").strip(),
                        source_line=optional_int(payload.get("source_line")),
                        provider=str(
                            payload.get("provider")
                            or provider_from_source_path(payload.get("source_path"))
                        ),
                        difficulty=str(payload.get("difficulty") or "").strip(),
                        task_type=str(payload.get("task_type") or "").strip(),
                        evidence_quote=str(payload.get("evidence_quote") or "").strip(),
                        expected_evidence=tuple(
                            str(value).strip()
                            for value in payload.get("expected_evidence") or []
                            if str(value).strip()
                        ),
                        must_cite_source=bool(payload.get("must_cite_source", True)),
                        risk=str(payload.get("risk") or "").strip(),
                    )
                )
    validate_cases(cases)
    return cases


def validate_cases(cases: list[AnswerBenchmarkCase]) -> None:
    """Validate required benchmark fields."""

    for case in cases:
        if not case.case_id or not case.query or not case.source_path:
            raise ValueError(f"Invalid benchmark case: {case.case_id!r}.")


def load_retrieval_contexts(
    *,
    retrieval_eval_dir: Path,
    scenario: str,
    top_contexts: int,
) -> dict[str, list[RetrievedContext]]:
    """Load retrieved contexts by case for one scenario."""

    retrieval_path = retrieval_eval_dir / "retrievals.jsonl"
    if not retrieval_path.exists():
        raise FileNotFoundError(retrieval_path)
    rows_by_case: dict[str, list[JsonDict]] = {}
    with retrieval_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if str(row.get("scenario_name")) != scenario:
                continue
            if row.get("stage") not in {None, "final"}:
                continue
            rows_by_case.setdefault(str(row.get("case_id")), []).append(row)

    contexts_by_case: dict[str, list[RetrievedContext]] = {}
    for case_id, rows in rows_by_case.items():
        sorted_rows = sorted(rows, key=lambda item: int(item.get("rank") or 999999))
        contexts_by_case[case_id] = [
            context_from_row(index=index, row=row)
            for index, row in enumerate(sorted_rows[:top_contexts], start=1)
        ]
    return contexts_by_case


def context_from_row(index: int, row: JsonDict) -> RetrievedContext:
    """Convert one retrieval row to a context item."""

    return RetrievedContext(
        citation_id=f"S{index}",
        rank=int(row.get("rank") or index),
        source_path=str(row.get("source_path") or ""),
        document_id=str(row.get("document_id") or ""),
        document_name=str(row.get("document_name") or ""),
        section_heading=str(row.get("section_heading") or ""),
        text=str(row.get("content_preview") or ""),
        source_match=bool(row.get("source_match")),
        quote_match=bool(row.get("quote_match")),
        score=optional_float(row.get("score")),
    )


def build_answer_llm(config: AnswerEvalConfig) -> Any | None:
    """Build the answer-generation LLM, or return None for extractive mode."""

    if config.generation_mode == "extractive":
        return None
    return build_markdown_element_llm(
        provider=config.llm_provider,
        gemini_model=config.gemini_model,
        gemini_api_keys=config.gemini_api_keys,
        provider_slots=config.provider_slots,
        request_timeout_seconds=config.request_timeout_seconds,
        max_slot_attempts=config.max_slot_attempts,
    )


def generate_answer(
    *,
    config: AnswerEvalConfig,
    answer_llm: Any | None,
    case: AnswerBenchmarkCase,
    contexts: list[RetrievedContext],
) -> tuple[str, str, str, float, str]:
    """Generate one answer, falling back to extractive mode if LLM generation fails."""

    started_at = time.perf_counter()
    if config.generation_mode == "extractive" or answer_llm is None:
        answer = build_extractive_answer(contexts=contexts)
        return answer, "completed", "", elapsed_ms(started_at), "extractive"
    try:
        prompt = build_answer_prompt(config=config, case=case, contexts=contexts)
        response = answer_llm.complete(prompt, temperature=0.0, max_tokens=512)
        answer = str(getattr(response, "text", response)).strip()
        if not answer:
            raise ValueError("LLM returned a blank answer.")
        return answer, "completed", "", elapsed_ms(started_at), "llm"
    except Exception as exc:
        answer = build_extractive_answer(contexts=contexts)
        return (
            answer,
            "fallback_extractive",
            f"{type(exc).__name__}: {exc}"[:1000],
            elapsed_ms(started_at),
            "extractive_fallback",
        )


def build_answer_prompt(
    *,
    config: AnswerEvalConfig,
    case: AnswerBenchmarkCase,
    contexts: list[RetrievedContext],
) -> str:
    """Build a grounded answer prompt."""

    compact_contexts = compact_contexts_for_prompt(config, contexts)
    return (
        "Bạn là trợ lý RAG bảo hiểm sức khỏe Việt Nam. "
        "Chỉ trả lời dựa trên các context được cung cấp. "
        "Không suy diễn ngoài bằng chứng. Nếu context không đủ, nói rõ "
        "'Không đủ bằng chứng trong tài liệu được truy xuất'.\n\n"
        "Yêu cầu bắt buộc:\n"
        "- Trả lời bằng tiếng Việt.\n"
        "- Mỗi ý quan trọng phải có citation dạng [S1], [S2].\n"
        "- Không bịa số tiền, giới hạn, thời gian chờ, điều kiện loại trừ.\n"
        "- Không nhắc đến việc bạn là AI evaluator.\n\n"
        f"Câu hỏi: {case.query}\n"
        "\n"
        "Contexts JSON:\n"
        f"{json.dumps(compact_contexts, ensure_ascii=False)}\n\n"
        "Trả lời cuối cùng:"
    )


def compact_contexts_for_prompt(
    config: AnswerEvalConfig,
    contexts: list[RetrievedContext],
) -> list[JsonDict]:
    """Return context payloads bounded by config character limits."""

    compact_contexts: list[JsonDict] = []
    used_chars = 0
    for context in contexts:
        remaining = config.max_total_context_chars - used_chars
        if remaining <= 0:
            break
        max_chars = min(config.max_context_chars_per_item, remaining)
        text = context.text[:max_chars]
        used_chars += len(text)
        compact_contexts.append(
            {
                "citation_id": context.citation_id,
                "rank": context.rank,
                "source_path": context.source_path,
                "document_name": context.document_name,
                "section_heading": context.section_heading,
                "text": text,
            }
        )
    return compact_contexts


def build_extractive_answer(
    *,
    contexts: list[RetrievedContext],
) -> str:
    """Build a deterministic fallback answer from the top retrieved context."""

    if not contexts:
        return "Không đủ bằng chứng trong tài liệu được truy xuất."
    best_context = contexts[0]
    text = collapse_whitespace(best_context.text)
    if len(text) > 700:
        text = text[:700].rstrip() + "..."
    return cite_each_statement(text, best_context.citation_id)


def evaluate_generated_answer(
    *,
    case: AnswerBenchmarkCase,
    scenario_name: str,
    contexts: list[RetrievedContext],
    answer: str,
    generation_mode: str,
    generation_status: str,
    generation_latency_ms: float,
    generation_error: str,
    threshold: float,
) -> AnswerEvalResult:
    """Score one generated answer with deterministic citation and grounding metrics."""

    cited_ids = extract_citation_ids(answer)
    context_by_id = {context.citation_id: context for context in contexts}
    valid_cited_ids = [
        citation_id for citation_id in cited_ids if citation_id in context_by_id
    ]
    valid_citation_rate = safe_divide(len(valid_cited_ids), len(cited_ids), default=0.0)
    expected_source_in_context = any(
        context.source_path == case.source_path for context in contexts
    )
    expected_source_cited = any(
        context_by_id[citation_id].source_path == case.source_path
        for citation_id in valid_cited_ids
    )
    citation_coverage = calculate_citation_coverage(
        answer,
        valid_citation_ids=set(context_by_id),
    )
    gold_text = gold_text_for_case(case)
    answer_gold_token_recall = token_recall(gold_text, answer)
    expected_evidence_phrase_recall = (
        phrase_recall(case.expected_evidence, answer)
        if case.expected_evidence
        else None
    )
    combined_context = "\n".join(context.text for context in contexts)
    answer_context_token_precision = token_precision(answer, combined_context)
    unsupported_numeric_claim_count = count_unsupported_numeric_claims(
        answer=answer,
        contexts=contexts,
    )
    numeric_claim_support = 1.0 if unsupported_numeric_claim_count == 0 else 0.0
    phrase_score = (
        expected_evidence_phrase_recall
        if expected_evidence_phrase_recall is not None
        else answer_gold_token_recall
    )
    answer_quality_score = round(
        0.25 * float(expected_source_cited)
        + 0.25 * answer_gold_token_recall
        + 0.15 * phrase_score
        + 0.15 * citation_coverage
        + 0.10 * answer_context_token_precision
        + 0.10 * numeric_claim_support,
        4,
    )
    citation_success = (
        bool(cited_ids) and valid_citation_rate == 1.0 and citation_coverage == 1.0
    )
    source_citation_success = expected_source_cited if case.must_cite_source else True
    return AnswerEvalResult(
        case_id=case.case_id,
        benchmark_file=case.benchmark_file,
        benchmark_version=case.benchmark_version,
        scenario_name=scenario_name,
        provider=case.provider,
        difficulty=case.difficulty,
        task_type=case.task_type,
        risk=case.risk,
        query=case.query,
        expected_source_path=case.source_path,
        expected_source_in_context=expected_source_in_context,
        expected_source_cited=expected_source_cited,
        answer_has_citation=bool(cited_ids),
        valid_citation_rate=round(valid_citation_rate, 4),
        citation_coverage=round(citation_coverage, 4),
        answer_gold_token_recall=round(answer_gold_token_recall, 4),
        expected_evidence_phrase_recall=(
            round(expected_evidence_phrase_recall, 4)
            if expected_evidence_phrase_recall is not None
            else None
        ),
        answer_context_token_precision=round(answer_context_token_precision, 4),
        numeric_claim_support=numeric_claim_support,
        unsupported_numeric_claim_count=unsupported_numeric_claim_count,
        answer_quality_score=answer_quality_score,
        success=(
            answer_quality_score >= threshold
            and citation_success
            and source_citation_success
        ),
        threshold=threshold,
        retrieved_context_count=len(contexts),
        cited_context_ids=",".join(valid_cited_ids),
        generation_mode=generation_mode,
        generation_status=generation_status,
        generation_latency_ms=generation_latency_ms,
        generation_error=generation_error,
        answer=answer,
    )


def gold_text_for_case(case: AnswerBenchmarkCase) -> str:
    """Return the gold text used for answer semantic coverage heuristics."""

    normalized_expected = normalize_text(case.expected_answer)
    if case.evidence_quote and normalized_expected.startswith(
        GENERIC_EXPECTED_ANSWER_PREFIX
    ):
        return case.evidence_quote
    if case.expected_answer:
        return case.expected_answer
    return case.evidence_quote


def extract_citation_ids(answer: str) -> list[str]:
    """Extract citation IDs like S1 from an answer."""

    return re.findall(r"\[(S\d+)\]", answer)


def calculate_citation_coverage(
    answer: str,
    valid_citation_ids: set[str] | None = None,
) -> float:
    """Return the share of answer statements with citations, optionally valid-only."""

    content_statements = content_answer_statements(answer)
    if not content_statements:
        return 0.0
    cited_count = sum(
        1
        for statement in content_statements
        if statement_has_citation(statement, valid_citation_ids)
    )
    return safe_divide(cited_count, len(content_statements), default=0.0)


def statement_has_citation(
    statement: str,
    valid_citation_ids: set[str] | None = None,
) -> bool:
    """Return whether a statement has any citation, optionally only valid IDs."""

    citation_ids = extract_citation_ids(statement)
    if valid_citation_ids is None:
        return bool(citation_ids)
    return any(citation_id in valid_citation_ids for citation_id in citation_ids)


def cite_each_statement(text: str, citation_id: str) -> str:
    """Append the citation to every content-bearing statement in text."""

    cited_statements: list[str] = []
    for statement in split_answer_statements(text):
        if extract_citation_ids(statement):
            cited_statements.append(statement)
            continue
        if len(normalize_text(statement)) < 12:
            cited_statements.append(statement)
            continue
        cited_statements.append(
            add_citation_before_terminal_punctuation(statement, citation_id)
        )
    return " ".join(cited_statements)


def add_citation_before_terminal_punctuation(statement: str, citation_id: str) -> str:
    """Add a citation before terminal punctuation so coverage splitting is stable."""

    match = re.fullmatch(r"(.+?)([.!?。]+)$", statement)
    if match:
        return f"{match.group(1).rstrip()} [{citation_id}]{match.group(2)}"
    return f"{statement} [{citation_id}]"


def split_answer_statements(answer: str) -> list[str]:
    """Split answer text into simple statement units."""

    return [
        statement.strip()
        for statement in re.split(r"(?<=[.!?。])\s+|\n+", answer)
        if statement.strip()
    ]


def merge_detached_citations(statements: list[str]) -> list[str]:
    """Attach standalone citation-only statements to the previous statement."""

    merged: list[str] = []
    for statement in statements:
        if re.fullmatch(r"(?:\[S\d+\]\s*)+", statement) and merged:
            merged[-1] = f"{merged[-1]} {statement}"
            continue
        merged.append(statement)
    return merged


def phrase_recall(phrases: tuple[str, ...], text: str) -> float:
    """Return exact normalized phrase recall."""

    normalized_text = normalize_text(text)
    normalized_phrases = [
        normalize_text(phrase) for phrase in phrases if phrase.strip()
    ]
    if not normalized_phrases:
        return 0.0
    matched = sum(1 for phrase in normalized_phrases if phrase in normalized_text)
    return safe_divide(matched, len(normalized_phrases), default=0.0)


def token_recall(expected_text: str, actual_text: str) -> float:
    """Return significant-token recall from expected text to actual text."""

    expected_tokens = set(significant_tokens(expected_text))
    if not expected_tokens:
        return 0.0
    actual_tokens = set(significant_tokens(actual_text))
    return safe_divide(len(expected_tokens & actual_tokens), len(expected_tokens))


def token_precision(actual_text: str, support_text: str) -> float:
    """Return significant-token precision from actual text against support text."""

    actual_tokens = set(significant_tokens(remove_citations(actual_text)))
    if not actual_tokens:
        return 0.0
    support_tokens = set(significant_tokens(support_text))
    return safe_divide(len(actual_tokens & support_tokens), len(actual_tokens))


def significant_tokens(text: str) -> list[str]:
    """Return normalized, content-bearing tokens."""

    stopwords = {
        "của",
        "cho",
        "các",
        "theo",
        "được",
        "trong",
        "ngoài",
        "hoặc",
        "và",
        "với",
        "này",
        "một",
        "những",
        "người",
        "bảo",
        "hiểm",
        "công",
        "ty",
        "không",
        "tại",
        "khi",
        "nếu",
        "là",
        "có",
        "về",
    }
    normalized = normalize_text(remove_citations(text))
    tokens = re.findall(r"[a-z0-9à-ỹ]+", normalized)
    return [
        token
        for token in tokens
        if len(token) >= 3 and token not in stopwords and not token.startswith("số")
    ]


def count_unsupported_numeric_claims(
    *,
    answer: str,
    contexts: list[RetrievedContext],
) -> int:
    """Count numeric claims not present in their cited retrieved contexts."""

    context_by_id = {context.citation_id: context for context in contexts}
    unsupported_count = 0
    for statement in content_answer_statements(answer):
        statement_numbers = set(extract_numbers(remove_citations(statement)))
        if not statement_numbers:
            continue
        cited_contexts = [
            context_by_id[citation_id]
            for citation_id in extract_citation_ids(statement)
            if citation_id in context_by_id
        ]
        if not cited_contexts:
            unsupported_count += len(statement_numbers)
            continue
        cited_context_numbers = set(
            extract_numbers("\n".join(context.text for context in cited_contexts))
        )
        unsupported_count += len(statement_numbers - cited_context_numbers)
    return unsupported_count


def content_answer_statements(answer: str) -> list[str]:
    """Return content-bearing answer statements after citation cleanup."""

    statements = merge_detached_citations(split_answer_statements(answer))
    return [
        statement
        for statement in statements
        if len(normalize_text(statement)) >= 12
        and "không đủ bằng chứng" not in normalize_text(statement)
    ]


def extract_numbers(text: str) -> list[str]:
    """Extract normalized numeric expressions."""

    numbers = re.findall(r"\d[\d.,/%-]*", text)
    return [number.strip(".,;:") for number in numbers if number.strip(".,;:")]


def remove_citations(text: str) -> str:
    """Remove citation markers from text."""

    return re.sub(r"\[S\d+\]", "", text)


def build_summary_rows(results: list[AnswerEvalResult]) -> list[JsonDict]:
    """Build overall and provider summary rows."""

    rows = [summary_row("overall", "all", results)]
    providers = sorted({result.provider for result in results})
    rows.extend(
        summary_row(
            "provider",
            provider,
            [result for result in results if result.provider == provider],
        )
        for provider in providers
    )
    risks = sorted({result.risk for result in results})
    rows.extend(
        summary_row(
            "risk",
            risk,
            [result for result in results if result.risk == risk],
        )
        for risk in risks
    )
    return rows


def summary_row(
    group_type: str,
    group_name: str,
    results: list[AnswerEvalResult],
) -> JsonDict:
    """Build one summary row."""

    completed = [
        result
        for result in results
        if result.generation_status in {"completed", "fallback_extractive"}
    ]
    return {
        "group_type": group_type,
        "group_name": group_name,
        "cases": len(results),
        "completed_cases": len(completed),
        "generation_completed_rate": mean_bool(
            result.generation_status == "completed" for result in results
        ),
        "fallback_rate": mean_bool(
            result.generation_status == "fallback_extractive" for result in results
        ),
        "success_rate": mean_bool(result.success for result in completed),
        "answer_quality_score_mean": mean_float(
            result.answer_quality_score for result in completed
        ),
        "expected_source_in_context_rate": mean_bool(
            result.expected_source_in_context for result in completed
        ),
        "expected_source_cited_rate": mean_bool(
            result.expected_source_cited for result in completed
        ),
        "answer_has_citation_rate": mean_bool(
            result.answer_has_citation for result in completed
        ),
        "valid_citation_rate_mean": mean_float(
            result.valid_citation_rate for result in completed
        ),
        "citation_coverage_mean": mean_float(
            result.citation_coverage for result in completed
        ),
        "answer_gold_token_recall_mean": mean_float(
            result.answer_gold_token_recall for result in completed
        ),
        "answer_context_token_precision_mean": mean_float(
            result.answer_context_token_precision for result in completed
        ),
        "numeric_claim_support_rate": mean_float(
            result.numeric_claim_support for result in completed
        ),
        "latency_ms_mean": mean_float(
            result.generation_latency_ms for result in completed
        ),
    }


def write_outputs(config: AnswerEvalConfig, results: list[AnswerEvalResult]) -> None:
    """Persist answer eval artifacts."""

    rows = [asdict(result) for result in results]
    write_jsonl(config.output_dir / "answer_eval_rows.jsonl", rows)
    write_csv(config.output_dir / "answer_eval_rows.csv", rows)
    summary_rows = build_summary_rows(results)
    write_json(config.output_dir / "answer_eval_summary.json", summary_rows)
    write_csv(config.output_dir / "answer_eval_summary.csv", summary_rows)
    write_answers_markdown(config.output_dir / "answers.md", results)
    write_report(
        config.output_dir / "answer_citation_eval_report.md",
        config,
        summary_rows,
    )
    write_manifest(config.output_dir, config, len(results))


def write_answers_markdown(path: Path, results: list[AnswerEvalResult]) -> None:
    """Write full generated answers for inspection."""

    lines = ["# Answer Citation Evaluation - Full Answers", ""]
    for result in results:
        lines.extend(
            [
                f"## {result.case_id}",
                "",
                f"- Provider: `{result.provider}`",
                f"- Score: `{result.answer_quality_score}`",
                f"- Success: `{result.success}`",
                f"- Expected source cited: `{result.expected_source_cited}`",
                f"- Generation status: `{result.generation_status}`",
                "",
                f"**Query:** {result.query}",
                "",
                "**Answer:**",
                "",
                result.answer,
                "",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_report(
    path: Path,
    config: AnswerEvalConfig,
    summary_rows: list[JsonDict],
) -> None:
    """Write compact Markdown evaluation report."""

    lines = [
        "# Answer + Citation Evaluation Report",
        "",
        f"- Retrieval eval dir: `{config.retrieval_eval_dir}`",
        f"- Scenario: `{config.scenario}`",
        f"- Generation mode: `{config.generation_mode}`",
        f"- Threshold: `{config.threshold}`",
        f"- Top contexts: `{config.top_contexts}`",
        "",
        "| Group | Cases | Success | Quality | Source in context | Source cited | "
        "Citation coverage | Gold recall | Context precision | Numeric support |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| "
            f"{row['group_type']}:{row['group_name']} | {row['cases']} | "
            f"{format_float(row['success_rate'])} | "
            f"{format_float(row['answer_quality_score_mean'])} | "
            f"{format_float(row['expected_source_in_context_rate'])} | "
            f"{format_float(row['expected_source_cited_rate'])} | "
            f"{format_float(row['citation_coverage_mean'])} | "
            f"{format_float(row['answer_gold_token_recall_mean'])} | "
            f"{format_float(row['answer_context_token_precision_mean'])} | "
            f"{format_float(row['numeric_claim_support_rate'])} |"
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_manifest(output_dir: Path, config: AnswerEvalConfig, case_count: int) -> None:
    """Write run manifest without secrets."""

    payload = {
        "component": "answer_citation_eval",
        "retrieval_eval_dir": str(config.retrieval_eval_dir),
        "benchmark_dir": str(config.benchmark_dir),
        "scenario": config.scenario,
        "case_count": case_count,
        "generation_mode": config.generation_mode,
        "threshold": config.threshold,
        "top_contexts": config.top_contexts,
        "max_context_chars_per_item": config.max_context_chars_per_item,
        "max_total_context_chars": config.max_total_context_chars,
        "llm_provider": config.llm_provider,
        "gemini_model": config.gemini_model,
        "provider_slot_counts": provider_slot_counts(config.provider_slots),
        "request_timeout_seconds": config.request_timeout_seconds,
        "max_slot_attempts": config.max_slot_attempts,
    }
    write_json(output_dir / "manifest.json", payload)


def write_json(path: Path, payload: Any) -> None:
    """Write JSON."""

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[JsonDict]) -> None:
    """Write JSONL."""

    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[JsonDict]) -> None:
    """Write CSV rows."""

    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mean_bool(values: Any) -> float | None:
    """Return mean of boolean values."""

    clean_values = [1.0 if value else 0.0 for value in values]
    return mean_float(clean_values)


def mean_float(values: Any) -> float | None:
    """Return rounded mean of numeric values."""

    clean_values = [float(value) for value in values if value is not None]
    if not clean_values:
        return None
    return round(statistics.fmean(clean_values), 4)


def format_float(value: Any) -> str:
    """Format optional float for Markdown tables."""

    if value is None:
        return ""
    return f"{float(value):.4f}"


def provider_from_source_path(source_path: object) -> str:
    """Infer provider folder from a benchmark source path."""

    value = str(source_path or "")
    return value.split("/", 1)[0] if "/" in value else ""


def normalize_text(text: str) -> str:
    """Normalize Vietnamese text for matching."""

    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def collapse_whitespace(text: str) -> str:
    """Collapse whitespace while preserving readable text."""

    return re.sub(r"\s+", " ", text).strip()


def optional_int(value: object) -> int | None:
    """Parse optional integer values."""

    if value is None or str(value).strip() == "":
        return None
    return int(value)


def optional_float(value: object) -> float | None:
    """Parse optional float values."""

    if value is None or str(value).strip() == "":
        return None
    return float(value)


def safe_divide(
    numerator: int | float,
    denominator: int | float,
    default: float = 0.0,
) -> float:
    """Divide safely with a default for zero denominators."""

    if denominator == 0:
        return default
    return float(numerator) / float(denominator)


def elapsed_ms(started_at: float) -> float:
    """Return elapsed milliseconds from a perf-counter start."""

    return round((time.perf_counter() - started_at) * 1000, 3)


if __name__ == "__main__":
    raise SystemExit(main())
