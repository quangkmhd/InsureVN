"""Generate Health RAG context benchmark v2 with parallel LLM provider slots."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SAFE_THREAD_ENVIRONMENT = {
    "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}
for environment_key, environment_value in SAFE_THREAD_ENVIRONMENT.items():
    os.environ.setdefault(environment_key, environment_value)

from src.eval.context_benchmark_v2 import (
    DEFAULT_DISTRIBUTION,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    ContextBenchmarkV2Config,
    run_context_benchmark_generation,
    verify_benchmark_output,
)
from src.eval.llm_provider_slots import collect_markdown_element_llm_provider_slots


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--env-path", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--target-tokens", type=int, default=1500)
    parser.add_argument("--min-tokens", type=int, default=80)
    parser.add_argument("--max-workers", type=int, default=21)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--random-seed", type=int, default=20260508)
    parser.add_argument("--max-rounds", type=int, default=25)
    parser.add_argument("--progress-every", type=int, default=5)
    parser.add_argument("--max-provider-list-cases", type=int, default=15)
    parser.add_argument("--max-hotline-cases", type=int, default=15)
    parser.add_argument("--max-low-risk-cases", type=int, default=45)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--resume-partial",
        action="store_true",
        help="Resume from partial accepted/failed JSONL files in output dir.",
    )
    parser.add_argument(
        "--allow-fewer-slots",
        action="store_true",
        help="Allow running with fewer than --max-workers provider slots.",
    )
    return parser.parse_args()


def main() -> None:
    """Run benchmark generation or verify an existing output directory."""

    args = parse_args()
    if args.verify_only:
        verification = verify_benchmark_output(
            args.output_dir,
            expected_distribution=DEFAULT_DISTRIBUTION,
            input_dir=args.input_dir,
        )
        print(json.dumps(verification, ensure_ascii=False, sort_keys=True))
        return

    load_dotenv(dotenv_path=args.env_path)
    slots = collect_markdown_element_llm_provider_slots()
    if len(slots) < args.max_workers and not args.allow_fewer_slots:
        msg = (
            f"Found {len(slots)} provider slots, but --max-workers is "
            f"{args.max_workers}. Add keys or pass --allow-fewer-slots."
        )
        raise ValueError(msg)
    active_slots = slots[: args.max_workers]
    config = ContextBenchmarkV2Config(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        target_tokens=args.target_tokens,
        min_tokens=args.min_tokens,
        max_workers=args.max_workers,
        max_retries=args.max_retries,
        timeout_seconds=args.timeout_seconds,
        random_seed=args.random_seed,
        max_rounds=args.max_rounds,
        progress_every=args.progress_every,
        resume_partial=args.resume_partial,
        max_provider_list_cases=args.max_provider_list_cases,
        max_hotline_cases=args.max_hotline_cases,
        max_low_risk_cases=args.max_low_risk_cases,
    )
    result = run_context_benchmark_generation(config=config, slots=active_slots)
    payload = result.__dict__ | {"output_dir": str(result.output_dir)}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
