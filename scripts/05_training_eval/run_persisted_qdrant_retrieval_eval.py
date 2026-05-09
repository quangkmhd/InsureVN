"""CLI for retrieval evaluation over persisted local Qdrant indexes."""

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

from src.eval.persisted_qdrant_retrieval_eval import (
    DEFAULT_EVAL_TOP_K,
    PersistedQdrantRetrievalEvalConfig,
    run_persisted_qdrant_retrieval_eval,
)


def main() -> int:
    """Run persisted Qdrant retrieval evaluation."""

    args = parse_args()
    strategies = parse_strategies(args.strategies)
    config = PersistedQdrantRetrievalEvalConfig(
        source_run_dir=args.source_run_dir,
        output_dir=args.output_dir,
        top_k=args.top_k,
        embedding_batch_size=args.embedding_batch_size,
        embedding_model_name=args.embedding_model_name,
        embedding_device=args.embedding_device,
        embedding_cache_path=args.embedding_cache_path,
        strategies=strategies,
    )
    output_dir = run_persisted_qdrant_retrieval_eval(config)
    print(output_dir)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-run-dir",
        type=Path,
        required=True,
        help=(
            "Chunking/embedding run directory containing out/manifest.json and qdrant/."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory. Defaults to <source-run-dir>/retrieval_eval.",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_EVAL_TOP_K)
    parser.add_argument("--embedding-batch-size", type=int, default=2)
    parser.add_argument("--embedding-model-name")
    parser.add_argument("--embedding-device")
    parser.add_argument("--embedding-cache-path", type=Path)
    parser.add_argument(
        "--strategies",
        help="Optional comma-separated strategy subset. Defaults to source manifest.",
    )
    return parser.parse_args()


def parse_strategies(value: str | None) -> tuple[str, ...] | None:
    """Parse an optional comma-separated strategy list."""

    if value is None or not value.strip():
        return None
    return tuple(strategy.strip() for strategy in value.split(",") if strategy.strip())


if __name__ == "__main__":
    raise SystemExit(main())
