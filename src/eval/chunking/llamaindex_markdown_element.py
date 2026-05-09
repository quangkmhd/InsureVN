"""LlamaIndex MarkdownElementNodeParser chunking."""

from __future__ import annotations

import asyncio

import nest_asyncio
from llama_index.core.llms import LLM
from llama_index.core.node_parser import MarkdownElementNodeParser

from src.eval.chunking.base import ChunkingStrategy, chunks_from_parts
from src.eval.chunking.heading_level_table_safe import split_at_heading_level
from src.eval.chunking.llamaindex_utils import (
    chunks_from_llamaindex_nodes,
    make_llamaindex_document,
)
from src.eval.models import CorpusDocument, TextChunk


class LlamaIndexMarkdownElementChunking(ChunkingStrategy):
    """Split Markdown into text/table element nodes with LlamaIndex."""

    name = "llamaindex_markdown_element"
    description = "LlamaIndex MarkdownElementNodeParser for table-aware nodes."

    def __init__(
        self,
        llm: LLM,
        num_workers: int = 4,
        fallback_cut_level: int = 2,
        fallback_max_chars: int = 6000,
        fallback_min_chars: int = 300,
        fallback_max_table_rows: int = 50,
    ) -> None:
        if llm is None:
            msg = "llamaindex_markdown_element requires a configured Gemini LLM."
            raise ValueError(msg)
        self.fallback_cut_level = fallback_cut_level
        self.fallback_max_chars = fallback_max_chars
        self.fallback_min_chars = fallback_min_chars
        self.fallback_max_table_rows = fallback_max_table_rows
        nest_asyncio.apply()
        self.parser = MarkdownElementNodeParser.from_defaults(
            llm=llm,
            num_workers=num_workers,
            show_progress=False,
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Parse Markdown elements, including table element nodes."""

        llama_document = make_llamaindex_document(document)
        try:
            nodes = asyncio.run(
                self.parser.aget_nodes_from_documents(
                    [llama_document],
                    show_progress=False,
                )
            )
            return chunks_from_llamaindex_nodes(document, self.name, nodes)
        except Exception as exc:
            return self.fallback_chunk_document(document, exc)

    def fallback_chunk_document(
        self,
        document: CorpusDocument,
        exc: Exception,
    ) -> list[TextChunk]:
        """Return table-safe chunks when LlamaIndex table summarization fails."""

        sections = split_at_heading_level(
            md_text=document.text,
            cut_level=self.fallback_cut_level,
            max_chars=self.fallback_max_chars,
            min_chars=self.fallback_min_chars,
            max_table_rows=self.fallback_max_table_rows,
        )
        fallback_reason = f"{type(exc).__name__}: {exc}"
        parts = [
            (
                section.content,
                {
                    "has_table": section.has_table,
                    "heading_cut_level": self.fallback_cut_level,
                    "llamaindex_fallback": True,
                    "llamaindex_fallback_reason": fallback_reason,
                    "llm_fallback": True,
                    "llm_fallback_reason": fallback_reason,
                    "split_method": section.split_method,
                },
            )
            for section in sections
        ]
        return chunks_from_parts(document, self.name, parts)
