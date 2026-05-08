"""LLM-guided Markdown chunking with deterministic table safety checks."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from llama_index.core.llms import LLM

from src.eval.chunking.base import ChunkingStrategy, chunks_from_parts
from src.eval.chunking.heading_level_table_safe import (
    HeadingSafeSection,
    split_at_heading_level,
    split_long_table_block,
    split_markdown_table_blocks,
)
from src.eval.chunking.table_utils import is_markdown_table_line
from src.eval.models import CorpusDocument, TextChunk

CHUNKING_SYSTEM_PROMPT = """Bạn là chuyên gia xử lý văn bản kỹ thuật.
Nhiệm vụ: Phân tích đoạn Markdown và xác định các điểm cắt chunk hợp lý.

QUY TẮC BẮT BUỘC:
1. TUYỆT ĐỐI không cắt giữa bảng Markdown. Bảng phải nằm NGUYÊN trong 1 chunk.
2. Mỗi chunk nên có 1 chủ đề/ý nghĩa hoàn chỉnh.
3. Chunk size mục tiêu: 200-600 từ.
4. Giữ heading lại với nội dung của nó.
5. Nếu bảng quá dài hơn 50 dòng, cho phép tách theo nhóm hàng nhưng PHẢI lặp lại header.
6. Trường `content` phải là đoạn trích NGUYÊN VĂN từ input Markdown. Không tóm tắt,
   không diễn giải, không sửa chữ, không bỏ sót nội dung ngoài khoảng trắng.

OUTPUT FORMAT (JSON):
{
  "chunks": [
    {
      "content": "nội dung chunk đầy đủ",
      "type": "text|table|mixed",
      "summary": "tóm tắt 1 câu",
      "has_table": true
    }
  ]
}
Chỉ trả về JSON, không giải thích thêm."""


class LLMMarkdownOptimalChunking(ChunkingStrategy):
    """Ask a real LLM for chunk boundaries, then enforce table safety."""

    name = "llm_markdown_optimal"
    description = "LLM-guided Markdown chunking with no mid-table cuts."

    def __init__(
        self,
        llm: LLM | None,
        cut_level: int,
        max_chars: int,
        min_chars: int,
        max_table_rows: int = 50,
        num_workers: int = 4,
    ) -> None:
        self.llm = llm
        self.cut_level = cut_level
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.max_table_rows = max_table_rows
        self.num_workers = max(1, num_workers)

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split one document with LLM-guided segment analysis."""

        if self.llm is None:
            msg = "llm_markdown_optimal requires a configured real LLM."
            raise ValueError(msg)
        seed_segments = split_at_heading_level(
            md_text=document.text,
            cut_level=self.cut_level,
            max_chars=self.max_chars,
            min_chars=self.min_chars,
            max_table_rows=self.max_table_rows,
        )
        segment_chunks = chunk_seed_segments(
            llm=self.llm,
            seed_segments=seed_segments,
            max_table_rows=self.max_table_rows,
            num_workers=self.num_workers,
        )
        parts: list[tuple[str, dict[str, object]]] = []
        for segment_index, (segment, llm_chunks) in enumerate(
            zip(seed_segments, segment_chunks, strict=True)
        ):
            for chunk_index, llm_chunk in enumerate(llm_chunks):
                parts.append(
                    (
                        str(llm_chunk["content"]),
                        {
                            "segment_index": segment_index,
                            "llm_chunk_index": chunk_index,
                            "type": llm_chunk.get("type", "mixed"),
                            "summary": llm_chunk.get("summary", ""),
                            "has_table": bool(llm_chunk.get("has_table", False)),
                            "heading_cut_level": self.cut_level,
                            "seed_split_method": segment.split_method,
                            "llm_fallback": bool(llm_chunk.get("fallback", False)),
                            "llm_fallback_reason": llm_chunk.get(
                                "fallback_reason",
                                "",
                            ),
                            "source_start": llm_chunk.get("source_start"),
                            "source_end": llm_chunk.get("source_end"),
                        },
                    )
                )
        return chunks_from_parts(document, self.name, parts)


def chunk_seed_segments(
    llm: LLM,
    seed_segments: list[HeadingSafeSection],
    max_table_rows: int,
    num_workers: int,
) -> list[list[dict[str, object]]]:
    """Chunk seed segments concurrently while preserving source order."""

    if len(seed_segments) <= 1 or num_workers <= 1:
        return [
            llm_chunk_segment(
                llm=llm,
                segment=segment.content,
                max_table_rows=max_table_rows,
            )
            for segment in seed_segments
        ]
    with ThreadPoolExecutor(max_workers=min(num_workers, len(seed_segments))) as pool:
        return list(
            pool.map(
                lambda segment: llm_chunk_segment(
                    llm=llm,
                    segment=segment.content,
                    max_table_rows=max_table_rows,
                ),
                seed_segments,
            )
        )


def llm_chunk_segment(
    llm: LLM,
    segment: str,
    max_table_rows: int = 50,
) -> list[dict[str, object]]:
    """Send one table-safe segment to an LLM and validate returned chunks."""

    try:
        response = llm.complete(
            f"{CHUNKING_SYSTEM_PROMPT}\n\nHãy chunk đoạn Markdown sau:\n\n{segment}"
        )
        chunks = parse_llm_chunk_response(llm_response_text(response))
        chunks = align_chunks_to_source(segment=segment, chunks=chunks)
        validate_llm_chunks_do_not_cut_tables(
            segment=segment,
            chunks=chunks,
            max_table_rows=max_table_rows,
        )
        return chunks
    except Exception as exc:
        return fallback_chunks(
            segment,
            max_table_rows=max_table_rows,
            fallback_reason=f"{type(exc).__name__}: {exc}",
        )


def parse_llm_chunk_response(raw_response: str) -> list[dict[str, object]]:
    """Parse the LLM JSON response into normalized chunk dictionaries."""

    raw_json = re.sub(r"```json|```", "", raw_response).strip()
    data = json.loads(raw_json)
    chunks_payload = data.get("chunks", [])
    if not isinstance(chunks_payload, list):
        msg = "LLM chunking response must contain a chunks list."
        raise ValueError(msg)
    chunks: list[dict[str, object]] = []
    for index, payload in enumerate(chunks_payload):
        if not isinstance(payload, dict):
            msg = "Each LLM chunk must be a JSON object."
            raise ValueError(msg)
        content = str(payload.get("content", "")).strip()
        if not content:
            continue
        chunks.append(
            {
                "content": content,
                "type": str(payload.get("type", "mixed")),
                "summary": str(payload.get("summary", "")),
                "has_table": bool(payload.get("has_table", "|" in content)),
                "chunk_index": index,
            }
        )
    if not chunks:
        msg = "LLM returned no non-empty chunks."
        raise ValueError(msg)
    return chunks


def llm_response_text(response: object) -> str:
    """Return text from a LlamaIndex completion response."""

    text = getattr(response, "text", None)
    if text is not None:
        return str(text)
    return str(response)


def align_chunks_to_source(
    segment: str,
    chunks: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Replace LLM chunk text with exact source slices or reject the output."""

    aligned_chunks: list[dict[str, object]] = []
    cursor = 0
    for chunk in chunks:
        proposed_content = str(chunk.get("content", ""))
        start = segment.find(proposed_content, cursor)
        if start < 0:
            msg = "LLM chunk content is not an ordered verbatim source substring."
            raise ValueError(msg)
        gap = segment[cursor:start]
        if gap.strip():
            msg = "LLM chunks do not cover all non-whitespace source text."
            raise ValueError(msg)
        end = start + len(proposed_content)
        aligned_chunk = dict(chunk)
        aligned_chunk["content"] = segment[start:end]
        aligned_chunk["source_start"] = start
        aligned_chunk["source_end"] = end
        aligned_chunks.append(aligned_chunk)
        cursor = end
    if segment[cursor:].strip():
        msg = "LLM chunks omit trailing non-whitespace source text."
        raise ValueError(msg)
    return aligned_chunks


def validate_llm_chunks_do_not_cut_tables(
    segment: str,
    chunks: list[dict[str, object]],
    max_table_rows: int,
) -> None:
    """Reject LLM output if any source table is missing or split."""

    chunk_texts = [str(chunk.get("content", "")) for chunk in chunks]
    for block_type, block_text in split_markdown_table_blocks(segment):
        if block_type != "table":
            continue
        if table_present_in_one_chunk(block_text, chunk_texts):
            continue
        table_chunks = split_long_table_block(block_text, max_table_rows)
        if len(table_chunks) == 1:
            msg = "LLM output cut or rewrote a protected Markdown table."
            raise ValueError(msg)
        for table_chunk in table_chunks:
            if not table_present_in_one_chunk(table_chunk, chunk_texts):
                msg = "LLM output cut or rewrote a protected Markdown table."
                raise ValueError(msg)


def table_present_in_one_chunk(table_text: str, chunk_texts: list[str]) -> bool:
    """Return True when a table appears intact in exactly one chunk."""

    containing_chunks = [
        chunk_text for chunk_text in chunk_texts if table_text.strip() in chunk_text
    ]
    return len(containing_chunks) == 1


def fallback_chunks(
    segment: str,
    max_table_rows: int,
    fallback_reason: str,
) -> list[dict[str, object]]:
    """Return deterministic chunks when LLM output is invalid or unavailable."""

    chunks: list[dict[str, object]] = []
    for index, section in enumerate(
        deterministic_table_safe_fallback(segment, max_table_rows=max_table_rows)
    ):
        chunks.append(
            {
                "content": section.content,
                "type": section_type(section),
                "summary": "",
                "has_table": section.has_table,
                "chunk_index": index,
                "fallback": True,
                "fallback_reason": fallback_reason,
            }
        )
    return chunks


def deterministic_table_safe_fallback(
    segment: str,
    max_table_rows: int,
) -> list[HeadingSafeSection]:
    """Split a segment into text/table blocks without LLM assistance."""

    sections: list[HeadingSafeSection] = []
    for block_type, block_text in split_markdown_table_blocks(segment):
        if block_type == "table":
            for table_chunk in split_long_table_block(block_text, max_table_rows):
                sections.append(
                    HeadingSafeSection(
                        content=table_chunk.strip(),
                        has_table=True,
                        split_method="llm_fallback_table",
                    )
                )
            continue
        sections.append(
            HeadingSafeSection(
                content=block_text.strip(),
                has_table=contains_table(block_text),
                split_method="llm_fallback_text",
            )
        )
    return [section for section in sections if section.content]


def section_type(section: HeadingSafeSection) -> str:
    """Return a stable chunk type label."""

    if section.has_table and section.split_method.endswith("table"):
        return "table"
    if section.has_table:
        return "mixed"
    return "text"


def contains_table(text: str) -> bool:
    """Return True when text contains Markdown table rows."""

    return any(is_markdown_table_line(line) for line in text.splitlines())
