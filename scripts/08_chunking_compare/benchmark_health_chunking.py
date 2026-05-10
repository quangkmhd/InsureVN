from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import dotenv_values
from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import (
    CharacterTextSplitter,
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.chunking.document_chunker import DocumentChunker  # noqa: E402

DEFAULT_SOURCE_ROOT = next(
    (parent.parent for parent in REPO_ROOT.parents if parent.name == ".worktrees"),
    REPO_ROOT,
)
DEFAULT_CORPUS_DIR = DEFAULT_SOURCE_ROOT / "data/health_insurance/markdown_collection"
DEFAULT_ENV_PATH = DEFAULT_SOURCE_ROOT / ".env"
DEFAULT_OUTPUT_DIR = Path("reports/chunking_benchmark_llm")
DEFAULT_CHUNK_SIZE_TOKENS = 400
DEFAULT_OVERLAP_TOKENS = 50
DEFAULT_SENTENCES_PER_CHUNK = 3
DEFAULT_MAX_CASES = 900
DEFAULT_PROJECT_CHUNKING_STRATEGY = "hierarchical_header_recursive"
DEFAULT_LLM_CHUNK_CACHE_PATH = (
    Path("reports/chunking_benchmark_llm") / "llm_chunk_cache.json"
)
TOKEN_CHARS = 4
RETRIEVAL_TOP_K = 5
LLM_BLOCK_BATCH_SIZE = 70
LLM_TARGET_CHARS = 1_400
LLM_MAX_CHARS = 3_200
LLM_POLICY_TIMEOUT_SECONDS = 60

STOPWORDS = {
    "anh",
    "bao",
    "bang",
    "benh",
    "cac",
    "cach",
    "can",
    "cap",
    "chi",
    "cho",
    "co",
    "con",
    "cua",
    "cung",
    "du",
    "duoc",
    "giay",
    "han",
    "hay",
    "hoac",
    "khach",
    "khi",
    "khong",
    "la",
    "lam",
    "mau",
    "mot",
    "nay",
    "nguoi",
    "nhung",
    "noi",
    "phai",
    "qua",
    "quy",
    "sau",
    "suc",
    "tai",
    "theo",
    "thi",
    "thong",
    "tin",
    "trong",
    "tu",
    "va",
    "ve",
    "voi",
}

QUESTION_HINTS = {
    "benefit": ("quyen loi", "han muc", "boi thuong", "chi tra", "tro cap"),
    "exclusion": ("loai tru", "khong chi tra", "tu choi", "mien tru"),
    "waiting": ("thoi gian cho", "ngay cho", "benh dac biet"),
    "claim": ("boi thuong", "ho so", "yeu cau", "claim", "khieu nai"),
    "provider": ("benh vien", "phong kham", "co so y te", "bao lanh"),
    "premium": ("phi bao hiem", "bieu phi", "muc phi"),
    "eligibility": ("tuoi", "doi tuong", "tham gia", "nguoi duoc bao hiem"),
}
MARKDOWN_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]
MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?$"
)


@dataclass(frozen=True)
class SourceDocument:
    """One markdown file loaded from the private health insurance corpus."""

    doc_id: str
    file_name: str
    path: str
    text: str


@dataclass(frozen=True)
class Chunk:
    """One chunk emitted by a chunking method."""

    chunk_id: str
    method: str
    doc_id: str
    file_name: str
    text: str
    start: int
    end: int
    tokens: int


@dataclass(frozen=True)
class SourceBlock:
    """One source-preserving atomic block for LLM-guided chunk planning."""

    block_id: int
    text: str
    start: int
    end: int
    block_type: str
    heading: str


@dataclass(frozen=True)
class GoogleGenAIConfig:
    """Google GenAI connection settings for LLM-guided chunk planning."""

    api_key: str
    model: str
    timeout_seconds: int


@dataclass(frozen=True)
class EvidenceCase:
    """Synthetic retrieval test derived from one evidence span."""

    case_id: str
    doc_id: str
    file_name: str
    query: str
    evidence_text: str
    start: int
    end: int
    case_type: str


@dataclass(frozen=True)
class RetrievalMetrics:
    """Aggregated retrieval metrics for one chunking method."""

    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr_at_5: float
    ndcg_at_5: float
    evidence_coverage_at_5: float
    context_efficiency_at_5: float
    retrieval_score: float


@dataclass(frozen=True)
class QualityMetrics:
    """Chunk quality metrics that do not depend on generated answers."""

    chunk_count: int
    avg_tokens: float
    median_tokens: float
    p95_tokens: float
    total_tokens: int
    redundancy_ratio: float
    good_size_ratio: float
    tiny_ratio: float
    oversized_ratio: float
    mid_word_cut_ratio: float
    mid_sentence_cut_ratio: float
    header_orphan_ratio: float
    table_without_header_ratio: float
    quality_score: float


@dataclass(frozen=True)
class MethodResult:
    """Final benchmark result for one chunking method."""

    method: str
    display_name: str
    elapsed_seconds: float
    retrieval: RetrievalMetrics
    quality: QualityMetrics
    overall_score: float


class HashingEmbeddings(Embeddings):
    """Local deterministic embeddings for semantic chunking benchmarks."""

    def __init__(self, *, n_features: int = 512) -> None:
        """Initialize a stateless hashing vectorizer."""
        self._vectorizer = HashingVectorizer(
            analyzer="char_wb",
            alternate_sign=False,
            n_features=n_features,
            ngram_range=(3, 5),
            norm="l2",
            preprocessor=normalize_for_search,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed texts into local hash vectors."""
        if not texts:
            return []
        return self._vectorizer.transform(texts).toarray().astype(float).tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed one query into a local hash vector."""
        return self.embed_documents([text])[0]


def estimate_tokens(text: str) -> int:
    """Estimate tokens using the same coarse heuristic as the HTML tool."""
    return math.ceil(len(text) / TOKEN_CHARS) if text else 0


def normalize_for_search(text: str) -> str:
    """Lowercase and remove Vietnamese accents for lexical scoring."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d")


def slugify(value: str) -> str:
    """Create a stable ASCII id fragment."""
    normalized = normalize_for_search(value)
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "document"


def clean_text(text: str) -> str:
    """Normalize markdown text while preserving source offsets as much as possible."""
    return unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")


def load_documents(corpus_dir: Path) -> list[SourceDocument]:
    """Load markdown files from the corpus directory."""
    documents: list[SourceDocument] = []
    for path in sorted(corpus_dir.glob("*.md")):
        text = clean_text(path.read_text(encoding="utf-8", errors="ignore"))
        if not text.strip():
            continue
        documents.append(
            SourceDocument(
                doc_id=slugify(path.stem),
                file_name=path.name,
                path=str(path),
                text=text,
            )
        )
    return documents


def map_parts_to_chunks(
    *,
    method: str,
    document: SourceDocument,
    parts: list[str],
) -> list[Chunk]:
    """Map text-only splitter outputs back to source offsets."""
    chunks: list[Chunk] = []
    cursor = 0
    for index, raw_part in enumerate(parts):
        part = raw_part.strip()
        if not part:
            continue
        start, end = locate_part_span(document.text, part, cursor)
        cursor = max(cursor, start + 1)
        chunks.append(
            Chunk(
                chunk_id=f"{method}:{document.doc_id}:{index}",
                method=method,
                doc_id=document.doc_id,
                file_name=document.file_name,
                text=part,
                start=start,
                end=end,
                tokens=estimate_tokens(part),
            )
        )
    return chunks


def map_parts_to_table_safe_chunks(
    *,
    method: str,
    document: SourceDocument,
    parts: list[str],
) -> list[Chunk]:
    """Map text splitter outputs back to source spans without cutting tables."""
    spans: list[tuple[int, int]] = []
    cursor = 0
    for raw_part in parts:
        part = raw_part.strip()
        if not part:
            continue
        start, end = locate_part_span(document.text, part, cursor)
        cursor = max(cursor, start + 1)
        spans.append((start, end))

    table_spans = markdown_table_spans(document.text)
    safe_spans = [
        expand_span_to_table_boundaries(start, end, table_spans) for start, end in spans
    ]
    return span_chunks(
        method=method,
        document=document,
        spans=merge_overlapping_spans(safe_spans),
    )


def markdown_table_spans(text: str) -> list[tuple[int, int]]:
    """Return source spans for contiguous Markdown table blocks."""
    line_spans: list[tuple[int, int, str]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        line_start = cursor
        cursor += len(line)
        line_spans.append((line_start, cursor, line))

    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(line_spans):
        if not is_markdown_table_line(line_spans[index][2]):
            index += 1
            continue

        table_start_index = index
        table_lines: list[str] = []
        while index < len(line_spans) and is_markdown_table_line(line_spans[index][2]):
            table_lines.append(line_spans[index][2])
            index += 1

        has_separator = any(
            is_markdown_table_separator(line) for line in table_lines[1:]
        )
        if len(table_lines) >= 2 and has_separator:
            spans.append(
                (
                    line_spans[table_start_index][0],
                    line_spans[index - 1][1],
                )
            )
    return spans


def is_markdown_table_line(line: str) -> bool:
    """Detect one Markdown pipe-table line."""
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def is_markdown_table_separator(line: str) -> bool:
    """Detect a Markdown pipe-table separator line."""
    return bool(MARKDOWN_TABLE_SEPARATOR_RE.fullmatch(line.strip()))


def expand_span_to_table_boundaries(
    start: int,
    end: int,
    table_spans: list[tuple[int, int]],
) -> tuple[int, int]:
    """Expand a chunk span if either boundary lands inside a table."""
    safe_start = start
    safe_end = end
    for table_start, table_end in table_spans:
        if table_start < safe_start < table_end:
            safe_start = table_start
        if table_start < safe_end < table_end:
            safe_end = table_end
    return safe_start, safe_end


def merge_overlapping_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge source spans after table-boundary expansion."""
    sorted_spans = sorted(spans)
    merged: list[tuple[int, int]] = []
    for start, end in sorted_spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def locate_part_span(source_text: str, part: str, cursor: int) -> tuple[int, int]:
    """Locate a possibly context-augmented chunk inside its source document."""
    start = source_text.find(part, cursor)
    if start >= 0:
        return start, start + len(part)
    start = source_text.find(part)
    if start >= 0:
        return start, start + len(part)

    anchor_lines = [
        line.strip()
        for line in part.splitlines()
        if len(line.strip()) >= 24
        and not re.fullmatch(r"\|?\s*:?-{2,}:?.*", line.strip())
    ]
    first_anchor = next(
        (line for line in anchor_lines if source_text.find(line, cursor) >= 0),
        None,
    )
    if first_anchor is None:
        first_anchor = next(
            (line for line in anchor_lines if source_text.find(line) >= 0),
            None,
        )
    if first_anchor is None:
        return cursor, min(len(source_text), cursor + len(part))

    first_position = source_text.find(first_anchor, cursor)
    if first_position < 0:
        first_position = source_text.find(first_anchor)

    last_position = first_position + len(first_anchor)
    for line in reversed(anchor_lines):
        candidate_position = source_text.find(line, first_position)
        if candidate_position >= 0:
            last_position = max(last_position, candidate_position + len(line))
            break
    return first_position, min(len(source_text), last_position)


def fixed_chunks(
    document: SourceDocument, *, size_tokens: int, overlap_tokens: int
) -> list[Chunk]:
    """Split at exact character intervals."""
    chunk_chars = size_tokens * TOKEN_CHARS
    overlap_chars = overlap_tokens * TOKEN_CHARS
    step = max(1, chunk_chars - overlap_chars)
    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(document.text):
        end = min(len(document.text), start + chunk_chars)
        text = document.text[start:end]
        chunks.append(
            Chunk(
                chunk_id=f"fixed:{document.doc_id}:{index}",
                method="fixed",
                doc_id=document.doc_id,
                file_name=document.file_name,
                text=text,
                start=start,
                end=end,
                tokens=estimate_tokens(text),
            )
        )
        if end >= len(document.text):
            break
        start += step
        index += 1
    return chunks


def recursive_chunks(
    document: SourceDocument,
    *,
    size_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Split with recursive separators matching the browser playground."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size_tokens * TOKEN_CHARS,
        chunk_overlap=overlap_tokens * TOKEN_CHARS,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
    )
    return map_parts_to_chunks(
        method="recursive",
        document=document,
        parts=splitter.split_text(document.text),
    )


def databricks_fixed_size_chunks(
    document: SourceDocument,
    *,
    size_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Split with the Databricks guide fixed-size paragraph separator."""
    splitter = CharacterTextSplitter(
        separator="\n\n",
        chunk_size=size_tokens * TOKEN_CHARS,
        chunk_overlap=overlap_tokens * TOKEN_CHARS,
        length_function=len,
    )
    return map_parts_to_chunks(
        method="databricks_fixed_size",
        document=document,
        parts=splitter.split_text(document.text),
    )


def databricks_semantic_chunks(
    document: SourceDocument,
    *,
    size_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Split with the Databricks guide logical-boundary recursive splitter."""
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=size_tokens * TOKEN_CHARS,
        chunk_overlap=overlap_tokens * TOKEN_CHARS,
        length_function=len,
    )
    return map_parts_to_chunks(
        method="databricks_semantic",
        document=document,
        parts=splitter.split_text(document.text),
    )


def databricks_recursive_code_chunks(
    document: SourceDocument,
    *,
    size_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    """Apply the Databricks guide code-aware recursive splitter."""
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON,
        chunk_size=size_tokens * TOKEN_CHARS,
        chunk_overlap=overlap_tokens * TOKEN_CHARS,
    )
    return map_parts_to_chunks(
        method="databricks_recursive_code",
        document=document,
        parts=splitter.split_text(document.text),
    )


SENTENCE_END_RE = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[]|[#*\-]|\n)|\n{2,}",
    re.M,
)


def sentence_like_spans(text: str) -> list[tuple[int, int]]:
    """Return source spans for sentence-like units."""
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in SENTENCE_END_RE.finditer(text):
        end = match.start()
        if text[cursor:end].strip():
            spans.append((cursor, end))
        cursor = match.end()
    if text[cursor:].strip():
        spans.append((cursor, len(text)))
    return spans


def analyze_text_complexity(text: str) -> float:
    """Approximate Databricks adaptive chunk complexity between 0 and 1."""
    if not text.strip():
        return 0.0

    words = re.findall(r"\b\w+\b", normalize_for_search(text))
    lexical_density = len(set(words)) / len(words) if words else 0.0
    lexical_density = min(1.0, lexical_density / 0.8)

    sentence_spans = sentence_like_spans(text)
    sentence_lengths = [
        len(text[start:end].strip()) for start, end in sentence_spans if start < end
    ]
    if sentence_lengths:
        sentence_complexity = min(1.0, statistics.fmean(sentence_lengths) / 200)
    else:
        sentence_complexity = 0.0

    return (lexical_density + sentence_complexity) / 2


def databricks_adaptive_chunks(
    document: SourceDocument,
    *,
    min_chars: int = 300,
    max_chars: int = 1000,
    min_overlap_chars: int = 30,
    max_overlap_chars: int = 150,
) -> list[Chunk]:
    """Split with Databricks adaptive chunk sizing based on text complexity."""
    sentence_spans = sentence_like_spans(document.text)
    if not sentence_spans:
        return []

    chunk_spans: list[tuple[int, int]] = []
    current_spans: list[tuple[int, int]] = []
    current_size = 0
    current_complexity = 0.5

    for sentence_start, sentence_end in sentence_spans:
        sentence_text = document.text[sentence_start:sentence_end].strip()
        sentence_length = len(sentence_text)
        if sentence_length == 0:
            continue

        sentence_complexity = analyze_text_complexity(sentence_text)
        if current_spans:
            current_complexity = (current_complexity + sentence_complexity) / 2
        else:
            current_complexity = sentence_complexity

        target_size = max_chars - current_complexity * (max_chars - min_chars)
        target_overlap = min_overlap_chars + current_complexity * (
            max_overlap_chars - min_overlap_chars
        )

        if current_size + sentence_length > target_size and current_spans:
            chunk_spans.append((current_spans[0][0], current_spans[-1][1]))
            overlap_size = 0
            overlap_spans: list[tuple[int, int]] = []
            for previous_start, previous_end in reversed(current_spans):
                previous_length = len(
                    document.text[previous_start:previous_end].strip()
                )
                if overlap_size + previous_length <= target_overlap:
                    overlap_spans.insert(0, (previous_start, previous_end))
                    overlap_size += previous_length
                else:
                    break
            current_spans = overlap_spans + [(sentence_start, sentence_end)]
            current_size = sum(
                len(document.text[start:end].strip()) for start, end in current_spans
            )
            continue

        current_spans.append((sentence_start, sentence_end))
        current_size += sentence_length

    if current_spans:
        chunk_spans.append((current_spans[0][0], current_spans[-1][1]))

    return span_chunks(
        method="databricks_adaptive",
        document=document,
        spans=chunk_spans,
    )


def sentence_chunks(
    document: SourceDocument, *, sentences_per_chunk: int
) -> list[Chunk]:
    """Group a fixed number of sentence-like units."""
    spans = sentence_like_spans(document.text)

    chunks: list[Chunk] = []
    for index in range(0, len(spans), sentences_per_chunk):
        group = spans[index : index + sentences_per_chunk]
        start = group[0][0]
        end = group[-1][1]
        text = document.text[start:end].strip()
        chunks.append(
            Chunk(
                chunk_id=f"sentence:{document.doc_id}:{len(chunks)}",
                method="sentence",
                doc_id=document.doc_id,
                file_name=document.file_name,
                text=text,
                start=start,
                end=end,
                tokens=estimate_tokens(text),
            )
        )
    return chunks


HEADING_RE = re.compile(r"^#{1,3}\s+.+$", re.M)


def markdown_chunks(document: SourceDocument) -> list[Chunk]:
    """Split on H1-H3 markdown headings."""
    matches = list(HEADING_RE.finditer(document.text))
    if not matches:
        return recursive_chunks(
            document,
            size_tokens=DEFAULT_CHUNK_SIZE_TOKENS,
            overlap_tokens=0,
        )

    spans: list[tuple[int, int]] = []
    if matches[0].start() > 0 and document.text[: matches[0].start()].strip():
        spans.append((0, matches[0].start()))
    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(document.text)
        )
        spans.append((match.start(), end))
    return span_chunks(method="markdown", document=document, spans=spans)


def langchain_markdown_header_chunks(document: SourceDocument) -> list[Chunk]:
    """Split with LangChain MarkdownHeaderTextSplitter and preserve tables."""
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS_TO_SPLIT_ON
    )
    chunks = splitter.split_text(document.text)
    return map_parts_to_table_safe_chunks(
        method="langchain_markdown_header",
        document=document,
        parts=[chunk.page_content for chunk in chunks],
    )


REGEX_SPLIT_RE = re.compile(
    r"(?im)^(?:#{1,4}\s+.+|(?:Điều|Mục|Chương|Phần)\s+[0-9IVXLC]+[^\n]*)$"
)


def regex_chunks(document: SourceDocument) -> list[Chunk]:
    """Split on markdown headings and Vietnamese legal article headings."""
    matches = list(REGEX_SPLIT_RE.finditer(document.text))
    if not matches:
        return recursive_chunks(
            document,
            size_tokens=DEFAULT_CHUNK_SIZE_TOKENS,
            overlap_tokens=0,
        )
    spans: list[tuple[int, int]] = []
    if matches[0].start() > 0 and document.text[: matches[0].start()].strip():
        spans.append((0, matches[0].start()))
    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(document.text)
        )
        spans.append((match.start(), end))
    return span_chunks(method="regex", document=document, spans=spans)


def span_chunks(
    *,
    method: str,
    document: SourceDocument,
    spans: list[tuple[int, int]],
) -> list[Chunk]:
    """Build chunks from source spans."""
    chunks: list[Chunk] = []
    for index, (start, end) in enumerate(spans):
        text = document.text[start:end].strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{method}:{document.doc_id}:{index}",
                method=method,
                doc_id=document.doc_id,
                file_name=document.file_name,
                text=text,
                start=start,
                end=end,
                tokens=estimate_tokens(text),
            )
        )
    return chunks


def document_section_spans(document: SourceDocument) -> list[tuple[int, int]]:
    """Return heading-aware document section spans."""
    matches = list(REGEX_SPLIT_RE.finditer(document.text))
    if not matches:
        return [(0, len(document.text))]

    spans: list[tuple[int, int]] = []
    if matches[0].start() > 0 and document.text[: matches[0].start()].strip():
        spans.append((0, matches[0].start()))
    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(document.text)
        )
        spans.append((match.start(), end))
    return spans


def block_terms(text: str) -> set[str]:
    """Extract normalized content terms for lightweight semantic grouping."""
    normalized = normalize_for_search(text)
    return {
        word
        for word in re.findall(r"[a-z0-9]{3,}", normalized)
        if word not in STOPWORDS and not word.isdigit()
    }


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    """Compute Jaccard similarity for two term sets."""
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def blocks_between(
    blocks: list[SourceBlock],
    *,
    start: int,
    end: int,
) -> list[SourceBlock]:
    """Select atomic blocks contained in one source span."""
    return [block for block in blocks if block.start >= start and block.end <= end]


def ranges_to_method_chunks(
    *,
    method: str,
    document: SourceDocument,
    blocks: list[SourceBlock],
    ranges: list[dict[str, int]],
) -> list[Chunk]:
    """Convert block ranges into chunks for a named method."""
    by_id = {block.block_id: block for block in blocks}
    chunks: list[Chunk] = []
    for item in ranges:
        start_block = by_id[item["start"]]
        end_block = by_id[item["end"]]
        text = document.text[start_block.start : end_block.end].strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{method}:{document.doc_id}:{len(chunks)}",
                method=method,
                doc_id=document.doc_id,
                file_name=document.file_name,
                text=text,
                start=start_block.start,
                end=end_block.end,
                tokens=estimate_tokens(text),
            )
        )
    return chunks


def semantic_boundary_ranges(
    blocks: list[SourceBlock],
    *,
    target_chars: int,
    min_chars: int,
    max_chars: int,
    similarity_threshold: float,
) -> list[dict[str, int]]:
    """Group blocks using lexical semantic shifts and size guards."""
    ranges: list[dict[str, int]] = []
    if not blocks:
        return ranges

    current_start = blocks[0].block_id
    current_end = blocks[0].block_id
    current_chars = 0
    current_terms: set[str] = set()

    for block in blocks:
        block_term_set = block_terms(block.text)
        similarity = jaccard_similarity(current_terms, block_term_set)
        heading_boundary = block.block_type == "heading" and current_chars >= min_chars
        semantic_shift = (
            current_chars >= target_chars
            and similarity <= similarity_threshold
            and block.block_type != "table"
        )
        too_large = current_chars + len(block.text) > max_chars
        if current_chars and (too_large or heading_boundary or semantic_shift):
            ranges.append({"start": current_start, "end": current_end})
            current_start = block.block_id
            current_chars = 0
            current_terms = set()

        current_end = block.block_id
        current_chars += len(block.text)
        current_terms.update(block_term_set)

        if current_chars >= max_chars:
            ranges.append({"start": current_start, "end": current_end})
            current_start = block.block_id + 1
            current_chars = 0
            current_terms = set()

    if current_chars:
        ranges.append({"start": current_start, "end": current_end})
    return ranges


def hybrid_recursive_semantic_document_chunks(document: SourceDocument) -> list[Chunk]:
    """Combine document sections, semantic block shifts, and recursive guards."""
    blocks = atomic_blocks(document)
    all_ranges: list[dict[str, int]] = []
    for start, end in document_section_spans(document):
        section_blocks = blocks_between(blocks, start=start, end=end)
        if not section_blocks:
            continue
        section_text = document.text[start:end]
        table_lines = sum(
            1 for line in section_text.splitlines() if line.strip().startswith("|")
        )
        line_count = max(1, len(section_text.splitlines()))
        table_heavy = table_lines / line_count >= 0.35
        if end - start <= 2_200:
            all_ranges.append(
                {
                    "start": section_blocks[0].block_id,
                    "end": section_blocks[-1].block_id,
                }
            )
        elif table_heavy:
            all_ranges.extend(
                policy_block_ranges(
                    section_blocks,
                    policy={
                        "target_chars": 1_700,
                        "min_chars": 700,
                        "max_chars": 3_200,
                        "heading_split_level": 3,
                    },
                )
            )
        else:
            all_ranges.extend(
                semantic_boundary_ranges(
                    section_blocks,
                    target_chars=1_400,
                    min_chars=550,
                    max_chars=2_600,
                    similarity_threshold=0.08,
                )
            )
    return ranges_to_method_chunks(
        method="hybrid_recursive_semantic",
        document=document,
        blocks=blocks,
        ranges=all_ranges,
    )


def semantic_chunks(
    document: SourceDocument,
    *,
    embeddings: Embeddings,
    size_tokens: int,
) -> list[Chunk]:
    """Split with LangChain SemanticChunker and local hash embeddings."""
    target_chars = size_tokens * TOKEN_CHARS
    number_of_chunks = max(2, math.ceil(len(document.text) / target_chars))
    try:
        splitter = SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type="interquartile",
            breakpoint_threshold_amount=1.5,
            number_of_chunks=number_of_chunks,
            sentence_split_regex=r"(?<=[.!?])\s+|\n{2,}",
            min_chunk_size=350,
        )
        parts = splitter.split_text(document.text)
    except Exception:
        parts = [
            chunk.text
            for chunk in recursive_chunks(
                document,
                size_tokens=size_tokens,
                overlap_tokens=0,
            )
        ]
    return map_parts_to_chunks(method="semantic", document=document, parts=parts)


def project_chunker_chunks(
    document: SourceDocument,
    *,
    env: dict[str, str | None],
) -> list[Chunk]:
    """Split with the project hierarchical DocumentChunker configuration."""
    chunking_strategy = project_chunking_strategy(env)
    chunker = DocumentChunker(
        child_chunk_chars=int(env.get("RAG_CHILD_CHUNK_MAX_CHARS") or "1200"),
        child_chunk_overlap=int(env.get("RAG_CHILD_CHUNK_OVERLAP") or "150"),
        chunking_strategy=chunking_strategy,
    )
    metadata = {
        "company_code": slugify(document.file_name.split("__", maxsplit=1)[0]).upper(),
        "document_id": document.doc_id,
        "document_type": "policy",
        "document_name": document.file_name,
        "product_line": "health",
        "file_name": document.file_name,
        "ingestion_version": "chunking-benchmark-2026-05-07",
    }
    document_chunks = chunker.chunk_markdown(document.text, metadata=metadata)
    return map_parts_to_chunks(
        method="project_chunker",
        document=document,
        parts=[chunk.text for chunk in document_chunks.child_chunks],
    )


def project_chunking_strategy(env: dict[str, str | None]) -> str:
    """Return the benchmark project chunker strategy with current default."""
    return env.get("RAG_CHUNKING_STRATEGY") or DEFAULT_PROJECT_CHUNKING_STRATEGY


def source_hash(text: str) -> str:
    """Return a compact content hash for cache invalidation."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_json_cache(cache_path: Path) -> dict[str, Any]:
    """Load a JSON cache file if it exists and is valid."""
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    """Persist a JSON cache file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_google_genai_llm(env: dict[str, str | None]) -> GoogleGenAIConfig | None:
    """Build the configured Google GenAI settings for LLM chunk planning."""
    if (env.get("LLM_PROVIDER") or "").lower() != "google_genai":
        return None

    api_key = env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY")
    if not api_key:
        return None
    os.environ["GOOGLE_API_KEY"] = api_key
    return GoogleGenAIConfig(
        api_key=api_key,
        model=env.get("LLM_MODEL") or "gemma-4-31b-it",
        timeout_seconds=LLM_POLICY_TIMEOUT_SECONDS,
    )


def generate_google_genai_text(config: GoogleGenAIConfig, prompt: str) -> str:
    """Generate text through the Google Generative Language REST endpoint."""
    query = urllib.parse.urlencode({"key": config.api_key})
    model_name = urllib.parse.quote(config.model, safe="")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?{query}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 384,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(
            request, timeout=config.timeout_seconds
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Google GenAI request failed with HTTP {exc.code}."
        ) from exc
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Google GenAI response did not include candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    ]
    text = "\n".join(part for part in text_parts if part)
    if not text:
        raise ValueError("Google GenAI response did not include answer text.")
    return text


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object from an LLM response."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("LLM response did not include a JSON object.")


def atomic_blocks(document: SourceDocument) -> list[SourceBlock]:
    """Split a document into source-preserving blocks for LLM planning."""
    blocks: list[SourceBlock] = []
    current_heading = document.file_name
    paragraph_re = re.compile(r"(?:.+(?:\n|$))(?:(?:[ \t]*\n)+|$)")
    for match in paragraph_re.finditer(document.text):
        raw_text = match.group(0).strip()
        if not raw_text:
            continue
        for start, end in split_large_block(document.text, match.start(), match.end()):
            block_text = document.text[start:end].strip()
            if not block_text:
                continue
            heading_match = re.match(r"^#{1,6}\s+(.+)$", block_text)
            if heading_match:
                current_heading = heading_match.group(1).strip()
            blocks.append(
                SourceBlock(
                    block_id=len(blocks),
                    text=block_text,
                    start=start,
                    end=end,
                    block_type=classify_block(block_text),
                    heading=current_heading,
                )
            )
    if not blocks and document.text.strip():
        blocks.append(
            SourceBlock(
                block_id=0,
                text=document.text.strip(),
                start=0,
                end=len(document.text),
                block_type="paragraph",
                heading=document.file_name,
            )
        )
    return blocks


def split_large_block(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split oversized source blocks on line boundaries before LLM planning."""
    if end - start <= LLM_TARGET_CHARS:
        return [(start, end)]
    spans: list[tuple[int, int]] = []
    current_start = start
    current_end = start
    for line in text[start:end].splitlines(keepends=True):
        line_end = current_end + len(line)
        if line_end - current_start > LLM_TARGET_CHARS and current_end > current_start:
            spans.append((current_start, current_end))
            current_start = current_end
        current_end = line_end
    if current_end > current_start:
        spans.append((current_start, current_end))
    return spans


def classify_block(text: str) -> str:
    """Classify one markdown block for LLM chunk planning."""
    stripped = text.strip()
    if re.match(r"^#{1,6}\s+", stripped):
        return "heading"
    if "|" in stripped:
        return "table"
    if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", stripped):
        return "list"
    return "paragraph"


def block_preview(text: str, *, limit: int = 120) -> str:
    """Return a compact one-line preview for prompt descriptors."""
    preview = re.sub(r"\s+", " ", text).strip()
    return preview[:limit]


def corpus_hash(documents: list[SourceDocument]) -> str:
    """Return a compact hash for the loaded corpus identity."""
    digest = hashlib.sha256()
    for document in documents:
        digest.update(document.doc_id.encode("utf-8"))
        digest.update(str(len(document.text)).encode("utf-8"))
        digest.update(source_hash(document.text).encode("utf-8"))
    return digest.hexdigest()[:16]


def build_llm_policy_prompt(
    *,
    documents: list[SourceDocument],
) -> str:
    """Build a compact prompt asking the LLM to choose a corpus chunking policy."""
    sampled_documents = documents[:8]
    total_type_counts: Counter[str] = Counter()
    all_block_lengths: list[int] = []
    heading_examples: list[str] = []
    for document in sampled_documents:
        blocks = atomic_blocks(document)
        type_counts = Counter(block.block_type for block in blocks)
        total_type_counts.update(type_counts)
        block_lengths = [len(block.text) for block in blocks]
        all_block_lengths.extend(block_lengths)
        heading_examples.extend(
            block_preview(block.text.lstrip("#").strip(), limit=42)
            for block in blocks
            if block.block_type == "heading"
        )
    profile = {
        "document_count": len(documents),
        "sampled_document_count": len(sampled_documents),
        "total_source_chars": sum(len(document.text) for document in documents),
        "median_document_chars": int(
            statistics.median(len(document.text) for document in documents)
        )
        if documents
        else 0,
        "sample_block_types": dict(total_type_counts),
        "sample_median_block_chars": int(statistics.median(all_block_lengths))
        if all_block_lengths
        else 0,
        "sample_max_block_chars": max(all_block_lengths) if all_block_lengths else 0,
        "heading_examples": heading_examples[:8],
    }
    return (
        "Output exactly one JSON object for a source-preserving chunking policy "
        "for Vietnamese health insurance markdown RAG. The splitter will execute "
        "the policy; do not create chunk text. Preserve table context and section "
        "headings. Keys: target_chars, min_chars, max_chars, heading_split_level. "
        "Useful ranges: target_chars 900-1800, min_chars 400-900, max_chars "
        "2200-3600, heading_split_level 1-4.\n"
        f"Corpus profile: {json.dumps(profile, ensure_ascii=False)}"
    )


def parse_llm_ranges(response_text: str) -> list[dict[str, int]]:
    """Parse JSON ranges from an LLM response."""
    data = parse_json_object(response_text)
    ranges = data.get("ranges")
    if not isinstance(ranges, list):
        raise ValueError("LLM response JSON does not contain ranges list.")
    parsed_ranges: list[dict[str, int]] = []
    for item in ranges:
        if not isinstance(item, dict):
            raise ValueError("LLM range item is not an object.")
        parsed_ranges.append({"start": int(item["start"]), "end": int(item["end"])})
    return parsed_ranges


def parse_llm_policy(response_text: str) -> dict[str, int]:
    """Parse and normalize an LLM chunking policy."""
    data = parse_json_object(response_text)

    def bounded_int(key: str, default: int, minimum: int, maximum: int) -> int:
        value = int(data.get(key, default))
        return min(maximum, max(minimum, value))

    target_chars = bounded_int("target_chars", LLM_TARGET_CHARS, 900, 1_800)
    min_chars = bounded_int("min_chars", 600, 400, 900)
    max_chars = bounded_int("max_chars", LLM_MAX_CHARS, 2_200, 3_600)
    max_chars = max(max_chars, target_chars + 400)
    heading_split_level = bounded_int("heading_split_level", 3, 1, 4)
    return {
        "target_chars": target_chars,
        "min_chars": min_chars,
        "max_chars": max_chars,
        "heading_split_level": heading_split_level,
    }


def load_or_build_llm_policy(
    *,
    documents: list[SourceDocument],
    llm_model: GoogleGenAIConfig | None,
    env: dict[str, str | None],
    cache: dict[str, Any],
    cache_path: Path,
    stats: dict[str, int],
) -> dict[str, int] | None:
    """Load or create one LLM-selected policy for the whole corpus."""
    if llm_model is None:
        return None
    cache_key = ":".join(
        [
            "llm_corpus_policy_v1",
            env.get("LLM_PROVIDER") or "",
            env.get("LLM_MODEL") or "",
            corpus_hash(documents),
        ]
    )
    cached_policy = cache.get(cache_key)
    if isinstance(cached_policy, dict):
        try:
            stats["llm_cache_hits"] += 1
            policy = parse_llm_policy(json.dumps(cached_policy))
            for key, value in policy.items():
                stats[f"llm_policy_{key}"] = value
            return policy
        except (TypeError, ValueError):
            cache.pop(cache_key, None)

    try:
        prompt = build_llm_policy_prompt(documents=documents)
        response_text = generate_google_genai_text(llm_model, prompt)
        stats["llm_calls"] += 1
        policy = parse_llm_policy(response_text)
    except Exception:
        stats["llm_policy_fallbacks"] += 1
        return None
    for key, value in policy.items():
        stats[f"llm_policy_{key}"] = value
    cache[cache_key] = policy
    save_json_cache(cache_path, cache)
    return policy


def policy_block_ranges(
    blocks: list[SourceBlock],
    *,
    policy: dict[str, int],
) -> list[dict[str, int]]:
    """Group blocks with an LLM-selected source-preserving policy."""
    ranges: list[dict[str, int]] = []
    if not blocks:
        return ranges
    current_start = blocks[0].block_id
    current_end = blocks[0].block_id
    current_chars = 0
    target_chars = policy["target_chars"]
    min_chars = policy["min_chars"]
    max_chars = policy["max_chars"]
    split_level = policy["heading_split_level"]

    for block in blocks:
        heading_match = re.match(r"^(#{1,6})\s+", block.text.strip())
        heading_level = len(heading_match.group(1)) if heading_match else 0
        heading_boundary = 0 < heading_level <= split_level
        too_large = current_chars + len(block.text) > max_chars
        target_reached = current_chars >= target_chars and block.block_type != "table"
        should_split = current_chars and (
            too_large or (heading_boundary and current_chars >= min_chars)
        )
        if target_reached and heading_boundary:
            should_split = True
        if should_split:
            ranges.append({"start": current_start, "end": current_end})
            current_start = block.block_id
            current_chars = 0
        current_end = block.block_id
        current_chars += len(block.text)
        if current_chars >= max_chars:
            ranges.append({"start": current_start, "end": current_end})
            current_start = block.block_id + 1
            current_chars = 0
    if current_chars:
        ranges.append({"start": current_start, "end": current_end})
    return ranges


def validate_ranges(
    ranges: list[dict[str, int]],
    blocks: list[SourceBlock],
) -> list[dict[str, int]]:
    """Validate LLM ranges cover exactly the provided contiguous block IDs."""
    if not blocks:
        return []
    min_id = blocks[0].block_id
    max_id = blocks[-1].block_id
    expected = min_id
    normalized: list[dict[str, int]] = []
    for item in ranges:
        start = item["start"]
        end = item["end"]
        if start != expected or end < start or end > max_id:
            raise ValueError("LLM ranges are not contiguous.")
        normalized.append({"start": start, "end": end})
        expected = end + 1
    if expected != max_id + 1:
        raise ValueError("LLM ranges did not cover all blocks.")
    return normalized


def ranges_to_chunks(
    *,
    document: SourceDocument,
    blocks: list[SourceBlock],
    ranges: list[dict[str, int]],
) -> list[Chunk]:
    """Convert block id ranges into source-preserving LLM chunks."""
    by_id = {block.block_id: block for block in blocks}
    chunks: list[Chunk] = []
    for index, item in enumerate(ranges):
        start_block = by_id[item["start"]]
        end_block = by_id[item["end"]]
        text = document.text[start_block.start : end_block.end].strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"llm:{document.doc_id}:{index}",
                method="llm",
                doc_id=document.doc_id,
                file_name=document.file_name,
                text=text,
                start=start_block.start,
                end=end_block.end,
                tokens=estimate_tokens(text),
            )
        )
    return chunks


def llm_chunks(
    document: SourceDocument,
    *,
    llm_policy: dict[str, int] | None,
    env: dict[str, str | None],
    cache: dict[str, Any],
    cache_path: Path,
    stats: dict[str, int],
) -> list[Chunk]:
    """Split a document with Google GenAI-guided block grouping."""
    blocks = atomic_blocks(document)
    cache_key = ":".join(
        [
            "llm_policy_chunking_v2",
            env.get("LLM_PROVIDER") or "",
            env.get("LLM_MODEL") or "",
            document.doc_id,
            source_hash(document.text),
        ]
    )
    cached_ranges = cache.get(cache_key)
    if cached_ranges:
        try:
            stats["llm_cache_hits"] += 1
            return ranges_to_chunks(
                document=document,
                blocks=blocks,
                ranges=validate_ranges(cached_ranges, blocks),
            )
        except ValueError:
            cache.pop(cache_key, None)

    if llm_policy is None:
        return []

    try:
        validated_ranges = validate_ranges(
            policy_block_ranges(blocks, policy=llm_policy),
            blocks,
        )
    except Exception:
        stats["llm_fallback_documents"] += 1
        return []
    cache[cache_key] = validated_ranges
    save_json_cache(cache_path, cache)
    return ranges_to_chunks(document=document, blocks=blocks, ranges=validated_ranges)


def build_chunks_by_method(
    documents: list[SourceDocument],
    *,
    env: dict[str, str | None],
    size_tokens: int,
    overlap_tokens: int,
    sentences_per_chunk: int,
    llm_cache_path: Path,
    include_llm: bool,
) -> tuple[dict[str, list[Chunk]], dict[str, int]]:
    """Run chunking methods over all documents."""
    embeddings = HashingEmbeddings()
    llm_cache = load_json_cache(llm_cache_path)
    llm_model = build_google_genai_llm(env) if include_llm else None
    llm_stats = {
        "llm_calls": 0,
        "llm_cache_hits": 0,
        "llm_fallback_documents": 0,
        "llm_policy_fallbacks": 0,
    }
    llm_policy = (
        load_or_build_llm_policy(
            documents=documents,
            llm_model=llm_model,
            env=env,
            cache=llm_cache,
            cache_path=llm_cache_path,
            stats=llm_stats,
        )
        if include_llm
        else None
    )
    chunks_by_method: dict[str, list[Chunk]] = {
        "fixed": [],
        "databricks_fixed_size": [],
        "recursive": [],
        "databricks_semantic": [],
        "databricks_recursive_code": [],
        "databricks_adaptive": [],
        "sentence": [],
        "markdown": [],
        "langchain_markdown_header": [],
        "regex": [],
        "semantic": [],
        "project_chunker": [],
        "hybrid_recursive_semantic": [],
    }
    if include_llm and llm_policy is not None:
        chunks_by_method["llm"] = []
    for document in documents:
        chunks_by_method["fixed"].extend(
            fixed_chunks(
                document,
                size_tokens=size_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
        chunks_by_method["databricks_fixed_size"].extend(
            databricks_fixed_size_chunks(
                document,
                size_tokens=size_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
        chunks_by_method["recursive"].extend(
            recursive_chunks(
                document,
                size_tokens=size_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
        chunks_by_method["databricks_semantic"].extend(
            databricks_semantic_chunks(
                document,
                size_tokens=size_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
        chunks_by_method["databricks_recursive_code"].extend(
            databricks_recursive_code_chunks(
                document,
                size_tokens=size_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
        chunks_by_method["databricks_adaptive"].extend(
            databricks_adaptive_chunks(document)
        )
        chunks_by_method["sentence"].extend(
            sentence_chunks(document, sentences_per_chunk=sentences_per_chunk)
        )
        chunks_by_method["markdown"].extend(markdown_chunks(document))
        chunks_by_method["langchain_markdown_header"].extend(
            langchain_markdown_header_chunks(document)
        )
        chunks_by_method["regex"].extend(regex_chunks(document))
        chunks_by_method["semantic"].extend(
            semantic_chunks(document, embeddings=embeddings, size_tokens=size_tokens)
        )
        chunks_by_method["project_chunker"].extend(
            project_chunker_chunks(document, env=env)
        )
        chunks_by_method["hybrid_recursive_semantic"].extend(
            hybrid_recursive_semantic_document_chunks(document)
        )
        if "llm" in chunks_by_method:
            chunks_by_method["llm"].extend(
                llm_chunks(
                    document,
                    llm_policy=llm_policy,
                    env=env,
                    cache=llm_cache,
                    cache_path=llm_cache_path,
                    stats=llm_stats,
                )
            )
    return chunks_by_method, llm_stats


def evidence_spans_for_document(document: SourceDocument) -> list[tuple[int, int, str]]:
    """Create independent evidence spans from markdown paragraphs and table blocks."""
    spans: list[tuple[int, int, str]] = []
    heading_matches = list(re.finditer(r"^#{1,4}\s+(.+)$", document.text, re.M))
    sections: list[tuple[int, int, str]] = []
    if not heading_matches:
        sections.append((0, len(document.text), document.file_name))
    else:
        if heading_matches[0].start() > 0:
            sections.append((0, heading_matches[0].start(), document.file_name))
        for index, match in enumerate(heading_matches):
            end = (
                heading_matches[index + 1].start()
                if index + 1 < len(heading_matches)
                else len(document.text)
            )
            sections.append((match.start(), end, match.group(1).strip()))

    for section_start, section_end, heading in sections:
        section_text = document.text[section_start:section_end]
        cursor = 0
        blocks = list(re.finditer(r"(?:.+(?:\n|$))(?:(?:[ \t]*\n)+|$)", section_text))
        if not blocks:
            continue
        for block_match in blocks:
            block = block_match.group(0).strip()
            cursor = block_match.end()
            if len(block) < 180:
                continue
            block_start = section_start + block_match.start()
            block_end = section_start + block_match.end()
            for start, end in split_evidence_block(
                document.text, block_start, block_end
            ):
                spans.append((start, end, heading))
        if cursor < len(section_text):
            start = section_start + cursor
            end = section_end
            if end - start >= 180:
                spans.append((start, end, heading))
    return spans


def split_evidence_block(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split large evidence blocks on line boundaries."""
    max_chars = 1_400
    min_chars = 220
    if end - start <= max_chars:
        return [(start, end)]

    spans: list[tuple[int, int]] = []
    lines = text[start:end].splitlines(keepends=True)
    current_start = start
    current_end = start
    for line in lines:
        line_end = current_end + len(line)
        if (
            line_end - current_start > max_chars
            and current_end - current_start >= min_chars
        ):
            spans.append((current_start, current_end))
            current_start = current_end
        current_end = line_end
    if current_end - current_start >= min_chars:
        spans.append((current_start, current_end))
    return spans


def classify_case(text: str) -> str:
    """Classify an evidence span into a coarse insurance query type."""
    normalized = normalize_for_search(text)
    for case_type, hints in QUESTION_HINTS.items():
        if any(hint in normalized for hint in hints):
            return case_type
    if "|" in text:
        return "table"
    return "general"


def extract_keywords(text: str, *, limit: int = 10) -> list[str]:
    """Extract search terms from one evidence span."""
    normalized = normalize_for_search(text)
    words = re.findall(r"[a-z0-9]{3,}", normalized)
    counter: Counter[str] = Counter()
    for word in words:
        if word in STOPWORDS or word.isdigit():
            continue
        counter[word] += 1
    return [word for word, _count in counter.most_common(limit)]


def build_evidence_cases(
    documents: list[SourceDocument],
    *,
    max_cases: int,
) -> list[EvidenceCase]:
    """Generate synthetic benchmark cases from source evidence spans."""
    candidates: list[EvidenceCase] = []
    for document in documents:
        for index, (start, end, heading) in enumerate(
            evidence_spans_for_document(document)
        ):
            evidence_text = document.text[start:end].strip()
            keywords = extract_keywords(f"{heading}\n{evidence_text}")
            if len(keywords) < 4:
                continue
            case_type = classify_case(f"{heading}\n{evidence_text}")
            query_terms = " ".join(keywords[:10])
            query = f"{heading} {query_terms}".strip()
            candidates.append(
                EvidenceCase(
                    case_id=f"{document.doc_id}:{index}",
                    doc_id=document.doc_id,
                    file_name=document.file_name,
                    query=query,
                    evidence_text=evidence_text,
                    start=start,
                    end=end,
                    case_type=case_type,
                )
            )

    if len(candidates) <= max_cases:
        return candidates

    grouped: dict[str, list[EvidenceCase]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.doc_id].append(candidate)

    selected: list[EvidenceCase] = []
    per_doc = max(1, max_cases // max(1, len(grouped)))
    for doc_id in sorted(grouped):
        doc_cases = grouped[doc_id]
        step = max(1, len(doc_cases) // per_doc)
        selected.extend(doc_cases[::step][:per_doc])

    if len(selected) < max_cases:
        seen = {case.case_id for case in selected}
        for candidate in candidates:
            if candidate.case_id not in seen:
                selected.append(candidate)
                seen.add(candidate.case_id)
            if len(selected) >= max_cases:
                break
    return selected[:max_cases]


def overlap_chars(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Return the number of overlapping source characters between two spans."""
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def chunk_relevance(chunk: Chunk, case: EvidenceCase) -> float:
    """Return graded relevance of a chunk to a synthetic evidence case."""
    if chunk.doc_id != case.doc_id:
        return 0.0
    overlap = overlap_chars(chunk.start, chunk.end, case.start, case.end)
    if overlap <= 0:
        return 0.0
    evidence_len = max(1, case.end - case.start)
    return min(1.0, overlap / evidence_len)


def evaluate_retrieval(
    chunks: list[Chunk], cases: list[EvidenceCase]
) -> RetrievalMetrics:
    """Evaluate retrieval over synthetic cases with TF-IDF ranking."""
    chunk_texts = [chunk.text for chunk in chunks]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_features=120_000,
        min_df=1,
        sublinear_tf=True,
        preprocessor=normalize_for_search,
        token_pattern=r"(?u)\b\w\w+\b",
    )
    chunk_matrix = vectorizer.fit_transform(chunk_texts)
    query_matrix = vectorizer.transform([case.query for case in cases])

    hit_1 = 0.0
    hit_3 = 0.0
    hit_5 = 0.0
    mrr_5 = 0.0
    ndcg_5 = 0.0
    coverage_5 = 0.0
    efficiency_5 = 0.0

    for case_index, case in enumerate(cases):
        scores = (query_matrix[case_index] @ chunk_matrix.T).toarray().ravel()
        if scores.size == 0:
            continue
        top_count = min(RETRIEVAL_TOP_K, scores.size)
        top_indexes = np.argpartition(scores, -top_count)[-top_count:]
        top_indexes = top_indexes[np.argsort(scores[top_indexes])[::-1]]
        relevances = [chunk_relevance(chunks[index], case) for index in top_indexes]
        binary_relevances = [
            1.0 if relevance >= 0.2 else 0.0 for relevance in relevances
        ]

        hit_1 += binary_relevances[0]
        hit_3 += 1.0 if any(binary_relevances[:3]) else 0.0
        hit_5 += 1.0 if any(binary_relevances[:5]) else 0.0
        for rank, relevance in enumerate(binary_relevances, start=1):
            if relevance:
                mrr_5 += 1.0 / rank
                break

        dcg = sum(
            relevance / math.log2(rank + 1)
            for rank, relevance in enumerate(relevances[:5], start=1)
        )
        ideal_relevances = sorted(relevances, reverse=True)
        ideal_dcg = sum(
            relevance / math.log2(rank + 1)
            for rank, relevance in enumerate(ideal_relevances[:5], start=1)
        )
        ndcg_5 += dcg / ideal_dcg if ideal_dcg > 0 else 0.0
        coverage_5 += max(relevances[:5], default=0.0)

        retrieved_chars = sum(len(chunks[index].text) for index in top_indexes[:5])
        best_overlap = max(
            overlap_chars(chunks[index].start, chunks[index].end, case.start, case.end)
            if chunks[index].doc_id == case.doc_id
            else 0
            for index in top_indexes[:5]
        )
        efficiency_5 += best_overlap / retrieved_chars if retrieved_chars else 0.0

    count = max(1, len(cases))
    hit_at_1 = hit_1 / count
    hit_at_3 = hit_3 / count
    hit_at_5 = hit_5 / count
    mrr_at_5 = mrr_5 / count
    ndcg_at_5_value = ndcg_5 / count
    coverage_at_5 = coverage_5 / count
    efficiency_at_5 = efficiency_5 / count
    retrieval_score = 100.0 * (
        0.30 * hit_at_1
        + 0.20 * hit_at_3
        + 0.15 * hit_at_5
        + 0.20 * mrr_at_5
        + 0.15 * coverage_at_5
    )
    return RetrievalMetrics(
        hit_at_1=hit_at_1,
        hit_at_3=hit_at_3,
        hit_at_5=hit_at_5,
        mrr_at_5=mrr_at_5,
        ndcg_at_5=ndcg_at_5_value,
        evidence_coverage_at_5=coverage_at_5,
        context_efficiency_at_5=efficiency_at_5,
        retrieval_score=retrieval_score,
    )


def has_table_header(text: str) -> bool:
    """Detect whether a table chunk contains markdown header and separator rows."""
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    return len(lines) >= 2 and bool(re.fullmatch(r"\|?\s*:?-{2,}:?.*", lines[1]))


def evaluate_quality(
    chunks: list[Chunk], documents: list[SourceDocument]
) -> QualityMetrics:
    """Evaluate chunk shape, boundaries, table handling, and redundancy."""
    doc_lengths = {document.doc_id: len(document.text) for document in documents}
    total_source_chars = sum(doc_lengths.values())
    token_values = [chunk.tokens for chunk in chunks]
    tiny = 0
    oversized = 0
    good_size = 0
    mid_word = 0
    mid_sentence = 0
    header_orphan = 0
    table_without_header = 0
    doc_text_by_id = {document.doc_id: document.text for document in documents}

    for chunk in chunks:
        if chunk.tokens < 50:
            tiny += 1
        if chunk.tokens > 800:
            oversized += 1
        if 100 <= chunk.tokens <= 500:
            good_size += 1

        source_text = doc_text_by_id[chunk.doc_id]
        if chunk.end < len(source_text):
            before = source_text[chunk.end - 1] if chunk.end > 0 else " "
            after = source_text[chunk.end] if chunk.end < len(source_text) else " "
            if before not in {" ", "\n", "\t"} and after not in {" ", "\n", "\t"}:
                mid_word += 1
            last_char = chunk.text.rstrip()[-1:] if chunk.text.strip() else ""
            if last_char and last_char not in {".", "!", "?", "\n", "|"}:
                mid_sentence += 1

        heading_match = re.search(r"^#{1,6}\s+.+$", chunk.text, re.M)
        if heading_match:
            heading_end = heading_match.end()
            if len(chunk.text[heading_end:].strip()) < 40:
                header_orphan += 1

        if "|" in chunk.text and not has_table_header(chunk.text):
            table_lines = [
                line for line in chunk.text.splitlines() if line.strip().startswith("|")
            ]
            if len(table_lines) >= 2:
                table_without_header += 1

    count = max(1, len(chunks))
    redundancy_ratio = sum(len(chunk.text) for chunk in chunks) / max(
        1, total_source_chars
    )
    tiny_ratio = tiny / count
    oversized_ratio = oversized / count
    good_size_ratio = good_size / count
    mid_word_ratio = mid_word / count
    mid_sentence_ratio = mid_sentence / count
    header_orphan_ratio = header_orphan / count
    table_without_header_ratio = table_without_header / count
    redundancy_penalty = max(0.0, redundancy_ratio - 1.15) * 18.0
    quality_score = max(
        0.0,
        100.0
        - 18.0 * tiny_ratio
        - 18.0 * oversized_ratio
        - 22.0 * mid_word_ratio
        - 10.0 * mid_sentence_ratio
        - 12.0 * header_orphan_ratio
        - 12.0 * table_without_header_ratio
        - redundancy_penalty,
    )
    return QualityMetrics(
        chunk_count=len(chunks),
        avg_tokens=statistics.fmean(token_values) if token_values else 0.0,
        median_tokens=statistics.median(token_values) if token_values else 0.0,
        p95_tokens=float(np.percentile(token_values, 95)) if token_values else 0.0,
        total_tokens=sum(token_values),
        redundancy_ratio=redundancy_ratio,
        good_size_ratio=good_size_ratio,
        tiny_ratio=tiny_ratio,
        oversized_ratio=oversized_ratio,
        mid_word_cut_ratio=mid_word_ratio,
        mid_sentence_cut_ratio=mid_sentence_ratio,
        header_orphan_ratio=header_orphan_ratio,
        table_without_header_ratio=table_without_header_ratio,
        quality_score=quality_score,
    )


DISPLAY_NAMES = {
    "fixed": "Fixed-size",
    "databricks_fixed_size": "Databricks Fixed-size",
    "recursive": "Recursive",
    "databricks_semantic": "Databricks Semantic",
    "databricks_recursive_code": "Databricks Code Recursive",
    "databricks_adaptive": "Databricks Adaptive",
    "sentence": "Sentence",
    "markdown": "Markdown",
    "langchain_markdown_header": "LangChain MarkdownHeader",
    "regex": "Regex",
    "semantic": "Semantic",
    "project_chunker": "Project Chunker",
    "hybrid_recursive_semantic": "Hybrid Recursive+Semantic",
    "llm": "LLM Chunking",
}


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    """Run the full chunking benchmark."""
    env = dict(dotenv_values(args.env_path))
    documents = load_documents(args.corpus_dir)
    if args.max_documents:
        documents = documents[: args.max_documents]
    cases = build_evidence_cases(documents, max_cases=args.max_cases)
    chunks_by_method, llm_stats = build_chunks_by_method(
        documents,
        env=env,
        size_tokens=args.chunk_size_tokens,
        overlap_tokens=args.overlap_tokens,
        sentences_per_chunk=args.sentences_per_chunk,
        llm_cache_path=args.llm_cache_path,
        include_llm=not args.skip_llm,
    )

    results: list[MethodResult] = []
    for method, chunks in chunks_by_method.items():
        started = time.perf_counter()
        retrieval = evaluate_retrieval(chunks, cases)
        quality = evaluate_quality(chunks, documents)
        elapsed = time.perf_counter() - started
        overall_score = 0.78 * retrieval.retrieval_score + 0.22 * quality.quality_score
        results.append(
            MethodResult(
                method=method,
                display_name=DISPLAY_NAMES[method],
                elapsed_seconds=elapsed,
                retrieval=retrieval,
                quality=quality,
                overall_score=overall_score,
            )
        )

    results.sort(key=lambda result: result.overall_score, reverse=True)
    llm_chunking_enabled = "llm" in chunks_by_method
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_dir": "<private_health_markdown_corpus>",
        "env_path": "<redacted_env_path>",
        "document_count": len(documents),
        "total_source_chars": sum(len(document.text) for document in documents),
        "synthetic_case_count": len(cases),
        "case_type_counts": dict(Counter(case.case_type for case in cases)),
        "settings": {
            "chunk_size_tokens": args.chunk_size_tokens,
            "overlap_tokens": args.overlap_tokens,
            "sentences_per_chunk": args.sentences_per_chunk,
            "max_cases": args.max_cases,
            "max_documents": args.max_documents,
            "semantic_embedding_provider": env.get(
                "SEMANTIC_CHUNKING_EMBEDDING_PROVIDER"
            ),
            "semantic_embedding_model": env.get("SEMANTIC_CHUNKING_EMBEDDING_MODEL"),
            "llm_chunking_enabled": llm_chunking_enabled,
            "llm_provider": env.get("LLM_PROVIDER"),
            "llm_model": env.get("LLM_MODEL"),
            "llm_cache_path": str(args.llm_cache_path),
            "llm_chunking_mode": (
                "google_genai_policy_guided_source_preserving_block_grouping"
                if llm_chunking_enabled
                else "not_included_without_configured_policy"
            ),
            "llm_stats": llm_stats,
            "rag_chunking_strategy": project_chunking_strategy(env),
            "rag_child_chunk_max_chars": env.get("RAG_CHILD_CHUNK_MAX_CHARS"),
            "rag_child_chunk_overlap": env.get("RAG_CHILD_CHUNK_OVERLAP"),
            "project_chunker_benchmark_mode": (
                "table_aware_document_chunker_without_external_embedding_calls"
            ),
        },
        "results": [method_result_to_dict(result) for result in results],
    }


def method_result_to_dict(result: MethodResult) -> dict[str, Any]:
    """Convert a method result to JSON-serializable dictionaries."""
    data = asdict(result)
    return round_floats(data)


def round_floats(value: Any) -> Any:
    """Round nested float values for stable reports."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item) for item in value]
    return value


def write_reports(report: dict[str, Any], output_dir: Path) -> None:
    """Write JSON, CSV, and Markdown benchmark reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "health_chunking_benchmark.json"
    csv_path = output_dir / "health_chunking_benchmark.csv"
    md_path = output_dir / "health_chunking_benchmark.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    rows = [
        "rank,method,overall_score,retrieval_score,quality_score,hit_at_1,"
        "hit_at_3,hit_at_5,mrr_at_5,ndcg_at_5,evidence_coverage_at_5,"
        "context_efficiency_at_5,chunk_count,avg_tokens,median_tokens,p95_tokens,"
        "redundancy_ratio,good_size_ratio,tiny_ratio,oversized_ratio,"
        "mid_word_cut_ratio,mid_sentence_cut_ratio,header_orphan_ratio,"
        "table_without_header_ratio"
    ]
    for rank, result in enumerate(report["results"], start=1):
        retrieval = result["retrieval"]
        quality = result["quality"]
        rows.append(
            ",".join(
                str(value)
                for value in [
                    rank,
                    result["method"],
                    result["overall_score"],
                    retrieval["retrieval_score"],
                    quality["quality_score"],
                    retrieval["hit_at_1"],
                    retrieval["hit_at_3"],
                    retrieval["hit_at_5"],
                    retrieval["mrr_at_5"],
                    retrieval["ndcg_at_5"],
                    retrieval["evidence_coverage_at_5"],
                    retrieval["context_efficiency_at_5"],
                    quality["chunk_count"],
                    quality["avg_tokens"],
                    quality["median_tokens"],
                    quality["p95_tokens"],
                    quality["redundancy_ratio"],
                    quality["good_size_ratio"],
                    quality["tiny_ratio"],
                    quality["oversized_ratio"],
                    quality["mid_word_cut_ratio"],
                    quality["mid_sentence_cut_ratio"],
                    quality["header_orphan_ratio"],
                    quality["table_without_header_ratio"],
                ]
            )
        )
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a concise human-readable benchmark report."""
    lines = [
        "# Health Insurance Chunking Benchmark",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Documents: `{report['document_count']}`",
        f"- Source characters: `{report['total_source_chars']}`",
        f"- Synthetic retrieval cases: `{report['synthetic_case_count']}`",
        f"- Case mix: `{report['case_type_counts']}`",
        "",
        (
            "| Rank | Method | Overall | Retrieval | Quality | Hit@1 | Hit@3 | "
            "MRR@5 | Coverage@5 | Chunks | Avg tok | Redundancy |"
        ),
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, result in enumerate(report["results"], start=1):
        retrieval = result["retrieval"]
        quality = result["quality"]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    result["display_name"],
                    f"{result['overall_score']:.2f}",
                    f"{retrieval['retrieval_score']:.2f}",
                    f"{quality['quality_score']:.2f}",
                    f"{retrieval['hit_at_1']:.3f}",
                    f"{retrieval['hit_at_3']:.3f}",
                    f"{retrieval['mrr_at_5']:.3f}",
                    f"{retrieval['evidence_coverage_at_5']:.3f}",
                    str(quality["chunk_count"]),
                    f"{quality['avg_tokens']:.1f}",
                    f"{quality['redundancy_ratio']:.3f}",
                ]
            )
            + " |"
        )
    best = report["results"][0]
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                f"Best overall method: **{best['display_name']}** "
                f"({best['overall_score']:.2f}/100)."
            ),
            "",
            "Scores weight retrieval at 78% and chunk quality at 22%. "
            "Retrieval cases are generated from the private markdown corpus without "
            "manual labeling or database writes.",
            "",
        ]
    )
    return "\n".join(lines)


def print_summary(report: dict[str, Any]) -> None:
    """Print a terminal summary table."""
    print("Health insurance chunking benchmark")
    print(f"Documents: {report['document_count']}")
    print(f"Synthetic cases: {report['synthetic_case_count']}")
    if report["settings"].get("llm_chunking_enabled"):
        stats = report["settings"].get("llm_stats", {})
        print(
            "LLM chunking: "
            f"{report['settings'].get('llm_provider')}/"
            f"{report['settings'].get('llm_model')} "
            f"calls={stats.get('llm_calls', 0)} "
            f"cache_hits={stats.get('llm_cache_hits', 0)} "
            f"fallback_documents={stats.get('llm_fallback_documents', 0)} "
            f"policy_fallbacks={stats.get('llm_policy_fallbacks', 0)}"
        )
    print()
    print(
        f"{'Rank':>4} {'Method':<12} {'Overall':>8} {'Retr':>8} {'Qual':>8} "
        f"{'Hit@1':>7} {'Hit@3':>7} {'MRR@5':>7} {'Chunks':>8}"
    )
    for rank, result in enumerate(report["results"], start=1):
        retrieval = result["retrieval"]
        quality = result["quality"]
        print(
            f"{rank:>4} {result['display_name']:<12} "
            f"{result['overall_score']:>8.2f} "
            f"{retrieval['retrieval_score']:>8.2f} "
            f"{quality['quality_score']:>8.2f} "
            f"{retrieval['hit_at_1']:>7.3f} "
            f"{retrieval['hit_at_3']:>7.3f} "
            f"{retrieval['mrr_at_5']:>7.3f} "
            f"{quality['chunk_count']:>8}"
        )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark health markdown chunking methods, optionally "
            "including Google GenAI-guided LLM chunking."
        )
    )
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--env-path", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--chunk-size-tokens", type=int, default=DEFAULT_CHUNK_SIZE_TOKENS
    )
    parser.add_argument("--overlap-tokens", type=int, default=DEFAULT_OVERLAP_TOKENS)
    parser.add_argument(
        "--sentences-per-chunk",
        type=int,
        default=DEFAULT_SENTENCES_PER_CHUNK,
    )
    parser.add_argument("--max-cases", type=int, default=DEFAULT_MAX_CASES)
    parser.add_argument(
        "--max-documents",
        type=int,
        default=0,
        help="Limit documents for smoke tests; 0 means all documents.",
    )
    parser.add_argument(
        "--llm-cache-path",
        type=Path,
        default=DEFAULT_LLM_CHUNK_CACHE_PATH,
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip Google GenAI-guided LLM chunking.",
    )
    return parser.parse_args()


def main() -> None:
    """Run benchmark and write reports."""
    args = parse_args()
    started = time.perf_counter()
    report = run_benchmark(args)
    report["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    write_reports(report, args.output_dir)
    print_summary(report)
    print()
    print(f"Reports written to: {args.output_dir}")


if __name__ == "__main__":
    main()
