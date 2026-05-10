"""Configuration defaults for chunking evaluation runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.core.config import settings
from src.eval.llms.provider_slots import (
    EvalLLMProviderSlot,
    collect_markdown_element_llm_provider_slots,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _env_csv(name: str) -> tuple[str, ...]:
    """Read a comma-separated environment variable."""

    value = os.getenv(name, "")
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable."""

    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_optional_int(name: str) -> int | None:
    """Read an optional integer environment variable."""

    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return int(value)


def _env_float(name: str, default: float) -> float:
    """Read a float environment variable."""

    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable."""

    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path) -> Path:
    """Read a path environment variable relative to the project root."""

    value = os.getenv(name)
    path = Path(value.strip()) if value and value.strip() else default
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _collect_gemini_api_keys() -> tuple[str, ...]:
    """Read Gemini keys from aggregate and numbered env vars."""

    keys: list[str] = []
    for env_name in (
        "MARKDOWN_ELEMENT_GEMINI_API_KEYS",
        "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS",
        "GEMINI_API_KEYS",
    ):
        keys.extend(_env_csv(env_name))
    for prefix in ("MARKDOWN_ELEMENT_GEMINI_API_KEY", "GEMINI_API_KEY"):
        for index in range(1, 21):
            value = os.getenv(f"{prefix}_{index}", "").strip()
            if value:
                keys.append(value)
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(env_name, "").strip()
        if value:
            keys.append(value)

    unique_keys: list[str] = []
    for key in keys:
        if key not in unique_keys:
            unique_keys.append(key)
    return tuple(unique_keys)


def _resolve_eval_google_api_key() -> str:
    """Return the Google API key used by eval embedding adapters."""

    keys = _collect_eval_google_api_keys()
    return keys[0] if keys else ""


def _resolve_indirect_env_value(value: str) -> str:
    """Resolve a value that might itself be an environment variable name."""

    if value in os.environ:
        return os.environ[value]
    return value


def _collect_numbered_env_values(prefix: str) -> tuple[str, ...]:
    """Collect every numbered env var with the given prefix in numeric order."""

    values: list[tuple[int, str]] = []
    prefix_with_separator = f"{prefix}_"
    for environment_name, raw_value in os.environ.items():
        if not environment_name.startswith(prefix_with_separator):
            continue
        suffix = environment_name.removeprefix(prefix_with_separator)
        if not suffix.isdigit():
            continue
        resolved_value = _resolve_indirect_env_value(raw_value.strip())
        if resolved_value:
            values.append((int(suffix), resolved_value))
    return tuple(value for _, value in sorted(values))


def _collect_eval_google_api_keys() -> tuple[str, ...]:
    """Return all Google API keys available for eval embeddings."""

    keys: list[str] = []
    for env_name in (
        "CHUNKING_EVAL_EMBEDDING_GOOGLE_API_KEY",
        "CHUNKING_EVAL_EMBEDDING_GOOGLE_API_KEYS",
        "RAG_EMBEDDING_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        raw_value = os.getenv(env_name, "").strip()
        if not raw_value:
            continue
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
        for value in values:
            resolved_value = _resolve_indirect_env_value(value)
            if resolved_value:
                keys.append(resolved_value)
    keys.extend(_collect_numbered_env_values("GOOGLE_API_KEY"))
    keys.extend(_collect_numbered_env_values("GEMINI_API_KEY"))
    for value in settings.GOOGLE_API_KEYS:
        resolved_value = _resolve_indirect_env_value(value)
        if resolved_value:
            keys.append(resolved_value)

    unique_keys: list[str] = []
    for key in keys:
        if key not in unique_keys:
            unique_keys.append(key)
    return tuple(unique_keys)


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
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "generated"
DEFAULT_COLLECTION_NAME = "chunks"
FAST_MULTILINGUAL_EMBEDDING_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
DEFAULT_EMBEDDING_PROVIDER = os.getenv(
    "CHUNKING_EVAL_EMBEDDING_PROVIDER",
    "sentence_transformers",
)
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "CHUNKING_EVAL_EMBEDDING_MODEL",
    FAST_MULTILINGUAL_EMBEDDING_MODEL,
)
DEFAULT_EMBEDDING_DEVICE = (
    os.getenv(
        "CHUNKING_EVAL_EMBEDDING_DEVICE",
        "cuda",
    ).strip()
    or None
)
DEFAULT_EMBEDDING_GOOGLE_API_KEY = _resolve_eval_google_api_key()
DEFAULT_EMBEDDING_GOOGLE_API_KEYS = _collect_eval_google_api_keys()
DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY = _env_optional_int(
    "CHUNKING_EVAL_EMBEDDING_OUTPUT_DIMENSIONALITY"
)
if DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY is None:
    DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY = settings.RAG_DENSE_VECTOR_SIZE
DEFAULT_EMBEDDING_CACHE_ENABLED = _env_bool(
    "CHUNKING_EVAL_EMBEDDING_CACHE_ENABLED",
    True,
)
DEFAULT_EMBEDDING_CACHE_PATH = _env_path(
    "CHUNKING_EVAL_EMBEDDING_CACHE_PATH",
    DEFAULT_OUTPUT_DIR / "embedding_cache" / "cache.sqlite",
)
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 5
DEFAULT_BATCH_SIZE = 64
DEFAULT_LIMIT_DOCUMENTS = _env_int("CHUNKING_EVAL_LIMIT_DOCUMENTS", 10)
DEFAULT_STRATEGY_RETRIES = _env_int("CHUNKING_EVAL_STRATEGY_RETRIES", 2)
DEFAULT_RESUME_COMPLETED_STRATEGIES = _env_bool(
    "CHUNKING_EVAL_RESUME_COMPLETED_STRATEGIES",
    True,
)
DEFAULT_LLM_SCORING_CACHE_ENABLED = _env_bool(
    "CHUNKING_EVAL_LLM_SCORING_CACHE_ENABLED",
    True,
)
DEFAULT_HEADING_CUT_LEVEL = _env_int("CHUNKING_EVAL_HEADING_CUT_LEVEL", 0)
DEFAULT_HEADING_MAX_CHARS = _env_int("CHUNKING_EVAL_HEADING_MAX_CHARS", 6000)
DEFAULT_HEADING_MIN_CHARS = _env_int("CHUNKING_EVAL_HEADING_MIN_CHARS", 300)
DEFAULT_HEADING_MAX_TABLE_ROWS = _env_int(
    "CHUNKING_EVAL_HEADING_MAX_TABLE_ROWS",
    50,
)
DEFAULT_DEEPEVAL_THRESHOLD = 0.5
DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_PROVIDER = os.getenv(
    "SEMANTIC_CHUNKING_EMBEDDING_PROVIDER",
    "sentence_transformers",
)
DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_MODEL = os.getenv(
    "SEMANTIC_CHUNKING_EMBEDDING_MODEL",
    FAST_MULTILINGUAL_EMBEDDING_MODEL,
)
DEFAULT_SEMANTIC_CHUNKING_EMBEDDING_DEVICE = (
    os.getenv(
        "SEMANTIC_CHUNKING_EMBEDDING_DEVICE",
        DEFAULT_EMBEDDING_DEVICE or "",
    ).strip()
    or None
)
DEFAULT_SEMANTIC_CHUNKING_OLLAMA_BASE_URL = os.getenv(
    "SEMANTIC_CHUNKING_OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
)
DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER = os.getenv(
    "MARKDOWN_ELEMENT_LLM_PROVIDER",
    "multi",
)
DEFAULT_MARKDOWN_ELEMENT_GEMINI_MODEL = os.getenv(
    "MARKDOWN_ELEMENT_GEMINI_MODEL",
    os.getenv(
        "LLM_CHUNKING_MODEL",
        os.getenv("KG_SCHEMA_DISCOVERY_GEMINI_MODEL", "gemma-4-31b-it"),
    ),
)
DEFAULT_MARKDOWN_ELEMENT_GEMINI_API_KEYS = _collect_gemini_api_keys()
DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS = (
    collect_markdown_element_llm_provider_slots()
)
DEFAULT_MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS = _env_float(
    "MARKDOWN_ELEMENT_LLM_TIMEOUT_SECONDS",
    _env_float("LLM_CHUNKING_TIMEOUT_SECONDS", 120.0),
)
DEFAULT_MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS = _env_int(
    "MARKDOWN_ELEMENT_LLM_MAX_SLOT_ATTEMPTS",
    4,
)
DEFAULT_MARKDOWN_ELEMENT_NUM_WORKERS = _env_int(
    "MARKDOWN_ELEMENT_NUM_WORKERS",
    max(4, min(32, len(DEFAULT_MARKDOWN_ELEMENT_LLM_PROVIDER_SLOTS) or 4)),
)
DEFAULT_LATE_CHUNKING_EMBEDDING_MODEL = os.getenv(
    "LATE_CHUNKING_EMBEDDING_MODEL",
    FAST_MULTILINGUAL_EMBEDDING_MODEL,
)
DEFAULT_LATE_CHUNKING_MAX_TOKENS = _env_int("LATE_CHUNKING_MAX_TOKENS", 8192)
DEFAULT_LATE_CHUNKING_TRUST_REMOTE_CODE = _env_bool(
    "LATE_CHUNKING_TRUST_REMOTE_CODE",
    True,
)
DEFAULT_LATE_CHUNKING_DEVICE = os.getenv("LATE_CHUNKING_DEVICE", "").strip() or None

DEFAULT_MARKDOWN_HEADERS = (
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
    ("####", "Header 4"),
    ("#####", "Header 5"),
    ("######", "Header 6"),
)


@dataclass(frozen=True)
class ChunkingRunConfig:
    """Runtime settings for a chunking benchmark run."""

    benchmark_path: Path = DEFAULT_BENCHMARK_PATH
    corpus_dir: Path = DEFAULT_CORPUS_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL
    embedding_device: str | None = DEFAULT_EMBEDDING_DEVICE
    embedding_google_api_key: str = DEFAULT_EMBEDDING_GOOGLE_API_KEY
    embedding_google_api_keys: tuple[str, ...] = DEFAULT_EMBEDDING_GOOGLE_API_KEYS
    embedding_output_dimensionality: int | None = (
        DEFAULT_EMBEDDING_OUTPUT_DIMENSIONALITY
    )
    embedding_cache_enabled: bool = DEFAULT_EMBEDDING_CACHE_ENABLED
    embedding_cache_path: Path = DEFAULT_EMBEDDING_CACHE_PATH
    collection_name: str = DEFAULT_COLLECTION_NAME
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    top_k: int = DEFAULT_TOP_K
    batch_size: int = DEFAULT_BATCH_SIZE
    limit_documents: int | None = DEFAULT_LIMIT_DOCUMENTS
    run_id: str | None = None
    strategy_retries: int = DEFAULT_STRATEGY_RETRIES
    resume_completed_strategies: bool = DEFAULT_RESUME_COMPLETED_STRATEGIES
    llm_scoring_cache_enabled: bool = DEFAULT_LLM_SCORING_CACHE_ENABLED
    heading_cut_level: int = DEFAULT_HEADING_CUT_LEVEL
    heading_max_chars: int = DEFAULT_HEADING_MAX_CHARS
    heading_min_chars: int = DEFAULT_HEADING_MIN_CHARS
    heading_max_table_rows: int = DEFAULT_HEADING_MAX_TABLE_ROWS
    deepeval_threshold: float = DEFAULT_DEEPEVAL_THRESHOLD
    deepeval_model: str | None = None
    include_deepeval_reasons: bool = False
    run_deepeval: bool = True
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
    markdown_element_num_workers: int = DEFAULT_MARKDOWN_ELEMENT_NUM_WORKERS
    late_chunking_embedding_model: str = DEFAULT_LATE_CHUNKING_EMBEDDING_MODEL
    late_chunking_max_tokens: int = DEFAULT_LATE_CHUNKING_MAX_TOKENS
    late_chunking_trust_remote_code: bool = DEFAULT_LATE_CHUNKING_TRUST_REMOTE_CODE
    late_chunking_device: str | None = DEFAULT_LATE_CHUNKING_DEVICE
