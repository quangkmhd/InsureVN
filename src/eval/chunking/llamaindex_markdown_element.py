"""LlamaIndex MarkdownElementNodeParser chunking."""

from __future__ import annotations

from llama_index.core.llms import LLM
from llama_index.core.node_parser import MarkdownElementNodeParser

from src.eval.chunking.base import ChunkingStrategy
from src.eval.chunking.llamaindex_utils import (
    chunks_from_llamaindex_nodes,
    make_llamaindex_document,
)
from src.eval.models import CorpusDocument, TextChunk


class LlamaIndexMarkdownElementChunking(ChunkingStrategy):
    """Split Markdown into text/table element nodes with LlamaIndex."""

    name = "llamaindex_markdown_element"
    description = "LlamaIndex MarkdownElementNodeParser for table-aware nodes."

    def __init__(self, llm: LLM, num_workers: int = 4) -> None:
        if llm is None:
            msg = "llamaindex_markdown_element requires a configured Gemini LLM."
            raise ValueError(msg)
        self.parser = MarkdownElementNodeParser.from_defaults(
            llm=llm,
            num_workers=num_workers,
            show_progress=False,
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Parse Markdown elements, including table element nodes."""

        llama_document = make_llamaindex_document(document)
        nodes = self.parser.get_nodes_from_documents([llama_document])
        return chunks_from_llamaindex_nodes(document, self.name, nodes)
