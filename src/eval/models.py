"""Shared data models for chunking evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class ExpectedSource:
    """Ground-truth source citation from the benchmark dataset."""

    provider: str
    source_path: str
    line_start: int | None
    line_end: int | None
    evidence_quote: str
    relationship: str | None = None


@dataclass(frozen=True)
class BenchmarkCase:
    """One health insurance RAG benchmark question."""

    case_id: str
    question: str
    gold_answer: str
    case_type: str
    task_type: str
    risk_level: str
    expected_behavior: str
    expected_sources: tuple[ExpectedSource, ...]
    scoring: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class CorpusDocument:
    """A source markdown document loaded from the corpus."""

    source_path: str
    absolute_path: Path
    provider: str
    text: str
    line_offsets: tuple[int, ...]


@dataclass(frozen=True)
class TextChunk:
    """A chunk emitted by a chunking strategy."""

    chunk_id: str
    strategy: str
    source_path: str
    provider: str
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    start_line: int
    end_line: int
    metadata: JsonDict = field(default_factory=dict)
    embedding: list[float] | None = None

    def to_payload(self) -> JsonDict:
        """Return a Qdrant-compatible payload for this chunk."""

        return {
            "chunk_id": self.chunk_id,
            "strategy": self.strategy,
            "source_path": self.source_path,
            "provider": self.provider,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk retrieved for a benchmark case."""

    case_id: str
    strategy: str
    rank: int
    score: float
    chunk_id: str
    source_path: str
    provider: str
    text: str
    start_line: int
    end_line: int
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class MetricScore:
    """One DeepEval metric score for one benchmark case."""

    case_id: str
    strategy: str
    metric_name: str
    score: float | None
    threshold: float
    success: bool | None
    reason: str | None = None
    error: str | None = None
    scoring_cache_key: str | None = None
    scoring_cache_hit: bool = False


@dataclass(frozen=True)
class StrategySummary:
    """Aggregate result for one chunking strategy."""

    strategy: str
    document_count: int
    chunk_count: int
    database_path: str
    metric_means: JsonDict
    evaluation_error: str | None = None
    attempt_count: int = 1
    skipped_existing_success: bool = False


def to_json_dict(value: object) -> JsonDict:
    """Convert a dataclass instance to a JSON-ready dictionary."""

    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return value
    msg = f"Unsupported JSON conversion type: {type(value)!r}"
    raise TypeError(msg)
