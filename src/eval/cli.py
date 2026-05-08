"""Command-line interface for chunking benchmark runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.eval.chunking.registry import (
    all_strategy_names,
    available_strategy_specs,
    default_strategy_names,
)
from src.eval.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BENCHMARK_PATH,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CORPUS_DIR,
    DEFAULT_DEEPEVAL_THRESHOLD,
    DEFAULT_EMBEDDING_CACHE_ENABLED,
    DEFAULT_EMBEDDING_CACHE_PATH,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_HEADING_CUT_LEVEL,
    DEFAULT_HEADING_MAX_CHARS,
    DEFAULT_HEADING_MAX_TABLE_ROWS,
    DEFAULT_HEADING_MIN_CHARS,
    DEFAULT_LATE_CHUNKING_EMBEDDING_MODEL,
    DEFAULT_LATE_CHUNKING_MAX_TOKENS,
    DEFAULT_LIMIT_DOCUMENTS,
    DEFAULT_LLM_SCORING_CACHE_ENABLED,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RESUME_COMPLETED_STRATEGIES,
    DEFAULT_STRATEGY_RETRIES,
    DEFAULT_TOP_K,
    ChunkingRunConfig,
)
from src.eval.runner import ChunkingBenchmarkRunner


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        description="Build and evaluate real chunking strategies for health RAG.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list-strategies", help="List implemented strategies.")

    run_parser = subparsers.add_parser("run", help="Run chunking benchmark.")
    run_parser.add_argument(
        "--benchmark-path",
        type=Path,
        default=DEFAULT_BENCHMARK_PATH,
    )
    run_parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    run_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    run_parser.add_argument(
        "--run-id",
        help="Stable report run id for resumable runs under output-dir/reports.",
    )
    run_parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    run_parser.add_argument("--embedding-device", default=DEFAULT_EMBEDDING_DEVICE)
    run_parser.add_argument(
        "--embedding-cache-path",
        type=Path,
        default=DEFAULT_EMBEDDING_CACHE_PATH,
    )
    run_parser.add_argument(
        "--disable-embedding-cache",
        action="store_true",
        default=not DEFAULT_EMBEDDING_CACHE_ENABLED,
    )
    run_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    run_parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    run_parser.add_argument(
        "--late-chunking-embedding-model",
        default=DEFAULT_LATE_CHUNKING_EMBEDDING_MODEL,
    )
    run_parser.add_argument(
        "--late-chunking-max-tokens",
        type=int,
        default=DEFAULT_LATE_CHUNKING_MAX_TOKENS,
    )
    run_parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    run_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    run_parser.add_argument(
        "--strategy-retries",
        type=int,
        default=DEFAULT_STRATEGY_RETRIES,
        help="Retry count after the first failed attempt for each strategy.",
    )
    run_parser.add_argument(
        "--no-resume",
        action="store_true",
        default=not DEFAULT_RESUME_COMPLETED_STRATEGIES,
        help="Do not skip strategies that already succeeded in this run id.",
    )
    run_parser.add_argument(
        "--heading-cut-level",
        type=int,
        default=DEFAULT_HEADING_CUT_LEVEL,
        help="0 means auto-select from loaded corpus heading statistics.",
    )
    run_parser.add_argument(
        "--heading-max-chars",
        type=int,
        default=DEFAULT_HEADING_MAX_CHARS,
    )
    run_parser.add_argument(
        "--heading-min-chars",
        type=int,
        default=DEFAULT_HEADING_MIN_CHARS,
    )
    run_parser.add_argument(
        "--heading-max-table-rows",
        type=int,
        default=DEFAULT_HEADING_MAX_TABLE_ROWS,
    )
    run_parser.add_argument(
        "--strategies",
        default="recommended",
        help="Comma-separated names, 'recommended', or 'all'.",
    )
    run_parser.add_argument("--limit-cases", type=int)
    run_parser.add_argument(
        "--limit-documents",
        type=int,
        default=DEFAULT_LIMIT_DOCUMENTS,
        help="Number of benchmark-guided corpus files to index; use 0 for all.",
    )
    run_parser.add_argument("--skip-deepeval", action="store_true")
    run_parser.add_argument(
        "--disable-llm-scoring-cache",
        action="store_true",
        default=not DEFAULT_LLM_SCORING_CACHE_ENABLED,
    )
    run_parser.add_argument("--deepeval-model")
    run_parser.add_argument(
        "--deepeval-threshold",
        type=float,
        default=DEFAULT_DEEPEVAL_THRESHOLD,
    )
    run_parser.add_argument("--include-deepeval-reasons", action="store_true")
    return parser


def parse_strategy_names(value: str) -> list[str] | None:
    """Parse comma-separated strategy names."""

    normalized = value.strip().lower()
    if normalized in {"recommended", "default", "insurance"}:
        return None
    if normalized == "all":
        return all_strategy_names()
    return [name.strip() for name in value.split(",") if name.strip()]


def normalize_document_limit(value: int | None) -> int | None:
    """Convert non-positive document limits to full-corpus runs."""

    if value is None or value <= 0:
        return None
    return value


def main() -> None:
    """Run the CLI."""

    args = build_parser().parse_args()
    if args.command == "list-strategies":
        default_names = set(default_strategy_names())
        for spec in available_strategy_specs():
            markers = []
            if spec.name in default_names:
                markers.append("default")
            if spec.requires_embeddings:
                markers.append("requires embeddings")
            if spec.requires_llm:
                markers.append("requires LLM")
            if spec.optional_dependency:
                markers.append(f"requires {spec.optional_dependency}")
            marker = f" ({'; '.join(markers)})" if markers else ""
            print(f"{spec.name}{marker}: {spec.description}")
        return

    config = ChunkingRunConfig(
        benchmark_path=args.benchmark_path,
        corpus_dir=args.corpus_dir,
        output_dir=args.output_dir,
        run_id=args.run_id,
        embedding_model_name=args.embedding_model,
        embedding_device=args.embedding_device,
        embedding_cache_enabled=not args.disable_embedding_cache,
        embedding_cache_path=args.embedding_cache_path,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        late_chunking_embedding_model=args.late_chunking_embedding_model,
        late_chunking_max_tokens=args.late_chunking_max_tokens,
        top_k=args.top_k,
        batch_size=args.batch_size,
        strategy_retries=max(args.strategy_retries, 0),
        resume_completed_strategies=not args.no_resume,
        limit_documents=normalize_document_limit(args.limit_documents),
        heading_cut_level=args.heading_cut_level,
        heading_max_chars=args.heading_max_chars,
        heading_min_chars=args.heading_min_chars,
        heading_max_table_rows=args.heading_max_table_rows,
        deepeval_threshold=args.deepeval_threshold,
        deepeval_model=args.deepeval_model,
        include_deepeval_reasons=args.include_deepeval_reasons,
        run_deepeval=not args.skip_deepeval,
        llm_scoring_cache_enabled=not args.disable_llm_scoring_cache,
    )
    runner = ChunkingBenchmarkRunner(config)
    run_dir = runner.run(
        strategy_names=parse_strategy_names(args.strategies),
        limit_cases=args.limit_cases,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
