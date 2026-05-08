"""Base interfaces and helpers for chunking strategies."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from src.eval.corpus import line_number_for_offset
from src.eval.models import CorpusDocument, JsonDict, TextChunk


@dataclass(frozen=True)
class StrategySpec:
    """Human-readable strategy metadata."""

    name: str
    description: str
    requires_embeddings: bool = False
    requires_llm: bool = False
    optional_dependency: str | None = None


class ChunkingStrategy(ABC):
    """Common interface for static chunking strategies."""

    name: str
    description: str

    @abstractmethod
    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split one corpus document into chunks."""


def make_source_document(document: CorpusDocument) -> Document:
    """Build a LangChain Document with source metadata."""

    return Document(
        page_content=document.text,
        metadata={
            "source_path": document.source_path,
            "provider": document.provider,
        },
    )


def chunks_from_langchain_documents(
    document: CorpusDocument,
    strategy_name: str,
    split_documents: Iterable[Document],
) -> list[TextChunk]:
    """Convert LangChain documents into local chunk models."""

    parts = [
        (split_document.page_content, dict(split_document.metadata))
        for split_document in split_documents
        if split_document.page_content.strip()
    ]
    return chunks_from_parts(document, strategy_name, parts)


def chunks_from_texts(
    document: CorpusDocument,
    strategy_name: str,
    texts: Iterable[str],
) -> list[TextChunk]:
    """Convert raw text chunks into local chunk models."""

    return chunks_from_parts(document, strategy_name, [(text, {}) for text in texts])


def chunks_from_parts(
    document: CorpusDocument,
    strategy_name: str,
    parts: Iterable[tuple[str, JsonDict]],
) -> list[TextChunk]:
    """Create chunks while preserving best-effort source offsets."""

    chunks: list[TextChunk] = []
    cursor = 0
    for chunk_index, (text, metadata) in enumerate(parts):
        if not text.strip():
            continue
        start_char, end_char, offset_match = find_part_span(
            document.text,
            text,
            cursor,
        )
        cursor = max(cursor, end_char)
        enriched_metadata = {
            **metadata,
            "offset_match": offset_match,
            "chunk_length": len(text),
        }
        start_line = line_number_for_offset(document.line_offsets, start_char)
        end_line = line_number_for_offset(
            document.line_offsets,
            max(start_char, end_char - 1),
        )
        chunks.append(
            TextChunk(
                chunk_id=make_chunk_id(
                    strategy_name=strategy_name,
                    source_path=document.source_path,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    text=text,
                ),
                strategy=strategy_name,
                source_path=document.source_path,
                provider=document.provider,
                text=text,
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=end_char,
                start_line=start_line,
                end_line=end_line,
                metadata=enriched_metadata,
            )
        )
    return chunks


def find_part_span(
    source_text: str,
    part_text: str,
    cursor: int,
    allow_backward_search: bool = True,
) -> tuple[int, int, bool]:
    """Find a chunk's character span without trusting splitter metadata blindly."""

    candidates = [part_text, part_text.strip()]
    search_start = (
        max(0, cursor - max(2000, len(part_text) * 2))
        if allow_backward_search
        else cursor
    )
    for candidate in candidates:
        if not candidate:
            continue
        position = source_text.find(candidate, search_start)
        if position < 0 and allow_backward_search:
            position = source_text.find(candidate)
        if position >= 0:
            return position, position + len(candidate), True
    relaxed_part = normalize_whitespace(part_text)
    relaxed_source = normalize_whitespace(source_text[cursor:])
    relaxed_position = relaxed_source.find(relaxed_part)
    if relaxed_part and relaxed_position == 0:
        return cursor, min(len(source_text), cursor + len(part_text)), False
    start_char = cursor
    end_char = min(len(source_text), start_char + len(part_text))
    return start_char, end_char, False


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace for non-authoritative matching diagnostics."""

    return re.sub(r"\s+", " ", text).strip()


def make_chunk_id(
    strategy_name: str,
    source_path: str,
    chunk_index: int,
    start_char: int,
    text: str,
) -> str:
    """Create a stable chunk identifier."""

    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    return f"{strategy_name}:{source_path}:{chunk_index}:{start_char}:{digest}"


def header_path(metadata: dict[str, Any]) -> str:
    """Return a readable Markdown header path from splitter metadata."""

    headers = [
        str(metadata[key])
        for key in sorted(metadata)
        if key.startswith("Header ") and metadata.get(key)
    ]
    return " > ".join(headers)
