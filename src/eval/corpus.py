"""Corpus loading and source offset utilities."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from pathlib import Path

from src.eval.models import CorpusDocument


def build_line_offsets(text: str) -> tuple[int, ...]:
    """Return character offsets for the start of each source line."""

    offsets = [0]
    cursor = 0
    for line in text.splitlines(keepends=True):
        cursor += len(line)
        offsets.append(cursor)
    return tuple(offsets)


def line_number_for_offset(line_offsets: tuple[int, ...], offset: int) -> int:
    """Convert a character offset to a one-based source line number."""

    if not line_offsets:
        return 1
    safe_offset = max(0, offset)
    line_index = bisect_right(line_offsets, safe_offset) - 1
    return max(1, min(line_index + 1, len(line_offsets)))


def load_markdown_corpus(
    corpus_dir: Path,
    limit_documents: int | None = None,
    preferred_source_paths: Iterable[str] | None = None,
) -> list[CorpusDocument]:
    """Load markdown documents from a corpus directory."""

    documents: list[CorpusDocument] = []
    markdown_paths = ordered_markdown_paths(
        corpus_dir=corpus_dir,
        preferred_source_paths=preferred_source_paths,
    )
    for absolute_path in markdown_paths:
        relative_path = absolute_path.relative_to(corpus_dir).as_posix()
        provider = relative_path.split("/", maxsplit=1)[0]
        text = absolute_path.read_text(encoding="utf-8")
        documents.append(
            CorpusDocument(
                source_path=relative_path,
                absolute_path=absolute_path,
                provider=provider,
                text=text,
                line_offsets=build_line_offsets(text),
            )
        )
        if limit_documents is not None and len(documents) >= limit_documents:
            break
    return documents


def ordered_markdown_paths(
    corpus_dir: Path,
    preferred_source_paths: Iterable[str] | None = None,
) -> list[Path]:
    """Return corpus paths, honoring benchmark source order when provided."""

    sorted_paths = sorted(corpus_dir.rglob("*.md"))
    path_by_source = {
        path.relative_to(corpus_dir).as_posix(): path for path in sorted_paths
    }
    ordered_paths: list[Path] = []
    seen_sources: set[str] = set()
    for source_path in preferred_source_paths or ():
        path = path_by_source.get(source_path)
        if path is None or source_path in seen_sources:
            continue
        ordered_paths.append(path)
        seen_sources.add(source_path)
    ordered_paths.extend(
        path
        for path in sorted_paths
        if path.relative_to(corpus_dir).as_posix() not in seen_sources
    )
    return ordered_paths
