import json
from pathlib import Path

import pytest

from src.eval.llm_provider_slots import EvalLLMProviderSlot
from src.eval.models import TextChunk
from src.eval.streaming_qdrant_chunking import (
    MAX_METADATA_STRING_CHARS,
    SOURCE_SELECTION_EXPECTED,
    ResourceGuard,
    ResourceLimitExceededError,
    StreamingChunkEmbeddingConfig,
    chunk_cache_path,
    chunk_stats,
    load_cached_chunks,
    resolve_markdown_element_num_workers,
    sanitize_chunk_for_qdrant,
    selected_source_paths,
    text_sha256,
    write_cached_chunks,
)
from src.eval.vector_database import QdrantStrategyDatabase


class FakeEmbeddings:
    batch_size = 2

    @property
    def dimension(self) -> int:
        return 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text) + 1), 1.0, 0.0] for text in texts]

    def embed_query(self, _text: str) -> list[float]:
        return [1.0, 1.0, 0.0]


def test_sanitize_chunk_for_qdrant_removes_heavy_metadata() -> None:
    chunk = make_chunk(
        "chunk-1",
        metadata={
            "parent_text": "x" * 1000,
            "retrieval_text": "y" * 1000,
            "section": "z" * 600,
            "page": 3,
            "tags": ["a" * 600, 7],
            "nested": {"long": "b" * 600},
        },
    )

    sanitized = sanitize_chunk_for_qdrant(chunk)

    assert "parent_text" not in sanitized.metadata
    assert "retrieval_text" not in sanitized.metadata
    assert sanitized.metadata["page"] == 3
    assert len(sanitized.metadata["section"]) == MAX_METADATA_STRING_CHARS
    assert len(sanitized.metadata["tags"][0]) == MAX_METADATA_STRING_CHARS
    assert sanitized.metadata["tags"][1] == "7"
    assert len(sanitized.metadata["nested"]) == MAX_METADATA_STRING_CHARS
    assert sanitized.text == chunk.text


def test_chunk_stats_counts_tables_and_lengths() -> None:
    stats = chunk_stats(
        [
            make_chunk("chunk-1", text="plain text"),
            make_chunk("chunk-2", text="| Col |\n|---|\n| A |"),
        ]
    )

    assert stats == {
        "table_chunk_count": 1,
        "llm_fallback_chunk_count": 0,
        "source_boundary_chunk_count": 2,
        "total_chunk_chars": 29,
        "min_chunk_chars": 10,
        "max_chunk_chars": 19,
        "avg_chunk_chars": 14.5,
    }


def test_qdrant_strategy_database_upserts_incrementally(tmp_path: Path) -> None:
    database = QdrantStrategyDatabase(
        database_path=tmp_path / "qdrant",
        collection_name="chunks",
        embeddings=FakeEmbeddings(),
    )

    try:
        assert database.upsert_chunks([make_chunk("chunk-1", text="alpha")]) == 1
        assert database.upsert_chunks([make_chunk("chunk-2", text="beta")]) == 1

        retrieved = database.search(
            case_id="case-1",
            strategy="strategy-a",
            query="alpha",
            top_k=10,
        )
    finally:
        database.delete()

    assert {chunk.chunk_id for chunk in retrieved} == {"chunk-1", "chunk-2"}


def test_resource_guard_writes_abort_marker_for_low_memory(tmp_path: Path) -> None:
    config = StreamingChunkEmbeddingConfig(
        output_dir=tmp_path,
        qdrant_work_dir=tmp_path / "qdrant",
        embedding_cache_path=tmp_path / "cache.sqlite",
        cpu_abort_percent=None,
        min_available_memory_mb=1_000_000_000,
    )
    guard = ResourceGuard(config)

    with pytest.raises(ResourceLimitExceededError):
        guard.check_now("unit-test")

    marker = json.loads((tmp_path / "resource_guard_abort.json").read_text())
    assert "available memory" in marker["reason"]


def test_selected_source_paths_can_use_all_expected_sources(tmp_path: Path) -> None:
    benchmark_path = tmp_path / "benchmark.jsonl"
    corpus_dir = tmp_path / "corpus"
    (corpus_dir / "provider").mkdir(parents=True)
    (corpus_dir / "provider/a.md").write_text("a", encoding="utf-8")
    (corpus_dir / "provider/b.md").write_text("b", encoding="utf-8")
    benchmark_path.write_text(
        json.dumps(
            {
                "id": "case-1",
                "question": "Question?",
                "gold_answer": "Answer.",
                "expected_sources": [
                    {
                        "provider": "provider",
                        "source_path": "provider/a.md",
                        "line_start": 1,
                        "line_end": 1,
                        "evidence_quote": "a",
                        "relationship": "primary",
                    },
                    {
                        "provider": "provider",
                        "source_path": "provider/b.md",
                        "line_start": 1,
                        "line_end": 1,
                        "evidence_quote": "b",
                    },
                    {
                        "provider": "provider",
                        "source_path": "provider/missing.md",
                        "line_start": 1,
                        "line_end": 1,
                        "evidence_quote": "missing",
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    config = StreamingChunkEmbeddingConfig(
        benchmark_path=benchmark_path,
        corpus_dir=corpus_dir,
        source_selection=SOURCE_SELECTION_EXPECTED,
        limit_documents=None,
    )

    assert selected_source_paths(config) == ["provider/a.md", "provider/b.md"]


def test_resolve_markdown_element_num_workers_uses_all_slots_by_default() -> None:
    config = StreamingChunkEmbeddingConfig(
        markdown_element_num_workers=0,
        markdown_element_llm_provider_slots=(
            EvalLLMProviderSlot(
                slot_id="gemini:0",
                provider="gemini",
                model="model-a",
                api_key="key-a",
            ),
            EvalLLMProviderSlot(
                slot_id="nvidia:0",
                provider="nvidia",
                model="model-b",
                api_key="key-b",
            ),
        ),
    )

    assert resolve_markdown_element_num_workers(config) == 2


def test_resolve_markdown_element_num_workers_respects_explicit_override() -> None:
    config = StreamingChunkEmbeddingConfig(
        markdown_element_num_workers=7,
        markdown_element_llm_provider_slots=(
            EvalLLMProviderSlot(
                slot_id="gemini:0",
                provider="gemini",
                model="model-a",
                api_key="key-a",
            ),
            EvalLLMProviderSlot(
                slot_id="nvidia:0",
                provider="nvidia",
                model="model-b",
                api_key="key-b",
            ),
        ),
    )

    assert resolve_markdown_element_num_workers(config) == 7


def test_chunk_cache_round_trips_boundaries(tmp_path: Path) -> None:
    config = StreamingChunkEmbeddingConfig(chunk_cache_dir=tmp_path / "chunk_cache")
    source_text = "alpha\nbeta"
    source_hash = text_sha256(source_text)
    cache_path = chunk_cache_path(
        config=config,
        strategy_name="llm_markdown_optimal",
        source_path="provider/doc.md",
        source_sha256=source_hash,
    )
    chunk = make_chunk(
        "chunk-1",
        text="alpha",
        strategy="llm_markdown_optimal",
        metadata={"llm_fallback": False, "summary": "first"},
    )

    write_cached_chunks(
        cache_path=cache_path,
        chunks=[chunk],
        source_sha256=source_hash,
        config=config,
    )
    loaded_chunks = load_cached_chunks(
        cache_path=cache_path,
        strategy_name="llm_markdown_optimal",
        source_path="provider/doc.md",
        source_sha256=source_hash,
    )

    assert loaded_chunks == [chunk]
    assert (
        load_cached_chunks(
            cache_path=cache_path,
            strategy_name="llm_markdown_optimal",
            source_path="provider/doc.md",
            source_sha256=text_sha256("changed"),
        )
        is None
    )


def make_chunk(
    chunk_id: str,
    text: str = "hello world",
    strategy: str = "strategy-a",
    metadata: dict[str, object] | None = None,
) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        strategy=strategy,
        source_path="provider/doc.md",
        provider="provider",
        text=text,
        chunk_index=0,
        start_char=0,
        end_char=len(text),
        start_line=1,
        end_line=1,
        metadata=metadata or {},
    )
