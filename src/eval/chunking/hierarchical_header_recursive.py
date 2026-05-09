"""Hierarchical header-aware recursive chunking."""

from __future__ import annotations

from pathlib import Path

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.eval.chunking.base import (
    ChunkingStrategy,
    chunks_from_langchain_documents,
)
from src.eval.config import DEFAULT_MARKDOWN_HEADERS
from src.eval.models import CorpusDocument, TextChunk


class HierarchicalHeaderRecursiveChunking(ChunkingStrategy):
    """Split by Markdown header hierarchy and retain parent header path."""

    name = "hierarchical_header_recursive"
    description = "Header hierarchy metadata plus recursive child chunks."

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=list(DEFAULT_MARKDOWN_HEADERS),
            strip_headers=False,
        )
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split one Markdown document into hierarchical child chunks."""

        parent_documents = self.header_splitter.split_text(document.text)
        for parent_document in parent_documents:
            header_values = header_hierarchy(parent_document.metadata)
            fallback_title = Path(document.source_path).stem
            section_title = header_values[-1] if header_values else fallback_title
            parent_document.metadata["document_source_path"] = document.source_path
            parent_document.metadata["document_provider"] = document.provider
            parent_document.metadata["header_hierarchy"] = header_values
            parent_document.metadata["header_path"] = (
                " > ".join(header_values) if header_values else fallback_title
            )
            parent_document.metadata["header_level"] = len(header_values)
            parent_document.metadata["section_title"] = section_title
            parent_document.metadata["parent_section_length"] = len(
                parent_document.page_content
            )
        split_documents = self.child_splitter.split_documents(parent_documents)
        return chunks_from_langchain_documents(document, self.name, split_documents)


def header_hierarchy(metadata: dict[str, object]) -> list[str]:
    """Return ordered, non-empty Markdown header values from splitter metadata."""

    return [
        str(metadata[key])
        for key in sorted(metadata)
        if key.startswith("Header ") and metadata.get(key)
    ]
