import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.core.vietnamese_text import slugify_vietnamese
from src.services.observability import add_current_service_metadata, service_observe

ChunkingStrategy = Literal["hierarchical_header_recursive"]

REQUIRED_QDRANT_PAYLOAD_FIELDS = (
    "company_code",
    "document_id",
    "document_type",
    "document_name",
    "product_line",
    "section_type",
    "chunk_index",
    "parent_section_id",
    "file_name",
    "content_hash",
    "ingestion_version",
)
HIERARCHICAL_QDRANT_PAYLOAD_FIELDS = (
    "chunking_strategy",
    "header_hierarchy",
    "header_path",
    "header_level",
    "section_heading",
)
NON_EMPTY_QDRANT_PAYLOAD_FIELDS = (
    "company_code",
    "document_id",
    "document_type",
    "document_name",
    "product_line",
    "section_type",
    "parent_section_id",
    "file_name",
    "content_hash",
    "ingestion_version",
)
HIERARCHICAL_NON_EMPTY_QDRANT_PAYLOAD_FIELDS = (
    "chunking_strategy",
    "header_path",
    "section_heading",
)
MARKDOWN_HEADER_SPLIT_LEVELS = (
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
    ("####", "Header 4"),
    ("#####", "Header 5"),
    ("######", "Header 6"),
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


class DocumentChunker:
    """Parse markdown into parent sections and deterministic child chunks."""

    def __init__(
        self,
        child_chunk_chars: int = 1200,
        child_chunk_overlap: int = 150,
        chunking_strategy: ChunkingStrategy = "hierarchical_header_recursive",
    ) -> None:
        """Initialize the chunker.

        Args:
            child_chunk_chars: Maximum child chunk size in characters.
            child_chunk_overlap: Character overlap between adjacent child chunks.
            chunking_strategy: Splitting strategy for child chunks.
        """
        if child_chunk_chars <= 0:
            raise ValueError("child_chunk_chars must be positive.")
        if child_chunk_overlap < 0:
            raise ValueError("child_chunk_overlap cannot be negative.")
        if child_chunk_overlap >= child_chunk_chars:
            raise ValueError("child_chunk_overlap must be smaller than chunk size.")
        if chunking_strategy != "hierarchical_header_recursive":
            raise ValueError(
                "chunking_strategy must be 'hierarchical_header_recursive'."
            )

        self.child_chunk_chars = child_chunk_chars
        self.child_chunk_overlap = child_chunk_overlap
        self.chunking_strategy = chunking_strategy
        self._hierarchical_header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=list(MARKDOWN_HEADER_SPLIT_LEVELS),
            strip_headers=False,
        )
        self._hierarchical_child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_chars,
            chunk_overlap=child_chunk_overlap,
            length_function=len,
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
        return self._chunk_markdown_hierarchically(
            markdown_text=normalized_text,
            metadata=metadata,
        )

    @classmethod
    @service_observe(
        name="service.document_chunker.validate_payload",
        component="document_chunker",
    )
    def validate_payload(
        cls,
        payload: dict[str, Any],
        *,
        expected_chunking_strategy: ChunkingStrategy | None = None,
    ) -> None:
        """Validate required Qdrant citation payload fields."""
        missing_fields = [
            field for field in REQUIRED_QDRANT_PAYLOAD_FIELDS if field not in payload
        ]
        requires_hierarchical_metadata = (
            expected_chunking_strategy == "hierarchical_header_recursive"
            or payload.get("chunking_strategy") == "hierarchical_header_recursive"
        )
        if requires_hierarchical_metadata:
            missing_fields.extend(
                field
                for field in HIERARCHICAL_QDRANT_PAYLOAD_FIELDS
                if field not in payload
            )
        if missing_fields:
            raise ValueError(
                "Missing Qdrant payload field(s): " + ", ".join(missing_fields)
            )
        empty_fields = [
            field
            for field in NON_EMPTY_QDRANT_PAYLOAD_FIELDS
            if field in payload and _is_missing_or_blank(payload.get(field))
        ]
        if requires_hierarchical_metadata:
            empty_fields.extend(
                field
                for field in HIERARCHICAL_NON_EMPTY_QDRANT_PAYLOAD_FIELDS
                if field in payload and _is_missing_or_blank(payload.get(field))
            )
        if empty_fields:
            raise ValueError(
                "Empty Qdrant payload field(s): " + ", ".join(empty_fields)
            )
        if requires_hierarchical_metadata:
            cls._validate_hierarchical_payload(payload)

    @staticmethod
    def _validate_hierarchical_payload(payload: dict[str, Any]) -> None:
        invalid_fields: list[str] = []
        if payload.get("chunking_strategy") != "hierarchical_header_recursive":
            invalid_fields.append("chunking_strategy")
        header_hierarchy = payload.get("header_hierarchy")
        if not isinstance(header_hierarchy, list) or any(
            _is_missing_or_blank(header) for header in header_hierarchy
        ):
            invalid_fields.append("header_hierarchy")
        header_level = payload.get("header_level")
        if not isinstance(header_level, int) or header_level < 0:
            invalid_fields.append("header_level")
        if invalid_fields:
            raise ValueError(
                "Invalid hierarchical Qdrant payload field(s): "
                + ", ".join(invalid_fields)
            )

    def _chunk_markdown_hierarchically(
        self,
        *,
        markdown_text: str,
        metadata: dict[str, Any],
    ) -> ChunkedDocument:
        parent_sections = self._parse_hierarchical_parent_sections(
            markdown_text,
            metadata,
        )
        child_chunks: list[ChildChunk] = []
        chunking_metrics = ChunkingMetrics(recursive_section_count=len(parent_sections))

        for parent_section in parent_sections:
            child_texts = self._clean_chunks(
                self._hierarchical_child_splitter.split_text(parent_section.text)
            )
            if not child_texts and parent_section.text.strip():
                child_texts = [parent_section.text.strip()]
            for chunk_index, child_text in enumerate(child_texts):
                payload = self._build_payload(
                    parent_section=parent_section,
                    child_text=child_text,
                    chunk_index=chunk_index,
                )
                self.validate_payload(
                    payload,
                    expected_chunking_strategy=self.chunking_strategy,
                )
                child_chunks.append(
                    ChildChunk(
                        chunk_id=f"{parent_section.section_id}:chunk:{chunk_index}",
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

    def _parse_hierarchical_parent_sections(
        self,
        markdown_text: str,
        metadata: dict[str, Any],
    ) -> list[ParentSection]:
        split_documents = self._hierarchical_header_splitter.split_text(markdown_text)
        if not split_documents and markdown_text.strip():
            return [
                ParentSection(
                    section_id=f"{metadata['document_id']}:document",
                    heading=str(metadata["document_name"]),
                    level=1,
                    text=markdown_text.strip(),
                    metadata={
                        **metadata,
                        **self._hierarchical_header_metadata({}, metadata),
                    },
                )
            ]

        sections: list[ParentSection] = []
        for index, split_document in enumerate(split_documents):
            section_text = split_document.page_content.strip()
            if not section_text:
                continue
            header_metadata = self._hierarchical_header_metadata(
                split_document.metadata,
                metadata,
            )
            heading = str(header_metadata["section_heading"])
            sections.append(
                ParentSection(
                    section_id=(
                        f"{metadata['document_id']}:{self._slugify(heading)}:{index}"
                    ),
                    heading=heading,
                    level=int(header_metadata["header_level"]) or 1,
                    text=section_text,
                    metadata={**metadata, **header_metadata},
                )
            )
        return sections

    @staticmethod
    def _hierarchical_header_metadata(
        raw_metadata: dict[str, Any],
        document_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        header_values = [
            str(raw_metadata[key])
            for key in sorted(raw_metadata)
            if key.startswith("Header ") and raw_metadata.get(key)
        ]
        fallback_heading = str(document_metadata.get("document_name") or "document")
        section_heading = header_values[-1] if header_values else fallback_heading
        header_metadata: dict[str, Any] = {
            "chunking_strategy": "hierarchical_header_recursive",
            "header_hierarchy": header_values,
            "header_path": " > ".join(header_values)
            if header_values
            else section_heading,
            "header_level": len(header_values),
            "section_heading": section_heading,
        }
        for key, value in raw_metadata.items():
            if key.startswith("Header ") and value:
                header_metadata[key.lower().replace(" ", "_")] = str(value)
        return header_metadata

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
            "parent_section_count": len(chunked_document.parent_sections),
            "child_chunk_count": len(chunked_document.child_chunks),
            "empty_section_count": chunking_metrics.empty_section_count,
            "recursive_section_count": chunking_metrics.recursive_section_count,
            "chunk_length_min": min(chunk_lengths) if chunk_lengths else 0,
            "chunk_length_max": max(chunk_lengths) if chunk_lengths else 0,
            "chunk_length_avg": (
                round(sum(chunk_lengths) / len(chunk_lengths), 2)
                if chunk_lengths
                else 0
            ),
        }
        add_current_service_metadata({"chunking": chunking_metadata})

    @staticmethod
    def _is_table_line(line: str) -> bool:
        return line.lstrip().startswith("|")

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
        ingestion_version = metadata.get("ingestion_version", "unversioned")
        content_hash = sha256(
            unicodedata.normalize("NFC", child_text).encode("utf-8")
        ).hexdigest()
        content_type = self._content_type(child_text)
        return {
            **metadata,
            "section_type": self._section_type(parent_section.heading),
            "content_type": content_type,
            "has_table": content_type in {"mixed", "table"},
            "chunk_index": chunk_index,
            "parent_section_id": parent_section.section_id,
            "text": child_text,
            "content_hash": content_hash,
            "ingestion_version": ingestion_version,
        }

    @staticmethod
    def _section_type(heading: str) -> str:
        return DocumentChunker._slugify(heading).replace("-", "_")

    @staticmethod
    def _content_type(text: str) -> str:
        nonblank_lines = [line for line in text.splitlines() if line.strip()]
        if not nonblank_lines:
            return "text"
        table_line_count = sum(
            1 for line in nonblank_lines if DocumentChunker._is_table_line(line)
        )
        if table_line_count == 0:
            return "text"
        if table_line_count == len(nonblank_lines):
            return "table"
        return "mixed"

    @staticmethod
    def _slugify(value: str) -> str:
        return slugify_vietnamese(value)


def _qdrant_payload_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload_metadata = dict(metadata)
    source_path = payload_metadata.pop("source_path", None)
    payload_metadata.pop("page", None)
    payload_metadata.pop("page_number", None)
    if "file_name" not in payload_metadata and source_path:
        payload_metadata["file_name"] = Path(str(source_path)).name
    return payload_metadata


def _is_missing_or_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
