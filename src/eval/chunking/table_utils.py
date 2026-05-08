"""Shared Markdown table helpers for active chunking strategies."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MarkdownBlock:
    """A contiguous Markdown block."""

    kind: str
    text: str


def split_markdown_blocks(text: str) -> list[MarkdownBlock]:
    """Split Markdown into prose and table blocks."""

    blocks: list[MarkdownBlock] = []
    current_lines: list[str] = []
    current_kind: str | None = None
    for line in text.splitlines():
        line_kind = "table" if is_markdown_table_line(line) else "prose"
        if current_kind is None:
            current_kind = line_kind
        if line_kind != current_kind:
            blocks.append(
                MarkdownBlock(kind=current_kind, text="\n".join(current_lines))
            )
            current_lines = []
            current_kind = line_kind
        current_lines.append(line)
    if current_lines and current_kind is not None:
        blocks.append(MarkdownBlock(kind=current_kind, text="\n".join(current_lines)))
    return [block for block in blocks if block.text.strip()]


def is_markdown_table_line(line: str) -> bool:
    """Return True when a line looks like a Markdown table row."""

    stripped = line.strip()
    return stripped.count("|") >= 2 and not stripped.startswith("```")


def split_table_block(table_text: str, chunk_size: int) -> list[str]:
    """Split a large Markdown table by rows while retaining header rows."""

    lines = table_text.splitlines()
    if len(table_text) <= chunk_size or len(lines) <= 3:
        return [table_text]
    header_lines = lines[:2] if is_table_separator(lines[1]) else lines[:1]
    body_lines = lines[len(header_lines) :]
    chunks: list[str] = []
    current_rows: list[str] = []
    for row in body_lines:
        candidate = "\n".join([*header_lines, *current_rows, row])
        if current_rows and len(candidate) > chunk_size:
            chunks.append("\n".join([*header_lines, *current_rows]))
            current_rows = [row]
        else:
            current_rows.append(row)
    if current_rows:
        chunks.append("\n".join([*header_lines, *current_rows]))
    return chunks


def is_table_separator(line: str) -> bool:
    """Return True for Markdown table separator rows."""

    stripped = re.sub(r"[\s|:-]", "", line.strip())
    return not stripped and "-" in line
