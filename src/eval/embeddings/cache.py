"""SQLite embedding cache shared by chunking evaluation embeddings."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.eval.io import ensure_directory

CACHE_KEY_VERSION = "embedding-cache-v1"


@dataclass(frozen=True)
class EmbeddingCacheRequest:
    """One embedding cache lookup request."""

    provider: str
    model: str
    purpose: str
    config_hash: str
    text: str

    @property
    def text_hash(self) -> str:
        """Return SHA-256 hash of the exact embedded text."""

        return sha256_text(self.text)

    @property
    def cache_key(self) -> str:
        """Return a stable cache key."""

        payload = {
            "version": CACHE_KEY_VERSION,
            "provider": self.provider,
            "model": self.model,
            "purpose": self.purpose,
            "config_hash": self.config_hash,
            "text_hash": self.text_hash,
        }
        return sha256_text(stable_json(payload))


@dataclass
class EmbeddingCacheStats:
    """Runtime cache counters."""

    hits: int = 0
    misses: int = 0
    writes: int = 0
    stale: int = 0
    disabled: int = 0


class EmbeddingCache:
    """Small SQLite cache keyed by provider/model/purpose/config/text hash."""

    def __init__(self, path: Path, enabled: bool = True) -> None:
        self.path = path
        self.enabled = enabled
        self.stats = EmbeddingCacheStats()
        if enabled:
            ensure_directory(path.parent)
            self._initialize()

    def get_many(
        self,
        requests: list[EmbeddingCacheRequest],
        expected_dimension: int | None = None,
    ) -> dict[str, list[float]]:
        """Return cached vectors by cache key."""

        if not self.enabled:
            self.stats.disabled += len(requests)
            return {}
        cached_vectors: dict[str, list[float]] = {}
        with sqlite3.connect(self.path) as connection:
            for request in requests:
                row = connection.execute(
                    (
                        "SELECT dimension, vector_json FROM embeddings "
                        "WHERE cache_key = ?"
                    ),
                    (request.cache_key,),
                ).fetchone()
                if row is None:
                    self.stats.misses += 1
                    continue
                dimension = int(row[0])
                if expected_dimension is not None and dimension != expected_dimension:
                    self.stats.stale += 1
                    continue
                try:
                    vector = json.loads(str(row[1]))
                except json.JSONDecodeError:
                    self.stats.stale += 1
                    continue
                if not isinstance(vector, list) or len(vector) != dimension:
                    self.stats.stale += 1
                    continue
                try:
                    cached_vector = [float(value) for value in vector]
                except (TypeError, ValueError):
                    self.stats.stale += 1
                    continue
                cached_vectors[request.cache_key] = cached_vector
                self.stats.hits += 1
        return cached_vectors

    def set_many(
        self,
        items: list[tuple[EmbeddingCacheRequest, list[float]]],
    ) -> None:
        """Write vectors to the cache."""

        if not self.enabled:
            return
        now = datetime.now(UTC).isoformat()
        rows = [
            (
                request.cache_key,
                request.provider,
                request.model,
                request.purpose,
                request.text_hash,
                request.config_hash,
                len(vector),
                json.dumps(vector, ensure_ascii=False, separators=(",", ":")),
                now,
            )
            for request, vector in items
        ]
        with sqlite3.connect(self.path) as connection:
            connection.executemany(
                (
                    "INSERT OR REPLACE INTO embeddings "
                    "(cache_key, provider, model, purpose, text_hash, config_hash, "
                    "dimension, vector_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                rows,
            )
        self.stats.writes += len(rows)

    def to_payload(self) -> dict[str, object]:
        """Return cache configuration and runtime counters."""

        return {
            "enabled": self.enabled,
            "path": str(self.path),
            "stats": asdict(self.stats),
        }

    def _initialize(self) -> None:
        """Create cache schema."""

        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    cache_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_embeddings_lookup
                ON embeddings (provider, model, purpose, config_hash, text_hash)
                """
            )


def build_embedding_requests(
    provider: str,
    model: str,
    purpose: str,
    config_hash: str,
    texts: list[str],
) -> list[EmbeddingCacheRequest]:
    """Build cache requests for a batch of texts."""

    return [
        EmbeddingCacheRequest(
            provider=provider,
            model=model,
            purpose=purpose,
            config_hash=config_hash,
            text=text,
        )
        for text in texts
    ]


def embedding_config_hash(config: dict[str, Any]) -> str:
    """Hash embedding parameters that affect vector values."""

    return sha256_text(stable_json(config))


def sha256_text(text: str) -> str:
    """Return SHA-256 hex digest for text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_json(payload: dict[str, Any]) -> str:
    """Return deterministic JSON for hashing."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
