"""CLI for provider-pool LLM judging of persisted retrieval eval outputs."""

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

from src.eval.config import (
    DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS,
)
from src.eval.llm_retrieval_judge_eval import (
    DEFAULT_JUDGE_THRESHOLD,
    DEFAULT_MAX_CONTEXT_CHARS_PER_CHUNK,
    DEFAULT_MAX_TOTAL_CONTEXT_CHARS,
    LLMRetrievalJudgeConfig,
    run_llm_retrieval_judge_eval,
)


def main() -> int:
    """Run LLM retrieval judge evaluation."""

    args = parse_args()
    config = LLMRetrievalJudgeConfig(
        retrieval_eval_dirs=tuple(args.retrieval_eval_dirs),
        output_dir=args.output_dir,
        strategies=parse_strategies(args.strategies),
        limit_cases=args.limit_cases if args.limit_cases > 0 else None,
        threshold=args.threshold,
        max_workers=args.max_workers,
        request_timeout_seconds=args.request_timeout_seconds,
        max_slot_attempts=args.max_slot_attempts,
        max_context_chars_per_chunk=args.max_context_chars_per_chunk,
        max_total_context_chars=args.max_total_context_chars,
        provider_health_check=not args.disable_provider_health_check,
        resume_completed=not args.no_resume,
    )
    output_dir = run_llm_retrieval_judge_eval(config)
    print(output_dir)
    return 0


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retrieval-eval-dir",
        dest="retrieval_eval_dirs",
        action="append",
        type=Path,
        required=True,
        help="Retrieval eval output dir. Pass multiple times for multiple groups.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--strategies",
        help="Optional comma-separated strategy subset.",
    )
    parser.add_argument(
        "--limit-cases",
        type=int,
        default=0,
        help="Limit benchmark cases per retrieval eval dir. Use 0 for all.",
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_JUDGE_THRESHOLD)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=0,
        help="Judge worker count. Use 0 for one worker per healthy provider slot.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=min(DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS, 30.0),
    )
    parser.add_argument(
        "--max-slot-attempts",
        type=int,
        default=DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    )
    parser.add_argument(
        "--max-context-chars-per-chunk",
        type=int,
        default=DEFAULT_MAX_CONTEXT_CHARS_PER_CHUNK,
    )
    parser.add_argument(
        "--max-total-context-chars",
        type=int,
        default=DEFAULT_MAX_TOTAL_CONTEXT_CHARS,
    )
    parser.add_argument(
        "--disable-provider-health-check",
        action="store_true",
        help="Use all configured slots without preflight health checks.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not reuse completed score rows already in output dir.",
    )
    return parser.parse_args()


def parse_strategies(value: str | None) -> tuple[str, ...] | None:
    """Parse a comma-separated strategy list."""

    if value is None or not value.strip():
        return None
    return tuple(strategy.strip() for strategy in value.split(",") if strategy.strip())


if __name__ == "__main__":
    raise SystemExit(main())
