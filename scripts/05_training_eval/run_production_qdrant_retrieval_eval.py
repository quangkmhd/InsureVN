"""Run production-style Qdrant retrieval evaluation against benchmark JSONL files."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qdrant_client import QdrantClient

from src.core.config import settings
from src.models.evidence import HardFilters, RetrievalMode, RetrievalPlan
from src.services.document_retrieval.qdrant_retriever import (
    QdrantRetriever,
    build_dense_embedding_provider,
)
from src.services.document_retrieval.rerank_cross_encoder import (
    build_default_rerank_cross_encoder,
)
from src.services.evidence.evidence_merger import EvidenceReranker

DEFAULT_CORPUS_DIR = (
    PROJECT_ROOT
    / "data"
    / "health_insurance"
    / "health_insurance_markdowns_interpreted_cleaned"
)
DEFAULT_BENCHMARK_DIR = DEFAULT_CORPUS_DIR / "benchmark"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "eval_runs"
    / "20260510_qwen_full_folder_production_retrieval_eval"
)
DEFAULT_COLLECTION_NAME = "insurevn_qwen_prod_eval_20260510_full"
DEFAULT_TOP_K = 10
DEFAULT_SCENARIOS = ("vector", "hybrid")
PROVIDER_COMPANY_CODE_BY_PROVIDER = {
    "aia.com.vn": "AIA",
    "baominh.com.vn": "BaoMinh",
    "bic.vn": "BIC",
    "libertyinsurance.com.vn": "Liberty",
    "pacific_cross_all_pdfs": "PacificCross",
    "pti.com.vn": "PTI",
    "pvicare.net": "PVI",
}


@dataclass(frozen=True)
class BenchmarkCase:
    """One benchmark case loaded from JSONL."""

    case_id: str
    benchmark_file: str
    benchmark_version: str
    query: str
    source_path: str
    provider: str
    difficulty: str | None
    task_type: str | None
    evidence_quote: str | None
    expected_evidence: tuple[str, ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class EvalScenario:
    """One retrieval evaluation configuration."""

    name: str
    retrieval_mode: RetrievalMode
    use_company_filter: bool = False
    use_reranker: bool = False


def main() -> int:
    """Run production retrieval evaluation and persist artifacts."""
    args = parse_args()
    benchmark_paths = discover_benchmark_paths(args.benchmark_dir, args.benchmark_files)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = load_benchmark_cases(benchmark_paths)
    retriever = build_retriever(collection_name=args.collection_name)
    scenarios = parse_scenarios(args.scenarios)
    reranker = (
        build_reranker()
        if any(scenario.use_reranker for scenario in scenarios)
        else None
    )
    collection_point_count = count_collection_points(args.collection_name)

    case_rows: list[dict[str, Any]] = []
    retrieval_rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        for case in cases:
            case_metrics, ranked_rows = evaluate_case(
                retriever=retriever,
                case=case,
                scenario=scenario,
                top_k=args.top_k,
                retrieve_top_k=args.retrieve_top_k or args.top_k,
                rerank_top_k=args.rerank_top_k or args.top_k,
                reranker=reranker,
            )
            case_rows.append(case_metrics)
            retrieval_rows.extend(ranked_rows)

    summary_rows = build_summary_rows(case_rows)
    provider_rows = build_provider_rows(case_rows)
    manifest = {
        "component": "production_qdrant_retrieval_eval",
        "collection_name": args.collection_name,
        "collection_point_count": collection_point_count,
        "embedding_provider": settings.RAG_EMBEDDING_PROVIDER,
        "embedding_model": settings.RAG_EMBEDDING_MODEL,
        "dense_vector_size": settings.RAG_DENSE_VECTOR_SIZE,
        "sparse_model": settings.RAG_SPARSE_MODEL,
        "benchmark_files": [str(path) for path in benchmark_paths],
        "case_count": len(cases),
        "evaluated_case_count": len(case_rows),
        "scenario_names": [scenario.name for scenario in scenarios],
        "top_k": args.top_k,
        "retrieve_top_k": args.retrieve_top_k or args.top_k,
        "rerank_top_k": args.rerank_top_k or args.top_k,
        "corpus_dir": str(args.corpus_dir),
        "rerank_provider": settings.RAG_RERANK_PROVIDER,
        "rerank_model": settings.RAG_RERANK_MODEL,
        "rerank_batch_size": settings.RAG_RERANK_BATCH_SIZE,
        "rerank_max_length": settings.RAG_RERANK_MAX_LENGTH,
        "rerank_device": settings.RAG_RERANK_DEVICE,
        "rerank_trust_remote_code": settings.RAG_RERANK_TRUST_REMOTE_CODE,
        "rerank_load_in_4bit": settings.RAG_RERANK_LOAD_IN_4BIT,
        "rerank_device_map": settings.RAG_RERANK_DEVICE_MAP,
        "rerank_attn_implementation": settings.RAG_RERANK_ATTN_IMPLEMENTATION,
        "rerank_torch_dtype": settings.RAG_RERANK_TORCH_DTYPE,
    }

    write_json(output_dir / "manifest.json", manifest)
    write_jsonl(output_dir / "retrieval_case_metrics.jsonl", case_rows)
    write_jsonl(output_dir / "retrievals.jsonl", retrieval_rows)
    write_jsonl(output_dir / "retrieval_summary.jsonl", summary_rows)
    write_jsonl(output_dir / "retrieval_provider_summary.jsonl", provider_rows)
    write_csv(output_dir / "retrieval_case_metrics.csv", case_rows)
    write_csv(output_dir / "retrieval_summary.csv", summary_rows)
    write_csv(output_dir / "retrieval_provider_summary.csv", provider_rows)
    print(output_dir)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_DIR)
    parser.add_argument(
        "--benchmark-files",
        nargs="*",
        type=Path,
        help="Optional explicit benchmark JSONL files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--collection-name",
        default=DEFAULT_COLLECTION_NAME,
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--retrieve-top-k",
        type=int,
        default=None,
        help=(
            "Candidate retrieval size for rerank scenarios. Defaults to --top-k. "
            "Non-rerank scenarios continue to retrieve --top-k results."
        ),
    )
    parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=None,
        help="Final reranked result size for rerank scenarios. Defaults to --top-k.",
    )
    parser.add_argument(
        "--scenarios",
        default=",".join(DEFAULT_SCENARIOS),
        help=(
            "Comma-separated evaluation scenarios. Supported values: "
            "vector, hybrid, hybrid_company_filter, hybrid_rerank, "
            "hybrid_company_filter_rerank."
        ),
    )
    args = parser.parse_args()
    for option_name in ("top_k", "retrieve_top_k", "rerank_top_k"):
        option_value = getattr(args, option_name)
        if option_value is not None and option_value < 1:
            parser.error(
                f"--{option_name.replace('_', '-')} must be greater than zero."
            )
    return args


def parse_scenarios(value: str) -> list[EvalScenario]:
    """Parse and validate scenario names."""
    scenario_by_name = {
        "vector": EvalScenario(
            name="vector",
            retrieval_mode=RetrievalMode.VECTOR,
        ),
        "hybrid": EvalScenario(
            name="hybrid",
            retrieval_mode=RetrievalMode.HYBRID,
        ),
        "hybrid_company_filter": EvalScenario(
            name="hybrid_company_filter",
            retrieval_mode=RetrievalMode.HYBRID,
            use_company_filter=True,
        ),
        "hybrid_rerank": EvalScenario(
            name="hybrid_rerank",
            retrieval_mode=RetrievalMode.HYBRID,
            use_reranker=True,
        ),
        "hybrid_company_filter_rerank": EvalScenario(
            name="hybrid_company_filter_rerank",
            retrieval_mode=RetrievalMode.HYBRID,
            use_company_filter=True,
            use_reranker=True,
        ),
    }
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise ValueError("At least one scenario is required.")
    unknown_names = sorted(set(names) - set(scenario_by_name))
    if unknown_names:
        raise ValueError(
            "Unknown scenario(s): "
            + ", ".join(unknown_names)
            + ". Supported scenarios: "
            + ", ".join(sorted(scenario_by_name))
        )
    return [scenario_by_name[name] for name in names]


def discover_benchmark_paths(
    benchmark_dir: Path,
    benchmark_files: list[Path] | None,
) -> list[Path]:
    """Resolve benchmark files from explicit paths or the benchmark directory."""
    if benchmark_files:
        paths = [path.resolve() for path in benchmark_files]
    else:
        paths = sorted(benchmark_dir.resolve().glob("*.jsonl"))
    if not paths:
        raise ValueError("No benchmark JSONL files found.")
    return paths


def load_benchmark_cases(benchmark_paths: list[Path]) -> list[BenchmarkCase]:
    """Load benchmark cases from one or more JSONL files."""
    cases: list[BenchmarkCase] = []
    for path in benchmark_paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                source_path = str(payload.get("source_path") or "").strip()
                query = str(payload.get("query") or "").strip()
                case_id = str(payload.get("id") or f"{path.stem}:{line_number}")
                if not source_path or not query:
                    raise ValueError(
                        "Invalid benchmark row "
                        f"{path}:{line_number} missing query/source_path."
                    )
                provider = str(
                    payload.get("provider") or provider_from_source_path(source_path)
                )
                evidence_quote = payload.get("evidence_quote")
                expected_evidence_raw = payload.get("expected_evidence") or []
                if not isinstance(expected_evidence_raw, list):
                    expected_evidence_raw = []
                cases.append(
                    BenchmarkCase(
                        case_id=case_id,
                        benchmark_file=path.name,
                        benchmark_version=str(
                            payload.get("benchmark_version") or path.stem
                        ),
                        query=query,
                        source_path=source_path,
                        provider=provider,
                        difficulty=string_or_none(payload.get("difficulty")),
                        task_type=string_or_none(payload.get("task_type")),
                        evidence_quote=string_or_none(evidence_quote),
                        expected_evidence=tuple(
                            str(value).strip()
                            for value in expected_evidence_raw
                            if str(value).strip()
                        ),
                        raw=payload,
                    )
                )
    return cases


def build_retriever(collection_name: str) -> QdrantRetriever:
    """Build the production retriever for retrieval evaluation."""
    client_kwargs: dict[str, Any] = {"url": settings.RAG_QDRANT_URL}
    if settings.RAG_QDRANT_API_KEY:
        client_kwargs["api_key"] = settings.RAG_QDRANT_API_KEY
    embedding_provider = build_dense_embedding_provider(
        provider=settings.RAG_EMBEDDING_PROVIDER,
        model_name=settings.RAG_EMBEDDING_MODEL,
        vector_size=settings.RAG_DENSE_VECTOR_SIZE,
        batch_size=settings.RAG_EMBEDDING_BATCH_SIZE,
        max_length=settings.RAG_EMBEDDING_MAX_LENGTH,
        load_in_4bit=settings.RAG_EMBEDDING_LOAD_IN_4BIT,
        device_map=settings.RAG_EMBEDDING_DEVICE_MAP,
        attn_implementation=settings.RAG_EMBEDDING_ATTN_IMPLEMENTATION,
        query_task_description=settings.RAG_EMBEDDING_QUERY_TASK_DESCRIPTION,
    )
    return QdrantRetriever(
        client=QdrantClient(**client_kwargs),
        collection_name=collection_name,
        embedding_provider=embedding_provider,
        keyword_enabled=True,
        allow_dense_only_degraded_mode=True,
    )


def build_reranker() -> EvidenceReranker:
    """Build the configured production reranker."""
    return EvidenceReranker(cross_encoder=build_default_rerank_cross_encoder())


def count_collection_points(collection_name: str) -> int:
    """Return the total point count for the evaluation collection."""
    client_kwargs: dict[str, Any] = {"url": settings.RAG_QDRANT_URL}
    if settings.RAG_QDRANT_API_KEY:
        client_kwargs["api_key"] = settings.RAG_QDRANT_API_KEY
    client = QdrantClient(**client_kwargs)
    return int(client.count(collection_name=collection_name, exact=True).count)


def evaluate_case(
    *,
    retriever: QdrantRetriever,
    case: BenchmarkCase,
    scenario: EvalScenario,
    top_k: int,
    retrieve_top_k: int | None = None,
    rerank_top_k: int | None = None,
    reranker: EvidenceReranker | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run one retrieval case and return case metrics plus rank-level rows."""
    started_at = time.perf_counter()
    retrieve_latency_ms = 0.0
    rerank_latency_ms = 0.0
    execution_error: str | None = None
    candidate_top_k = retrieve_top_k or top_k
    final_top_k = rerank_top_k or top_k
    pre_rerank_evidences: list[Any] = []
    final_evidences: list[Any] = []
    company_filter_code = company_code_from_provider(case.provider)
    applied_filters = (
        HardFilters(company_codes=[company_filter_code])
        if scenario.use_company_filter and company_filter_code
        else None
    )

    try:
        retrieve_started_at = time.perf_counter()
        evidences = retriever.retrieve(
            RetrievalPlan(
                search_queries=[case.query],
                mode=scenario.retrieval_mode,
                filters=applied_filters,
                top_k=candidate_top_k if scenario.use_reranker else top_k,
            )
        )
        pre_rerank_evidences = list(evidences)
        final_evidences = list(evidences[:top_k])
        retrieve_latency_ms = round(
            (time.perf_counter() - retrieve_started_at) * 1000,
            3,
        )
        if scenario.use_reranker:
            if reranker is None:
                raise ValueError("Reranker is required for rerank scenarios.")
            rerank_started_at = time.perf_counter()
            evidences = rerank_with_retry(
                reranker=reranker,
                query=case.query,
                evidence_items=evidences,
                top_k=final_top_k,
            )
            final_evidences = list(evidences)
            rerank_latency_ms = round(
                (time.perf_counter() - rerank_started_at) * 1000,
                3,
            )
    except Exception as exc:
        execution_error = f"{type(exc).__name__}: {exc}"
        final_evidences = []

    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    final_metrics = calculate_rank_metrics(case=case, evidences=final_evidences)
    pre_rerank_metrics = (
        calculate_rank_metrics(case=case, evidences=pre_rerank_evidences)
        if scenario.use_reranker
        else {}
    )
    retrieval_rows: list[dict[str, Any]] = []
    if scenario.use_reranker:
        retrieval_rows.extend(
            build_retrieval_rows(
                case=case,
                scenario=scenario,
                evidences=pre_rerank_evidences,
                stage="pre_rerank",
                applied_filters=applied_filters,
                company_filter_code=company_filter_code,
                top_k=top_k,
                retrieve_top_k=candidate_top_k,
                rerank_top_k=final_top_k,
            )
        )
    retrieval_rows.extend(
        build_retrieval_rows(
            case=case,
            scenario=scenario,
            evidences=final_evidences,
            stage="final",
            applied_filters=applied_filters,
            company_filter_code=company_filter_code,
            top_k=top_k,
            retrieve_top_k=candidate_top_k,
            rerank_top_k=final_top_k,
        )
    )

    case_row = {
        "case_id": case.case_id,
        "benchmark_file": case.benchmark_file,
        "benchmark_version": case.benchmark_version,
        "provider": case.provider,
        "difficulty": case.difficulty,
        "task_type": case.task_type,
        "scenario_name": scenario.name,
        "mode": scenario.retrieval_mode.value,
        "company_filter_applied": bool(applied_filters),
        "company_filter_code": company_filter_code if applied_filters else None,
        "rerank_applied": scenario.use_reranker,
        "query": case.query,
        "expected_source_path": case.source_path,
        "retrieved_count": len(final_evidences),
        "candidate_retrieved_count": len(pre_rerank_evidences),
        "top_k": top_k,
        "retrieve_top_k": candidate_top_k,
        "rerank_top_k": final_top_k if scenario.use_reranker else None,
        "latency_ms": latency_ms,
        "retrieve_latency_ms": retrieve_latency_ms,
        "rerank_latency_ms": rerank_latency_ms,
        "success": int(execution_error is None),
        "execution_error": execution_error,
        **final_metrics,
    }
    if scenario.use_reranker:
        case_row.update(
            {f"pre_rerank_{key}": value for key, value in pre_rerank_metrics.items()}
        )
        case_row["source_rank_delta_after_rerank"] = rank_delta(
            before=pre_rerank_metrics.get("source_rank"),
            after=final_metrics.get("source_rank"),
        )
        case_row["quote_rank_delta_after_rerank"] = rank_delta(
            before=pre_rerank_metrics.get("quote_rank"),
            after=final_metrics.get("quote_rank"),
        )
    return case_row, retrieval_rows


def calculate_rank_metrics(
    *,
    case: BenchmarkCase,
    evidences: list[Any],
) -> dict[str, Any]:
    """Calculate source, quote, and phrase metrics for an ordered evidence list."""

    expected_source_path = case.source_path
    normalized_quote = normalize_text(case.evidence_quote or "")
    expected_evidence = tuple(normalize_text(value) for value in case.expected_evidence)

    source_rank: int | None = None
    quote_rank: int | None = None
    top5_combined_text_parts: list[str] = []
    top10_combined_text_parts: list[str] = []

    for rank, evidence in enumerate(evidences, start=1):
        source_path = str(
            evidence.metadata.get("source_path")
            or evidence.metadata.get("source_relative_path")
            or ""
        )
        combined_text = combine_retrieved_text(evidence)
        normalized_combined_text = normalize_text(combined_text)
        source_match = source_path == expected_source_path
        quote_match = (
            bool(normalized_quote) and normalized_quote in normalized_combined_text
        )

        if source_match and source_rank is None:
            source_rank = rank
        if quote_match and quote_rank is None:
            quote_rank = rank

        if rank <= 5:
            top5_combined_text_parts.append(normalized_combined_text)
        if rank <= 10:
            top10_combined_text_parts.append(normalized_combined_text)

    top5_text = " ".join(top5_combined_text_parts)
    top10_text = " ".join(top10_combined_text_parts)
    evidence_phrase_recall_at_5 = phrase_recall(expected_evidence, top5_text)
    evidence_phrase_recall_at_10 = phrase_recall(expected_evidence, top10_text)

    return {
        "source_rank": source_rank,
        "quote_rank": quote_rank,
        "source_hit_at_5": as_hit(source_rank, 5),
        "source_hit_at_10": as_hit(source_rank, 10),
        "mrr_at_5": reciprocal_rank(source_rank, 5),
        "mrr_at_10": reciprocal_rank(source_rank, 10),
        "has_evidence_quote": bool(case.evidence_quote),
        "quote_hit_at_5": as_hit(quote_rank, 5) if case.evidence_quote else None,
        "quote_hit_at_10": as_hit(quote_rank, 10) if case.evidence_quote else None,
        "expected_evidence_phrase_count": len(case.expected_evidence),
        "evidence_phrase_recall_at_5": evidence_phrase_recall_at_5,
        "evidence_phrase_recall_at_10": evidence_phrase_recall_at_10,
    }


def build_retrieval_rows(
    *,
    case: BenchmarkCase,
    scenario: EvalScenario,
    evidences: list[Any],
    stage: str,
    applied_filters: HardFilters | None,
    company_filter_code: str | None,
    top_k: int,
    retrieve_top_k: int,
    rerank_top_k: int,
) -> list[dict[str, Any]]:
    """Build per-rank retrieval rows for either pre-rerank or final results."""
    normalized_quote = normalize_text(case.evidence_quote or "")
    rows: list[dict[str, Any]] = []
    for rank, evidence in enumerate(evidences, start=1):
        source_path = str(
            evidence.metadata.get("source_path")
            or evidence.metadata.get("source_relative_path")
            or ""
        )
        combined_text = combine_retrieved_text(evidence)
        normalized_combined_text = normalize_text(combined_text)
        source_match = source_path == case.source_path
        quote_match = (
            bool(normalized_quote) and normalized_quote in normalized_combined_text
        )
        rows.append(
            {
                "case_id": case.case_id,
                "benchmark_file": case.benchmark_file,
                "benchmark_version": case.benchmark_version,
                "scenario_name": scenario.name,
                "mode": scenario.retrieval_mode.value,
                "stage": stage,
                "company_filter_applied": bool(applied_filters),
                "company_filter_code": company_filter_code if applied_filters else None,
                "scenario_uses_reranker": scenario.use_reranker,
                "rerank_applied": scenario.use_reranker and stage == "final",
                "top_k": top_k,
                "retrieve_top_k": retrieve_top_k,
                "rerank_top_k": rerank_top_k if scenario.use_reranker else None,
                "rank": rank,
                "score": evidence.metadata.get(
                    "rerank_score",
                    evidence.metadata.get("fusion_score", evidence.confidence),
                ),
                "retrieval_score": evidence.metadata.get(
                    "fusion_score",
                    evidence.confidence,
                ),
                "rerank_score": evidence.metadata.get("rerank_score"),
                "source_path": source_path,
                "document_id": evidence.metadata.get("document_id"),
                "document_name": evidence.metadata.get("document_name"),
                "section_heading": evidence.metadata.get("section_heading"),
                "source_match": source_match,
                "quote_match": quote_match,
                "content_preview": combined_text[:500],
            }
        )
    return rows


def combine_retrieved_text(evidence: Any) -> str:
    """Build one normalized retrieval text blob for matching metrics."""
    payload_text = str(evidence.metadata.get("text") or "")
    return "\n".join(part for part in (evidence.content, payload_text) if part).strip()


def build_summary_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate evaluation metrics by benchmark file and retrieval mode."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in case_rows:
        key = (
            str(row["benchmark_file"]),
            str(row["benchmark_version"]),
            str(row["scenario_name"]),
        )
        grouped.setdefault(key, []).append(row)

    overall_rows = aggregate_groups(grouped)
    overall_grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in case_rows:
        key = ("ALL", "ALL", str(row["scenario_name"]))
        overall_grouped.setdefault(key, []).append(row)
    return overall_rows + aggregate_groups(overall_grouped)


def build_provider_rows(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate source-hit metrics by provider and mode."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in case_rows:
        key = (
            str(row["provider"]),
            "provider_breakdown",
            str(row["scenario_name"]),
        )
        grouped.setdefault(key, []).append(row)
    return aggregate_groups(grouped)


def aggregate_groups(
    grouped_rows: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Aggregate grouped case metrics into summary rows."""
    summary_rows: list[dict[str, Any]] = []
    for (
        group_name,
        group_version,
        scenario_name,
    ), rows in sorted(grouped_rows.items()):
        quote_rows = [row for row in rows if row["quote_hit_at_5"] is not None]
        phrase_rows = [row for row in rows if row["expected_evidence_phrase_count"] > 0]
        latencies = [float(row["latency_ms"]) for row in rows]
        source_hit_rate_at_5 = mean_value(rows, "source_hit_at_5")
        source_hit_rate_at_10 = mean_value(rows, "source_hit_at_10")
        mrr_at_5 = mean_value(rows, "mrr_at_5")
        mrr_at_10 = mean_value(rows, "mrr_at_10")
        quote_hit_rate_at_5 = optional_mean(quote_rows, "quote_hit_at_5")
        quote_hit_rate_at_10 = optional_mean(quote_rows, "quote_hit_at_10")
        evidence_phrase_recall_at_5 = optional_mean(
            phrase_rows,
            "evidence_phrase_recall_at_5",
        )
        evidence_phrase_recall_at_10 = optional_mean(
            phrase_rows,
            "evidence_phrase_recall_at_10",
        )
        summary_row: dict[str, Any] = {
            "group_name": group_name,
            "group_version": group_version,
            "scenario_name": scenario_name,
            "mode": str(rows[0]["mode"]),
            "company_filter_applied": bool(rows[0]["company_filter_applied"]),
            "rerank_applied": bool(rows[0]["rerank_applied"]),
            "case_count": len(rows),
            "success_case_count": sum(int(row["success"]) for row in rows),
            "error_case_count": sum(1 for row in rows if row["execution_error"]),
            "source_hit_rate_at_5": round(source_hit_rate_at_5, 4),
            "source_hit_rate_at_10": round(source_hit_rate_at_10, 4),
            "mrr_at_5": round(mrr_at_5, 4),
            "mrr_at_10": round(mrr_at_10, 4),
            "quote_case_count": len(quote_rows),
            "quote_hit_rate_at_5": round(quote_hit_rate_at_5, 4),
            "quote_hit_rate_at_10": round(quote_hit_rate_at_10, 4),
            "phrase_case_count": len(phrase_rows),
            "evidence_phrase_recall_at_5": round(evidence_phrase_recall_at_5, 4),
            "evidence_phrase_recall_at_10": round(evidence_phrase_recall_at_10, 4),
            "latency_ms_avg": round(sum(latencies) / len(latencies), 3),
            "latency_ms_p95": round(percentile(latencies, 0.95), 3),
            "retrieve_latency_ms_avg": round(
                mean_value(rows, "retrieve_latency_ms"),
                3,
            ),
            "rerank_latency_ms_avg": round(
                mean_value(rows, "rerank_latency_ms"),
                3,
            ),
        }
        add_pre_rerank_summary_metrics(
            summary_row=summary_row,
            rows=rows,
            source_hit_rate_at_5=source_hit_rate_at_5,
            source_hit_rate_at_10=source_hit_rate_at_10,
            mrr_at_5=mrr_at_5,
            mrr_at_10=mrr_at_10,
            quote_hit_rate_at_5=quote_hit_rate_at_5,
            quote_hit_rate_at_10=quote_hit_rate_at_10,
            evidence_phrase_recall_at_5=evidence_phrase_recall_at_5,
            evidence_phrase_recall_at_10=evidence_phrase_recall_at_10,
        )
        summary_rows.append(summary_row)
    return summary_rows


def add_pre_rerank_summary_metrics(
    *,
    summary_row: dict[str, Any],
    rows: list[dict[str, Any]],
    source_hit_rate_at_5: float,
    source_hit_rate_at_10: float,
    mrr_at_5: float,
    mrr_at_10: float,
    quote_hit_rate_at_5: float,
    quote_hit_rate_at_10: float,
    evidence_phrase_recall_at_5: float,
    evidence_phrase_recall_at_10: float,
) -> None:
    """Attach pre-rerank aggregates and final-minus-pre deltas when available."""
    if not any("pre_rerank_source_hit_at_10" in row for row in rows):
        return

    pre_source_hit_rate_at_5 = optional_key_mean(rows, "pre_rerank_source_hit_at_5")
    pre_source_hit_rate_at_10 = optional_key_mean(rows, "pre_rerank_source_hit_at_10")
    pre_mrr_at_5 = optional_key_mean(rows, "pre_rerank_mrr_at_5")
    pre_mrr_at_10 = optional_key_mean(rows, "pre_rerank_mrr_at_10")
    pre_quote_hit_rate_at_5 = optional_key_mean(rows, "pre_rerank_quote_hit_at_5")
    pre_quote_hit_rate_at_10 = optional_key_mean(rows, "pre_rerank_quote_hit_at_10")
    pre_evidence_phrase_recall_at_5 = optional_key_mean(
        rows,
        "pre_rerank_evidence_phrase_recall_at_5",
    )
    pre_evidence_phrase_recall_at_10 = optional_key_mean(
        rows,
        "pre_rerank_evidence_phrase_recall_at_10",
    )

    summary_row.update(
        {
            "pre_rerank_source_hit_rate_at_5": round(pre_source_hit_rate_at_5, 4),
            "pre_rerank_source_hit_rate_at_10": round(pre_source_hit_rate_at_10, 4),
            "pre_rerank_mrr_at_5": round(pre_mrr_at_5, 4),
            "pre_rerank_mrr_at_10": round(pre_mrr_at_10, 4),
            "pre_rerank_quote_hit_rate_at_5": round(pre_quote_hit_rate_at_5, 4),
            "pre_rerank_quote_hit_rate_at_10": round(pre_quote_hit_rate_at_10, 4),
            "pre_rerank_evidence_phrase_recall_at_5": round(
                pre_evidence_phrase_recall_at_5,
                4,
            ),
            "pre_rerank_evidence_phrase_recall_at_10": round(
                pre_evidence_phrase_recall_at_10,
                4,
            ),
            "source_hit_rate_at_5_delta_vs_pre_rerank": round(
                source_hit_rate_at_5 - pre_source_hit_rate_at_5,
                4,
            ),
            "source_hit_rate_at_10_delta_vs_pre_rerank": round(
                source_hit_rate_at_10 - pre_source_hit_rate_at_10,
                4,
            ),
            "mrr_at_5_delta_vs_pre_rerank": round(mrr_at_5 - pre_mrr_at_5, 4),
            "mrr_at_10_delta_vs_pre_rerank": round(mrr_at_10 - pre_mrr_at_10, 4),
            "quote_hit_rate_at_5_delta_vs_pre_rerank": round(
                quote_hit_rate_at_5 - pre_quote_hit_rate_at_5,
                4,
            ),
            "quote_hit_rate_at_10_delta_vs_pre_rerank": round(
                quote_hit_rate_at_10 - pre_quote_hit_rate_at_10,
                4,
            ),
            "evidence_phrase_recall_at_5_delta_vs_pre_rerank": round(
                evidence_phrase_recall_at_5 - pre_evidence_phrase_recall_at_5,
                4,
            ),
            "evidence_phrase_recall_at_10_delta_vs_pre_rerank": round(
                evidence_phrase_recall_at_10 - pre_evidence_phrase_recall_at_10,
                4,
            ),
        }
    )


def rerank_with_retry(
    *,
    reranker: EvidenceReranker,
    query: str,
    evidence_items: list[Any],
    top_k: int,
    max_attempts: int = 3,
) -> list[Any]:
    """Apply reranking with simple retry for transient API failures."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return reranker.rerank_evidence(
                query=query,
                evidence_items=evidence_items,
                top_k=top_k,
            )
        except Exception as exc:  # pragma: no cover - network path
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(float(attempt))
    if last_error is None:
        raise ValueError("Rerank retry loop failed without an exception.")
    raise last_error


def as_hit(rank: int | None, cutoff: int) -> int:
    """Return 1 when a relevant item is found within cutoff, else 0."""
    return int(rank is not None and rank <= cutoff)


def reciprocal_rank(rank: int | None, cutoff: int) -> float:
    """Return reciprocal rank within cutoff, else 0."""
    if rank is None or rank > cutoff:
        return 0.0
    return 1.0 / float(rank)


def rank_delta(*, before: Any, after: Any) -> int | None:
    """Return final rank minus original rank when both ranks are known."""
    if before is None or after is None:
        return None
    return int(after) - int(before)


def phrase_recall(
    expected_phrases: tuple[str, ...],
    combined_text: str,
) -> float | None:
    """Measure phrase coverage in the concatenated retrieval text."""
    if not expected_phrases:
        return None
    hits = sum(1 for phrase in expected_phrases if phrase and phrase in combined_text)
    return round(hits / len(expected_phrases), 4)


def mean_value(rows: list[dict[str, Any]], key: str) -> float:
    """Return arithmetic mean for a required numeric field."""
    values = [float(row[key]) for row in rows]
    return sum(values) / len(values)


def optional_mean(rows: list[dict[str, Any]], key: str) -> float:
    """Return arithmetic mean over non-null numeric values, else 0."""
    values = [float(row[key]) for row in rows if row[key] is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def optional_key_mean(rows: list[dict[str, Any]], key: str) -> float:
    """Return arithmetic mean for optional numeric fields, else 0."""
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def percentile(values: list[float], quantile: float) -> float:
    """Return a simple inclusive percentile for non-empty numeric values."""
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def normalize_text(value: str) -> str:
    """Normalize text for robust benchmark substring matching."""
    normalized = unicodedata.normalize("NFC", value).lower()
    normalized = normalized.replace("**", " ")
    normalized = " ".join(normalized.split())
    return normalized.strip()


def provider_from_source_path(source_path: str) -> str:
    """Infer provider slug from a benchmark source path."""
    path = Path(source_path)
    if not path.parts:
        return "unknown"
    return path.parts[0]


def company_code_from_provider(provider: str) -> str | None:
    """Map a provider folder slug to the indexed company code."""
    return PROVIDER_COMPANY_CODE_BY_PROVIDER.get(provider)


def string_or_none(value: Any) -> str | None:
    """Convert blank-like values to None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON artifact."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write newline-delimited JSON rows."""
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to CSV using stable sorted headers."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
