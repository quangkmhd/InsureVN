"""Hierarchical header-aware recursive chunking."""

from __future__ import annotations

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.eval.chunking.base import (
    ChunkingStrategy,
    chunks_from_langchain_documents,
    header_path,
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
            parent_document.metadata["header_path"] = header_path(
                parent_document.metadata
            )
            parent_document.metadata["parent_section_length"] = len(
                parent_document.page_content
            )
        split_documents = self.child_splitter.split_documents(parent_documents)
        return chunks_from_langchain_documents(document, self.name, split_documents)
