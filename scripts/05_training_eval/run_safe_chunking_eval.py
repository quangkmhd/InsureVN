"""Run a resource-safe 10-document chunking retrieval evaluation.

This wrapper runs one strategy per subprocess, copies only small artifacts, and
removes each temporary vector database immediately after the strategy finishes.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_PATH = (
    PROJECT_ROOT
    / "data"
    / "benchmark"
    / "health_rag_benchmark"
    / "health_insurance_rag_benchmark.jsonl"
)
DEFAULT_CORPUS_DIR = (
    PROJECT_ROOT
    / "data"
    / "health_insurance"
    / "health_insurance_markdowns_interpreted_cleaned"
)
DEFAULT_WORK_ROOT = Path("/tmp/insurevn_safe_chunking_eval")
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "data" / "eval_runs" / "safe_ten_file_eval"
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT
    / "docs"
    / "work_log"
    / "2026-05-08-safe-ten-file-chunking-eval-report.md"
)
SELECTABLE_STRATEGIES = (
    "semantic_embedding",
    "heading_level_table_safe",
    "markdown_header_recursive_table",
    "insurance_contract_hybrid_late",
    "markdown_then_semantic",
    "table_as_one_hybrid",
    "llm_markdown_optimal",
    "llamaindex_markdown_element",
    "hierarchical_header_recursive",
)
DEFAULT_STRATEGIES = ("hierarchical_header_recursive",)
SKIPPED_FULL_STRATEGIES = (
    "llm_markdown_optimal",
    "llamaindex_markdown_element",
)
SMALL_ARTIFACT_NAMES = (
    "strategy_summary.csv",
    "strategy_summary.jsonl",
    "retrievals.jsonl",
    "deepeval_scores.jsonl",
    "manifest.json",
)


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class StrategyRunStatus:
    """Execution status for one strategy subprocess."""

    strategy: str
    run_id: str
    status: str
    return_code: int | None
    duration_seconds: float
    log_path: Path
    artifact_dir: Path
    error: str


def main() -> int:
    """Run the safe evaluation wrapper."""

    args = parse_args()
    artifact_root = args.artifact_root.resolve()
    work_root = args.work_root.resolve()
    report_path = args.report_path.resolve()
    reset_directory(artifact_root)
    reset_directory(work_root)
    (artifact_root / "logs").mkdir(parents=True, exist_ok=True)
    (artifact_root / "artifacts").mkdir(parents=True, exist_ok=True)

    loaded_source_paths = select_loaded_source_paths(
        benchmark_path=args.benchmark_path,
        corpus_dir=args.corpus_dir,
        limit_documents=args.limit_documents,
    )
    (artifact_root / "loaded_source_paths.json").write_text(
        json.dumps(loaded_source_paths, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    statuses: list[StrategyRunStatus] = []
    for strategy in args.strategies:
        status = run_strategy(
            strategy=strategy,
            benchmark_path=args.benchmark_path,
            corpus_dir=args.corpus_dir,
            work_root=work_root,
            artifact_root=artifact_root,
            embedding_cache_path=work_root / "embedding_cache.sqlite",
            limit_documents=args.limit_documents,
            timeout_seconds=args.strategy_timeout_seconds,
            taskset_cpus=args.taskset_cpus,
            max_system_cpu_percent=args.max_system_cpu_percent,
            max_process_cpu_percent=args.max_process_cpu_percent,
            cpu_check_interval_seconds=args.cpu_check_interval_seconds,
            cpu_limit_grace_seconds=args.cpu_limit_grace_seconds,
        )
        statuses.append(status)
        write_statuses(artifact_root / "strategy_run_status.csv", statuses)

    aggregate_small_artifacts(artifact_root, statuses)
    metrics = build_deterministic_metrics(
        benchmark_path=args.benchmark_path,
        corpus_dir=args.corpus_dir,
        limit_documents=args.limit_documents,
        artifact_root=artifact_root,
        statuses=statuses,
    )
    write_metrics_csv(artifact_root / "deterministic_retrieval_metrics.csv", metrics)
    write_report(
        report_path=report_path,
        artifact_root=artifact_root,
        statuses=statuses,
        metrics=metrics,
        loaded_source_paths=loaded_source_paths,
        timeout_seconds=args.strategy_timeout_seconds,
        taskset_cpus=args.taskset_cpus,
        max_system_cpu_percent=args.max_system_cpu_percent,
        max_process_cpu_percent=args.max_process_cpu_percent,
        cpu_limit_grace_seconds=args.cpu_limit_grace_seconds,
    )
    shutil.rmtree(work_root, ignore_errors=True)
    return 0 if all(status.status == "completed" for status in statuses) else 1


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-path", type=Path, default=DEFAULT_BENCHMARK_PATH)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--limit-documents", type=int, default=10)
    parser.add_argument("--strategy-timeout-seconds", type=int, default=900)
    parser.add_argument("--taskset-cpus", default="0")
    parser.add_argument("--max-system-cpu-percent", type=float, default=85.0)
    parser.add_argument("--max-process-cpu-percent", type=float, default=0.0)
    parser.add_argument("--cpu-check-interval-seconds", type=float, default=2.0)
    parser.add_argument("--cpu-limit-grace-seconds", type=float, default=6.0)
    parser.add_argument(
        "--strategies",
        default=",".join(DEFAULT_STRATEGIES),
        help=(
            "Comma-separated chunking strategy names. Defaults to "
            "hierarchical_header_recursive."
        ),
    )
    args = parser.parse_args()
    try:
        args.strategies = parse_strategy_names(args.strategies)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def parse_strategy_names(value: str) -> tuple[str, ...]:
    """Parse and validate a comma-separated strategy list."""
    strategy_names = tuple(name.strip() for name in value.split(",") if name.strip())
    if not strategy_names:
        raise ValueError("At least one strategy name is required.")
    unknown_strategies = sorted(set(strategy_names) - set(SELECTABLE_STRATEGIES))
    if unknown_strategies:
        known = ", ".join(SELECTABLE_STRATEGIES)
        raise ValueError(
            f"Unknown chunking strategies: {unknown_strategies}. "
            f"Known strategies: {known}"
        )
    return strategy_names


def reset_directory(path: Path) -> None:
    """Remove and recreate a directory."""

    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def run_strategy(
    strategy: str,
    benchmark_path: Path,
    corpus_dir: Path,
    work_root: Path,
    artifact_root: Path,
    embedding_cache_path: Path,
    limit_documents: int,
    timeout_seconds: int,
    taskset_cpus: str,
    max_system_cpu_percent: float,
    max_process_cpu_percent: float,
    cpu_check_interval_seconds: float,
    cpu_limit_grace_seconds: float,
) -> StrategyRunStatus:
    """Run one strategy in a subprocess and preserve only small artifacts."""

    run_id = f"safe10_{strategy}"
    strategy_work_root = work_root / strategy
    strategy_artifact_dir = artifact_root / "artifacts" / strategy
    log_path = artifact_root / "logs" / f"{strategy}.log"
    strategy_artifact_dir.mkdir(parents=True, exist_ok=True)
    command = resource_friendly_prefix(taskset_cpus) + [
        sys.executable,
        "-m",
        "src.eval",
        "run",
        "--run-id",
        run_id,
        "--strategies",
        strategy,
        "--limit-documents",
        str(limit_documents),
        "--benchmark-path",
        str(benchmark_path),
        "--corpus-dir",
        str(corpus_dir),
        "--output-dir",
        str(strategy_work_root),
        "--embedding-cache-path",
        str(embedding_cache_path),
        "--embedding-device",
        "cuda",
        "--batch-size",
        "16",
        "--strategy-retries",
        "0",
        "--skip-deepeval",
    ]
    env = safe_eval_environment()
    started_at = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write("Command: " + " ".join(command) + "\n\n")
        log_file.flush()
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        stop_reason = wait_with_resource_limits(
            process=process,
            timeout_seconds=timeout_seconds,
            max_system_cpu_percent=max_system_cpu_percent,
            max_process_cpu_percent=max_process_cpu_percent,
            cpu_check_interval_seconds=cpu_check_interval_seconds,
            cpu_limit_grace_seconds=cpu_limit_grace_seconds,
        )
    duration_seconds = time.monotonic() - started_at
    report_dir = strategy_work_root / "reports" / run_id
    copy_small_artifacts(report_dir, strategy_artifact_dir)
    shutil.rmtree(strategy_work_root, ignore_errors=True)

    if stop_reason == "timeout":
        status = "timeout"
        error = f"Timed out after {timeout_seconds} seconds."
    elif stop_reason == "system_cpu_limit":
        status = "cpu_limit"
        error = (
            "System CPU exceeded "
            f"{max_system_cpu_percent:.1f}% for "
            f"{cpu_limit_grace_seconds:.1f}s."
        )
    elif stop_reason == "cpu_limit":
        status = "cpu_limit"
        error = (
            "Process group exceeded "
            f"{max_process_cpu_percent:.1f}% CPU for "
            f"{cpu_limit_grace_seconds:.1f}s."
        )
    elif process.returncode == 0:
        status = "completed"
        error = ""
    else:
        status = "failed"
        error = f"Process exited with return code {process.returncode}."

    return StrategyRunStatus(
        strategy=strategy,
        run_id=run_id,
        status=status,
        return_code=process.returncode,
        duration_seconds=duration_seconds,
        log_path=log_path,
        artifact_dir=strategy_artifact_dir,
        error=error,
    )


def resource_friendly_prefix(taskset_cpus: str) -> list[str]:
    """Return nice/ionice command prefix when available."""

    prefix: list[str] = []
    if shutil.which("ionice"):
        prefix.extend(["ionice", "-c3"])
    if shutil.which("nice"):
        prefix.extend(["nice", "-n", "10"])
    if shutil.which("taskset") and taskset_cpus.strip():
        prefix.extend(["taskset", "-c", taskset_cpus.strip()])
    return prefix


def safe_eval_environment() -> dict[str, str]:
    """Build environment overrides that keep local resource use bounded."""

    env = os.environ.copy()
    env.update(
        {
            "MARKDOWN_ELEMENT_NUM_WORKERS": "1",
            "MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS": "20",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
    return env


def wait_with_resource_limits(
    process: subprocess.Popen[str],
    timeout_seconds: int,
    max_system_cpu_percent: float,
    max_process_cpu_percent: float,
    cpu_check_interval_seconds: float,
    cpu_limit_grace_seconds: float,
) -> str | None:
    """Wait for a process and stop it on timeout or sustained CPU overuse."""

    deadline = time.monotonic() + timeout_seconds
    system_cpu_over_limit_started_at: float | None = None
    cpu_over_limit_started_at: float | None = None
    previous_system_cpu_times = read_system_cpu_times()
    while process.poll() is None:
        time.sleep(cpu_check_interval_seconds)
        if time.monotonic() >= deadline:
            terminate_process_group(process)
            return "timeout"
        current_system_cpu_times = read_system_cpu_times()
        system_cpu_percent = system_cpu_percent_between(
            previous_system_cpu_times,
            current_system_cpu_times,
        )
        previous_system_cpu_times = current_system_cpu_times
        if max_system_cpu_percent > 0 and system_cpu_percent > max_system_cpu_percent:
            if system_cpu_over_limit_started_at is None:
                system_cpu_over_limit_started_at = time.monotonic()
            over_limit_duration = time.monotonic() - system_cpu_over_limit_started_at
            if over_limit_duration >= cpu_limit_grace_seconds:
                terminate_process_group(process)
                return "system_cpu_limit"
        else:
            system_cpu_over_limit_started_at = None

        process_cpu_percent = process_group_cpu_percent(process.pid)
        if (
            max_process_cpu_percent > 0
            and process_cpu_percent > max_process_cpu_percent
        ):
            if cpu_over_limit_started_at is None:
                cpu_over_limit_started_at = time.monotonic()
            over_limit_duration = time.monotonic() - cpu_over_limit_started_at
            if over_limit_duration >= cpu_limit_grace_seconds:
                terminate_process_group(process)
                return "cpu_limit"
        else:
            cpu_over_limit_started_at = None
    return None


def read_system_cpu_times() -> tuple[int, int]:
    """Return total and idle CPU jiffies from /proc/stat."""

    try:
        first_line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return (0, 0)
    fields = [int(value) for value in first_line.split()[1:] if value.isdigit()]
    if len(fields) < 5:
        return (0, 0)
    idle = fields[3] + fields[4]
    return (sum(fields), idle)


def system_cpu_percent_between(
    previous_times: tuple[int, int],
    current_times: tuple[int, int],
) -> float:
    """Return CPU utilization percentage between two /proc/stat samples."""

    previous_total, previous_idle = previous_times
    current_total, current_idle = current_times
    total_delta = current_total - previous_total
    idle_delta = current_idle - previous_idle
    if total_delta <= 0:
        return 0.0
    busy_delta = max(0, total_delta - idle_delta)
    return (busy_delta / total_delta) * 100.0


def process_group_cpu_percent(process_id: int) -> float:
    """Return summed CPU percentage for a process group."""

    with suppress(ProcessLookupError):
        process_group_id = os.getpgid(process_id)
        result = subprocess.run(
            ["ps", "-eo", "pgid=,pcpu="],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        total = 0.0
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            try:
                pgid = int(parts[0])
                cpu_percent = float(parts[1])
            except ValueError:
                continue
            if pgid == process_group_id:
                total += cpu_percent
        return total
    return 0.0


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate a subprocess process group, then force kill if needed."""

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=30)


def copy_small_artifacts(report_dir: Path, strategy_artifact_dir: Path) -> None:
    """Copy final JSON/CSV artifacts without preserving vector DB files."""

    for artifact_name in SMALL_ARTIFACT_NAMES:
        source_path = report_dir / artifact_name
        if source_path.exists():
            shutil.copy2(source_path, strategy_artifact_dir / artifact_name)


def write_statuses(path: Path, statuses: list[StrategyRunStatus]) -> None:
    """Write strategy subprocess statuses to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=[
                "strategy",
                "status",
                "return_code",
                "duration_seconds",
                "error",
                "log_path",
                "artifact_dir",
            ],
        )
        writer.writeheader()
        for status in statuses:
            writer.writerow(
                {
                    "strategy": status.strategy,
                    "status": status.status,
                    "return_code": status.return_code,
                    "duration_seconds": f"{status.duration_seconds:.1f}",
                    "error": status.error,
                    "log_path": str(status.log_path),
                    "artifact_dir": str(status.artifact_dir),
                }
            )


def aggregate_small_artifacts(
    artifact_root: Path,
    statuses: list[StrategyRunStatus],
) -> None:
    """Aggregate per-strategy summary and retrieval JSONL files."""

    aggregate_jsonl(
        artifact_root / "combined_strategy_summary.jsonl",
        [status.artifact_dir / "strategy_summary.jsonl" for status in statuses],
    )
    aggregate_jsonl(
        artifact_root / "combined_retrievals.jsonl",
        [status.artifact_dir / "retrievals.jsonl" for status in statuses],
    )


def aggregate_jsonl(output_path: Path, input_paths: list[Path]) -> None:
    """Concatenate JSONL files that exist."""

    with output_path.open("w", encoding="utf-8") as output_file:
        for input_path in input_paths:
            if not input_path.exists():
                continue
            with input_path.open("r", encoding="utf-8") as input_file:
                for line in input_file:
                    if line.strip():
                        output_file.write(line)


def select_loaded_source_paths(
    benchmark_path: Path,
    corpus_dir: Path,
    limit_documents: int,
) -> list[str]:
    """Select the same first N primary source paths used by the eval runner."""

    source_paths: list[str] = []
    seen: set[str] = set()
    for case in read_jsonl(benchmark_path):
        primary_source = primary_source_path(case)
        if not primary_source or primary_source in seen:
            continue
        if not (corpus_dir / primary_source).exists():
            continue
        source_paths.append(primary_source)
        seen.add(primary_source)
        if len(source_paths) >= limit_documents:
            break
    return source_paths


def build_deterministic_metrics(
    benchmark_path: Path,
    corpus_dir: Path,
    limit_documents: int,
    artifact_root: Path,
    statuses: list[StrategyRunStatus],
) -> list[JsonDict]:
    """Compute deterministic retrieval metrics against benchmark citations."""

    loaded_sources = set(
        select_loaded_source_paths(
            benchmark_path=benchmark_path,
            corpus_dir=corpus_dir,
            limit_documents=limit_documents,
        )
    )
    benchmark_cases = [
        case
        for case in read_jsonl(benchmark_path)
        if primary_source_path(case) in loaded_sources
    ]
    retrievals_by_strategy_case: dict[tuple[str, str], list[JsonDict]] = {}
    for retrieval in read_jsonl(artifact_root / "combined_retrievals.jsonl"):
        key = (str(retrieval.get("strategy", "")), str(retrieval.get("case_id", "")))
        retrievals_by_strategy_case.setdefault(key, []).append(retrieval)

    rows: list[JsonDict] = []
    for status in statuses:
        summary = first_jsonl_row(status.artifact_dir / "strategy_summary.jsonl") or {}
        chunk_count = int(summary.get("chunk_count", 0) or 0)
        case_metrics = [
            score_case(
                case=case,
                retrieved=retrievals_by_strategy_case.get(
                    (status.strategy, str(case.get("id", ""))),
                    [],
                ),
            )
            for case in benchmark_cases
        ]
        rows.append(
            {
                "strategy": status.strategy,
                "status": status.status,
                "cases": len(benchmark_cases),
                "chunk_count": chunk_count,
                "primary_hit_rate_at_5": mean(
                    metric["primary_hit_at_5"] for metric in case_metrics
                ),
                "primary_mrr_at_5": mean(
                    metric["primary_mrr_at_5"] for metric in case_metrics
                ),
                "required_source_recall_at_5": mean(
                    metric["required_source_recall_at_5"] for metric in case_metrics
                ),
                "line_overlap_recall_at_5": mean(
                    metric["line_overlap_recall_at_5"] for metric in case_metrics
                ),
                "duration_seconds": status.duration_seconds,
                "error": status.error or summary.get("evaluation_error", ""),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["status"]) != "completed",
            -float(row["required_source_recall_at_5"]),
            -float(row["primary_mrr_at_5"]),
            int(row["chunk_count"]),
        ),
    )


def score_case(case: JsonDict, retrieved: list[JsonDict]) -> JsonDict:
    """Score retrieved chunks for one benchmark case."""

    top_retrieved = sorted(retrieved, key=lambda item: int(item.get("rank", 999)))[:5]
    expected_sources = list(case.get("expected_sources", []))
    primary_source = primary_source_path(case)
    primary_rank = first_matching_rank(top_retrieved, primary_source)
    required_sources = set(required_source_paths(case))
    retrieved_sources = {str(item.get("source_path", "")) for item in top_retrieved}
    line_expected_sources = [
        source
        for source in expected_sources
        if source.get("line_start") is not None and source.get("line_end") is not None
    ]
    return {
        "primary_hit_at_5": 1.0 if primary_rank is not None else 0.0,
        "primary_mrr_at_5": (1.0 / primary_rank) if primary_rank is not None else 0.0,
        "required_source_recall_at_5": (
            len(required_sources & retrieved_sources) / len(required_sources)
            if required_sources
            else 0.0
        ),
        "line_overlap_recall_at_5": (
            sum(
                1
                for source in line_expected_sources
                if has_line_overlap(source, top_retrieved)
            )
            / len(line_expected_sources)
            if line_expected_sources
            else 0.0
        ),
    }


def first_matching_rank(retrieved: list[JsonDict], source_path: str) -> int | None:
    """Return the first one-based rank matching a source path."""

    for item in retrieved:
        if str(item.get("source_path", "")) == source_path:
            return int(item.get("rank", 0))
    return None


def has_line_overlap(expected_source: JsonDict, retrieved: list[JsonDict]) -> bool:
    """Return True if any retrieved chunk overlaps an expected source line span."""

    expected_path = str(expected_source.get("source_path", ""))
    expected_start = int(expected_source.get("line_start") or 0)
    expected_end = int(expected_source.get("line_end") or expected_start)
    for item in retrieved:
        if str(item.get("source_path", "")) != expected_path:
            continue
        start_line = int(item.get("start_line", 0))
        end_line = int(item.get("end_line", 0))
        if max(expected_start, start_line) <= min(expected_end, end_line):
            return True
    return False


def required_source_paths(case: JsonDict) -> list[str]:
    """Return unique required source paths for a benchmark case."""

    paths = [
        str(path)
        for path in case.get("scoring", {}).get("required_source_paths", [])
        if str(path)
    ]
    if not paths:
        paths = [
            str(source.get("source_path", ""))
            for source in case.get("expected_sources", [])
            if source.get("source_path")
        ]
    return list(dict.fromkeys(paths))


def primary_source_path(case: JsonDict) -> str:
    """Return the primary source path from one benchmark case."""

    for source in case.get("expected_sources", []):
        if source.get("relationship") == "primary":
            return str(source.get("source_path", ""))
    expected_sources = case.get("expected_sources", [])
    if expected_sources:
        return str(expected_sources[0].get("source_path", ""))
    return ""


def read_jsonl(path: Path) -> list[JsonDict]:
    """Read JSONL objects from a path if it exists."""

    if not path.exists():
        return []
    rows: list[JsonDict] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def first_jsonl_row(path: Path) -> JsonDict | None:
    """Return the first row from a JSONL file."""

    rows = read_jsonl(path)
    return rows[0] if rows else None


def mean(values: Any) -> float:
    """Return a rounded arithmetic mean for numeric values."""

    materialized = [float(value) for value in values]
    if not materialized:
        return 0.0
    return round(sum(materialized) / len(materialized), 4)


def write_metrics_csv(path: Path, rows: list[JsonDict]) -> None:
    """Write deterministic metrics to CSV."""

    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    report_path: Path,
    artifact_root: Path,
    statuses: list[StrategyRunStatus],
    metrics: list[JsonDict],
    loaded_source_paths: list[str],
    timeout_seconds: int,
    taskset_cpus: str,
    max_system_cpu_percent: float,
    max_process_cpu_percent: float,
    cpu_limit_grace_seconds: float,
) -> None:
    """Write a compact Markdown report."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    best_metric = next(
        (metric for metric in metrics if metric.get("status") == "completed"),
        None,
    )
    lines = [
        "# Safe 10-File Chunking Retrieval Eval",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        "- Embedding: "
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 on CUDA",
        "- Judge/DeepEval: skipped to avoid OpenAI and avoid LLM judge cost",
        f"- Strategy timeout: {timeout_seconds}s each",
        f"- CPU pinning: taskset CPUs `{taskset_cpus}`",
        "- CPU guard: kill a strategy if system CPU exceeds "
        f"{max_system_cpu_percent:.1f}% for "
        f"{cpu_limit_grace_seconds:.1f}s",
        "- Optional process CPU guard: "
        + (
            f"{max_process_cpu_percent:.1f}%"
            if max_process_cpu_percent > 0
            else "disabled"
        ),
        f"- Artifact root: `{artifact_root}`",
        "- Vector DB policy: temporary only, deleted after each strategy",
        "",
        "## Scope",
        "",
        "Full 10-file run covers deterministic/local strategies only. "
        "`llm_markdown_optimal` and `llamaindex_markdown_element` are excluded "
        "from the full run because they can trigger many LLM calls on large "
        "provider-list tables and previously caused local resource pressure.",
        "",
        "## Loaded Sources",
        "",
    ]
    lines.extend(f"- `{source_path}`" for source_path in loaded_source_paths)
    lines.extend(
        [
            "",
            "## Strategy Status",
            "",
            "| Strategy | Status | Duration | Error |",
            "|---|---:|---:|---|",
        ]
    )
    for status in statuses:
        lines.append(
            "| "
            f"{status.strategy} | {status.status} | "
            f"{status.duration_seconds:.1f}s | {status.error or ''} |"
        )
    lines.extend(
        [
            "",
            "## Deterministic Retrieval Metrics",
            "",
            "| Strategy | Chunks | Primary Hit@5 | Primary MRR@5 | "
            "Required Source Recall@5 | Line Overlap Recall@5 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for metric in metrics:
        lines.append(
            "| "
            f"{metric['strategy']} | {metric['chunk_count']} | "
            f"{metric['primary_hit_rate_at_5']:.4f} | "
            f"{metric['primary_mrr_at_5']:.4f} | "
            f"{metric['required_source_recall_at_5']:.4f} | "
            f"{metric['line_overlap_recall_at_5']:.4f} |"
        )
    lines.extend(["", "## Conclusion", ""])
    if best_metric is None:
        lines.append("No strategy completed successfully.")
    else:
        lines.append(
            "Best completed strategy by required-source recall and MRR: "
            f"`{best_metric['strategy']}`."
        )
    lines.extend(
        [
            "",
            "## Skipped Full Strategies",
            "",
        ]
    )
    lines.extend(f"- `{strategy}`" for strategy in SKIPPED_FULL_STRATEGIES)
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
