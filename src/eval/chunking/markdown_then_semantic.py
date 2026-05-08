"""Hybrid Markdown section plus semantic chunking."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import MarkdownHeaderTextSplitter

from src.eval.chunking.base import ChunkingStrategy, chunks_from_langchain_documents
from src.eval.config import DEFAULT_MARKDOWN_HEADERS
from src.eval.models import CorpusDocument, TextChunk


class MarkdownThenSemanticChunking(ChunkingStrategy):
    """Split by Markdown hierarchy, then apply embedding-based semantic splits."""

    name = "markdown_then_semantic"
    description = "MarkdownHeaderTextSplitter followed by LangChain SemanticChunker."

    def __init__(self, embeddings: Embeddings, min_chunk_size: int = 200) -> None:
        self.retrieval_embeddings = embeddings
        self.section_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=list(DEFAULT_MARKDOWN_HEADERS),
            strip_headers=False,
        )
        self.semantic_splitter = SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
            min_chunk_size=min_chunk_size,
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split one document by Markdown sections and semantic breakpoints."""

        section_documents = self.section_splitter.split_text(document.text)
        split_documents = self.semantic_splitter.split_documents(section_documents)
        return chunks_from_langchain_documents(document, self.name, split_documents)
