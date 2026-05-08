"""Auto heading-level chunking that never cuts inside Markdown tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.eval.chunking.base import ChunkingStrategy, chunks_from_parts
from src.eval.chunking.table_utils import (
    is_markdown_table_line,
    is_table_separator,
)
from src.eval.models import CorpusDocument, TextChunk


@dataclass(frozen=True)
class HeadingSafeSection:
    """A table-safe section emitted by heading-aware splitting."""

    content: str
    has_table: bool
    split_method: str


class HeadingLevelTableSafeChunking(ChunkingStrategy):
    """Split at the corpus-selected heading level with table safety guards."""

    name = "heading_level_table_safe"
    description = "Auto heading-level split with merge/split guards for tables."

    def __init__(
        self,
        cut_level: int,
        max_chars: int,
        min_chars: int,
        max_table_rows: int = 50,
    ) -> None:
        self.cut_level = cut_level
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.max_table_rows = max_table_rows

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split one document at the selected heading level."""

        sections = split_at_heading_level(
            md_text=document.text,
            cut_level=self.cut_level,
            max_chars=self.max_chars,
            min_chars=self.min_chars,
            max_table_rows=self.max_table_rows,
        )
        parts = [
            (
                section.content,
                {
                    "has_table": section.has_table,
                    "split_method": section.split_method,
                    "heading_cut_level": self.cut_level,
                },
            )
            for section in sections
        ]
        return chunks_from_parts(document, self.name, parts)


def split_at_heading_level(
    md_text: str,
    cut_level: int,
    max_chars: int = 6000,
    min_chars: int = 300,
    max_table_rows: int = 50,
) -> list[HeadingSafeSection]:
    """Split Markdown at a heading level, then table-safely refine sections."""

    raw_sections = split_raw_sections_at_heading(md_text, cut_level)
    refined_sections: list[HeadingSafeSection] = []
    merge_buffer = ""
    for raw_section in raw_sections:
        section = raw_section.strip()
        if not section:
            continue
        if len(section) > max_chars:
            oversized_sections = split_oversized_section(
                section,
                cut_level=cut_level,
                max_chars=max_chars,
                min_chars=min_chars,
                max_table_rows=max_table_rows,
            )
            if merge_buffer:
                refined_sections.append(
                    make_section(merge_buffer, "merged_small_heading_sections")
                )
                merge_buffer = ""
            refined_sections.extend(oversized_sections)
            continue
        if len(section) < min_chars:
            merge_buffer = f"{merge_buffer}\n\n{section}".strip()
            if len(merge_buffer) >= min_chars:
                refined_sections.append(
                    make_section(merge_buffer, "merged_small_heading_sections")
                )
                merge_buffer = ""
            continue
        if merge_buffer:
            refined_sections.append(
                make_section(merge_buffer, "merged_small_heading_sections")
            )
            merge_buffer = ""
        refined_sections.append(make_section(section, f"heading_h{cut_level}"))
    if merge_buffer:
        refined_sections.append(
            make_section(merge_buffer, "merged_small_heading_sections")
        )
    return refined_sections


def split_raw_sections_at_heading(md_text: str, cut_level: int) -> list[str]:
    """Split only at headings of exactly the requested level."""

    if cut_level > 6:
        return [md_text]
    pattern = re.compile(rf"^{'#' * cut_level}\s+", re.MULTILINE)
    boundaries = [match.start() for match in pattern.finditer(md_text)]
    if not boundaries:
        return [md_text]
    if boundaries[0] != 0:
        boundaries.insert(0, 0)
    boundaries.append(len(md_text))
    return [
        md_text[boundaries[index] : boundaries[index + 1]].strip()
        for index in range(len(boundaries) - 1)
    ]


def split_oversized_section(
    section: str,
    cut_level: int,
    max_chars: int,
    min_chars: int,
    max_table_rows: int,
) -> list[HeadingSafeSection]:
    """Split large sections by child heading or by table-safe blocks."""

    if cut_level < 6 and has_heading_level(section, cut_level + 1):
        child_sections = split_at_heading_level(
            md_text=section,
            cut_level=cut_level + 1,
            max_chars=max_chars,
            min_chars=min_chars,
            max_table_rows=max_table_rows,
        )
        if all(len(child.content) <= max_chars for child in child_sections):
            return child_sections
    return split_by_table_safe_blocks(
        section,
        max_chars=max_chars,
        max_table_rows=max_table_rows,
    )


def has_heading_level(text: str, level: int) -> bool:
    """Return True when a section contains a heading at the requested level."""

    pattern = re.compile(rf"^{'#' * level}\s+", re.MULTILINE)
    return pattern.search(text) is not None


def split_by_table_safe_blocks(
    text: str,
    max_chars: int,
    max_table_rows: int,
) -> list[HeadingSafeSection]:
    """Split prose/table blocks while preserving every table block."""

    sections: list[HeadingSafeSection] = []
    prose_buffer = ""
    for block_type, block_text in split_markdown_table_blocks(text):
        if block_type == "table":
            if prose_buffer.strip():
                sections.extend(split_prose_block(prose_buffer, max_chars))
                prose_buffer = ""
            for table_chunk in split_long_table_block(block_text, max_table_rows):
                sections.append(make_section(table_chunk, "table_block"))
            continue
        candidate = f"{prose_buffer}\n\n{block_text}".strip()
        if prose_buffer and len(candidate) > max_chars:
            sections.extend(split_prose_block(prose_buffer, max_chars))
            prose_buffer = block_text
        else:
            prose_buffer = candidate
    if prose_buffer.strip():
        sections.extend(split_prose_block(prose_buffer, max_chars))
    return sections


def split_markdown_table_blocks(text: str) -> list[tuple[str, str]]:
    """Split Markdown into table and non-table blocks."""

    blocks: list[tuple[str, str]] = []
    current_lines: list[str] = []
    current_type: str | None = None
    for line in text.splitlines():
        line_type = "table" if is_markdown_table_line(line) else "text"
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


def split_long_table_block(table_text: str, max_rows: int) -> list[str]:
    """Split a very long Markdown table by rows and repeat the header."""

    lines = table_text.splitlines()
    if len(lines) <= max_rows:
        return [table_text]
    header_line_count = 2 if len(lines) > 1 and is_table_separator(lines[1]) else 1
    header_lines = lines[:header_line_count]
    body_lines = lines[header_line_count:]
    chunks: list[str] = []
    rows_per_chunk = max(1, max_rows - header_line_count)
    for start in range(0, len(body_lines), rows_per_chunk):
        row_group = body_lines[start : start + rows_per_chunk]
        chunks.append("\n".join([*header_lines, *row_group]))
    return chunks


def split_prose_block(text: str, max_chars: int) -> list[HeadingSafeSection]:
    """Split prose without table lines."""

    if len(text) <= max_chars:
        return [make_section(text, "prose_block")]
    paragraphs = [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]
    sections: list[HeadingSafeSection] = []
    buffer = ""
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}".strip()
        if buffer and len(candidate) > max_chars:
            sections.append(make_section(buffer, "prose_paragraph_group"))
            buffer = paragraph
        else:
            buffer = candidate
    if buffer:
        sections.append(make_section(buffer, "prose_paragraph_group"))
    return sections


def make_section(content: str, split_method: str) -> HeadingSafeSection:
    """Build a section model with table metadata."""

    stripped = content.strip()
    return HeadingSafeSection(
        content=stripped,
        has_table=contains_markdown_table(stripped),
        split_method=split_method,
    )


def contains_markdown_table(text: str) -> bool:
    """Return True if text contains a Markdown table row."""

    return any(is_markdown_table_line(line) for line in text.splitlines())
