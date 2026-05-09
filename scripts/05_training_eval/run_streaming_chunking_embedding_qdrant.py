"""CLI for streaming chunking + embedding + Qdrant upsert benchmarks."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SAFE_THREAD_ENVIRONMENT = {
    "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
}
for environment_key, environment_value in SAFE_THREAD_ENVIRONMENT.items():
    os.environ.setdefault(environment_key, environment_value)

from src.eval.streaming_qdrant_chunking import (
    DEFAULT_CPU_ABORT_CONSECUTIVE_SAMPLES,
    DEFAULT_CPU_ABORT_PERCENT,
    DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    DEFAULT_MIN_AVAILABLE_MEMORY_MB,
    DEFAULT_RESOURCE_SAMPLE_SECONDS,
    SAFE_STREAMING_STRATEGY_NAMES,
    SOURCE_SELECTION_PRIMARY,
    SUPPORTED_SOURCE_SELECTIONS,
    StreamingChunkEmbeddingConfig,
    run_streaming_chunking_embedding_qdrant,
)


def main() -> int:
    """Run the streaming Qdrant chunking benchmark."""

    args = parse_args()
    apply_safe_thread_environment()
    strategies = tuple(
        strategy.strip() for strategy in args.strategies.split(",") if strategy.strip()
    )
    config = StreamingChunkEmbeddingConfig(
        benchmark_path=args.benchmark_path,
        corpus_dir=args.corpus_dir,
        output_dir=args.output_dir,
        qdrant_work_dir=args.qdrant_work_dir,
        embedding_cache_path=args.embedding_cache_path,
        strategies=strategies,
        limit_documents=args.limit_documents if args.limit_documents > 0 else None,
        source_selection=args.source_selection,
        embedding_batch_size=args.embedding_batch_size,
        keep_qdrant=args.keep_qdrant,
        max_chunks_per_file=args.max_chunks_per_file,
        cpu_abort_percent=None
        if args.disable_resource_guard
        else args.cpu_abort_percent,
        min_available_memory_mb=None
        if args.disable_resource_guard
        else args.min_available_memory_mb,
        resource_sample_seconds=args.resource_sample_seconds,
        cpu_abort_consecutive_samples=args.cpu_abort_consecutive_samples,
        markdown_element_llm_provider=args.markdown_element_llm_provider,
        markdown_element_llm_timeout_seconds=(
            args.markdown_element_llm_timeout_seconds
        ),
        markdown_element_llm_max_slot_attempts=(
            args.markdown_element_llm_max_slot_attempts
        ),
        markdown_element_num_workers=args.markdown_element_num_workers,
        chunk_cache_dir=args.chunk_cache_dir,
        reuse_chunk_cache=not args.no_reuse_chunk_cache,
        write_chunk_cache=not args.no_write_chunk_cache,
        write_chunk_records=not args.no_write_chunk_records,
    )
    output_dir = run_streaming_chunking_embedding_qdrant(config)
    print(output_dir)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark-path",
        type=Path,
        default=StreamingChunkEmbeddingConfig.benchmark_path,
        help="Benchmark JSONL used to select source documents and eval cases.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=StreamingChunkEmbeddingConfig.corpus_dir,
        help="Root directory containing cleaned Markdown source files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/insurevn_streaming_chunking_embedding_qdrant/out"),
    )
    parser.add_argument(
        "--qdrant-work-dir",
        type=Path,
        default=Path("/tmp/insurevn_streaming_chunking_embedding_qdrant/qdrant"),
    )
    parser.add_argument(
        "--embedding-cache-path",
        type=Path,
        default=Path(
            "/tmp/insurevn_streaming_chunking_embedding_qdrant/embedding_cache.sqlite"
        ),
    )
    parser.add_argument(
        "--strategies",
        default=",".join(SAFE_STREAMING_STRATEGY_NAMES),
        help="Comma-separated chunking strategy names.",
    )
    parser.add_argument(
        "--limit-documents",
        type=int,
        default=10,
        help="Limit selected source documents. Use 0 to include all selected sources.",
    )
    parser.add_argument(
        "--source-selection",
        choices=sorted(SUPPORTED_SOURCE_SELECTIONS),
        default=SOURCE_SELECTION_PRIMARY,
        help="Select primary source paths or every expected source path from JSONL.",
    )
    parser.add_argument("--embedding-batch-size", type=int, default=8)
    parser.add_argument("--max-chunks-per-file", type=int)
    parser.add_argument("--markdown-element-llm-provider", default="multi")
    parser.add_argument(
        "--markdown-element-llm-timeout-seconds", type=float, default=60
    )
    parser.add_argument(
        "--markdown-element-llm-max-slot-attempts",
        type=int,
        default=DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
        help="Maximum provider slots to try for one LLM prompt before fallback.",
    )
    parser.add_argument(
        "--markdown-element-num-workers",
        type=int,
        default=0,
        help="LLM chunking workers. Use 0 to use every configured provider slot.",
    )
    parser.add_argument(
        "--chunk-cache-dir",
        type=Path,
        default=Path("data/eval_chunk_cache/chunk_boundaries"),
        help="Directory for reusable chunk boundary cache files.",
    )
    parser.add_argument(
        "--no-reuse-chunk-cache",
        action="store_true",
        help="Do not read existing chunk boundary cache files.",
    )
    parser.add_argument(
        "--no-write-chunk-cache",
        action="store_true",
        help="Do not write reusable chunk boundary cache files.",
    )
    parser.add_argument(
        "--no-write-chunk-records",
        action="store_true",
        help="Do not write per-chunk boundary JSONL records in the output dir.",
    )
    parser.add_argument(
        "--cpu-abort-percent",
        type=float,
        default=DEFAULT_CPU_ABORT_PERCENT,
        help="Abort when system CPU stays above this percent for consecutive samples.",
    )
    parser.add_argument(
        "--min-available-memory-mb",
        type=int,
        default=DEFAULT_MIN_AVAILABLE_MEMORY_MB,
        help="Abort when MemAvailable drops below this MiB value.",
    )
    parser.add_argument(
        "--resource-sample-seconds",
        type=float,
        default=DEFAULT_RESOURCE_SAMPLE_SECONDS,
    )
    parser.add_argument(
        "--cpu-abort-consecutive-samples",
        type=int,
        default=DEFAULT_CPU_ABORT_CONSECUTIVE_SAMPLES,
        help="Abort only after this many consecutive high-CPU samples.",
    )
    parser.add_argument(
        "--disable-resource-guard",
        action="store_true",
        help="Disable CPU and memory abort checks.",
    )
    parser.add_argument(
        "--keep-qdrant",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep Qdrant directories after each strategy for later evaluation.",
    )
    return parser.parse_args(argv)


def apply_safe_thread_environment() -> None:
    """Limit CPU thread fan-out before model libraries do work."""

    for environment_key, environment_value in SAFE_THREAD_ENVIRONMENT.items():
        os.environ.setdefault(environment_key, environment_value)


if __name__ == "__main__":
    raise SystemExit(main())
