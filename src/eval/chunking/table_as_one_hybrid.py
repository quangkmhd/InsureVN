"""Table-as-one hybrid chunking."""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.eval.chunking.base import ChunkingStrategy, chunks_from_parts
from src.eval.chunking.table_utils import (
    split_markdown_blocks,
    split_table_block,
)
from src.eval.models import CorpusDocument, TextChunk


class TableAsOneHybridChunking(ChunkingStrategy):
    """Keep Markdown tables intact when possible and recursively split prose."""

    name = "table_as_one_hybrid"
    description = "Preserve important tables as one chunk, recurse prose blocks."

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        max_rows_per_table_chunk: int = 30,
    ) -> None:
        self.chunk_size = chunk_size
        self.max_rows_per_table_chunk = max_rows_per_table_chunk
        self.prose_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split prose recursively while preserving table row groups."""

        parts: list[tuple[str, dict[str, object]]] = []
        for block in split_markdown_blocks(document.text):
            if block.kind == "table":
                for table_chunk in split_table_as_one(
                    block.text,
                    self.chunk_size,
                    self.max_rows_per_table_chunk,
                ):
                    parts.append((table_chunk, {"block_type": "table_as_one"}))
                continue
            split_documents = self.prose_splitter.create_documents([block.text])
            parts.extend(
                (
                    split_document.page_content,
                    {"block_type": "prose"},
                )
                for split_document in split_documents
                if split_document.page_content.strip()
            )
        return chunks_from_parts(document, self.name, parts)


def split_table_as_one(
    table_text: str,
    chunk_size: int,
    max_rows_per_table_chunk: int,
) -> list[str]:
    """Keep short tables as one chunk and split long tables by rows."""

    rows = table_text.splitlines()
    if len(rows) <= max_rows_per_table_chunk and len(table_text) <= chunk_size * 2:
        return [table_text]
    return split_table_block(table_text, chunk_size)
