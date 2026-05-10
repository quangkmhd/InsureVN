"""Provider-pool LLM judge for persisted retrieval evaluation outputs."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.eval.config import (
    DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS,
    DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL,
    DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER,
    DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS,
)
from src.eval.embedding_cache import sha256_text, stable_json
from src.eval.evaluators.deepeval_retrieval import extract_json_text
from src.eval.io import ensure_directory, load_benchmark_cases, read_jsonl, write_csv
from src.eval.llamaindex_llms import build_markdown_element_llm
from src.eval.llm_provider_slots import EvalLLMProviderSlot, provider_slot_counts
from src.eval.models import BenchmarkCase, RetrievedChunk
from src.eval.runner import retrieved_chunk_from_payload

DEFAULT_JUDGE_THRESHOLD = 0.6
DEFAULT_MAX_CONTEXT_CHARS_PER_CHUNK = 1200
DEFAULT_MAX_TOTAL_CONTEXT_CHARS = 6000

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class LLMRetrievalJudgeConfig:
    """Configuration for provider-pool LLM judging of retrieval outputs."""

    retrieval_eval_dirs: tuple[Path, ...]
    output_dir: Path
    strategies: tuple[str, ...] | None = None
    limit_cases: int | None = None
    threshold: float = DEFAULT_JUDGE_THRESHOLD
    max_workers: int = 0
    llm_provider: str = DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER
    gemini_model: str = DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL
    gemini_api_keys: tuple[str, ...] = DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS
    provider_slots: tuple[EvalLLMProviderSlot, ...] = (
        DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS
    )
    request_timeout_seconds: float = DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS
    max_slot_attempts: int = DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS
    max_context_chars_per_chunk: int = DEFAULT_MAX_CONTEXT_CHARS_PER_CHUNK
    max_total_context_chars: int = DEFAULT_MAX_TOTAL_CONTEXT_CHARS
    provider_health_check: bool = True
    resume_completed: bool = True


@dataclass(frozen=True)
class LLMJudgeScore:
    """One LLM judge score for one strategy/case retrieval result."""

    strategy: str
    case_id: str
    status: str
    context_precision: float | None
    answer_support: float | None
    context_relevancy: float | None
    overall_score: float | None
    success: bool | None
    threshold: float
    retrieved_count: int
    primary_source_path: str
    judge_model: str
    cache_hit: bool = False
    error: str = ""
    reason: str = ""
    scoring_cache_key: str = ""


@dataclass(frozen=True)
class LLMJudgeStrategySummary:
    """Aggregate LLM judge scores for one strategy."""

    strategy: str
    status: str
    cases: int
    completed_cases: int
    failed_cases: int
    context_precision_mean: float | None
    answer_support_mean: float | None
    context_relevancy_mean: float | None
    overall_score_mean: float | None
    success_rate: float | None


def run_llm_retrieval_judge_eval(config: LLMRetrievalJudgeConfig) -> Path:
    """Run LLM judge scoring for persisted retrieval outputs."""

    ensure_directory(config.output_dir)
    retrieval_inputs = load_retrieval_inputs(config)
    selected_slots, slot_health = resolve_judge_slots(config)
    judge_llm = build_markdown_element_llm(
        provider=config.llm_provider,
        gemini_model=config.gemini_model,
        gemini_api_keys=config.gemini_api_keys,
        provider_slots=selected_slots,
        request_timeout_seconds=config.request_timeout_seconds,
        max_slot_attempts=config.max_slot_attempts,
    )
    if judge_llm is None:
        msg = "LLM judge provider is disabled."
        raise ValueError(msg)

    existing_scores = load_existing_scores(config.output_dir / "llm_judge_scores.jsonl")
    score_by_key = {
        score.scoring_cache_key: score
        for score in existing_scores
        if score.scoring_cache_key and score.status == "completed"
    }
    pending_inputs = [
        retrieval_input
        for retrieval_input in retrieval_inputs
        if not (
            config.resume_completed and retrieval_input["cache_key"] in score_by_key
        )
    ]
    scores = [
        mark_cache_hit(score)
        for score in existing_scores
        if score.scoring_cache_key in score_by_key
    ]
    output_lock = threading.Lock()
    max_workers = resolve_max_workers(config, selected_slots)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                judge_one_retrieval,
                judge_llm,
                config,
                retrieval_input,
            )
            for retrieval_input in pending_inputs
        ]
        for future in as_completed(futures):
            score = future.result()
            with output_lock:
                scores.append(score)
                write_score_outputs(config.output_dir, scores)

    sorted_scores = sort_scores(scores)
    write_score_outputs(config.output_dir, sorted_scores)
    summaries = summarize_judge_scores(sorted_scores)
    write_csv(
        config.output_dir / "llm_judge_strategy_summary.csv",
        [asdict(summary) for summary in summaries],
    )
    write_manifest(config, retrieval_inputs, selected_slots, slot_health, max_workers)
    write_markdown_report(config.output_dir, summaries, slot_health)
    return config.output_dir


def load_retrieval_inputs(config: LLMRetrievalJudgeConfig) -> list[JsonDict]:
    """Load retrieval rows and benchmark cases from deterministic eval dirs."""

    inputs: list[JsonDict] = []
    selected_strategies = set(config.strategies or ())
    for retrieval_eval_dir in config.retrieval_eval_dirs:
        manifest = json.loads(
            (retrieval_eval_dir / "manifest.json").read_text(encoding="utf-8")
        )
        benchmark_path = Path(str(manifest["source_manifest"]["benchmark_path"]))
        benchmark_cases = load_benchmark_cases(benchmark_path)
        if config.limit_cases is not None:
            benchmark_cases = benchmark_cases[: config.limit_cases]
        case_by_id = {
            benchmark_case.case_id: benchmark_case for benchmark_case in benchmark_cases
        }
        retrieved_by_key: dict[tuple[str, str], list[RetrievedChunk]] = {}
        for payload in read_jsonl(retrieval_eval_dir / "retrievals.jsonl"):
            chunk = retrieved_chunk_from_payload(payload)
            if selected_strategies and chunk.strategy not in selected_strategies:
                continue
            if chunk.case_id not in case_by_id:
                continue
            retrieved_by_key.setdefault((chunk.strategy, chunk.case_id), []).append(
                chunk
            )
        for (strategy, case_id), retrieved_chunks in sorted(retrieved_by_key.items()):
            benchmark_case = case_by_id[case_id]
            retrieved_chunks = sorted(retrieved_chunks, key=lambda chunk: chunk.rank)
            cache_key = build_judge_cache_key(
                config, strategy, benchmark_case, retrieved_chunks
            )
            inputs.append(
                {
                    "strategy": strategy,
                    "case": benchmark_case,
                    "retrieved_chunks": retrieved_chunks,
                    "cache_key": cache_key,
                }
            )
    return inputs


def judge_one_retrieval(
    judge_llm: Any,
    config: LLMRetrievalJudgeConfig,
    retrieval_input: JsonDict,
) -> LLMJudgeScore:
    """Score one strategy/case retrieval result with the provider-pool judge."""

    benchmark_case = retrieval_input["case"]
    retrieved_chunks = retrieval_input["retrieved_chunks"]
    strategy = str(retrieval_input["strategy"])
    cache_key = str(retrieval_input["cache_key"])
    try:
        prompt = build_judge_prompt(config, strategy, benchmark_case, retrieved_chunks)
        response = judge_llm.complete(prompt, temperature=0.0, max_tokens=512)
        payload = parse_judge_response(str(getattr(response, "text", response)))
        context_precision = clamp_score(payload["context_precision"])
        answer_support = clamp_score(payload["answer_support"])
        context_relevancy = clamp_score(payload["context_relevancy"])
        overall_score = round(
            (context_precision + answer_support + context_relevancy) / 3,
            4,
        )
        return LLMJudgeScore(
            strategy=strategy,
            case_id=benchmark_case.case_id,
            status="completed",
            context_precision=context_precision,
            answer_support=answer_support,
            context_relevancy=context_relevancy,
            overall_score=overall_score,
            success=overall_score >= config.threshold,
            threshold=config.threshold,
            retrieved_count=len(retrieved_chunks),
            primary_source_path=primary_source_path(benchmark_case),
            judge_model=judge_model_name(config),
            reason=str(payload.get("reason", ""))[:1000],
            scoring_cache_key=cache_key,
        )
    except Exception as exc:
        return LLMJudgeScore(
            strategy=strategy,
            case_id=benchmark_case.case_id,
            status="failed",
            context_precision=None,
            answer_support=None,
            context_relevancy=None,
            overall_score=None,
            success=None,
            threshold=config.threshold,
            retrieved_count=len(retrieved_chunks),
            primary_source_path=primary_source_path(benchmark_case),
            judge_model=judge_model_name(config),
            error=f"{type(exc).__name__}: {exc}",
            scoring_cache_key=cache_key,
        )


def build_judge_prompt(
    config: LLMRetrievalJudgeConfig,
    strategy: str,
    benchmark_case: BenchmarkCase,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    """Build a compact JSON-only judge prompt."""

    contexts = compact_contexts(config, retrieved_chunks)
    return (
        "Bạn là AI evaluator cho hệ thống RAG bảo hiểm sức khỏe Việt Nam. "
        "Chấm retrieval context theo câu hỏi và gold answer. "
        "Không phạt vì văn phong; chỉ đánh giá liệu context retrieve có đúng, "
        "liên quan, đủ bằng chứng để trả lời gold answer hay không.\n\n"
        "Return ONLY valid JSON with this exact shape:\n"
        '{"context_precision": 0.0, "answer_support": 0.0, '
        '"context_relevancy": 0.0, "reason": "short Vietnamese reason"}\n\n'
        "Score definitions, each from 0 to 1:\n"
        "- context_precision: retrieved chunks are mostly useful and not noisy.\n"
        "- answer_support: retrieved chunks contain enough evidence to support "
        "the gold answer.\n"
        "- context_relevancy: retrieved chunks are relevant to the question intent.\n\n"
        f"Strategy: {strategy}\n"
        f"Case ID: {benchmark_case.case_id}\n"
        f"Question: {benchmark_case.question}\n"
        f"Gold answer: {benchmark_case.gold_answer}\n"
        f"Expected primary source: {primary_source_path(benchmark_case)}\n\n"
        "Retrieved contexts:\n"
        f"{json.dumps(contexts, ensure_ascii=False)}"
    )


def compact_contexts(
    config: LLMRetrievalJudgeConfig,
    retrieved_chunks: list[RetrievedChunk],
) -> list[JsonDict]:
    """Return truncated contexts for judge prompts."""

    contexts: list[JsonDict] = []
    used_chars = 0
    for chunk in sorted(retrieved_chunks, key=lambda item: item.rank):
        remaining_chars = config.max_total_context_chars - used_chars
        if remaining_chars <= 0:
            break
        max_chars = min(config.max_context_chars_per_chunk, remaining_chars)
        text = chunk.text[:max_chars]
        used_chars += len(text)
        contexts.append(
            {
                "rank": chunk.rank,
                "source_path": chunk.source_path,
                "lines": [chunk.start_line, chunk.end_line],
                "text": text,
            }
        )
    return contexts


def parse_judge_response(response_text: str) -> JsonDict:
    """Parse a judge JSON response."""

    payload = json.loads(extract_json_text(response_text))
    if not isinstance(payload, dict):
        msg = "Judge response must be a JSON object."
        raise ValueError(msg)
    for key in ("context_precision", "answer_support", "context_relevancy"):
        if key not in payload:
            msg = f"Judge response missing {key}."
            raise ValueError(msg)
    return payload


def clamp_score(value: object) -> float:
    """Convert a judge score to the [0, 1] range."""

    return max(0.0, min(1.0, round(float(value), 4)))


def resolve_judge_slots(
    config: LLMRetrievalJudgeConfig,
) -> tuple[tuple[EvalLLMProviderSlot, ...], list[JsonDict]]:
    """Optionally filter provider slots with a cheap health check."""

    if not config.provider_health_check:
        return config.provider_slots, []
    healthy_slots: list[EvalLLMProviderSlot] = []
    health_rows: list[JsonDict] = []
    for slot in config.provider_slots:
        started_at = time.monotonic()
        try:
            single_slot_llm = build_markdown_element_llm(
                provider="multi",
                gemini_model=config.gemini_model,
                gemini_api_keys=config.gemini_api_keys,
                provider_slots=(slot,),
                request_timeout_seconds=min(config.request_timeout_seconds, 10),
                max_slot_attempts=1,
            )
            if single_slot_llm is None:
                raise ValueError("provider disabled")
            single_slot_llm.complete(
                'Return exactly this JSON: {"ok": true}',
                temperature=0.0,
                max_tokens=32,
            )
            healthy_slots.append(slot)
            health_rows.append(slot_health_row(slot, "healthy", started_at))
        except Exception as exc:
            health_rows.append(
                slot_health_row(
                    slot, "failed", started_at, f"{type(exc).__name__}: {exc}"
                )
            )
    return tuple(healthy_slots or config.provider_slots), health_rows


def slot_health_row(
    slot: EvalLLMProviderSlot,
    status: str,
    started_at: float,
    error: str = "",
) -> JsonDict:
    """Return a provider slot health row without secrets."""

    return {
        "slot_id": slot.slot_id,
        "provider": slot.provider,
        "model": slot.model,
        "status": status,
        "duration_seconds": round(time.monotonic() - started_at, 3),
        "error": error[:1000],
    }


def resolve_max_workers(
    config: LLMRetrievalJudgeConfig,
    selected_slots: tuple[EvalLLMProviderSlot, ...],
) -> int:
    """Resolve judge worker count."""

    if config.max_workers > 0:
        return config.max_workers
    return max(1, len(selected_slots))


def build_judge_cache_key(
    config: LLMRetrievalJudgeConfig,
    strategy: str,
    benchmark_case: BenchmarkCase,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    """Build a stable cache key for one LLM judge input."""

    payload = {
        "version": "llm-retrieval-judge-v1",
        "strategy": strategy,
        "case_id": benchmark_case.case_id,
        "question": benchmark_case.question,
        "gold_answer": benchmark_case.gold_answer,
        "threshold": config.threshold,
        "model": judge_model_name(config),
        "max_context_chars_per_chunk": config.max_context_chars_per_chunk,
        "max_total_context_chars": config.max_total_context_chars,
        "retrieved_context": [
            {
                "rank": chunk.rank,
                "chunk_id": chunk.chunk_id,
                "source_path": chunk.source_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "text": chunk.text,
            }
            for chunk in retrieved_chunks
        ],
    }
    return sha256_text(stable_json(payload))


def load_existing_scores(path: Path) -> list[LLMJudgeScore]:
    """Load existing judge rows."""

    if not path.exists():
        return []
    scores: list[LLMJudgeScore] = []
    for payload in read_jsonl(path):
        scores.append(
            LLMJudgeScore(
                strategy=str(payload.get("strategy", "")),
                case_id=str(payload.get("case_id", "")),
                status=str(payload.get("status", "")),
                context_precision=optional_float(payload.get("context_precision")),
                answer_support=optional_float(payload.get("answer_support")),
                context_relevancy=optional_float(payload.get("context_relevancy")),
                overall_score=optional_float(payload.get("overall_score")),
                success=optional_bool(payload.get("success")),
                threshold=float(payload.get("threshold", DEFAULT_JUDGE_THRESHOLD)),
                retrieved_count=int(payload.get("retrieved_count", 0)),
                primary_source_path=str(payload.get("primary_source_path", "")),
                judge_model=str(payload.get("judge_model", "")),
                cache_hit=bool(payload.get("cache_hit", False)),
                error=str(payload.get("error", "")),
                reason=str(payload.get("reason", "")),
                scoring_cache_key=str(payload.get("scoring_cache_key", "")),
            )
        )
    return scores


def mark_cache_hit(score: LLMJudgeScore) -> LLMJudgeScore:
    """Return an existing score row marked as cache hit."""

    return LLMJudgeScore(
        strategy=score.strategy,
        case_id=score.case_id,
        status=score.status,
        context_precision=score.context_precision,
        answer_support=score.answer_support,
        context_relevancy=score.context_relevancy,
        overall_score=score.overall_score,
        success=score.success,
        threshold=score.threshold,
        retrieved_count=score.retrieved_count,
        primary_source_path=score.primary_source_path,
        judge_model=score.judge_model,
        cache_hit=True,
        error=score.error,
        reason=score.reason,
        scoring_cache_key=score.scoring_cache_key,
    )


def write_score_outputs(output_dir: Path, scores: list[LLMJudgeScore]) -> None:
    """Write score JSONL and CSV snapshots."""

    sorted_rows = [asdict(score) for score in sort_scores(scores)]
    ensure_directory(output_dir)
    with (output_dir / "llm_judge_scores.jsonl").open("w", encoding="utf-8") as output:
        for row in sorted_rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv(output_dir / "llm_judge_scores.csv", sorted_rows)


def summarize_judge_scores(
    scores: list[LLMJudgeScore],
) -> list[LLMJudgeStrategySummary]:
    """Aggregate judge scores by strategy."""

    strategy_names = sorted({score.strategy for score in scores})
    summaries: list[LLMJudgeStrategySummary] = []
    for strategy in strategy_names:
        strategy_scores = [score for score in scores if score.strategy == strategy]
        completed = [score for score in strategy_scores if score.status == "completed"]
        failed = [score for score in strategy_scores if score.status != "completed"]
        summaries.append(
            LLMJudgeStrategySummary(
                strategy=strategy,
                status="completed" if not failed else "partial",
                cases=len(strategy_scores),
                completed_cases=len(completed),
                failed_cases=len(failed),
                context_precision_mean=mean_score(
                    score.context_precision for score in completed
                ),
                answer_support_mean=mean_score(
                    score.answer_support for score in completed
                ),
                context_relevancy_mean=mean_score(
                    score.context_relevancy for score in completed
                ),
                overall_score_mean=mean_score(
                    score.overall_score for score in completed
                ),
                success_rate=mean_score(
                    1.0 if score.success else 0.0 for score in completed
                ),
            )
        )
    return sorted(
        summaries,
        key=lambda summary: (
            summary.overall_score_mean or 0.0,
            summary.answer_support_mean or 0.0,
            summary.context_precision_mean or 0.0,
        ),
        reverse=True,
    )


def mean_score(values: Any) -> float | None:
    """Return rounded mean for non-null numeric values."""

    clean_values = [float(value) for value in values if value is not None]
    if not clean_values:
        return None
    return round(sum(clean_values) / len(clean_values), 4)


def sort_scores(scores: list[LLMJudgeScore]) -> list[LLMJudgeScore]:
    """Sort score rows stably."""

    return sorted(scores, key=lambda score: (score.strategy, score.case_id))


def write_manifest(
    config: LLMRetrievalJudgeConfig,
    retrieval_inputs: list[JsonDict],
    selected_slots: tuple[EvalLLMProviderSlot, ...],
    slot_health: list[JsonDict],
    max_workers: int,
) -> None:
    """Write judge run manifest."""

    payload = {
        "retrieval_eval_dirs": [str(path) for path in config.retrieval_eval_dirs],
        "strategies": sorted({str(row["strategy"]) for row in retrieval_inputs}),
        "case_strategy_count": len(retrieval_inputs),
        "threshold": config.threshold,
        "judge_model": judge_model_name(config),
        "provider_slot_counts_all": provider_slot_counts(config.provider_slots),
        "provider_slot_counts_selected": provider_slot_counts(selected_slots),
        "provider_health_check": config.provider_health_check,
        "provider_health": slot_health,
        "max_workers": max_workers,
        "request_timeout_seconds": config.request_timeout_seconds,
        "max_slot_attempts": config.max_slot_attempts,
        "max_context_chars_per_chunk": config.max_context_chars_per_chunk,
        "max_total_context_chars": config.max_total_context_chars,
    }
    (config.output_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_markdown_report(
    output_dir: Path,
    summaries: list[LLMJudgeStrategySummary],
    slot_health: list[JsonDict],
) -> None:
    """Write a compact Markdown judge report."""

    lines = [
        "# LLM Retrieval Judge Report",
        "",
        "| Rank | Strategy | Cases | Failed | Overall | Support | Precision | "
        "Relevancy | Success rate |",
        "| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, summary in enumerate(summaries, 1):
        lines.append(
            "| "
            f"{rank} | `{summary.strategy}` | {summary.cases} | "
            f"{summary.failed_cases} | {format_optional(summary.overall_score_mean)} | "
            f"{format_optional(summary.answer_support_mean)} | "
            f"{format_optional(summary.context_precision_mean)} | "
            f"{format_optional(summary.context_relevancy_mean)} | "
            f"{format_optional(summary.success_rate)} |"
        )
    if slot_health:
        healthy_count = sum(1 for row in slot_health if row["status"] == "healthy")
        lines.extend(
            [
                "",
                f"Provider health: {healthy_count}/{len(slot_health)} slots healthy.",
            ]
        )
    (output_dir / "llm_judge_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def format_optional(value: float | None) -> str:
    """Format optional float values."""

    return "" if value is None else f"{value:.4f}"


def judge_model_name(config: LLMRetrievalJudgeConfig) -> str:
    """Return a stable model name for reports."""

    return f"{config.llm_provider}-provider-pool"


def primary_source_path(benchmark_case: BenchmarkCase) -> str:
    """Return the primary expected source path for a benchmark case."""

    for source in benchmark_case.expected_sources:
        if source.relationship == "primary":
            return source.source_path
    return (
        benchmark_case.expected_sources[0].source_path
        if benchmark_case.expected_sources
        else ""
    )


def optional_float(value: object) -> float | None:
    """Parse optional float."""

    if value is None or value == "":
        return None
    return float(value)


def optional_bool(value: object) -> bool | None:
    """Parse optional bool."""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}
