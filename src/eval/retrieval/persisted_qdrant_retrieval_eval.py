"""Evaluate retrieval from persisted local Qdrant strategy indexes."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from src.eval.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_GOOGLE_API_KEY,
    DEFAULT_EMBEDDING_GOOGLE_API_KEYS,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY,
    DEFAULT_EMBEDDING_PROVIDER,
)
from src.eval.embeddings import build_retrieval_embeddings
from src.eval.embeddings.cache import EmbeddingCache
from src.eval.io import ensure_directory, load_benchmark_cases, write_csv, write_jsonl
from src.eval.models import BenchmarkCase, ExpectedSource, RetrievedChunk
from src.eval.runner import primary_expected_source_path
from src.eval.vector_database import QdrantStrategyDatabase

DEFAULT_EVAL_TOP_K = 5

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class PersistedQdrantRetrievalEvalConfig:
    """Configuration for retrieval evaluation over existing Qdrant indexes."""

    source_run_dir: Path
    output_dir: Path | None = None
    top_k: int = DEFAULT_EVAL_TOP_K
    embedding_batch_size: int = 2
    embedding_provider: str | None = None
    embedding_model_name: str | None = None
    embedding_device: str | None = None
    embedding_google_api_key: str = DEFAULT_EMBEDDING_GOOGLE_API_KEY
    embedding_google_api_keys: tuple[str, ...] = DEFAULT_EMBEDDING_GOOGLE_API_KEYS
    embedding_output_dimensionality: int | None = (
        DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY
    )
    embedding_cache_path: Path | None = None
    strategies: tuple[str, ...] | None = None


@dataclass(frozen=True)
class RetrievalCaseMetric:
    """Deterministic retrieval metric row for one case and strategy."""

    strategy: str
    case_id: str
    primary_source_path: str
    retrieved_count: int
    primary_hit_at_k: float
    primary_rank_at_k: int | None
    primary_mrr_at_k: float
    required_source_count: int
    required_source_recall_at_k: float
    line_expected_count: int
    line_overlap_recall_at_k: float


@dataclass(frozen=True)
class RetrievalStrategySummary:
    """Aggregate retrieval metrics for one strategy."""

    strategy: str
    status: str
    cases: int
    qdrant_points: int
    retrieval_count: int
    primary_hit_rate_at_k: float
    primary_mrr_at_k: float
    required_source_recall_at_k: float
    line_overlap_recall_at_k: float
    duration_seconds: float
    qdrant_path: str
    error: str = ""


def run_persisted_qdrant_retrieval_eval(
    config: PersistedQdrantRetrievalEvalConfig,
) -> Path:
    """Evaluate retrieval using already-persisted Qdrant indexes."""

    source_run_dir = config.source_run_dir.resolve()
    manifest = load_run_manifest(source_run_dir)
    output_dir = (config.output_dir or source_run_dir / "retrieval_eval").resolve()
    ensure_directory(output_dir)

    benchmark_path = Path(str(manifest["benchmark_path"]))
    collection_name = str(manifest.get("collection_name", DEFAULT_COLLECTION_NAME))
    source_paths = tuple(str(path) for path in manifest.get("source_paths", []))
    strategies = resolve_strategy_names(config, manifest, source_run_dir)
    embedding_cache_path = config.embedding_cache_path or (
        source_run_dir / "embedding_cache.sqlite"
    )
    embeddings = build_retrieval_embeddings(
        provider=(
            config.embedding_provider
            or str(manifest.get("embedding_provider") or DEFAULT_EMBEDDING_PROVIDER)
        ),
        model_name=(
            config.embedding_model_name
            or str(manifest.get("embedding_model_name") or DEFAULT_EMBEDDING_MODEL)
        ),
        batch_size=config.embedding_batch_size,
        device=(
            config.embedding_device
            if config.embedding_device is not None
            else str(manifest.get("embedding_device") or DEFAULT_EMBEDDING_DEVICE)
        ),
        google_api_key=config.embedding_google_api_key,
        google_api_keys=config.embedding_google_api_keys,
        google_output_dimensionality=(
            config.embedding_output_dimensionality
            if config.embedding_output_dimensionality is not None
            else manifest.get("embedding_output_dimensionality")
        ),
        cache=EmbeddingCache(path=embedding_cache_path, enabled=True),
    )
    benchmark_cases = filter_cases_by_source_paths(
        benchmark_cases=load_benchmark_cases(benchmark_path),
        source_paths=set(source_paths),
    )

    retrieval_rows: list[JsonDict] = []
    case_metric_rows: list[RetrievalCaseMetric] = []
    summary_rows: list[RetrievalStrategySummary] = []
    for strategy_name in strategies:
        strategy_started_at = time.monotonic()
        strategy_retrieval_rows: list[JsonDict] = []
        strategy_case_metrics: list[RetrievalCaseMetric] = []
        strategy_status = "completed"
        strategy_error = ""
        qdrant_path = source_run_dir / "qdrant" / strategy_name
        qdrant_points = 0
        database: QdrantStrategyDatabase | None = None
        try:
            qdrant_points = count_qdrant_points(qdrant_path, collection_name)
            database = QdrantStrategyDatabase(
                database_path=qdrant_path,
                collection_name=collection_name,
                embeddings=embeddings,
            )
            for benchmark_case in benchmark_cases:
                retrieved_chunks = database.search(
                    case_id=benchmark_case.case_id,
                    strategy=strategy_name,
                    query=benchmark_case.question,
                    top_k=config.top_k,
                )
                strategy_retrieval_rows.extend(
                    retrieval_row(chunk) for chunk in retrieved_chunks
                )
                strategy_case_metrics.append(
                    score_retrieval_case(
                        strategy=strategy_name,
                        benchmark_case=benchmark_case,
                        retrieved_chunks=retrieved_chunks,
                        top_k=config.top_k,
                    )
                )
        except Exception as exc:
            strategy_status = "failed"
            strategy_error = f"{type(exc).__name__}: {exc}"
            strategy_retrieval_rows = []
            strategy_case_metrics = []
        finally:
            if database is not None:
                database.close()

        retrieval_rows.extend(strategy_retrieval_rows)
        case_metric_rows.extend(strategy_case_metrics)
        summary_rows.append(
            summarize_strategy(
                strategy=strategy_name,
                status=strategy_status,
                qdrant_points=qdrant_points,
                retrieval_count=len(strategy_retrieval_rows),
                case_metrics=strategy_case_metrics,
                duration_seconds=time.monotonic() - strategy_started_at,
                qdrant_path=qdrant_path,
                error=strategy_error,
            )
        )
        write_jsonl(output_dir / "retrievals.jsonl", retrieval_rows)
        write_jsonl(output_dir / "retrieval_case_metrics.jsonl", case_metric_rows)
        write_jsonl(output_dir / "retrieval_strategy_summary.jsonl", summary_rows)
        write_csv(
            output_dir / "retrieval_case_metrics.csv",
            [asdict(row) for row in case_metric_rows],
        )
        write_csv(
            output_dir / "retrieval_strategy_summary.csv",
            [asdict(row) for row in sort_strategy_summaries(summary_rows)],
        )

    write_eval_manifest(
        output_dir=output_dir,
        source_run_dir=source_run_dir,
        source_manifest=manifest,
        strategies=strategies,
        benchmark_case_count=len(benchmark_cases),
        top_k=config.top_k,
        embedding_cache_path=embedding_cache_path,
    )
    write_markdown_report(
        output_dir=output_dir,
        source_run_dir=source_run_dir,
        summaries=sort_strategy_summaries(summary_rows),
        benchmark_case_count=len(benchmark_cases),
        top_k=config.top_k,
    )
    return output_dir


def load_run_manifest(source_run_dir: Path) -> JsonDict:
    """Load the chunking/embedding run manifest."""

    manifest_path = source_run_dir / "out" / "manifest.json"
    if not manifest_path.exists():
        msg = f"Missing run manifest: {manifest_path}"
        raise FileNotFoundError(msg)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Expected JSON object manifest at {manifest_path}"
        raise ValueError(msg)
    return payload


def resolve_strategy_names(
    config: PersistedQdrantRetrievalEvalConfig,
    manifest: JsonDict,
    source_run_dir: Path,
) -> tuple[str, ...]:
    """Return strategy names requested and present in the source Qdrant dir."""

    requested_strategies = config.strategies or tuple(
        str(strategy) for strategy in manifest.get("strategies", [])
    )
    qdrant_root = source_run_dir / "qdrant"
    strategies = tuple(
        strategy
        for strategy in requested_strategies
        if strategy and (qdrant_root / strategy).is_dir()
    )
    if not strategies:
        msg = f"No requested Qdrant strategy directories found under {qdrant_root}"
        raise ValueError(msg)
    return strategies


def filter_cases_by_source_paths(
    benchmark_cases: list[BenchmarkCase],
    source_paths: set[str],
) -> list[BenchmarkCase]:
    """Keep benchmark cases whose primary source was indexed."""

    return [
        benchmark_case
        for benchmark_case in benchmark_cases
        if primary_expected_source_path(benchmark_case) in source_paths
    ]


def count_qdrant_points(qdrant_path: Path, collection_name: str) -> int:
    """Return exact point count for a local Qdrant collection."""

    client = QdrantClient(path=str(qdrant_path))
    try:
        return int(client.count(collection_name=collection_name, exact=True).count)
    finally:
        client.close()


def retrieval_row(chunk: RetrievedChunk) -> JsonDict:
    """Convert one retrieved chunk to a JSON row."""

    return asdict(chunk)


def score_retrieval_case(
    strategy: str,
    benchmark_case: BenchmarkCase,
    retrieved_chunks: list[RetrievedChunk],
    top_k: int,
) -> RetrievalCaseMetric:
    """Score retrieved chunks against benchmark source citations."""

    top_retrieved = sorted(retrieved_chunks, key=lambda chunk: chunk.rank)[:top_k]
    primary_source = primary_expected_source_path(benchmark_case)
    primary_rank = first_matching_rank(top_retrieved, primary_source)
    required_sources = set(required_source_paths(benchmark_case))
    retrieved_sources = {chunk.source_path for chunk in top_retrieved}
    line_expected_sources = [
        source
        for source in benchmark_case.expected_sources
        if source.line_start is not None and source.line_end is not None
    ]
    return RetrievalCaseMetric(
        strategy=strategy,
        case_id=benchmark_case.case_id,
        primary_source_path=primary_source,
        retrieved_count=len(top_retrieved),
        primary_hit_at_k=1.0 if primary_rank is not None else 0.0,
        primary_rank_at_k=primary_rank,
        primary_mrr_at_k=(1.0 / primary_rank) if primary_rank is not None else 0.0,
        required_source_count=len(required_sources),
        required_source_recall_at_k=(
            len(required_sources & retrieved_sources) / len(required_sources)
            if required_sources
            else 0.0
        ),
        line_expected_count=len(line_expected_sources),
        line_overlap_recall_at_k=(
            sum(
                1
                for source in line_expected_sources
                if has_line_overlap(source, top_retrieved)
            )
            / len(line_expected_sources)
            if line_expected_sources
            else 0.0
        ),
    )


def first_matching_rank(
    retrieved_chunks: list[RetrievedChunk],
    source_path: str,
) -> int | None:
    """Return first one-based rank matching a source path."""

    for chunk in retrieved_chunks:
        if chunk.source_path == source_path:
            return chunk.rank
    return None


def required_source_paths(benchmark_case: BenchmarkCase) -> list[str]:
    """Return unique source paths required by scoring metadata or citations."""

    paths = [
        str(path)
        for path in benchmark_case.scoring.get("required_source_paths", [])
        if str(path)
    ]
    if not paths:
        paths = [
            expected_source.source_path
            for expected_source in benchmark_case.expected_sources
            if expected_source.source_path
        ]
    return list(dict.fromkeys(paths))


def has_line_overlap(
    expected_source: ExpectedSource,
    retrieved_chunks: list[RetrievedChunk],
) -> bool:
    """Return whether any retrieved chunk overlaps the expected line span."""

    if expected_source.line_start is None or expected_source.line_end is None:
        return False
    for chunk in retrieved_chunks:
        if chunk.source_path != expected_source.source_path:
            continue
        if max(expected_source.line_start, chunk.start_line) <= min(
            expected_source.line_end,
            chunk.end_line,
        ):
            return True
    return False


def summarize_strategy(
    strategy: str,
    status: str,
    qdrant_points: int,
    retrieval_count: int,
    case_metrics: list[RetrievalCaseMetric],
    duration_seconds: float,
    qdrant_path: Path,
    error: str,
) -> RetrievalStrategySummary:
    """Aggregate case metrics for one strategy."""

    return RetrievalStrategySummary(
        strategy=strategy,
        status=status,
        cases=len(case_metrics),
        qdrant_points=qdrant_points,
        retrieval_count=retrieval_count,
        primary_hit_rate_at_k=mean(row.primary_hit_at_k for row in case_metrics),
        primary_mrr_at_k=mean(row.primary_mrr_at_k for row in case_metrics),
        required_source_recall_at_k=mean(
            row.required_source_recall_at_k for row in case_metrics
        ),
        line_overlap_recall_at_k=mean(
            row.line_overlap_recall_at_k for row in case_metrics
        ),
        duration_seconds=round(duration_seconds, 3),
        qdrant_path=str(qdrant_path),
        error=error,
    )


def mean(values: Any) -> float:
    """Return rounded arithmetic mean."""

    materialized = [float(value) for value in values]
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 4)


def sort_strategy_summaries(
    summaries: list[RetrievalStrategySummary],
) -> list[RetrievalStrategySummary]:
    """Sort summaries from best to worst deterministic retrieval score."""

    return sorted(
        summaries,
        key=lambda row: (
            row.status != "completed",
            -row.required_source_recall_at_k,
            -row.primary_mrr_at_k,
            -row.line_overlap_recall_at_k,
            row.qdrant_points,
        ),
    )


def write_eval_manifest(
    output_dir: Path,
    source_run_dir: Path,
    source_manifest: JsonDict,
    strategies: tuple[str, ...],
    benchmark_case_count: int,
    top_k: int,
    embedding_cache_path: Path,
) -> None:
    """Write evaluation run manifest."""

    payload = {
        "source_run_dir": str(source_run_dir),
        "source_manifest": source_manifest,
        "strategies": list(strategies),
        "benchmark_case_count": benchmark_case_count,
        "top_k": top_k,
        "embedding_cache_path": str(embedding_cache_path),
        "embedding_provider": source_manifest.get(
            "embedding_provider",
            DEFAULT_EMBEDDING_PROVIDER,
        ),
        "embedding_model_name": source_manifest.get(
            "embedding_model_name",
            DEFAULT_EMBEDDING_MODEL,
        ),
        "embedding_device": source_manifest.get(
            "embedding_device",
            DEFAULT_EMBEDDING_DEVICE,
        ),
        "embedding_output_dimensionality": source_manifest.get(
            "embedding_output_dimensionality",
            DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY,
        ),
        "embedding_google_api_key_count": source_manifest.get(
            "embedding_google_api_key_count",
            0,
        ),
        "evaluation_mode": "persisted_qdrant_read_only",
        "llm_judge": "not_used",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_markdown_report(
    output_dir: Path,
    source_run_dir: Path,
    summaries: list[RetrievalStrategySummary],
    benchmark_case_count: int,
    top_k: int,
) -> None:
    """Write a compact Markdown retrieval evaluation report."""

    best_summary = next(
        (summary for summary in summaries if summary.status == "completed"),
        None,
    )
    lines = [
        "# Persisted Qdrant Retrieval Evaluation",
        "",
        f"- Source run: `{source_run_dir}`",
        f"- Benchmark cases evaluated: {benchmark_case_count}",
        f"- Top K: {top_k}",
        "- Evaluation mode: persisted Qdrant read-only",
        "- LLM judge: not used",
        "",
        "## Strategy Summary",
        "",
        "| Strategy | Status | Cases | Qdrant Points | Primary Hit@K | "
        "Primary MRR@K | Required Source Recall@K | Line Overlap Recall@K |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        lines.append(
            "| "
            f"{summary.strategy} | {summary.status} | {summary.cases} | "
            f"{summary.qdrant_points} | {summary.primary_hit_rate_at_k:.4f} | "
            f"{summary.primary_mrr_at_k:.4f} | "
            f"{summary.required_source_recall_at_k:.4f} | "
            f"{summary.line_overlap_recall_at_k:.4f} |"
        )
    lines.extend(["", "## Conclusion", ""])
    if best_summary is None:
        lines.append("No strategy completed successfully.")
    else:
        lines.append(
            "Best completed strategy by required-source recall, MRR, and line "
            f"overlap: `{best_summary.strategy}`."
        )
    lines.append("")
    (output_dir / "retrieval_eval_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
