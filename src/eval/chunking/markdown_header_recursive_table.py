"""MarkdownHeader plus recursive chunking with table-aware handling."""

from __future__ import annotations

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.eval.chunking.base import ChunkingStrategy, chunks_from_parts
from src.eval.chunking.table_utils import (
    is_markdown_table_line,
    split_table_block,
)
from src.eval.models import CorpusDocument, TextChunk


class MarkdownHeaderRecursiveTableChunking(ChunkingStrategy):
    """Split by Markdown headers, then split prose and tables separately."""

    name = "markdown_header_recursive_table"
    description = (
        "MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter + tables."
    )

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.chunk_size = chunk_size
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ],
            strip_headers=False,
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split Markdown sections and handle tables as their own chunks."""

        section_documents = self.markdown_splitter.split_text(document.text)
        parts: list[tuple[str, dict[str, object]]] = []
        for section_document in section_documents:
            section_metadata = dict(section_document.metadata)
            for block_type, block_text in split_section_table_blocks(
                section_document.page_content
            ):
                if block_type == "table":
                    for table_chunk in split_table_block(block_text, self.chunk_size):
                        parts.append(
                            (
                                table_chunk,
                                {**section_metadata, "block_type": "markdown_table"},
                            )
                        )
                else:
                    split_documents = self.text_splitter.create_documents([block_text])
                    parts.extend(
                        (
                            split_document.page_content,
                            {**section_metadata, "block_type": "prose"},
                        )
                        for split_document in split_documents
                        if split_document.page_content.strip()
                    )
        return chunks_from_parts(document, self.name, parts)


def split_section_table_blocks(text: str) -> list[tuple[str, str]]:
    """Split a section into prose/table blocks."""

    blocks: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_type: str | None = None
    for line in text.splitlines():
        line_type = "table" if is_markdown_table_line(line) else "prose"
        if current_type is None:
            current_type = line_type
        if line_type != current_type:
            blocks.append((current_type, "\n".join(current_lines)))
            current_lines = []
            current_type = line_type
        current_lines.append(line)
    if current_lines and current_type is not None:
        blocks.append((current_type, "\n".join(current_lines)))
    return [
        (block_type, block_text)
        for block_type, block_text in blocks
        if block_text.strip()
    ]
