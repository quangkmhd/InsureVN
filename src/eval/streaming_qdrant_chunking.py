"""Streaming chunking, embedding, and Qdrant indexing for safe benchmarks."""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

from src.eval.chunking.base import ChunkingStrategy
from src.eval.chunking.heading_level_table_safe import HeadingLevelTableSafeChunking
from src.eval.chunking.hierarchical_header_recursive import (
    HierarchicalHeaderRecursiveChunking,
)
from src.eval.chunking.insurance_contract_hybrid_late import (
    InsuranceContractHybridLateChunking,
)
from src.eval.chunking.llamaindex_markdown_element import (
    LlamaIndexMarkdownElementChunking,
)
from src.eval.chunking.llm_markdown_optimal import LLMMarkdownOptimalChunking
from src.eval.chunking.markdown_header_recursive_table import (
    MarkdownHeaderRecursiveTableChunking,
)
from src.eval.chunking.markdown_then_semantic import MarkdownThenSemanticChunking
from src.eval.chunking.semantic import SemanticChunking
from src.eval.chunking.table_as_one_hybrid import TableAsOneHybridChunking
from src.eval.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BENCHMARK_PATH,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_CORPUS_DIR,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_HEADING_CUT_LEVEL,
    DEFAULT_HEADING_MAX_CHARS,
    DEFAULT_HEADING_MAX_TABLE_ROWS,
    DEFAULT_HEADING_MIN_CHARS,
    DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS,
    DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL,
    DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER,
    DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS,
    DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS,
    DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_DEVICE,
    DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_PROVIDER,
    DEFAULT_SEMANTIC_CHUNKING_OLLAMA_BASE_URL,
)
from src.eval.corpus import build_line_offsets
from src.eval.embedding_cache import EmbeddingCache
from src.eval.embeddings import (
    SentenceTransformerEmbeddings,
    build_semantic_chunking_embeddings,
)
from src.eval.io import ensure_directory, load_benchmark_cases, write_jsonl
from src.eval.llamaindex_llms import build_markdown_element_llm
from src.eval.llm_provider_slots import EvalLLMProviderSlot, provider_slot_counts
from src.eval.models import BenchmarkCase, CorpusDocument, TextChunk
from src.eval.runner import primary_source_paths
from src.eval.vector_database import QdrantStrategyDatabase

SAFE_STREAMING_STRATEGY_NAMES = (
    "semantic_embedding",
    "heading_level_table_safe",
    "markdown_header_recursive_table",
    "insurance_contract_hybrid_late",
    "markdown_then_semantic",
    "table_as_one_hybrid",
    "hierarchical_header_recursive",
)
LLM_STREAMING_STRATEGY_NAMES = (
    "llm_markdown_optimal",
    "llamaindex_markdown_element",
)
SOURCE_SELECTION_PRIMARY = "primary"
SOURCE_SELECTION_EXPECTED = "expected"
SUPPORTED_SOURCE_SELECTIONS = {
    SOURCE_SELECTION_PRIMARY,
    SOURCE_SELECTION_EXPECTED,
}
HEAVY_METADATA_KEYS = {
    "parent_text",
    "retrieval_text",
}
MAX_METADATA_STRING_CHARS = 500
DEFAULT_CPU_ABORT_PERCENT = 85.0
DEFAULT_MIN_AVAILABLE_MEMORY_MB = 2048
DEFAULT_RESOURCE_SAMPLE_SECONDS = 2.0
DEFAULT_CPU_ABORT_CONSECUTIVE_SAMPLES = 3
DEFAULT_CHUNK_CACHE_DIR = Path("data/eval_chunk_cache/chunk_boundaries")
CHUNK_CACHE_SCHEMA_VERSION = 1
CHUNK_RECORDS_FILENAME = "streaming_chunk_records.jsonl"
PROC_STAT_PATH = Path("/proc/stat")
PROC_MEMINFO_PATH = Path("/proc/meminfo")


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class StreamingChunkEmbeddingConfig:
    """Configuration for streaming chunking, embedding, and Qdrant upsert."""

    benchmark_path: Path = DEFAULT_BENCHMARK_PATH
    corpus_dir: Path = DEFAULT_CORPUS_DIR
    output_dir: Path = Path("/tmp/insurevn_streaming_chunking_embedding_qdrant")
    qdrant_work_dir: Path = Path("/tmp/insurevn_streaming_chunking_embedding_qdrant/db")
    embedding_cache_path: Path = Path(
        "/tmp/insurevn_streaming_chunking_embedding_qdrant/embedding_cache.sqlite"
    )
    strategies: tuple[str, ...] = SAFE_STREAMING_STRATEGY_NAMES
    limit_documents: int | None = 10
    source_selection: str = SOURCE_SELECTION_PRIMARY
    collection_name: str = DEFAULT_COLLECTION_NAME
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL
    embedding_device: str | None = DEFAULT_EMBEDDING_DEVICE
    embedding_batch_size: int = min(DEFAULT_BATCH_SIZE, 16)
    semantic_chunking_embedding_provider: str = (
        DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_PROVIDER
    )
    semantic_chunking_embedding_model: str = DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_MODEL
    semantic_chunking_embedding_device: str | None = (
        DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_DEVICE
    )
    semantic_chunking_ollama_base_url: str = DEFAULT_SEMANTIC_CHUNKING_OLLAMA_BASE_URL
    markdown_element_llm_provider: str = DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER
    markdown_element_gemini_model: str = DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL
    markdown_element_gemini_api_keys: tuple[str, ...] = (
        DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS
    )
    markdown_element_llm_provider_slots: tuple[EvalLLMProviderSlot, ...] = (
        DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS
    )
    markdown_element_llm_timeout_seconds: float = (
        DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS
    )
    markdown_element_llm_max_slot_attempts: int = (
        DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS
    )
    markdown_element_num_workers: int = 0
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    heading_cut_level: int = DEFAULT_HEADING_CUT_LEVEL or 2
    heading_max_chars: int = DEFAULT_HEADING_MAX_CHARS
    heading_min_chars: int = DEFAULT_HEADING_MIN_CHARS
    heading_max_table_rows: int = DEFAULT_HEADING_MAX_TABLE_ROWS
    keep_qdrant: bool = True
    max_chunks_per_file: int | None = None
    cpu_abort_percent: float | None = DEFAULT_CPU_ABORT_PERCENT
    min_available_memory_mb: int | None = DEFAULT_MIN_AVAILABLE_MEMORY_MB
    resource_sample_seconds: float = DEFAULT_RESOURCE_SAMPLE_SECONDS
    cpu_abort_consecutive_samples: int = DEFAULT_CPU_ABORT_CONSECUTIVE_SAMPLES
    chunk_cache_dir: Path | None = DEFAULT_CHUNK_CACHE_DIR
    reuse_chunk_cache: bool = True
    write_chunk_cache: bool = True
    write_chunk_records: bool = True


@dataclass(frozen=True)
class StreamingFileResult:
    """Chunking, embedding, and Qdrant stats for one source file."""

    strategy: str
    source_path: str
    status: str
    chunk_count: int
    table_chunk_count: int
    total_chunk_chars: int
    min_chunk_chars: int
    max_chunk_chars: int
    avg_chunk_chars: float
    chunk_seconds: float
    qdrant_upsert_seconds: float
    qdrant_upserted_points: int
    llm_fallback_chunk_count: int = 0
    source_boundary_chunk_count: int = 0
    chunk_cache_hit: bool = False
    chunk_cache_path: str = ""
    error: str = ""


@dataclass(frozen=True)
class CpuSnapshot:
    """One /proc/stat CPU sample."""

    busy_ticks: int
    total_ticks: int


@dataclass(frozen=True)
class StreamingStrategyResult:
    """Aggregate stats for one streaming strategy run."""

    strategy: str
    status: str
    file_count: int
    chunk_count: int
    duration_seconds: float
    qdrant_path: str
    qdrant_kept: bool
    error: str = ""


class ResourceLimitExceededError(RuntimeError):
    """Raised when the benchmark run exceeds configured host limits."""


class ResourceGuard:
    """Monitor system CPU and memory while the streaming benchmark runs."""

    def __init__(self, config: StreamingChunkEmbeddingConfig) -> None:
        self.config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_cpu_snapshot: CpuSnapshot | None = None
        self._consecutive_cpu_violations = 0

    def __enter__(self) -> ResourceGuard:
        """Start the watchdog thread when resource limits are enabled."""

        if not self.enabled:
            return self
        self._last_cpu_snapshot = read_cpu_snapshot()
        self._thread = threading.Thread(
            target=self._watchdog,
            name="streaming-eval-resource-guard",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Stop the watchdog thread."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    @property
    def enabled(self) -> bool:
        """Return whether any resource limit is configured."""

        return (
            self.config.cpu_abort_percent is not None
            or self.config.min_available_memory_mb is not None
        )

    def check_now(self, context: str) -> None:
        """Raise when the current resource sample violates configured limits."""

        if not self.enabled:
            return
        violation = self._resource_violation(context)
        if violation is not None:
            self._write_abort_marker(violation)
            raise ResourceLimitExceededError(violation)

    def _watchdog(self) -> None:
        while not self._stop_event.wait(self.config.resource_sample_seconds):
            violation = self._resource_violation("watchdog")
            if violation is not None:
                self._write_abort_marker(violation)
                os._exit(137)

    def _resource_violation(self, context: str) -> str | None:
        available_memory_mb = read_available_memory_mb()
        min_memory_mb = self.config.min_available_memory_mb
        if (
            available_memory_mb is not None
            and min_memory_mb is not None
            and available_memory_mb < min_memory_mb
        ):
            return (
                f"{context}: available memory {available_memory_mb} MiB "
                f"is below limit {min_memory_mb} MiB"
            )

        with self._lock:
            cpu_percent = self._sample_cpu_percent()
            cpu_limit = self.config.cpu_abort_percent
            if cpu_percent is None or cpu_limit is None:
                return None
            if cpu_percent >= cpu_limit:
                self._consecutive_cpu_violations += 1
            else:
                self._consecutive_cpu_violations = 0
            required_samples = max(1, self.config.cpu_abort_consecutive_samples)
            if self._consecutive_cpu_violations >= required_samples:
                return (
                    f"{context}: system CPU {cpu_percent:.1f}% exceeded "
                    f"{cpu_limit:.1f}% for {self._consecutive_cpu_violations} "
                    "consecutive samples"
                )
        return None

    def _sample_cpu_percent(self) -> float | None:
        current_snapshot = read_cpu_snapshot()
        previous_snapshot = self._last_cpu_snapshot
        self._last_cpu_snapshot = current_snapshot
        if current_snapshot is None or previous_snapshot is None:
            return None
        delta_total = current_snapshot.total_ticks - previous_snapshot.total_ticks
        delta_busy = current_snapshot.busy_ticks - previous_snapshot.busy_ticks
        if delta_total <= 0:
            return None
        return max(0.0, min(100.0, delta_busy * 100.0 / delta_total))

    def _write_abort_marker(self, reason: str) -> None:
        payload = {
            "reason": reason,
            "cpu_abort_percent": self.config.cpu_abort_percent,
            "min_available_memory_mb": self.config.min_available_memory_mb,
            "resource_sample_seconds": self.config.resource_sample_seconds,
            "processing_mode": "strategy_then_file_streaming",
        }
        try:
            ensure_directory(self.config.output_dir)
            (self.config.output_dir / "resource_guard_abort.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            return


def run_streaming_chunking_embedding_qdrant(
    config: StreamingChunkEmbeddingConfig,
) -> Path:
    """Run chunking and embedding file-by-file, upserting to Qdrant incrementally."""

    ensure_directory(config.output_dir)
    ensure_directory(config.qdrant_work_dir)
    resource_guard = ResourceGuard(config)
    with resource_guard:
        source_paths = selected_source_paths(config)
        (config.output_dir / "loaded_source_paths.json").write_text(
            json.dumps(source_paths, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        resource_guard.check_now("before_embedding_model")
        embedding_cache = EmbeddingCache(path=config.embedding_cache_path, enabled=True)
        retrieval_embeddings = SentenceTransformerEmbeddings(
            model_name=config.embedding_model_name,
            batch_size=config.embedding_batch_size,
            device=config.embedding_device,
            cache=embedding_cache,
        )
        semantic_embeddings = build_streaming_semantic_embeddings(
            config=config,
            retrieval_embeddings=retrieval_embeddings,
            embedding_cache=embedding_cache,
        )
        markdown_element_llm = build_streaming_markdown_element_llm(config)

        file_result_rows: list[StreamingFileResult] = []
        strategy_result_rows: list[StreamingStrategyResult] = []
        for strategy_name in config.strategies:
            resource_guard.check_now(f"before_strategy:{strategy_name}")
            strategy_started_at = time.monotonic()
            qdrant_database = QdrantStrategyDatabase(
                database_path=config.qdrant_work_dir / strategy_name,
                collection_name=config.collection_name,
                embeddings=retrieval_embeddings,
            )
            strategy_status = "completed"
            strategy_error = ""
            strategy_chunk_count = 0
            try:
                chunking_strategy = build_streaming_strategy(
                    name=strategy_name,
                    config=config,
                    semantic_embeddings=semantic_embeddings,
                    retrieval_embeddings=retrieval_embeddings,
                    markdown_element_llm=markdown_element_llm,
                )
                for source_path in source_paths:
                    resource_guard.check_now(f"before_file:{source_path}")
                    file_result = process_one_file(
                        source_path=source_path,
                        strategy=chunking_strategy,
                        config=config,
                        qdrant_database=qdrant_database,
                        resource_guard=resource_guard,
                    )
                    file_result_rows.append(file_result)
                    if file_result.status != "completed":
                        strategy_status = "partial"
                    strategy_chunk_count += file_result.chunk_count
                    write_csv(
                        config.output_dir / "streaming_file_results.csv",
                        [asdict(row) for row in file_result_rows],
                    )
                    release_memory()
                    resource_guard.check_now(f"after_file:{source_path}")
            except ResourceLimitExceededError:
                raise
            except Exception as exc:
                strategy_status = "failed"
                strategy_error = f"{type(exc).__name__}: {exc}"
            finally:
                qdrant_database.close()
                if not config.keep_qdrant:
                    qdrant_database.delete()

            strategy_result_rows.append(
                StreamingStrategyResult(
                    strategy=strategy_name,
                    status=strategy_status,
                    file_count=len(source_paths),
                    chunk_count=strategy_chunk_count,
                    duration_seconds=round(time.monotonic() - strategy_started_at, 3),
                    qdrant_path=str(config.qdrant_work_dir / strategy_name),
                    qdrant_kept=config.keep_qdrant,
                    error=strategy_error,
                )
            )
            write_csv(
                config.output_dir / "streaming_strategy_results.csv",
                [asdict(row) for row in strategy_result_rows],
            )
            release_memory()

        write_jsonl(
            config.output_dir / "streaming_file_results.jsonl",
            file_result_rows,
        )
        write_jsonl(
            config.output_dir / "streaming_strategy_results.jsonl",
            strategy_result_rows,
        )
        write_manifest(config, source_paths)
    return config.output_dir


def selected_source_paths(config: StreamingChunkEmbeddingConfig) -> list[str]:
    """Return benchmark source paths in runner-compatible order."""

    benchmark_cases = load_benchmark_cases(config.benchmark_path)
    if config.source_selection == SOURCE_SELECTION_PRIMARY:
        candidate_paths = primary_source_paths(benchmark_cases)
    elif config.source_selection == SOURCE_SELECTION_EXPECTED:
        candidate_paths = expected_source_paths(benchmark_cases)
    else:
        msg = (
            f"Unsupported source selection {config.source_selection!r}; "
            f"expected one of {sorted(SUPPORTED_SOURCE_SELECTIONS)}."
        )
        raise ValueError(msg)
    selected_paths: list[str] = []
    for source_path in candidate_paths:
        if (config.corpus_dir / source_path).exists():
            selected_paths.append(source_path)
        if (
            config.limit_documents is not None
            and len(selected_paths) >= config.limit_documents
        ):
            break
    return selected_paths


def expected_source_paths(benchmark_cases: list[BenchmarkCase]) -> list[str]:
    """Return unique expected source paths in benchmark order."""

    source_paths: list[str] = []
    for benchmark_case in benchmark_cases:
        for expected_source in benchmark_case.expected_sources:
            source_path = expected_source.source_path
            if source_path and source_path not in source_paths:
                source_paths.append(source_path)
    return source_paths


def build_streaming_semantic_embeddings(
    config: StreamingChunkEmbeddingConfig,
    retrieval_embeddings: SentenceTransformerEmbeddings,
    embedding_cache: EmbeddingCache,
) -> Any:
    """Build semantic chunker embeddings, reusing retrieval embeddings when valid."""

    same_model = (
        config.semantic_chunking_embedding_provider.strip().lower()
        in {"sentence_transformer", "sentence_transformers"}
        and config.semantic_chunking_embedding_model == config.embedding_model_name
        and config.semantic_chunking_embedding_device == config.embedding_device
    )
    if same_model:
        return retrieval_embeddings
    return build_semantic_chunking_embeddings(
        provider=config.semantic_chunking_embedding_provider,
        model_name=config.semantic_chunking_embedding_model,
        ollama_base_url=config.semantic_chunking_ollama_base_url,
        batch_size=config.embedding_batch_size,
        device=config.semantic_chunking_embedding_device,
        cache=embedding_cache,
    )


def build_streaming_strategy(
    name: str,
    config: StreamingChunkEmbeddingConfig,
    semantic_embeddings: Any,
    retrieval_embeddings: SentenceTransformerEmbeddings,
    markdown_element_llm: Any,
) -> ChunkingStrategy:
    """Instantiate a chunking strategy for streaming one-file processing."""

    if name == "semantic_embedding":
        return SemanticChunking(semantic_embeddings)
    if name == "heading_level_table_safe":
        return HeadingLevelTableSafeChunking(
            cut_level=config.heading_cut_level,
            max_chars=config.heading_max_chars,
            min_chars=config.heading_min_chars,
            max_table_rows=config.heading_max_table_rows,
        )
    if name == "markdown_header_recursive_table":
        return MarkdownHeaderRecursiveTableChunking(
            config.chunk_size,
            config.chunk_overlap,
        )
    if name == "insurance_contract_hybrid_late":
        return InsuranceContractHybridLateChunking(
            retrieval_embeddings=retrieval_embeddings,
            table_summary_llm=None,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            table_summary_workers=1,
        )
    if name == "llm_markdown_optimal":
        return LLMMarkdownOptimalChunking(
            llm=markdown_element_llm,
            cut_level=config.heading_cut_level,
            max_chars=config.heading_max_chars,
            min_chars=config.heading_min_chars,
            max_table_rows=config.heading_max_table_rows,
            num_workers=resolve_markdown_element_num_workers(config),
        )
    if name == "markdown_then_semantic":
        return MarkdownThenSemanticChunking(semantic_embeddings)
    if name == "table_as_one_hybrid":
        return TableAsOneHybridChunking(config.chunk_size, config.chunk_overlap)
    if name == "llamaindex_markdown_element":
        return LlamaIndexMarkdownElementChunking(
            llm=markdown_element_llm,
            num_workers=resolve_markdown_element_num_workers(config),
            fallback_cut_level=config.heading_cut_level,
            fallback_max_chars=config.heading_max_chars,
            fallback_min_chars=config.heading_min_chars,
            fallback_max_table_rows=config.heading_max_table_rows,
        )
    if name == "hierarchical_header_recursive":
        return HierarchicalHeaderRecursiveChunking(
            config.chunk_size,
            config.chunk_overlap,
        )
    msg = f"Unsupported streaming strategy: {name}"
    raise ValueError(msg)


def build_streaming_markdown_element_llm(
    config: StreamingChunkEmbeddingConfig,
) -> Any:
    """Build the optional LLM used by LLM chunking strategies."""

    if not needs_streaming_llm(config.strategies):
        return None
    return build_markdown_element_llm(
        provider=config.markdown_element_llm_provider,
        gemini_model=config.markdown_element_gemini_model,
        gemini_api_keys=config.markdown_element_gemini_api_keys,
        provider_slots=config.markdown_element_llm_provider_slots,
        request_timeout_seconds=config.markdown_element_llm_timeout_seconds,
        max_slot_attempts=config.markdown_element_llm_max_slot_attempts,
    )


def needs_streaming_llm(strategy_names: tuple[str, ...]) -> bool:
    """Return whether selected streaming strategies need an LLM."""

    return any(
        strategy_name in LLM_STREAMING_STRATEGY_NAMES
        for strategy_name in strategy_names
    )


def resolve_markdown_element_num_workers(
    config: StreamingChunkEmbeddingConfig,
) -> int:
    """Resolve LLM chunking worker count from config and provider slots."""

    if config.markdown_element_num_workers > 0:
        return config.markdown_element_num_workers
    return max(1, len(config.markdown_element_llm_provider_slots))


def process_one_file(
    source_path: str,
    strategy: ChunkingStrategy,
    config: StreamingChunkEmbeddingConfig,
    qdrant_database: QdrantStrategyDatabase,
    resource_guard: ResourceGuard | None = None,
) -> StreamingFileResult:
    """Load, chunk, embed, and Qdrant-upsert one file."""

    chunk_seconds = 0.0
    qdrant_upsert_seconds = 0.0
    try:
        if resource_guard is not None:
            resource_guard.check_now(f"before_load:{source_path}")
        document = load_one_corpus_document(config.corpus_dir, source_path)
        if resource_guard is not None:
            resource_guard.check_now(f"after_load:{source_path}")
        document_sha256 = text_sha256(document.text)
        cache_path = chunk_cache_path(
            config=config,
            strategy_name=strategy.name,
            source_path=source_path,
            source_sha256=document_sha256,
        )
        chunk_started_at = time.monotonic()
        chunks = (
            load_cached_chunks(cache_path, strategy.name, source_path, document_sha256)
            if config.reuse_chunk_cache
            else None
        )
        chunk_cache_hit = chunks is not None
        if chunks is None:
            chunks = strategy.chunk_document(document)
        chunk_seconds = time.monotonic() - chunk_started_at
        if resource_guard is not None:
            resource_guard.check_now(f"after_chunk:{source_path}")
        if (
            config.max_chunks_per_file is not None
            and len(chunks) > config.max_chunks_per_file
        ):
            msg = (
                f"{len(chunks)} chunks exceeds max_chunks_per_file="
                f"{config.max_chunks_per_file}."
            )
            return file_result_from_error(strategy.name, source_path, msg)
        sanitized_chunks = [sanitize_chunk_for_qdrant(chunk) for chunk in chunks]
        if not chunk_cache_hit and config.write_chunk_cache:
            write_cached_chunks(
                cache_path=cache_path,
                chunks=sanitized_chunks,
                source_sha256=document_sha256,
                config=config,
            )
        if config.write_chunk_records:
            append_chunk_records(
                path=config.output_dir / CHUNK_RECORDS_FILENAME,
                chunks=sanitized_chunks,
                source_sha256=document_sha256,
                chunk_cache_hit=chunk_cache_hit,
                cache_path=cache_path,
            )
        upsert_started_at = time.monotonic()
        if resource_guard is not None:
            resource_guard.check_now(f"before_upsert:{source_path}")
        upserted_count = qdrant_database.upsert_chunks(sanitized_chunks)
        qdrant_upsert_seconds = time.monotonic() - upsert_started_at
        if resource_guard is not None:
            resource_guard.check_now(f"after_upsert:{source_path}")
        stats = chunk_stats(sanitized_chunks)
        return StreamingFileResult(
            strategy=strategy.name,
            source_path=source_path,
            status="completed",
            chunk_count=len(sanitized_chunks),
            table_chunk_count=stats["table_chunk_count"],
            total_chunk_chars=stats["total_chunk_chars"],
            min_chunk_chars=stats["min_chunk_chars"],
            max_chunk_chars=stats["max_chunk_chars"],
            avg_chunk_chars=stats["avg_chunk_chars"],
            chunk_seconds=round(chunk_seconds, 3),
            qdrant_upsert_seconds=round(qdrant_upsert_seconds, 3),
            qdrant_upserted_points=upserted_count,
            llm_fallback_chunk_count=stats["llm_fallback_chunk_count"],
            source_boundary_chunk_count=stats["source_boundary_chunk_count"],
            chunk_cache_hit=chunk_cache_hit,
            chunk_cache_path=str(cache_path) if cache_path is not None else "",
        )
    except ResourceLimitExceededError:
        raise
    except Exception as exc:
        return StreamingFileResult(
            strategy=strategy.name,
            source_path=source_path,
            status="failed",
            chunk_count=0,
            table_chunk_count=0,
            total_chunk_chars=0,
            min_chunk_chars=0,
            max_chunk_chars=0,
            avg_chunk_chars=0.0,
            chunk_seconds=round(chunk_seconds, 3),
            qdrant_upsert_seconds=round(qdrant_upsert_seconds, 3),
            qdrant_upserted_points=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def file_result_from_error(
    strategy: str,
    source_path: str,
    error: str,
) -> StreamingFileResult:
    """Build a failed file result without chunk statistics."""

    return StreamingFileResult(
        strategy=strategy,
        source_path=source_path,
        status="failed",
        chunk_count=0,
        table_chunk_count=0,
        total_chunk_chars=0,
        min_chunk_chars=0,
        max_chunk_chars=0,
        avg_chunk_chars=0.0,
        chunk_seconds=0.0,
        qdrant_upsert_seconds=0.0,
        qdrant_upserted_points=0,
        error=error,
    )


def text_sha256(text: str) -> str:
    """Return a stable SHA-256 hash for source text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_cache_path(
    config: StreamingChunkEmbeddingConfig,
    strategy_name: str,
    source_path: str,
    source_sha256: str,
) -> Path | None:
    """Return the cache file path for one strategy/source/config tuple."""

    if config.chunk_cache_dir is None:
        return None
    cache_payload = {
        "schema_version": CHUNK_CACHE_SCHEMA_VERSION,
        "strategy": strategy_name,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "chunking_config": chunking_cache_config(config, strategy_name),
    }
    cache_key = hashlib.sha256(
        json.dumps(
            cache_payload,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return config.chunk_cache_dir / strategy_name / f"{cache_key}.json"


def chunking_cache_config(
    config: StreamingChunkEmbeddingConfig,
    strategy_name: str,
) -> JsonDict:
    """Return chunking parameters that affect reusable chunk boundaries."""

    return {
        "strategy": strategy_name,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "heading_cut_level": config.heading_cut_level,
        "heading_max_chars": config.heading_max_chars,
        "heading_min_chars": config.heading_min_chars,
        "heading_max_table_rows": config.heading_max_table_rows,
    }


def load_cached_chunks(
    cache_path: Path | None,
    strategy_name: str,
    source_path: str,
    source_sha256: str,
) -> list[TextChunk] | None:
    """Load cached chunks when the cache matches the current source."""

    if cache_path is None or not cache_path.exists():
        return None
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CHUNK_CACHE_SCHEMA_VERSION:
        return None
    if payload.get("strategy") != strategy_name:
        return None
    if payload.get("source_path") != source_path:
        return None
    if payload.get("source_sha256") != source_sha256:
        return None
    chunks_payload = payload.get("chunks", [])
    if not isinstance(chunks_payload, list):
        return None
    return [text_chunk_from_dict(chunk_payload) for chunk_payload in chunks_payload]


def write_cached_chunks(
    cache_path: Path | None,
    chunks: list[TextChunk],
    source_sha256: str,
    config: StreamingChunkEmbeddingConfig,
) -> None:
    """Persist chunk boundaries so future runs can skip LLM chunking."""

    if cache_path is None or not chunks:
        return
    ensure_directory(cache_path.parent)
    first_chunk = chunks[0]
    payload = {
        "schema_version": CHUNK_CACHE_SCHEMA_VERSION,
        "strategy": first_chunk.strategy,
        "source_path": first_chunk.source_path,
        "source_sha256": source_sha256,
        "chunking_config": chunking_cache_config(config, first_chunk.strategy),
        "created_at_epoch": time.time(),
        "chunk_count": len(chunks),
        "chunks": [text_chunk_to_dict(chunk) for chunk in chunks],
    }
    temp_path = cache_path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(cache_path)


def append_chunk_records(
    path: Path,
    chunks: list[TextChunk],
    source_sha256: str,
    chunk_cache_hit: bool,
    cache_path: Path | None,
) -> None:
    """Append per-chunk boundary records for later inspection."""

    ensure_directory(path.parent)
    cache_path_text = str(cache_path) if cache_path is not None else ""
    with path.open("a", encoding="utf-8") as output_file:
        for chunk in chunks:
            record = text_chunk_to_dict(chunk)
            record["source_sha256"] = source_sha256
            record["chunk_cache_hit"] = chunk_cache_hit
            record["chunk_cache_path"] = cache_path_text
            output_file.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )


def text_chunk_to_dict(chunk: TextChunk) -> JsonDict:
    """Serialize a TextChunk without embedding vectors."""

    return {
        "chunk_id": chunk.chunk_id,
        "strategy": chunk.strategy,
        "source_path": chunk.source_path,
        "provider": chunk.provider,
        "text": chunk.text,
        "chunk_index": chunk.chunk_index,
        "start_char": chunk.start_char,
        "end_char": chunk.end_char,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "metadata": chunk.metadata,
    }


def text_chunk_from_dict(payload: JsonDict) -> TextChunk:
    """Deserialize a cached chunk."""

    return TextChunk(
        chunk_id=str(payload["chunk_id"]),
        strategy=str(payload["strategy"]),
        source_path=str(payload["source_path"]),
        provider=str(payload["provider"]),
        text=str(payload["text"]),
        chunk_index=int(payload["chunk_index"]),
        start_char=int(payload["start_char"]),
        end_char=int(payload["end_char"]),
        start_line=int(payload["start_line"]),
        end_line=int(payload["end_line"]),
        metadata=dict(payload.get("metadata") or {}),
    )


def load_one_corpus_document(corpus_dir: Path, source_path: str) -> CorpusDocument:
    """Load one Markdown corpus document."""

    absolute_path = corpus_dir / source_path
    text = absolute_path.read_text(encoding="utf-8")
    provider = source_path.split("/", maxsplit=1)[0]
    return CorpusDocument(
        source_path=source_path,
        absolute_path=absolute_path,
        provider=provider,
        text=text,
        line_offsets=build_line_offsets(text),
    )


def sanitize_chunk_for_qdrant(chunk: TextChunk) -> TextChunk:
    """Drop large duplicated metadata before Qdrant payload upsert."""

    return TextChunk(
        chunk_id=chunk.chunk_id,
        strategy=chunk.strategy,
        source_path=chunk.source_path,
        provider=chunk.provider,
        text=chunk.text,
        chunk_index=chunk.chunk_index,
        start_char=chunk.start_char,
        end_char=chunk.end_char,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        metadata=sanitize_metadata(chunk.metadata),
        embedding=chunk.embedding,
    )


def sanitize_metadata(metadata: JsonDict) -> JsonDict:
    """Keep metadata small and JSON-friendly for Qdrant payloads."""

    sanitized: JsonDict = {}
    for key, value in metadata.items():
        if key in HEAVY_METADATA_KEYS:
            continue
        if isinstance(value, str):
            sanitized[key] = value[:MAX_METADATA_STRING_CHARS]
            continue
        if isinstance(value, int | float | bool) or value is None:
            sanitized[key] = value
            continue
        if isinstance(value, list):
            sanitized[key] = [str(item)[:MAX_METADATA_STRING_CHARS] for item in value]
            continue
        sanitized[key] = str(value)[:MAX_METADATA_STRING_CHARS]
    return sanitized


def chunk_stats(chunks: list[TextChunk]) -> JsonDict:
    """Return compact chunk statistics."""

    lengths = [len(chunk.text) for chunk in chunks]
    table_chunk_count = sum(1 for chunk in chunks if "|" in chunk.text)
    llm_fallback_chunk_count = sum(
        1 for chunk in chunks if chunk.metadata.get("llm_fallback") is True
    )
    source_boundary_chunk_count = sum(
        1
        for chunk in chunks
        if chunk.start_char >= 0 and chunk.end_char >= chunk.start_char
    )
    if not lengths:
        return {
            "table_chunk_count": 0,
            "llm_fallback_chunk_count": 0,
            "source_boundary_chunk_count": 0,
            "total_chunk_chars": 0,
            "min_chunk_chars": 0,
            "max_chunk_chars": 0,
            "avg_chunk_chars": 0.0,
        }
    return {
        "table_chunk_count": table_chunk_count,
        "llm_fallback_chunk_count": llm_fallback_chunk_count,
        "source_boundary_chunk_count": source_boundary_chunk_count,
        "total_chunk_chars": sum(lengths),
        "min_chunk_chars": min(lengths),
        "max_chunk_chars": max(lengths),
        "avg_chunk_chars": round(sum(lengths) / len(lengths), 2),
    }


def read_cpu_snapshot() -> CpuSnapshot | None:
    """Read aggregate CPU ticks from Linux /proc/stat."""

    try:
        first_line = PROC_STAT_PATH.read_text(encoding="utf-8").splitlines()[0]
    except (IndexError, OSError):
        return None
    parts = first_line.split()
    if not parts or parts[0] != "cpu":
        return None
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError:
        return None
    if len(values) < 4:
        return None
    idle_ticks = values[3]
    if len(values) > 4:
        idle_ticks += values[4]
    total_ticks = sum(values)
    return CpuSnapshot(busy_ticks=total_ticks - idle_ticks, total_ticks=total_ticks)


def read_available_memory_mb() -> int | None:
    """Read MemAvailable from Linux /proc/meminfo."""

    try:
        lines = PROC_MEMINFO_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.startswith("MemAvailable:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            return None
        try:
            return int(parts[1]) // 1024
        except ValueError:
            return None
    return None


def release_memory() -> None:
    """Release Python and CUDA caches between files."""

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def write_csv(path: Path, rows: list[JsonDict]) -> None:
    """Write rows to CSV."""

    ensure_directory(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(
    config: StreamingChunkEmbeddingConfig,
    source_paths: list[str],
) -> None:
    """Write run configuration manifest."""

    payload = {
        "benchmark_path": str(config.benchmark_path),
        "corpus_dir": str(config.corpus_dir),
        "strategies": list(config.strategies),
        "source_selection": config.source_selection,
        "source_paths": source_paths,
        "embedding_model_name": config.embedding_model_name,
        "embedding_device": config.embedding_device,
        "embedding_batch_size": config.embedding_batch_size,
        "markdown_element_llm_provider": config.markdown_element_llm_provider,
        "markdown_element_gemini_model": config.markdown_element_gemini_model,
        "markdown_element_llm_provider_slot_counts": provider_slot_counts(
            config.markdown_element_llm_provider_slots
        ),
        "markdown_element_llm_timeout_seconds": (
            config.markdown_element_llm_timeout_seconds
        ),
        "markdown_element_llm_max_slot_attempts": (
            config.markdown_element_llm_max_slot_attempts
        ),
        "markdown_element_num_workers": config.markdown_element_num_workers,
        "resolved_markdown_element_num_workers": (
            resolve_markdown_element_num_workers(config)
            if needs_streaming_llm(config.strategies)
            else 0
        ),
        "collection_name": config.collection_name,
        "keep_qdrant": config.keep_qdrant,
        "chunk_cache_dir": str(config.chunk_cache_dir)
        if config.chunk_cache_dir is not None
        else "",
        "reuse_chunk_cache": config.reuse_chunk_cache,
        "write_chunk_cache": config.write_chunk_cache,
        "write_chunk_records": config.write_chunk_records,
        "chunk_records_path": str(config.output_dir / CHUNK_RECORDS_FILENAME),
        "processing_mode": "strategy_then_file_streaming",
        "qdrant_mode": "incremental_upsert_per_file",
    }
    (config.output_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
