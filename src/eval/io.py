"""Input and output helpers for chunking evaluation."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from src.eval.models import BenchmarkCase, ExpectedSource, JsonDict, to_json_dict


def ensure_directory(path: Path) -> Path:
    """Create and return a directory path."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def load_benchmark_cases(path: Path, limit: int | None = None) -> list[BenchmarkCase]:
    """Load benchmark cases from a JSONL file."""

    cases: list[BenchmarkCase] = []
    with path.open("r", encoding="utf-8") as benchmark_file:
        for line in benchmark_file:
            if not line.strip():
                continue
            payload = json.loads(line)
            expected_sources = tuple(
                ExpectedSource(
                    provider=source.get("provider", ""),
                    source_path=source.get("source_path", ""),
                    line_start=source.get("line_start"),
                    line_end=source.get("line_end"),
                    evidence_quote=source.get("evidence_quote", ""),
                    relationship=source.get("relationship"),
                )
                for source in payload.get("expected_sources", [])
            )
            cases.append(
                BenchmarkCase(
                    case_id=payload["id"],
                    question=payload["question"],
                    gold_answer=payload["gold_answer"],
                    case_type=payload.get("case_type", ""),
                    task_type=payload.get("task_type", ""),
                    risk_level=payload.get("risk_level", ""),
                    expected_behavior=payload.get("expected_behavior", ""),
                    expected_sources=expected_sources,
                    scoring=payload.get("scoring", {}),
                )
            )
            if limit is not None and len(cases) >= limit:
                break
    return cases


def write_json(path: Path, payload: JsonDict) -> None:
    """Write a JSON object with stable UTF-8 formatting."""

    ensure_directory(path.parent)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def read_json(path: Path) -> JsonDict | None:
    """Read a JSON object, returning None when the file is absent."""

    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Expected JSON object at {path}."
        raise ValueError(msg)
    return payload


def read_jsonl(path: Path) -> list[JsonDict]:
    """Read JSONL dictionaries, returning an empty list when absent."""

    if not path.exists():
        return []
    rows: list[JsonDict] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                msg = f"Expected JSON object row in {path}."
                raise ValueError(msg)
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[object]) -> None:
    """Write rows to JSONL, accepting dataclasses or dictionaries."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(
                json.dumps(to_json_dict(row), ensure_ascii=False, sort_keys=True) + "\n"
            )


def write_csv(path: Path, rows: list[JsonDict]) -> None:
    """Write dictionaries to CSV using the union of keys as fieldnames."""

    ensure_directory(path.parent)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
