import math
import re
import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from src.services.observability import add_current_service_metadata, service_observe

ChunkingStrategy = Literal["recursive", "hybrid_semantic"]
SemanticBreakpointType = Literal[
    "percentile",
    "standard_deviation",
    "interquartile",
    "gradient",
]

REQUIRED_QDRANT_PAYLOAD_FIELDS = (
    "company_code",
    "document_id",
    "document_type",
    "document_name",
    "product_line",
    "plan_code",
    "section_type",
    "page_number",
    "chunk_index",
    "parent_section_id",
    "file_name",
    "source_table_id",
    "effective_date",
    "content_hash",
    "ingestion_version",
)


@dataclass(frozen=True)
class ParentSection:
    """A normalized markdown section used for parent expansion."""

    section_id: str
    heading: str
    level: int
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ChildChunk:
    """A searchable child chunk with Qdrant-ready payload metadata."""

    chunk_id: str
    parent_section_id: str
    text: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ChunkedDocument:
    """Parent sections and child chunks produced from one markdown document."""

    parent_sections: list[ParentSection]
    child_chunks: list[ChildChunk]


@dataclass
class ChunkingMetrics:
    """Aggregated telemetry for one document chunking operation."""

    empty_section_count: int = 0
    recursive_section_count: int = 0
    semantic_section_count: int = 0
    table_heavy_section_count: int = 0
    fallback_chunk_count: int = 0


class DocumentChunker:
    """Parse markdown into parent sections and deterministic child chunks."""

    def __init__(
        self,
        child_chunk_chars: int = 1200,
        child_chunk_overlap: int = 150,
        chunking_strategy: ChunkingStrategy = "recursive",
        semantic_embedding_provider: Embeddings | None = None,
        semantic_target_chars: int = 1400,
        semantic_max_chars: int = 3500,
        semantic_min_chars: int = 350,
        semantic_breakpoint_type: SemanticBreakpointType = "interquartile",
        semantic_breakpoint_amount: float = 1.5,
        table_line_ratio_threshold: float = 0.55,
        table_chunk_chars: int = 3500,
    ) -> None:
        """Initialize the chunker.

        Args:
            child_chunk_chars: Maximum child chunk size in characters.
            child_chunk_overlap: Character overlap between adjacent child chunks.
            chunking_strategy: Splitting strategy for child chunks.
            semantic_embedding_provider: Embeddings used by semantic chunking.
            semantic_target_chars: Target semantic chunk size used to estimate
                the number of semantic chunks for long sections.
            semantic_max_chars: Maximum accepted semantic chunk size before
                falling back to recursive Markdown splitting.
            semantic_min_chars: Minimum semantic chunk size passed to LangChain.
            semantic_breakpoint_type: LangChain semantic breakpoint strategy.
            semantic_breakpoint_amount: Threshold amount for semantic breakpoints.
            table_line_ratio_threshold: Ratio of Markdown table lines that marks
                a section as table-heavy.
            table_chunk_chars: Maximum table chunk size in characters.
        """
        if child_chunk_chars <= 0:
            raise ValueError("child_chunk_chars must be positive.")
        if child_chunk_overlap < 0:
            raise ValueError("child_chunk_overlap cannot be negative.")
        if child_chunk_overlap >= child_chunk_chars:
            raise ValueError("child_chunk_overlap must be smaller than chunk size.")
        if chunking_strategy not in {"recursive", "hybrid_semantic"}:
            raise ValueError(
                "chunking_strategy must be 'recursive' or 'hybrid_semantic'."
            )
        if semantic_target_chars <= 0:
            raise ValueError("semantic_target_chars must be positive.")
        if semantic_max_chars <= 0:
            raise ValueError("semantic_max_chars must be positive.")
        if semantic_min_chars <= 0:
            raise ValueError("semantic_min_chars must be positive.")
        if not 0 < table_line_ratio_threshold <= 1:
            raise ValueError("table_line_ratio_threshold must be between 0 and 1.")
        if table_chunk_chars <= 0:
            raise ValueError("table_chunk_chars must be positive.")

        self.child_chunk_chars = child_chunk_chars
        self.child_chunk_overlap = child_chunk_overlap
        self.chunking_strategy = chunking_strategy
        self.semantic_embedding_provider = semantic_embedding_provider
        self.semantic_target_chars = semantic_target_chars
        self.semantic_max_chars = semantic_max_chars
        self.semantic_min_chars = semantic_min_chars
        self.semantic_breakpoint_type = semantic_breakpoint_type
        self.semantic_breakpoint_amount = semantic_breakpoint_amount
        self.table_line_ratio_threshold = table_line_ratio_threshold
        self.table_chunk_chars = table_chunk_chars
        self._recursive_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.MARKDOWN,
            chunk_size=child_chunk_chars,
            chunk_overlap=child_chunk_overlap,
        )

    @service_observe(
        name="service.document_chunker.chunk_markdown", component="document_chunker"
    )
    def chunk_markdown(
        self,
        markdown_text: str,
        metadata: dict[str, Any],
    ) -> ChunkedDocument:
        """Chunk markdown text into parent sections and child chunks.

        Args:
            markdown_text: Source markdown content.
            metadata: Document-level payload metadata.

        Returns:
            Parsed parent sections and Qdrant-ready child chunks.
        """
        normalized_text = unicodedata.normalize("NFC", markdown_text)
        parent_sections = self._parse_parent_sections(normalized_text, metadata)
        chunking_metrics = ChunkingMetrics()
        child_chunks: list[ChildChunk] = []

        for parent_section in parent_sections:
            for chunk_index, child_text in enumerate(
                self._split_text(parent_section.text, chunking_metrics)
            ):
                payload = self._build_payload(
                    parent_section=parent_section,
                    child_text=child_text,
                    chunk_index=chunk_index,
                )
                self.validate_payload(payload)
                chunk_id = (
                    f"{metadata['document_id']}:"
                    f"{self._slugify(parent_section.heading)}:{chunk_index}"
                )
                child_chunks.append(
                    ChildChunk(
                        chunk_id=chunk_id,
                        parent_section_id=parent_section.section_id,
                        text=child_text,
                        payload=payload,
                    )
                )

        chunked_document = ChunkedDocument(
            parent_sections=parent_sections,
            child_chunks=child_chunks,
        )
        self._update_langfuse_chunking_summary(
            chunked_document=chunked_document,
            chunking_metrics=chunking_metrics,
        )
        return chunked_document

    @classmethod
    @service_observe(
        name="service.document_chunker.validate_payload",
        component="document_chunker",
    )
    def validate_payload(cls, payload: dict[str, Any]) -> None:
        """Validate required Qdrant citation payload fields."""
        missing_fields = [
            field for field in REQUIRED_QDRANT_PAYLOAD_FIELDS if field not in payload
        ]
        if missing_fields:
            raise ValueError(
                "Missing Qdrant payload field(s): " + ", ".join(missing_fields)
            )

    def _parse_parent_sections(
        self,
        markdown_text: str,
        metadata: dict[str, Any],
    ) -> list[ParentSection]:
        sections: list[ParentSection] = []
        heading_matches = list(
            re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown_text, re.M)
        )

        if not heading_matches:
            section_text = markdown_text.strip()
            return [
                ParentSection(
                    section_id=f"{metadata['document_id']}:document",
                    heading=str(metadata["document_name"]),
                    level=1,
                    text=section_text,
                    metadata=metadata,
                )
            ]

        for index, match in enumerate(heading_matches):
            next_start = (
                heading_matches[index + 1].start()
                if index + 1 < len(heading_matches)
                else len(markdown_text)
            )
            raw_section_text = markdown_text[match.start() : next_start].strip()
            heading = match.group(2).strip()
            sections.append(
                ParentSection(
                    section_id=(
                        f"{metadata['document_id']}:{self._slugify(heading)}:{index}"
                    ),
                    heading=heading,
                    level=len(match.group(1)),
                    text=raw_section_text,
                    metadata=metadata,
                )
            )

        return sections

    def _split_text(
        self,
        text: str,
        chunking_metrics: ChunkingMetrics | None = None,
    ) -> list[str]:
        normalized_text = text.strip()
        if not normalized_text:
            if chunking_metrics is not None:
                chunking_metrics.empty_section_count += 1
            return []
        if len(normalized_text) <= self.child_chunk_chars:
            if chunking_metrics is not None:
                chunking_metrics.recursive_section_count += 1
            return [normalized_text]

        if self._is_table_heavy(normalized_text):
            if chunking_metrics is not None:
                chunking_metrics.table_heavy_section_count += 1
            return self._split_table_heavy_text(normalized_text)
        if self._uses_semantic_chunking():
            if chunking_metrics is not None:
                chunking_metrics.semantic_section_count += 1
            return self._split_semantically(normalized_text, chunking_metrics)
        if chunking_metrics is not None:
            chunking_metrics.recursive_section_count += 1
        return self._split_recursively(normalized_text)

    def _uses_semantic_chunking(self) -> bool:
        return (
            self.chunking_strategy == "hybrid_semantic"
            and self.semantic_embedding_provider is not None
        )

    def _split_semantically(
        self,
        text: str,
        chunking_metrics: ChunkingMetrics | None = None,
    ) -> list[str]:
        number_of_chunks = None
        if len(text) > self.semantic_target_chars:
            number_of_chunks = max(2, math.ceil(len(text) / self.semantic_target_chars))

        semantic_splitter = SemanticChunker(
            embeddings=self.semantic_embedding_provider,
            breakpoint_threshold_type=self.semantic_breakpoint_type,
            breakpoint_threshold_amount=self.semantic_breakpoint_amount,
            number_of_chunks=number_of_chunks,
            sentence_split_regex=r"(?<=[.!?])\s+|\n{2,}",
            min_chunk_size=self.semantic_min_chars,
        )
        semantic_chunks = self._clean_chunks(semantic_splitter.split_text(text))
        if not semantic_chunks:
            recursive_chunks = self._split_recursively(text)
            if chunking_metrics is not None:
                chunking_metrics.fallback_chunk_count += len(recursive_chunks)
            return recursive_chunks

        guarded_chunks: list[str] = []
        for semantic_chunk in semantic_chunks:
            if len(semantic_chunk) <= self.semantic_max_chars:
                guarded_chunks.append(semantic_chunk)
            else:
                recursive_chunks = self._split_recursively(semantic_chunk)
                if chunking_metrics is not None:
                    chunking_metrics.fallback_chunk_count += len(recursive_chunks)
                guarded_chunks.extend(recursive_chunks)
        return self._clean_chunks(guarded_chunks)

    def _update_langfuse_chunking_summary(
        self,
        *,
        chunked_document: ChunkedDocument,
        chunking_metrics: ChunkingMetrics,
    ) -> None:
        chunk_lengths = [
            len(child_chunk.text) for child_chunk in chunked_document.child_chunks
        ]
        chunking_metadata = {
            "strategy": self.chunking_strategy,
            "semantic_enabled": self._uses_semantic_chunking(),
            "parent_section_count": len(chunked_document.parent_sections),
            "child_chunk_count": len(chunked_document.child_chunks),
            "empty_section_count": chunking_metrics.empty_section_count,
            "recursive_section_count": chunking_metrics.recursive_section_count,
            "semantic_section_count": chunking_metrics.semantic_section_count,
            "table_heavy_section_count": chunking_metrics.table_heavy_section_count,
            "fallback_chunk_count": chunking_metrics.fallback_chunk_count,
            "chunk_length_min": min(chunk_lengths) if chunk_lengths else 0,
            "chunk_length_max": max(chunk_lengths) if chunk_lengths else 0,
            "chunk_length_avg": (
                round(sum(chunk_lengths) / len(chunk_lengths), 2)
                if chunk_lengths
                else 0
            ),
            "table_line_ratio_threshold": self.table_line_ratio_threshold,
            "table_chunk_chars": self.table_chunk_chars,
            "semantic_target_chars": self.semantic_target_chars,
            "semantic_max_chars": self.semantic_max_chars,
        }
        add_current_service_metadata({"chunking": chunking_metadata})

    def _split_recursively(self, text: str) -> list[str]:
        return self._clean_chunks(self._recursive_splitter.split_text(text))

    def _is_table_heavy(self, text: str) -> bool:
        nonblank_lines = [line for line in text.splitlines() if line.strip()]
        if not nonblank_lines:
            return False
        table_line_count = sum(
            1 for line in nonblank_lines if self._is_table_line(line)
        )
        return (
            table_line_count > 0
            and table_line_count / len(nonblank_lines)
            >= self.table_line_ratio_threshold
        )

    def _split_table_heavy_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        pending_text_lines: list[str] = []
        current_heading = ""
        lines = text.splitlines()
        index = 0

        while index < len(lines):
            line = lines[index]
            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading_match:
                current_heading = line.strip()

            if self._is_table_line(line):
                table_lines: list[str] = []
                while index < len(lines) and self._is_table_line(lines[index]):
                    table_lines.append(lines[index])
                    index += 1

                context_prefix = self._table_context_prefix(
                    pending_text_lines,
                    fallback_heading=current_heading,
                )
                chunks.extend(
                    self._split_table_block(
                        table_lines=table_lines,
                        context_prefix=context_prefix,
                    )
                )
                pending_text_lines = []
                continue

            pending_text_lines.append(line)
            index += 1

        trailing_text = "\n".join(pending_text_lines).strip()
        if trailing_text:
            chunks.extend(self._split_recursively(trailing_text))

        return self._clean_chunks(chunks) or self._split_recursively(text)

    def _split_table_block(
        self,
        *,
        table_lines: list[str],
        context_prefix: str,
    ) -> list[str]:
        if not table_lines:
            return []

        header_lines, row_start_index = self._table_header(table_lines)
        rows = table_lines[row_start_index:]
        base_lines = [context_prefix] if context_prefix else []
        base_lines.extend(header_lines)
        if not rows:
            return ["\n".join(base_lines)]

        chunks: list[str] = []
        current_lines = list(base_lines)
        base_line_count = len(base_lines)

        for row in rows:
            candidate_lines = [*current_lines, row]
            if (
                len("\n".join(candidate_lines)) > self.table_chunk_chars
                and len(current_lines) > base_line_count
            ):
                chunks.append("\n".join(current_lines))
                current_lines = [*base_lines, row]
            else:
                current_lines = candidate_lines

        if len(current_lines) > base_line_count:
            chunks.append("\n".join(current_lines))
        return chunks

    def _table_header(self, table_lines: list[str]) -> tuple[list[str], int]:
        header_lines = [table_lines[0]]
        row_start_index = 1
        if len(table_lines) > 1 and self._is_table_separator_line(table_lines[1]):
            header_lines.append(table_lines[1])
            row_start_index = 2
        if len(table_lines) > row_start_index and self._is_table_header_continuation(
            table_lines[row_start_index]
        ):
            header_lines.append(table_lines[row_start_index])
            row_start_index += 1
        return header_lines, row_start_index

    @staticmethod
    def _table_context_prefix(
        pending_text_lines: list[str],
        *,
        fallback_heading: str,
    ) -> str:
        nonblank_lines = [line.strip() for line in pending_text_lines if line.strip()]
        prefix_lines: list[str] = []
        if fallback_heading:
            prefix_lines.append(fallback_heading)
        for line in nonblank_lines[-2:]:
            if line not in prefix_lines:
                prefix_lines.append(line)
        return "\n".join(prefix_lines)

    @staticmethod
    def _is_table_line(line: str) -> bool:
        return line.lstrip().startswith("|")

    @staticmethod
    def _is_table_separator_line(line: str) -> bool:
        cells = DocumentChunker._table_cells(line)
        return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells)

    @staticmethod
    def _is_table_header_continuation(line: str) -> bool:
        cells = DocumentChunker._table_cells(line)
        return bool(cells) and not cells[0] and any(cells[1:])

    @staticmethod
    def _table_cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    @staticmethod
    def _clean_chunks(chunks: list[str]) -> list[str]:
        return [chunk for chunk in (value.strip() for value in chunks) if chunk]

    def _build_payload(
        self,
        parent_section: ParentSection,
        child_text: str,
        chunk_index: int,
    ) -> dict[str, Any]:
        metadata = _qdrant_payload_metadata(parent_section.metadata)
        page_number = metadata.get("page_number", metadata.get("page", 1))
        ingestion_version = metadata.get("ingestion_version", "unversioned")
        content_hash = sha256(
            unicodedata.normalize("NFC", child_text).encode("utf-8")
        ).hexdigest()
        return {
            **metadata,
            "section_type": self._section_type(parent_section.heading),
            "page_number": page_number,
            "chunk_index": chunk_index,
            "parent_section_id": parent_section.section_id,
            "text": child_text,
            "parent_text": parent_section.text,
            "content_hash": content_hash,
            "ingestion_version": ingestion_version,
        }

    @staticmethod
    def _section_type(heading: str) -> str:
        return DocumentChunker._slugify(heading).replace("-", "_")

    @staticmethod
    def _slugify(value: str) -> str:
        normalized_value = unicodedata.normalize("NFKD", value)
        ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
        return slug or "section"


def _qdrant_payload_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload_metadata = dict(metadata)
    source_path = payload_metadata.pop("source_path", None)
    if "file_name" not in payload_metadata and source_path:
        payload_metadata["file_name"] = Path(str(source_path)).name
    return payload_metadata
