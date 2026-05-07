from __future__ import annotations

import math
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_ollama import OllamaEmbeddings
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.core.config import settings

router = APIRouter()

SEMANTIC_EMBEDDING_CACHE_SIZE = 2_048
SemanticBreakpointType = Literal[
    "percentile",
    "standard_deviation",
    "interquartile",
    "gradient",
]
CHUNKING_COMPARE_HTML_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "08_chunking_compare"
    / "00_chunking_compare.html"
)
SEMANTIC_BREAKPOINT_TYPES: set[str] = {
    "percentile",
    "standard_deviation",
    "interquartile",
    "gradient",
}
_SEMANTIC_EMBEDDING_CACHE: OrderedDict[tuple[str, int, str], list[float]] = (
    OrderedDict()
)
_SEMANTIC_EMBEDDING_LOCK = Lock()


class SemanticChunkRequest(BaseModel):
    """Request body for LangChain semantic chunking."""

    text: str = Field(min_length=1, max_length=50_000)
    chunk_size_tokens: int = Field(default=400, ge=50, le=2_000)
    overlap_tokens: int = Field(default=0, ge=0, le=500)
    breakpoint_threshold_type: SemanticBreakpointType = Field(default="interquartile")
    breakpoint_threshold_amount: float | None = Field(default=1.5, gt=0)
    min_chunk_chars: int = Field(default=350, ge=1, le=10_000)


class SemanticChunk(BaseModel):
    """One semantic chunk mapped back to source character offsets."""

    text: str
    start: int
    end: int
    tokens: int
    issues: list[str] = Field(default_factory=list)


class SemanticChunkResponse(BaseModel):
    """LangChain semantic chunking response."""

    strategy: str
    provider: str
    model: str
    chunks: list[SemanticChunk]


class SemanticOllamaEmbeddingProvider(Embeddings):
    """Ollama embeddings tuned for LangChain semantic chunking."""

    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
    ) -> None:
        """Initialize the underlying LangChain Ollama embedding client."""
        self._model_name = model_name
        self._ollama_embeddings = OllamaEmbeddings(
            model=model_name,
            base_url=base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed source sentences for semantic breakpoint detection."""
        embeddings: list[list[float] | None] = [None] * len(texts)
        uncached_texts: list[str] = []
        uncached_indexes: list[int] = []

        for index, text in enumerate(texts):
            cache_key = self._cache_key(text)
            cached_embedding = _get_cached_embedding(cache_key)
            if cached_embedding is None:
                uncached_texts.append(text)
                uncached_indexes.append(index)
            else:
                embeddings[index] = cached_embedding

        if uncached_texts:
            uncached_embeddings = self._ollama_embeddings.embed_documents(
                uncached_texts
            )
            if len(uncached_embeddings) != len(uncached_texts):
                raise RuntimeError(
                    "Ollama embedding response did not return one vector per text."
                )
            for index, text, embedding in zip(
                uncached_indexes,
                uncached_texts,
                uncached_embeddings,
                strict=True,
            ):
                cache_key = self._cache_key(text)
                _cache_embedding(cache_key, embedding)
                embeddings[index] = list(embedding)

        return [list(embedding) for embedding in embeddings if embedding is not None]

    def embed_query(self, text: str) -> list[float]:
        """Embed one query string with the configured Ollama embedding model."""
        cache_key = self._cache_key(text)
        cached_embedding = _get_cached_embedding(cache_key)
        if cached_embedding is not None:
            return cached_embedding

        embedding = self._ollama_embeddings.embed_query(text)
        _cache_embedding(cache_key, embedding)
        return list(embedding)

    def _cache_key(self, text: str) -> tuple[str, int, str]:
        return (self._model_name, 0, text)


def build_semantic_embedding_provider(request: Request) -> Embeddings:
    """Build the configured embedding provider for semantic chunking."""
    origin = request.headers.get("origin")
    if settings.SEMANTIC_CHUNKING_EMBEDDING_PROVIDER != "ollama":
        raise HTTPException(
            status_code=503,
            detail=(
                "Only ollama is supported for semantic chunking embeddings. "
                "Set SEMANTIC_CHUNKING_EMBEDDING_PROVIDER=ollama."
            ),
            headers=_cors_headers(origin),
        )
    try:
        return SemanticOllamaEmbeddingProvider(
            model_name=settings.SEMANTIC_CHUNKING_EMBEDDING_MODEL,
            base_url=settings.SEMANTIC_CHUNKING_OLLAMA_BASE_URL,
        )
    except Exception as exc:
        detail = f"Semantic embedding provider is not configured: {type(exc).__name__}"
        raise HTTPException(
            status_code=503,
            detail=detail,
            headers=_cors_headers(origin),
        ) from exc


@router.get("/tools/chunking-compare", include_in_schema=False)
async def chunking_compare_tool() -> FileResponse:
    """Serve the chunking comparison HTML from the FastAPI app."""
    return FileResponse(CHUNKING_COMPARE_HTML_PATH)


@router.options("/chunking/semantic", include_in_schema=False)
async def semantic_chunk_options(request: Request, response: Response) -> Response:
    """Allow local static HTML to call the semantic chunking endpoint."""
    _set_cors_headers(response, request.headers.get("origin"))
    return response


@router.post("/chunking/semantic", response_model=SemanticChunkResponse)
async def semantic_chunk(
    chunk_request: SemanticChunkRequest,
    http_request: Request,
    response: Response,
    embedding_provider: Annotated[
        Embeddings, Depends(build_semantic_embedding_provider)
    ],
) -> SemanticChunkResponse:
    """Split text with LangChain SemanticChunker and local embeddings."""
    origin = http_request.headers.get("origin")
    _set_cors_headers(response, origin)
    try:
        raw_chunks = await run_in_threadpool(
            _split_with_langchain_semantic_chunker,
            request=chunk_request,
            embedding_provider=embedding_provider,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
            headers=_cors_headers(origin),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Semantic chunking provider failed: {type(exc).__name__}",
            headers=_cors_headers(origin),
        ) from exc

    chunks = _map_chunks_to_source(raw_chunks, chunk_request.text)
    return SemanticChunkResponse(
        strategy="langchain_semantic",
        provider=settings.SEMANTIC_CHUNKING_EMBEDDING_PROVIDER,
        model=settings.SEMANTIC_CHUNKING_EMBEDDING_MODEL,
        chunks=chunks,
    )


def _split_with_langchain_semantic_chunker(
    *,
    request: SemanticChunkRequest,
    embedding_provider: Embeddings,
) -> list[str]:
    target_chars = request.chunk_size_tokens * 4
    number_of_chunks = None
    if len(request.text) > target_chars:
        number_of_chunks = max(2, math.ceil(len(request.text) / target_chars))

    splitter = SemanticChunker(
        embeddings=embedding_provider,
        breakpoint_threshold_type=request.breakpoint_threshold_type,
        breakpoint_threshold_amount=request.breakpoint_threshold_amount,
        number_of_chunks=number_of_chunks,
        sentence_split_regex=r"(?<=[.!?])\s+|\n{2,}",
        min_chunk_size=request.min_chunk_chars,
    )
    return [
        chunk.strip() for chunk in splitter.split_text(request.text) if chunk.strip()
    ]


def _map_chunks_to_source(
    raw_chunks: list[str], source_text: str
) -> list[SemanticChunk]:
    chunks: list[SemanticChunk] = []
    cursor = 0
    for raw_chunk in raw_chunks:
        start = source_text.find(raw_chunk, cursor)
        if start < 0:
            start = source_text.find(raw_chunk)
        if start < 0:
            start = cursor
        end = min(len(source_text), start + len(raw_chunk))
        cursor = max(cursor, end)
        chunks.append(
            SemanticChunk(
                text=raw_chunk,
                start=start,
                end=end,
                tokens=_estimate_tokens(raw_chunk),
                issues=["langchain semantic"],
            )
        )
    return chunks


def _estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4) if text else 0


def _get_cached_embedding(cache_key: tuple[str, int, str]) -> list[float] | None:
    with _SEMANTIC_EMBEDDING_LOCK:
        cached_embedding = _SEMANTIC_EMBEDDING_CACHE.get(cache_key)
        if cached_embedding is None:
            return None
        _SEMANTIC_EMBEDDING_CACHE.move_to_end(cache_key)
        return list(cached_embedding)


def _cache_embedding(cache_key: tuple[str, int, str], embedding: list[float]) -> None:
    with _SEMANTIC_EMBEDDING_LOCK:
        _SEMANTIC_EMBEDDING_CACHE[cache_key] = list(embedding)
        _SEMANTIC_EMBEDDING_CACHE.move_to_end(cache_key)
        while len(_SEMANTIC_EMBEDDING_CACHE) > SEMANTIC_EMBEDDING_CACHE_SIZE:
            _SEMANTIC_EMBEDDING_CACHE.popitem(last=False)


def _cors_headers(origin: str | None) -> dict[str, str]:
    if not _is_allowed_cors_origin(origin):
        return {}
    return {
        "Access-Control-Allow-Origin": origin or "",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Vary": "Origin",
    }


def _is_allowed_cors_origin(origin: str | None) -> bool:
    if not origin:
        return False
    if origin == "null":
        return True
    parsed_origin = urlparse(origin)
    return parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {
        "localhost",
        "127.0.0.1",
    }


def _set_cors_headers(response: Response, origin: str | None) -> None:
    for header_name, header_value in _cors_headers(origin).items():
        response.headers[header_name] = header_value
