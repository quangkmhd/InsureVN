"""Helpers for LlamaIndex node parser based chunking strategies."""

from __future__ import annotations

from typing import Any

from llama_index.core import Document

from src.eval.chunking.base import chunks_from_parts
from src.eval.models import CorpusDocument, JsonDict, TextChunk


def make_llamaindex_document(document: CorpusDocument) -> Document:
    """Create a LlamaIndex document with source metadata."""

    return Document(
        text=document.text,
        metadata={
            "source_path": document.source_path,
            "provider": document.provider,
        },
    )


def chunks_from_llamaindex_nodes(
    document: CorpusDocument,
    strategy_name: str,
    nodes: list[Any],
) -> list[TextChunk]:
    """Convert LlamaIndex nodes into local chunks."""

    parts: list[tuple[str, JsonDict]] = []
    for node in nodes:
        content = node.get_content()
        if not content.strip():
            continue
        metadata = sanitize_metadata(getattr(node, "metadata", {}))
        metadata["llamaindex_node_id"] = str(getattr(node, "node_id", ""))
        metadata["llamaindex_node_type"] = node.__class__.__name__
        parts.append((content, metadata))
    return chunks_from_parts(document, strategy_name, parts)


def sanitize_metadata(metadata: dict[str, Any]) -> JsonDict:
    """Convert LlamaIndex metadata to JSON-safe primitive values."""

    sanitized: JsonDict = {}
    for key, value in metadata.items():
        if isinstance(value, str | int | float | bool) or value is None:
            sanitized[key] = value
        elif isinstance(value, list | tuple):
            sanitized[key] = [str(item) for item in value]
        elif isinstance(value, dict):
            sanitized[key] = {
                str(item_key): str(item_value) for item_key, item_value in value.items()
            }
        else:
            sanitized[key] = str(value)
    return sanitized
