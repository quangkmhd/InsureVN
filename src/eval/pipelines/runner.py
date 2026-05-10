"""End-to-end chunking benchmark runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.eval.chunking.base import ChunkingStrategy
from src.eval.chunking.registry import (
    build_strategies,
    default_strategy_names,
    validate_strategy_names,
)
from src.eval.config import ChunkingRunConfig
from src.eval.corpus import load_markdown_corpus
from src.eval.embeddings.cache import EmbeddingCache, sha256_text, stable_json
from src.eval.embeddings import (
    build_retrieval_embeddings,
    build_semantic_chunking_embeddings,
)
from src.eval.evaluators.deepeval_retrieval import (
    DeepEvalRetrievalEvaluator,
    ProviderPoolDeepEvalLLM,
)
from src.eval.heading_analysis import (
    HeadingLevelRecommendation,
    analyze_heading_structure,
    decide_cut_level,
    heading_analysis_payload,
)
from src.eval.io import (
    ensure_directory,
    load_benchmark_cases,
    read_json,
    read_jsonl,
    write_csv,
    write_json,
    write_jsonl,
)
from src.eval.llamaindex_llms import build_markdown_element_llm
from src.eval.llm_provider_slots import provider_slot_counts
from src.eval.models import (
    BenchmarkCase,
    CorpusDocument,
    JsonDict,
    MetricScore,
    RetrievedChunk,
    StrategySummary,
    TextChunk,
)
from src.eval.vector_database import QdrantStrategyDatabase


@dataclass(frozen=True)
class StrategyRunResult:
    """Artifacts produced by one strategy run."""

    chunks: list[TextChunk]
    retrievals: list[RetrievedChunk]
    metric_scores: list[MetricScore]
    summary: StrategySummary


@dataclass(frozen=True)
class PreviousRunState:
    """Reusable successful artifacts from an existing run directory."""

    summaries: list[StrategySummary]
    retrievals: list[RetrievedChunk]
    metric_scores: list[MetricScore]
    completed_strategy_names: set[str]


@dataclass
class LLMScoringCacheStats:
    """Runtime counters for reused DeepEval scoring rows."""

    hits: int = 0
    misses: int = 0
    disabled: int = 0


class ChunkingBenchmarkRunner:
    """Build per-strategy vector databases, retrieve benchmark cases, and score."""

    def __init__(self, config: ChunkingRunConfig) -> None:
        self.config = config

    def run(
        self,
        strategy_names: list[str] | None = None,
        limit_cases: int | None = None,
        limit_documents: int | None = None,
    ) -> Path:
        """Run the benchmark and return the report directory."""

        run_dir = self._create_run_dir()
        all_benchmark_cases = load_benchmark_cases(self.config.benchmark_path)
        effective_limit_documents = resolve_document_limit(
            requested_limit=limit_documents,
            configured_limit=self.config.limit_documents,
        )
        corpus_documents = load_markdown_corpus(
            self.config.corpus_dir,
            effective_limit_documents,
            preferred_source_paths=primary_source_paths(all_benchmark_cases),
        )
        benchmark_cases = filter_cases_by_primary_source(
            all_benchmark_cases,
            {document.source_path for document in corpus_documents},
        )
        if limit_cases is not None:
            benchmark_cases = benchmark_cases[:limit_cases]
        heading_recommendations = analyze_heading_structure(corpus_documents)
        heading_cut_level = self.config.heading_cut_level or decide_cut_level(
            heading_recommendations
        )
        requested_strategy_names = strategy_names or default_strategy_names()
        validate_strategy_names(requested_strategy_names)
        validate_shared_embedding_model(self.config, requested_strategy_names)
        embedding_cache = EmbeddingCache(
            path=self.config.embedding_cache_path,
            enabled=self.config.embedding_cache_enabled,
        )
        retrieval_embeddings = build_retrieval_embeddings(
            provider=self.config.embedding_provider,
            model_name=self.config.embedding_model_name,
            batch_size=self.config.batch_size,
            device=self.config.embedding_device,
            cache=embedding_cache,
            google_api_key=self.config.embedding_google_api_key,
            google_api_keys=self.config.embedding_google_api_keys,
            google_output_dimensionality=(
                self.config.embedding_output_dimensionality
            ),
        )
        semantic_chunking_embeddings = (
            (
                retrieval_embeddings
                if can_reuse_retrieval_embeddings_for_semantic_chunking(self.config)
                else build_semantic_chunking_embeddings(
                    provider=self.config.semantic_chunking_embedding_provider,
                    model_name=self.config.semantic_chunking_embedding_model,
                    ollama_base_url=self.config.semantic_chunking_ollama_base_url,
                    batch_size=self.config.batch_size,
                    device=self.config.semantic_chunking_embedding_device,
                    cache=embedding_cache,
                )
            )
            if needs_semantic_chunking_embeddings(requested_strategy_names)
            else None
        )
        markdown_element_llm = (
            build_markdown_element_llm(
                provider=self.config.markdown_element_llm_provider,
                gemini_model=self.config.markdown_element_gemini_model,
                gemini_api_keys=self.config.markdown_element_gemini_api_keys,
                provider_slots=self.config.markdown_element_llm_provider_slots,
                request_timeout_seconds=(
                    self.config.markdown_element_llm_timeout_seconds
                ),
            )
            if needs_markdown_element_llm(requested_strategy_names)
            else None
        )
        hybrid_retrieval_embeddings = (
            retrieval_embeddings
            if needs_hybrid_retrieval_embeddings(requested_strategy_names)
            else None
        )
        validate_runtime_embedding_dimensions(
            retrieval_embeddings=retrieval_embeddings,
            semantic_chunking_embeddings=semantic_chunking_embeddings,
            hybrid_retrieval_embeddings=hybrid_retrieval_embeddings,
        )
        strategies = build_strategies(
            selected_names=requested_strategy_names,
            semantic_chunking_embeddings=semantic_chunking_embeddings,
            markdown_element_llm=markdown_element_llm,
            markdown_element_num_workers=self.config.markdown_element_num_workers,
            hybrid_retrieval_embeddings=hybrid_retrieval_embeddings,
            heading_cut_level=heading_cut_level,
            heading_max_chars=self.config.heading_max_chars,
            heading_min_chars=self.config.heading_min_chars,
            heading_max_table_rows=self.config.heading_max_table_rows,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )
        evaluator = self._build_evaluator()
        resume_signature = build_resume_signature(
            config=self.config,
            benchmark_cases=benchmark_cases,
            loaded_source_paths=[
                corpus_document.source_path for corpus_document in corpus_documents
            ],
            limit_documents=effective_limit_documents,
            heading_cut_level=heading_cut_level,
        )
        previous_run_state = load_previous_run_state(
            run_dir=run_dir,
            strategy_names=[strategy.name for strategy in strategies],
            resume_signature=resume_signature,
            enabled=self.config.resume_completed_strategies,
        )
        scoring_cache_stats = LLMScoringCacheStats()
        llm_scoring_cache_enabled = (
            evaluator is not None and self.config.llm_scoring_cache_enabled
        )
        scoring_cache = load_llm_scoring_cache(
            run_dir=run_dir,
            evaluator=evaluator,
            enabled=llm_scoring_cache_enabled,
        )

        all_retrievals: list[RetrievedChunk] = list(previous_run_state.retrievals)
        all_scores: list[MetricScore] = list(previous_run_state.metric_scores)
        summaries: list[StrategySummary] = list(previous_run_state.summaries)

        for strategy in strategies:
            if strategy.name in previous_run_state.completed_strategy_names:
                continue
            strategy_result = run_strategy_with_retries(
                strategy=strategy,
                corpus_documents=corpus_documents,
                benchmark_cases=benchmark_cases,
                evaluator=evaluator,
                retrieval_embeddings=retrieval_embeddings,
                database_path=run_dir / "vector_databases" / strategy.name,
                collection_name=self.config.collection_name,
                top_k=self.config.top_k,
                max_retries=self.config.strategy_retries,
                scoring_cache=scoring_cache,
                scoring_cache_stats=scoring_cache_stats,
                scoring_cache_enabled=llm_scoring_cache_enabled,
            )
            all_retrievals.extend(strategy_result.retrievals)
            all_scores.extend(strategy_result.metric_scores)
            summaries.append(strategy_result.summary)

        self._write_reports(
            run_dir=run_dir,
            benchmark_cases=benchmark_cases,
            summaries=summaries,
            retrievals=all_retrievals,
            metric_scores=all_scores,
            strategy_names=[strategy.name for strategy in strategies],
            limit_documents=effective_limit_documents,
            benchmark_case_count_before_filter=len(all_benchmark_cases),
            loaded_source_paths=[
                corpus_document.source_path for corpus_document in corpus_documents
            ],
            heading_cut_level=heading_cut_level,
            heading_recommendations=heading_recommendations,
            embedding_cache_payload=embedding_cache.to_payload(),
            llm_scoring_cache_payload={
                "enabled": llm_scoring_cache_enabled,
                "stats": asdict(scoring_cache_stats),
            },
            resume_signature=resume_signature,
            skipped_strategy_names=sorted(previous_run_state.completed_strategy_names),
        )
        return run_dir

    def _build_evaluator(self) -> DeepEvalRetrievalEvaluator | None:
        if not self.config.run_deepeval:
            return None
        deepeval_model = self.config.deepeval_model
        if deepeval_model is None:
            judge_llm = build_markdown_element_llm(
                provider=self.config.markdown_element_llm_provider,
                gemini_model=self.config.markdown_element_gemini_model,
                gemini_api_keys=self.config.markdown_element_gemini_api_keys,
                provider_slots=self.config.markdown_element_llm_provider_slots,
                request_timeout_seconds=(
                    self.config.markdown_element_llm_timeout_seconds
                ),
            )
            deepeval_model = ProviderPoolDeepEvalLLM(
                provider_pool_llm=judge_llm,
                model_name=build_provider_pool_judge_name(self.config),
            )
        return DeepEvalRetrievalEvaluator(
            threshold=self.config.deepeval_threshold,
            model=deepeval_model,
            include_reason=self.config.include_deepeval_reasons,
        )

    def _create_run_dir(self) -> Path:
        run_id = self.config.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        validate_run_id(run_id)
        run_dir = self.config.output_dir / "reports" / run_id
        ensure_directory(run_dir)
        return run_dir

    def _write_reports(
        self,
        run_dir: Path,
        benchmark_cases: list[BenchmarkCase],
        summaries: list[StrategySummary],
        retrievals: list[RetrievedChunk],
        metric_scores: list[MetricScore],
        strategy_names: list[str],
        limit_documents: int | None,
        benchmark_case_count_before_filter: int,
        loaded_source_paths: list[str],
        heading_cut_level: int,
        heading_recommendations: dict[int, HeadingLevelRecommendation],
        embedding_cache_payload: dict[str, object],
        llm_scoring_cache_payload: dict[str, object],
        resume_signature: JsonDict,
        skipped_strategy_names: list[str],
    ) -> None:
        write_jsonl(run_dir / "retrievals.jsonl", retrievals)
        write_jsonl(run_dir / "deepeval_scores.jsonl", metric_scores)
        write_jsonl(run_dir / "strategy_summary.jsonl", summaries)
        write_csv(run_dir / "strategy_summary.csv", summary_csv_rows(summaries))
        write_json(
            run_dir / "manifest.json",
            {
                "run_id": run_dir.name,
                "benchmark_path": str(self.config.benchmark_path),
                "corpus_dir": str(self.config.corpus_dir),
                "embedding_provider": self.config.embedding_provider,
                "embedding_model_name": self.config.embedding_model_name,
                "embedding_device": self.config.embedding_device,
                "embedding_output_dimensionality": (
                    self.config.embedding_output_dimensionality
                ),
                "embedding_cache": embedding_cache_payload,
                "llm_scoring_cache": llm_scoring_cache_payload,
                "strategy_retries": self.config.strategy_retries,
                "resume_completed_strategies": (
                    self.config.resume_completed_strategies
                ),
                "resume_signature": resume_signature,
                "skipped_strategy_names": skipped_strategy_names,
                "semantic_chunking_embedding_provider": (
                    self.config.semantic_chunking_embedding_provider
                ),
                "semantic_chunking_embedding_model": (
                    self.config.semantic_chunking_embedding_model
                ),
                "semantic_chunking_embedding_device": (
                    self.config.semantic_chunking_embedding_device
                ),
                "semantic_chunking_ollama_base_url": (
                    self.config.semantic_chunking_ollama_base_url
                ),
                "markdown_element_llm_provider": (
                    self.config.markdown_element_llm_provider
                ),
                "markdown_element_gemini_model": (
                    self.config.markdown_element_gemini_model
                ),
                "markdown_element_gemini_api_key_count": len(
                    self.config.markdown_element_gemini_api_keys
                ),
                "markdown_element_llm_slot_count": len(
                    self.config.markdown_element_llm_provider_slots
                ),
                "markdown_element_llm_provider_slot_counts": provider_slot_counts(
                    self.config.markdown_element_llm_provider_slots
                ),
                "markdown_element_llm_timeout_seconds": (
                    self.config.markdown_element_llm_timeout_seconds
                ),
                "markdown_element_num_workers": (
                    self.config.markdown_element_num_workers
                ),
                "late_chunking_embedding_model": (
                    self.config.late_chunking_embedding_model
                ),
                "late_chunking_span_pooling_enabled": False,
                "late_chunking_max_tokens": self.config.late_chunking_max_tokens,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "heading_cut_level": heading_cut_level,
                "heading_max_chars": self.config.heading_max_chars,
                "heading_min_chars": self.config.heading_min_chars,
                "heading_max_table_rows": self.config.heading_max_table_rows,
                "heading_recommendations": heading_analysis_payload(
                    heading_recommendations
                ),
                "top_k": self.config.top_k,
                "run_deepeval": self.config.run_deepeval,
                "deepeval_model": (
                    self.config.deepeval_model
                    or build_provider_pool_judge_name(self.config)
                ),
                "benchmark_case_count": len(benchmark_cases),
                "benchmark_case_count_before_corpus_filter": (
                    benchmark_case_count_before_filter
                ),
                "benchmark_case_filter": "primary_source_in_loaded_corpus",
                "document_limit": limit_documents,
                "loaded_source_paths": loaded_source_paths,
                "strategy_names": strategy_names,
            },
        )


def run_strategy_with_retries(
    strategy: ChunkingStrategy,
    corpus_documents: list[CorpusDocument],
    benchmark_cases: list[BenchmarkCase],
    evaluator: DeepEvalRetrievalEvaluator | None,
    retrieval_embeddings: object,
    database_path: Path,
    collection_name: str,
    top_k: int,
    max_retries: int,
    scoring_cache: dict[str, list[MetricScore]],
    scoring_cache_stats: LLMScoringCacheStats,
    scoring_cache_enabled: bool,
) -> StrategyRunResult:
    """Run one strategy, retrying failed attempts."""

    attempts = max(max_retries, 0) + 1
    last_result: StrategyRunResult | None = None
    for attempt_number in range(1, attempts + 1):
        last_result = run_strategy_once(
            strategy=strategy,
            corpus_documents=corpus_documents,
            benchmark_cases=benchmark_cases,
            evaluator=evaluator,
            retrieval_embeddings=retrieval_embeddings,
            database_path=database_path,
            collection_name=collection_name,
            top_k=top_k,
            attempt_number=attempt_number,
            scoring_cache=scoring_cache,
            scoring_cache_stats=scoring_cache_stats,
            scoring_cache_enabled=scoring_cache_enabled,
        )
        if last_result.summary.evaluation_error is None:
            return last_result
    if last_result is None:
        msg = "Strategy retry loop did not run any attempts."
        raise RuntimeError(msg)
    return last_result


def run_strategy_once(
    strategy: ChunkingStrategy,
    corpus_documents: list[CorpusDocument],
    benchmark_cases: list[BenchmarkCase],
    evaluator: DeepEvalRetrievalEvaluator | None,
    retrieval_embeddings: object,
    database_path: Path,
    collection_name: str,
    top_k: int,
    attempt_number: int,
    scoring_cache: dict[str, list[MetricScore]],
    scoring_cache_stats: LLMScoringCacheStats,
    scoring_cache_enabled: bool,
) -> StrategyRunResult:
    """Run one strategy attempt and return its artifacts."""

    strategy_chunks: list[TextChunk] = []
    strategy_retrievals: list[RetrievedChunk] = []
    strategy_scores: list[MetricScore] = []
    evaluation_error: str | None = None
    database: QdrantStrategyDatabase | None = None
    try:
        for corpus_document in corpus_documents:
            strategy_chunks.extend(strategy.chunk_document(corpus_document))

        strategy_embeddings = (
            strategy.retrieval_embeddings
            if hasattr(strategy, "retrieval_embeddings")
            else retrieval_embeddings
        )
        database = QdrantStrategyDatabase(
            database_path=database_path,
            collection_name=collection_name,
            embeddings=strategy_embeddings,
        )
        database.rebuild(strategy_chunks)
        for benchmark_case in benchmark_cases:
            retrieved_chunks = database.search(
                case_id=benchmark_case.case_id,
                strategy=strategy.name,
                query=benchmark_case.question,
                top_k=top_k,
            )
            strategy_retrievals.extend(retrieved_chunks)
            if evaluator is not None:
                if scoring_cache_enabled:
                    case_scores = evaluate_case_with_llm_scoring_cache(
                        evaluator=evaluator,
                        strategy=strategy.name,
                        benchmark_case=benchmark_case,
                        retrieved_chunks=retrieved_chunks,
                        scoring_cache=scoring_cache,
                        scoring_cache_stats=scoring_cache_stats,
                    )
                else:
                    scoring_cache_stats.disabled += len(evaluator.metric_names)
                    case_scores = evaluator.evaluate_case(
                        strategy=strategy.name,
                        benchmark_case=benchmark_case,
                        retrieved_chunks=retrieved_chunks,
                    )
                strategy_scores.extend(case_scores)
    except Exception as exc:
        evaluation_error = f"{type(exc).__name__}: {exc}"
    finally:
        if database is not None:
            database.close()

    return StrategyRunResult(
        chunks=strategy_chunks,
        retrievals=strategy_retrievals if evaluation_error is None else [],
        metric_scores=strategy_scores if evaluation_error is None else [],
        summary=StrategySummary(
            strategy=strategy.name,
            document_count=len(corpus_documents),
            chunk_count=len(strategy_chunks),
            database_path=str(database_path),
            metric_means=metric_means(strategy_scores),
            evaluation_error=evaluation_error,
            attempt_count=attempt_number,
            skipped_existing_success=False,
        ),
    )


def evaluate_case_with_llm_scoring_cache(
    evaluator: DeepEvalRetrievalEvaluator,
    strategy: str,
    benchmark_case: BenchmarkCase,
    retrieved_chunks: list[RetrievedChunk],
    scoring_cache: dict[str, list[MetricScore]],
    scoring_cache_stats: LLMScoringCacheStats,
) -> list[MetricScore]:
    """Evaluate one case, reusing existing LLM scores when context matches."""

    scoring_cache_key = build_llm_scoring_cache_key(
        evaluator=evaluator,
        strategy=strategy,
        benchmark_case=benchmark_case,
        retrieved_chunks=retrieved_chunks,
    )
    cached_scores = scoring_cache.get(scoring_cache_key)
    if cached_scores is not None:
        scoring_cache_stats.hits += len(cached_scores)
        return [
            metric_score_with_cache_hit(metric_score, scoring_cache_key)
            for metric_score in cached_scores
        ]

    scoring_cache_stats.misses += len(evaluator.metric_names)
    scores = evaluator.evaluate_case(
        strategy=strategy,
        benchmark_case=benchmark_case,
        retrieved_chunks=retrieved_chunks,
        scoring_cache_key=scoring_cache_key,
    )
    if all(score.error is None for score in scores):
        scoring_cache[scoring_cache_key] = scores
    return scores


def load_llm_scoring_cache(
    run_dir: Path,
    evaluator: DeepEvalRetrievalEvaluator | None,
    enabled: bool,
) -> dict[str, list[MetricScore]]:
    """Load previous successful DeepEval scores by scoring cache key."""

    if evaluator is None or not enabled:
        return {}

    expected_metric_names = set(evaluator.metric_names)
    grouped_scores: dict[str, list[MetricScore]] = {}
    for payload in read_jsonl(run_dir / "deepeval_scores.jsonl"):
        metric_score = metric_score_from_payload(payload)
        if metric_score.scoring_cache_key is None or metric_score.error is not None:
            continue
        grouped_scores.setdefault(metric_score.scoring_cache_key, []).append(
            metric_score
        )

    return {
        cache_key: metric_scores
        for cache_key, metric_scores in grouped_scores.items()
        if {metric_score.metric_name for metric_score in metric_scores}
        == expected_metric_names
    }


def build_llm_scoring_cache_key(
    evaluator: DeepEvalRetrievalEvaluator,
    strategy: str,
    benchmark_case: BenchmarkCase,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    """Build a stable key for one LLM scoring input."""

    payload = {
        "version": "llm-scoring-cache-v1",
        "evaluator": evaluator.cache_config_payload(),
        "strategy": strategy,
        "case_id": benchmark_case.case_id,
        "question": benchmark_case.question,
        "gold_answer": benchmark_case.gold_answer,
        "retrieval_context": [
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


def metric_score_with_cache_hit(
    metric_score: MetricScore,
    scoring_cache_key: str,
) -> MetricScore:
    """Return a metric score marked as reused from cache."""

    return MetricScore(
        case_id=metric_score.case_id,
        strategy=metric_score.strategy,
        metric_name=metric_score.metric_name,
        score=metric_score.score,
        threshold=metric_score.threshold,
        success=metric_score.success,
        reason=metric_score.reason,
        error=metric_score.error,
        scoring_cache_key=scoring_cache_key,
        scoring_cache_hit=True,
    )


def load_previous_run_state(
    run_dir: Path,
    strategy_names: list[str],
    resume_signature: JsonDict,
    enabled: bool,
) -> PreviousRunState:
    """Load successful strategy artifacts from an existing compatible run."""

    empty_state = PreviousRunState(
        summaries=[],
        retrievals=[],
        metric_scores=[],
        completed_strategy_names=set(),
    )
    if not enabled:
        return empty_state
    manifest = read_json(run_dir / "manifest.json")
    if manifest is None or manifest.get("resume_signature") != resume_signature:
        return empty_state

    requested_strategy_names = set(strategy_names)
    completed_summaries: list[StrategySummary] = []
    completed_strategy_names: set[str] = set()
    for payload in read_jsonl(run_dir / "strategy_summary.jsonl"):
        strategy_name = str(payload.get("strategy", ""))
        if strategy_name not in requested_strategy_names:
            continue
        if payload.get("evaluation_error"):
            continue
        summary = strategy_summary_from_payload(
            payload,
            skipped_existing_success=True,
        )
        if not Path(summary.database_path).exists():
            continue
        completed_summaries.append(summary)
        completed_strategy_names.add(strategy_name)

    if not completed_strategy_names:
        return empty_state

    return PreviousRunState(
        summaries=completed_summaries,
        retrievals=[
            retrieved_chunk_from_payload(payload)
            for payload in read_jsonl(run_dir / "retrievals.jsonl")
            if str(payload.get("strategy", "")) in completed_strategy_names
        ],
        metric_scores=[
            metric_score_from_payload(payload)
            for payload in read_jsonl(run_dir / "deepeval_scores.jsonl")
            if str(payload.get("strategy", "")) in completed_strategy_names
        ],
        completed_strategy_names=completed_strategy_names,
    )


def strategy_summary_from_payload(
    payload: JsonDict,
    skipped_existing_success: bool,
) -> StrategySummary:
    """Build a strategy summary from a JSONL row."""

    return StrategySummary(
        strategy=str(payload.get("strategy", "")),
        document_count=int(payload.get("document_count", 0)),
        chunk_count=int(payload.get("chunk_count", 0)),
        database_path=str(payload.get("database_path", "")),
        metric_means=dict(payload.get("metric_means", {})),
        evaluation_error=payload.get("evaluation_error") or None,
        attempt_count=int(payload.get("attempt_count", 1)),
        skipped_existing_success=skipped_existing_success,
    )


def retrieved_chunk_from_payload(payload: JsonDict) -> RetrievedChunk:
    """Build a retrieved chunk from a JSONL row."""

    return RetrievedChunk(
        case_id=str(payload.get("case_id", "")),
        strategy=str(payload.get("strategy", "")),
        rank=int(payload.get("rank", 0)),
        score=float(payload.get("score", 0.0)),
        chunk_id=str(payload.get("chunk_id", "")),
        source_path=str(payload.get("source_path", "")),
        provider=str(payload.get("provider", "")),
        text=str(payload.get("text", "")),
        start_line=int(payload.get("start_line", 0)),
        end_line=int(payload.get("end_line", 0)),
        metadata=dict(payload.get("metadata", {})),
    )


def metric_score_from_payload(payload: JsonDict) -> MetricScore:
    """Build a metric score from a JSONL row."""

    return MetricScore(
        case_id=str(payload.get("case_id", "")),
        strategy=str(payload.get("strategy", "")),
        metric_name=str(payload.get("metric_name", "")),
        score=optional_float(payload.get("score")),
        threshold=float(payload.get("threshold", 0.0)),
        success=optional_bool(payload.get("success")),
        reason=payload.get("reason"),
        error=payload.get("error"),
        scoring_cache_key=payload.get("scoring_cache_key"),
        scoring_cache_hit=bool(payload.get("scoring_cache_hit", False)),
    )


def build_resume_signature(
    config: ChunkingRunConfig,
    benchmark_cases: list[BenchmarkCase],
    loaded_source_paths: list[str],
    limit_documents: int | None,
    heading_cut_level: int,
) -> JsonDict:
    """Build the compatibility signature used for resumable strategy skips."""

    return {
        "benchmark_path": str(config.benchmark_path),
        "benchmark_case_ids": [
            benchmark_case.case_id for benchmark_case in benchmark_cases
        ],
        "corpus_dir": str(config.corpus_dir),
        "loaded_source_paths": loaded_source_paths,
        "document_limit": limit_documents,
        "embedding_provider": config.embedding_provider,
        "embedding_model_name": config.embedding_model_name,
        "embedding_device": config.embedding_device,
        "embedding_output_dimensionality": config.embedding_output_dimensionality,
        "semantic_chunking_embedding_provider": (
            config.semantic_chunking_embedding_provider
        ),
        "semantic_chunking_embedding_model": config.semantic_chunking_embedding_model,
        "semantic_chunking_embedding_device": (
            config.semantic_chunking_embedding_device
        ),
        "semantic_chunking_ollama_base_url": config.semantic_chunking_ollama_base_url,
        "late_chunking_embedding_model": config.late_chunking_embedding_model,
        "late_chunking_span_pooling_enabled": False,
        "late_chunking_max_tokens": config.late_chunking_max_tokens,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "heading_cut_level": heading_cut_level,
        "heading_max_chars": config.heading_max_chars,
        "heading_min_chars": config.heading_min_chars,
        "heading_max_table_rows": config.heading_max_table_rows,
        "top_k": config.top_k,
        "run_deepeval": config.run_deepeval,
        "deepeval_model": config.deepeval_model
        or build_provider_pool_judge_name(config),
        "deepeval_threshold": config.deepeval_threshold,
        "include_deepeval_reasons": config.include_deepeval_reasons,
        "markdown_element_llm_provider": config.markdown_element_llm_provider,
        "markdown_element_gemini_model": config.markdown_element_gemini_model,
        "markdown_element_llm_provider_slot_counts": provider_slot_counts(
            config.markdown_element_llm_provider_slots
        ),
        "markdown_element_llm_timeout_seconds": (
            config.markdown_element_llm_timeout_seconds
        ),
    }


def optional_float(value: object) -> float | None:
    """Convert optional JSON value to float."""

    if value is None:
        return None
    return float(value)


def optional_bool(value: object) -> bool | None:
    """Convert optional JSON value to bool."""

    if value is None:
        return None
    return bool(value)


def build_provider_pool_judge_name(config: ChunkingRunConfig) -> str:
    """Return a stable DeepEval judge name for the configured provider pool."""

    provider_counts = provider_slot_counts(config.markdown_element_llm_provider_slots)
    provider_count_parts = [
        f"{provider}:{count}" for provider, count in sorted(provider_counts.items())
    ]
    return "provider_pool(" + ",".join(provider_count_parts) + ")"


def validate_run_id(run_id: str) -> None:
    """Validate a report run id before using it as a directory name."""

    if not run_id or run_id in {".", ".."}:
        msg = "run_id must not be empty, '.', or '..'."
        raise ValueError(msg)
    allowed_characters = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    )
    if any(character not in allowed_characters for character in run_id):
        msg = "run_id may contain only letters, numbers, dots, dashes, and underscores."
        raise ValueError(msg)


def metric_means(metric_scores: list[MetricScore]) -> dict[str, float]:
    """Aggregate DeepEval metric scores by metric name."""

    score_values: dict[str, list[float]] = {}
    for metric_score in metric_scores:
        if metric_score.score is None:
            continue
        score_values.setdefault(metric_score.metric_name, []).append(metric_score.score)
    return {
        metric_name: sum(values) / len(values)
        for metric_name, values in sorted(score_values.items())
        if values
    }


def summary_csv_rows(summaries: list[StrategySummary]) -> list[dict[str, object]]:
    """Flatten summary dataclasses for CSV output."""

    rows: list[dict[str, object]] = []
    for summary in summaries:
        row: dict[str, object] = {
            "strategy": summary.strategy,
            "document_count": summary.document_count,
            "chunk_count": summary.chunk_count,
            "database_path": summary.database_path,
            "evaluation_error": summary.evaluation_error or "",
            "attempt_count": summary.attempt_count,
            "skipped_existing_success": summary.skipped_existing_success,
        }
        for metric_name, value in summary.metric_means.items():
            row[f"{metric_name}_mean"] = value
        rows.append(row)
    return rows


def strategy_summary_payload(
    summaries: list[StrategySummary],
) -> list[dict[str, object]]:
    """Return summaries as dictionaries."""

    return [asdict(summary) for summary in summaries]


def primary_source_paths(benchmark_cases: list[BenchmarkCase]) -> list[str]:
    """Return unique benchmark primary source paths in benchmark order."""

    source_paths: list[str] = []
    for benchmark_case in benchmark_cases:
        source_path = primary_expected_source_path(benchmark_case)
        if source_path and source_path not in source_paths:
            source_paths.append(source_path)
    return source_paths


def filter_cases_by_primary_source(
    benchmark_cases: list[BenchmarkCase],
    source_paths: set[str],
) -> list[BenchmarkCase]:
    """Keep only benchmark cases whose primary source is indexed."""

    filtered_cases: list[BenchmarkCase] = []
    for benchmark_case in benchmark_cases:
        primary_source_path = primary_expected_source_path(benchmark_case)
        if primary_source_path in source_paths:
            filtered_cases.append(benchmark_case)
    return filtered_cases


def primary_expected_source_path(benchmark_case: BenchmarkCase) -> str:
    """Return the primary expected source path for a benchmark case."""

    for expected_source in benchmark_case.expected_sources:
        if expected_source.relationship == "primary":
            return expected_source.source_path
    if benchmark_case.expected_sources:
        return benchmark_case.expected_sources[0].source_path
    return ""


def resolve_document_limit(
    requested_limit: int | None,
    configured_limit: int | None,
) -> int | None:
    """Resolve per-run and config document limits."""

    document_limit = configured_limit if requested_limit is None else requested_limit
    if document_limit is not None and document_limit <= 0:
        return None
    return document_limit


def needs_semantic_chunking_embeddings(strategy_names: list[str]) -> bool:
    """Return True when selected strategies need semantic breakpoint embeddings."""

    return any(
        strategy_name in {"semantic_embedding", "markdown_then_semantic"}
        for strategy_name in strategy_names
    )


def can_reuse_retrieval_embeddings_for_semantic_chunking(
    config: ChunkingRunConfig,
) -> bool:
    """Return True when semantic chunking can share retrieval embeddings."""

    normalized_provider = config.semantic_chunking_embedding_provider.strip().lower()
    return (
        config.embedding_provider.strip().lower()
        in {"sentence_transformer", "sentence_transformers"}
        and normalized_provider
        in {"sentence_transformer", "sentence_transformers"}
        and config.semantic_chunking_embedding_model == config.embedding_model_name
        and config.semantic_chunking_embedding_device == config.embedding_device
    )


def needs_markdown_element_llm(strategy_names: list[str]) -> bool:
    """Return True when selected strategies need a configured LLM."""

    return any(
        strategy_name
        in {
            "insurance_contract_hybrid_late",
            "llm_markdown_optimal",
            "llamaindex_markdown_element",
        }
        for strategy_name in strategy_names
    )


def needs_hybrid_retrieval_embeddings(strategy_names: list[str]) -> bool:
    """Return True when selected strategies need hybrid retrieval embeddings."""

    return "insurance_contract_hybrid_late" in strategy_names


def validate_shared_embedding_model(
    config: ChunkingRunConfig,
    strategy_names: list[str],
) -> None:
    """Require one embedding model name when the hybrid strategy is benchmarked."""

    if (
        needs_hybrid_retrieval_embeddings(strategy_names)
        and config.embedding_model_name != config.late_chunking_embedding_model
    ):
        msg = (
            "insurance_contract_hybrid_late uses the retrieval embedding model. "
            "Set --embedding-model and --late-chunking-embedding-model to the same "
            "model, or update CHUNKING_EVAL_EMBEDDING_MODEL and "
            "LATE_CHUNKING_EMBEDDING_MODEL together."
        )
        raise ValueError(msg)


def validate_runtime_embedding_dimensions(
    retrieval_embeddings: object,
    semantic_chunking_embeddings: object | None,
    hybrid_retrieval_embeddings: object | None,
) -> None:
    """Require selected embedding adapters to expose the same vector dimension."""

    dimensions = {"retrieval": embedding_dimension(retrieval_embeddings)}
    if semantic_chunking_embeddings is not None:
        dimensions["semantic_chunking"] = embedding_dimension(
            semantic_chunking_embeddings
        )
    if hybrid_retrieval_embeddings is not None:
        dimensions["hybrid_retrieval"] = embedding_dimension(
            hybrid_retrieval_embeddings
        )

    expected_dimension = dimensions["retrieval"]
    mismatched_dimensions = {
        name: dimension
        for name, dimension in dimensions.items()
        if dimension != expected_dimension
    }
    if mismatched_dimensions:
        msg = (
            "Selected embedding adapters do not share one vector dimension: "
            f"{dimensions}. Use the same embedding family/config, not vector "
            "padding, truncation, or projection."
        )
        raise ValueError(msg)


def embedding_dimension(embeddings: object) -> int:
    """Return embedding dimension from adapter property or a probe query."""

    if hasattr(embeddings, "dimension"):
        dimension = embeddings.dimension
        if isinstance(dimension, int):
            return dimension
    return len(embeddings.embed_query("dimension probe"))
