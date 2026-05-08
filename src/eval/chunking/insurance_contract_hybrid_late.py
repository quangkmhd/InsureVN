"""Insurance-contract hybrid chunking with fast retrieval embeddings."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from llama_index.core.llms import LLM

from src.eval.chunking.base import (
    ChunkingStrategy,
    find_part_span,
    header_path,
    make_chunk_id,
)
from src.eval.chunking.markdown_header_recursive_table import (
    split_section_table_blocks,
)
from src.eval.chunking.table_utils import split_table_block
from src.eval.config import DEFAULT_MARKDOWN_HEADERS
from src.eval.corpus import line_number_for_offset
from src.eval.models import CorpusDocument, TextChunk

DEFINITION_HEADING_PATTERN = re.compile(r"định nghĩa|diễn giải", re.IGNORECASE)
MARKDOWN_TAG_PATTERN = re.compile(r"<[^>]+>|\*\*|__|`")
WHITESPACE_PATTERN = re.compile(r"\s+")
TABLE_SUMMARY_PREFIX = "**Tóm tắt bảng:**"


class InsuranceContractHybridLateChunking(ChunkingStrategy):
    """Hybrid pipeline for complex insurance contracts with fast retrieval vectors."""

    name = "insurance_contract_hybrid_late"
    description = (
        "Definitions + table summaries + Markdown parents + child chunks + "
        "the configured retrieval embedding model."
    )

    def __init__(
        self,
        retrieval_embeddings: Embeddings,
        table_summary_llm: LLM | None,
        chunk_size: int,
        chunk_overlap: int,
        table_summary_workers: int = 4,
    ) -> None:
        self.retrieval_embeddings = retrieval_embeddings
        self.table_summary_llm = table_summary_llm
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.table_summary_workers = max(1, table_summary_workers)

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Run the full hybrid chunking pipeline for one document."""

        definitions = extract_definitions(document.text)
        parent_sections = split_markdown_parent_sections(document.text)
        chunks: list[TextChunk] = []
        source_cursor = 0
        for parent_index, parent_document in enumerate(parent_sections):
            parent_metadata = dict(parent_document.metadata)
            parent_header_path = header_path(parent_metadata)
            enriched_parent_text = enrich_tables_with_summaries(
                parent_document.page_content,
                self.table_summary_llm,
                self.table_summary_workers,
            )
            child_texts = split_child_chunks(
                enriched_parent_text,
                self.chunk_size,
                self.chunk_overlap,
            )
            parent_context_prefix = build_parent_context_prefix(
                document=document,
                parent_header_path=parent_header_path,
            )
            context_text = f"{parent_context_prefix}\n\n{enriched_parent_text}"
            for child_text in child_texts:
                definition_context = matching_definition_context(
                    child_text,
                    definitions,
                )
                chunk_text = build_child_retrieval_text(
                    parent_header_path=parent_header_path,
                    definition_context=definition_context,
                    child_text=child_text,
                )
                chunk = build_late_text_chunk(
                    document=document,
                    strategy_name=self.name,
                    text=chunk_text,
                    source_text=child_text,
                    metadata={
                        **parent_metadata,
                        "parent_index": parent_index,
                        "parent_header_path": parent_header_path,
                        "parent_text": enriched_parent_text,
                        "retrieval_text": context_text,
                        "definition_terms": list(definition_context),
                        "late_chunking": False,
                        "late_context_scope": "markdown_parent_section",
                        "embedding_model": getattr(
                            self.retrieval_embeddings,
                            "model_name",
                            "",
                        ),
                    },
                    embedding=None,
                    chunk_index=len(chunks),
                    search_cursor=source_cursor,
                )
                chunks.append(chunk)
                source_cursor = max(source_cursor, chunk.end_char)
        return chunks


def split_markdown_parent_sections(text: str) -> list[Document]:
    """Split Markdown into parent sections by heading hierarchy."""

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=list(DEFAULT_MARKDOWN_HEADERS),
        strip_headers=False,
    )
    sections = splitter.split_text(text)
    if sections:
        return sections
    return [Document(page_content=text, metadata={})]


def split_child_chunks(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Split a parent section into child chunks without cutting tables."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    child_chunks: list[str] = []
    pending_table_summary = ""
    for block_type, block_text in split_section_table_blocks(text):
        if block_type == "table":
            table_chunks = split_table_block(block_text, chunk_size=chunk_size)
            for table_chunk in table_chunks:
                child_chunks.append(
                    prepend_pending_table_summary(
                        pending_table_summary,
                        table_chunk,
                    )
                )
            pending_table_summary = ""
            continue

        prose_text, table_summary = detach_trailing_table_summary(block_text)
        child_chunks.extend(
            document.page_content
            for document in splitter.create_documents([prose_text])
            if document.page_content.strip()
        )
        if table_summary:
            pending_table_summary = table_summary

    if pending_table_summary:
        child_chunks.append(pending_table_summary)
    return [chunk for chunk in child_chunks if chunk.strip()]


def detach_trailing_table_summary(text: str) -> tuple[str, str]:
    """Detach a generated table summary from the end of a prose block."""

    paragraphs = text.split("\n\n")
    if paragraphs and paragraphs[-1].strip().startswith(TABLE_SUMMARY_PREFIX):
        return "\n\n".join(paragraphs[:-1]).strip(), paragraphs[-1].strip()
    return text, ""


def prepend_pending_table_summary(summary: str, table_chunk: str) -> str:
    """Attach the generated table summary to an atomic table chunk."""

    if not summary:
        return table_chunk
    return f"{summary}\n\n{table_chunk}"


def enrich_tables_with_summaries(
    text: str,
    llm: LLM | None,
    max_workers: int = 1,
) -> str:
    """Insert LLM-generated table summaries before Markdown tables."""

    blocks = split_section_table_blocks(text)
    enriched_blocks: list[str] = []
    for block_type, block_text in blocks:
        if block_type != "table":
            enriched_blocks.append(block_text)
            continue
        table_chunks = split_table_block(block_text, chunk_size=1800)
        summaries = summarize_table_chunks(table_chunks, llm, max_workers)
        for table_chunk, summary in zip(table_chunks, summaries, strict=True):
            enriched_blocks.append(f"{TABLE_SUMMARY_PREFIX} {summary}\n\n{table_chunk}")
    return "\n\n".join(enriched_blocks)


def summarize_table_chunks(
    table_chunks: list[str],
    llm: LLM | None,
    max_workers: int,
) -> list[str]:
    """Summarize table chunks concurrently while preserving table order."""

    if len(table_chunks) <= 1 or max_workers <= 1:
        return [summarize_table(table_chunk, llm) for table_chunk in table_chunks]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(table_chunks))) as pool:
        return list(
            pool.map(
                lambda table_chunk: summarize_table(table_chunk, llm),
                table_chunks,
            )
        )


def summarize_table(table_markdown: str, llm: LLM | None) -> str:
    """Summarize a Markdown table with the configured LLM."""

    if llm is None:
        msg = "insurance_contract_hybrid_late requires an LLM for table summaries."
        raise ValueError(msg)
    prompt = (
        "Bạn là hệ thống chuẩn bị dữ liệu RAG cho hợp đồng bảo hiểm. "
        "Hãy đọc bảng Markdown sau và viết một mô tả ngắn 1 câu, nêu rõ "
        "bảng nói về nội dung gì. Không bịa số liệu ngoài bảng.\n\n"
        f"{table_markdown}"
    )
    return str(llm.complete(prompt)).strip()


def extract_definitions(text: str) -> dict[str, str]:
    """Extract term definitions from definition-like Markdown tables."""

    definitions: dict[str, str] = {}
    lines = text.splitlines()
    in_definition_area = False
    for line in lines:
        if line.startswith("#") and DEFINITION_HEADING_PATTERN.search(line):
            in_definition_area = True
            continue
        if line.startswith("#") and in_definition_area:
            in_definition_area = False
        if "|" not in line:
            continue
        cells = split_markdown_table_row(line)
        if len(cells) < 2:
            continue
        term = clean_markdown_text(cells[0])
        definition = clean_markdown_text(" ".join(cells[1:]))
        if is_definition_candidate(term, definition, in_definition_area):
            definitions[term] = definition
    return definitions


def split_markdown_table_row(line: str) -> list[str]:
    """Split a Markdown table row into cells."""

    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def clean_markdown_text(text: str) -> str:
    """Remove Markdown/HTML noise from a definition cell."""

    cleaned = MARKDOWN_TAG_PATTERN.sub("", text)
    return WHITESPACE_PATTERN.sub(" ", cleaned).strip()


def is_definition_candidate(
    term: str,
    definition: str,
    in_definition_area: bool,
) -> bool:
    """Return True when a table row looks like a definition."""

    if not term or not definition:
        return False
    if len(term) > 80 or len(definition) < 20:
        return False
    if set(term) <= {"-", ":", " "}:
        return False
    return in_definition_area or bool(re.search(r"là|được hiểu là", definition))


def matching_definition_context(
    text: str,
    definitions: dict[str, str],
    max_definitions: int = 6,
) -> dict[str, str]:
    """Return definitions whose terms appear in a child chunk."""

    normalized_text = text.casefold()
    matches: dict[str, str] = {}
    for term, definition in definitions.items():
        if term.casefold() in normalized_text:
            matches[term] = definition
        if len(matches) >= max_definitions:
            break
    return matches


def build_parent_context_prefix(
    document: CorpusDocument,
    parent_header_path: str,
) -> str:
    """Build global metadata injected before late-context encoding."""

    return "\n".join(
        [
            f"Provider: {document.provider}",
            f"Source document: {document.source_path}",
            f"Header path: {parent_header_path or '/'}",
        ]
    )


def build_child_retrieval_text(
    parent_header_path: str,
    definition_context: dict[str, str],
    child_text: str,
) -> str:
    """Build child text returned after retrieval."""

    sections = [f"Header path: {parent_header_path or '/'}"]
    if definition_context:
        definitions = "\n".join(
            f"- {term}: {definition}" for term, definition in definition_context.items()
        )
        sections.append("Định nghĩa liên quan:\n" + definitions)
    sections.append(child_text)
    return "\n\n".join(sections)


def build_late_text_chunk(
    document: CorpusDocument,
    strategy_name: str,
    text: str,
    source_text: str,
    metadata: dict[str, object],
    embedding: list[float] | None,
    chunk_index: int,
    search_cursor: int,
) -> TextChunk:
    """Build a TextChunk with optional precomputed vector metadata."""

    offset_text = source_text_for_offsets(source_text)
    start_char, end_char, offset_match = find_part_span(
        document.text,
        offset_text,
        search_cursor,
        allow_backward_search=False,
    )
    start_line = line_number_for_offset(document.line_offsets, start_char)
    end_line = line_number_for_offset(
        document.line_offsets,
        max(start_char, end_char - 1),
    )
    return TextChunk(
        chunk_id=make_chunk_id(
            strategy_name=strategy_name,
            source_path=document.source_path,
            chunk_index=chunk_index,
            start_char=start_char,
            text=text,
        ),
        strategy=strategy_name,
        source_path=document.source_path,
        provider=document.provider,
        text=text,
        chunk_index=chunk_index,
        start_char=start_char,
        end_char=end_char,
        start_line=start_line,
        end_line=end_line,
        metadata={
            **metadata,
            "offset_match": offset_match,
            "chunk_length": len(text),
        },
        embedding=embedding,
    )


def source_text_for_offsets(text: str) -> str:
    """Remove generated table summary lines before source-offset matching."""

    lines = [
        line
        for line in text.splitlines()
        if not line.strip().startswith(TABLE_SUMMARY_PREFIX)
    ]
    cleaned = "\n".join(lines).strip()
    return cleaned or text
