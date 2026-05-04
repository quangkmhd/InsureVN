import re
import unicodedata
from dataclasses import dataclass
from typing import Any


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
    "source_path",
    "source_table_id",
    "effective_date",
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


class DocumentChunker:
    """Parse markdown into parent sections and deterministic child chunks."""

    def __init__(
        self,
        child_chunk_chars: int = 1200,
        child_chunk_overlap: int = 150,
    ) -> None:
        """Initialize the chunker.

        Args:
            child_chunk_chars: Maximum child chunk size in characters.
            child_chunk_overlap: Character overlap between adjacent child chunks.
        """
        if child_chunk_chars <= 0:
            raise ValueError("child_chunk_chars must be positive.")
        if child_chunk_overlap < 0:
            raise ValueError("child_chunk_overlap cannot be negative.")
        if child_chunk_overlap >= child_chunk_chars:
            raise ValueError("child_chunk_overlap must be smaller than chunk size.")

        self.child_chunk_chars = child_chunk_chars
        self.child_chunk_overlap = child_chunk_overlap

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
        child_chunks: list[ChildChunk] = []

        for parent_section in parent_sections:
            for chunk_index, child_text in enumerate(
                self._split_text(parent_section.text)
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

        return ChunkedDocument(
            parent_sections=parent_sections,
            child_chunks=child_chunks,
        )

    @classmethod
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
        heading_matches = list(re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown_text, re.M))

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

    def _split_text(self, text: str) -> list[str]:
        normalized_text = unicodedata.normalize("NFC", text.strip())
        if len(normalized_text) <= self.child_chunk_chars:
            return [normalized_text]

        chunks: list[str] = []
        start = 0
        while start < len(normalized_text):
            end = min(start + self.child_chunk_chars, len(normalized_text))
            chunks.append(normalized_text[start:end].strip())
            if end == len(normalized_text):
                break
            start = end - self.child_chunk_overlap
        return chunks

    def _build_payload(
        self,
        parent_section: ParentSection,
        child_text: str,
        chunk_index: int,
    ) -> dict[str, Any]:
        metadata = dict(parent_section.metadata)
        page_number = metadata.get("page_number", metadata.get("page", 1))
        return {
            **metadata,
            "section_type": self._section_type(parent_section.heading),
            "page_number": page_number,
            "chunk_index": chunk_index,
            "text": child_text,
            "parent_section_id": parent_section.section_id,
            "parent_text": parent_section.text,
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
