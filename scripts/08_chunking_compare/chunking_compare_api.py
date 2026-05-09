from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Annotated, Any, Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

router = APIRouter()

SEMANTIC_EMBEDDING_CACHE_SIZE = 2_048
LLM_CHUNKING_UNIT_MAX_CHARS = 1_800
LLM_CHUNKING_PROMPT_VERSION = "v2"
ADAPTIVE_DENSITY_LARGE_BLOCK_TARGET_CHARS = 1_400
ADAPTIVE_DENSITY_MIN_CHARS = 500
CHUNKING_COMPARE_HTML_PATH = Path(__file__).with_name("00_chunking_compare.html")
SemanticBreakpointType = Literal[
    "percentile",
    "standard_deviation",
    "interquartile",
    "gradient",
]
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
_LLM_CHUNKING_CACHE_LOCK = Lock()
_ADAPTIVE_DENSITY_STOP_WORDS = {
    "anh",
    "bao",
    "bang",
    "benh",
    "cac",
    "cach",
    "can",
    "cap",
    "chi",
    "cho",
    "co",
    "con",
    "cua",
    "cung",
    "du",
    "duoc",
    "giay",
    "han",
    "hay",
    "hoac",
    "khach",
    "khi",
    "khong",
    "la",
    "lam",
    "mau",
    "mot",
    "nay",
    "nguoi",
    "nhung",
    "noi",
    "phai",
    "qua",
    "quy",
    "sau",
    "suc",
    "tai",
    "theo",
    "thi",
    "thong",
    "tin",
    "trong",
    "tu",
    "va",
    "ve",
    "voi",
}


import sys
from pathlib import Path

# Add REPO_ROOT to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.config import settings as app_settings


class ChunkingCompareSettings:
    """Settings scoped to the local chunking comparison playground."""

    def __init__(self) -> None:
        """Load script settings from the centralized app settings."""
        self.SEMANTIC_CHUNKING_EMBEDDING_PROVIDER: str = os.getenv(
            "SEMANTIC_CHUNKING_EMBEDDING_PROVIDER", "ollama"
        )
        self.SEMANTIC_CHUNKING_EMBEDDING_MODEL: str = os.getenv(
            "SEMANTIC_CHUNKING_EMBEDDING_MODEL", "bge-m3"
        )
        self.SEMANTIC_CHUNKING_OLLAMA_BASE_URL: str = os.getenv(
            "SEMANTIC_CHUNKING_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        )
        
        # Delegate to centralized app settings
        self.LLM_CHUNKING_PROVIDER: str = app_settings.LLM_CHUNKING_PROVIDER
        self.LLM_CHUNKING_MODEL: str = app_settings.LLM_CHUNKING_MODEL
        self.LLM_CHUNKING_API_KEY: str = app_settings.LLM_CHUNKING_API_KEY
        self.LLM_CHUNKING_BASE_URL: str = app_settings.LLM_CHUNKING_BASE_URL
        
        self.LLM_CHUNKING_MAX_INPUT_CHARS: int = app_settings.LLM_CHUNKING_MAX_INPUT_CHARS
        self.LLM_CHUNKING_TIMEOUT_SECONDS: float = app_settings.LLM_CHUNKING_TIMEOUT_SECONDS
        self.LLM_CHUNKING_CACHE_PATH: Path = Path(app_settings.LLM_CHUNKING_CACHE_PATH)
        self.LLM_CHUNKING_UNIT_PREVIEW_CHARS: int = app_settings.LLM_CHUNKING_UNIT_PREVIEW_CHARS
        
        self.GOOGLE_API_KEY: str = app_settings.GOOGLE_API_KEY
        self.GEMINI_API_KEY: str = app_settings.GEMINI_API_KEY
        self.LLM_API_KEY: str = app_settings.LLM_API_KEY


settings = ChunkingCompareSettings()


class SemanticChunkRequest(BaseModel):
    """Request body for LangChain semantic chunking."""

    text: str = Field(min_length=1, max_length=50_000)
    chunk_size_tokens: int = Field(default=400, ge=50, le=2_000)
    overlap_tokens: int = Field(default=0, ge=0, le=500)
    breakpoint_threshold_type: SemanticBreakpointType = Field(default="interquartile")
    breakpoint_threshold_amount: float | None = Field(default=1.5, gt=0)
    min_chunk_chars: int = Field(default=350, ge=1, le=10_000)


class LLMChunkRequest(BaseModel):
    """Request body for LLM-guided chunking."""

    text: str = Field(min_length=1, max_length=50_000)
    chunk_size_tokens: int = Field(default=400, ge=50, le=2_000)


class LateChunkRequest(BaseModel):
    """Request body for benchmark-style late chunking."""

    text: str = Field(min_length=1, max_length=50_000)
    chunk_size_tokens: int = Field(default=400, ge=50, le=2_000)
    overlap_tokens: int = Field(default=50, ge=0, le=500)


class AdaptiveDensityChunkRequest(BaseModel):
    """Request body for adaptive semantic density chunking."""

    text: str = Field(min_length=1, max_length=50_000)
    chunk_size_tokens: int = Field(default=400, ge=50, le=2_000)


class SemanticChunk(BaseModel):
    """One chunk mapped back to source character offsets."""

    text: str
    start: int
    end: int
    tokens: int
    issues: list[str] = Field(default_factory=list)
    index_text: str | None = None
    display_text: str | None = None


class SemanticChunkResponse(BaseModel):
    """Chunking response returned by all playground strategies."""

    strategy: str
    provider: str
    model: str
    chunks: list[SemanticChunk]


class LLMChunkBoundary(BaseModel):
    """One inclusive source-unit range selected by the LLM."""

    start_unit: int = Field(ge=1)
    end_unit: int = Field(ge=1)


class LLMChunkingPlan(BaseModel):
    """Boundary response expected from the LLM chunking model."""

    chunks: list[LLMChunkBoundary] = Field(min_length=1)


class LLMChunkingUnit(BaseModel):
    """One source unit exposed to the LLM for boundary selection."""

    unit_id: int
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class AdaptiveDensityUnit:
    """One source unit annotated for adaptive semantic density splitting."""

    block_id: int
    text: str
    start: int
    end: int
    block_type: str
    heading: str


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


class LocalHashingEmbeddingProvider(Embeddings):
    """Deterministic local embeddings used when Ollama embedding runners fail."""

    def __init__(self, *, dimensions: int = 128) -> None:
        """Initialize a fixed-size lexical hashing embedding provider."""
        self._dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents with local lexical hashing."""
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed one query with local lexical hashing."""
        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for term in _content_terms(text):
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class LLMChunkingProvider:
    """Provider interface for LLM-guided chunking."""

    def split_text(self, request: LLMChunkRequest) -> list[str]:
        """Split text into exact source chunks."""
        raise NotImplementedError


class GoogleGenAILLMChunkingProvider(LLMChunkingProvider):
    """Google GenAI REST provider for LLM-guided source chunking."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: int,
        cache_path: Path,
        unit_preview_chars: int,
    ) -> None:
        """Initialize Google GenAI request settings."""
        self._api_key = api_key
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._cache_path = cache_path
        self._unit_preview_chars = unit_preview_chars

    def split_text(self, request: LLMChunkRequest) -> list[str]:
        """Ask the configured model for contiguous source-unit boundaries."""
        cache_key = _llm_chunking_cache_key(
            model_name=self._model_name,
            request=request,
            unit_preview_chars=self._unit_preview_chars,
        )
        cached_chunks = _get_cached_llm_chunks(self._cache_path, cache_key)
        if cached_chunks is not None:
            return cached_chunks

        target_chars = request.chunk_size_tokens * 4
        units = _build_llm_chunking_units(request.text)
        prompt = _build_llm_chunking_prompt(
            units,
            target_chars=target_chars,
            preview_chars=self._unit_preview_chars,
        )
        response_text = self._generate_text(prompt)
        chunking_plan = _parse_llm_chunking_response(response_text)
        chunks = _chunks_from_llm_boundaries(
            request.text,
            units,
            chunking_plan.chunks,
        )
        _cache_llm_chunks(self._cache_path, cache_key, chunks)
        return chunks

    def _generate_text(self, prompt: str) -> str:
        query = urllib.parse.urlencode({"key": self._api_key})
        model_name = urllib.parse.quote(self._model_name, safe="")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?{query}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self._timeout_seconds,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return _google_genai_text_from_payload(payload)
            except urllib.error.HTTPError as exc:
                if attempt == 3 or exc.code not in {429, 500, 503}:
                    raise RuntimeError(
                        f"Google GenAI request failed with HTTP {exc.code}."
                    ) from exc
                time.sleep(attempt * 1.5)
        raise RuntimeError("Google GenAI did not return a chunking response.")


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


def build_llm_chunking_provider(request: Request) -> LLMChunkingProvider:
    """Build the configured provider for LLM-guided chunking."""
    origin = request.headers.get("origin")
    if settings.LLM_CHUNKING_PROVIDER != "google_genai":
        raise HTTPException(
            status_code=503,
            detail=(
                "Only google_genai is supported for LLM chunking. "
                "Set LLM_CHUNKING_PROVIDER=google_genai."
            ),
            headers=_cors_headers(origin),
        )

    api_key = settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY or settings.LLM_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "GOOGLE_API_KEY, GEMINI_API_KEY, or LLM_API_KEY is required "
                "for LLM chunking."
            ),
            headers=_cors_headers(origin),
        )

    return GoogleGenAILLMChunkingProvider(
        api_key=api_key,
        model_name=settings.LLM_CHUNKING_MODEL,
        timeout_seconds=settings.LLM_CHUNKING_TIMEOUT_SECONDS,
        cache_path=settings.LLM_CHUNKING_CACHE_PATH,
        unit_preview_chars=settings.LLM_CHUNKING_UNIT_PREVIEW_CHARS,
    )


@router.get("/tools/chunking-compare", include_in_schema=False)
async def chunking_compare_tool() -> FileResponse:
    """Serve the chunking comparison HTML from the FastAPI app."""
    return FileResponse(CHUNKING_COMPARE_HTML_PATH)


@router.options("/chunking/semantic", include_in_schema=False)
async def semantic_chunk_options(request: Request) -> Response:
    """Allow local static HTML to call the semantic chunking endpoint."""
    return Response(
        status_code=204, headers=_cors_headers(request.headers.get("origin"))
    )


@router.options("/chunking/llm", include_in_schema=False)
async def llm_chunk_options(request: Request) -> Response:
    """Allow local static HTML to call the LLM chunking endpoint."""
    return Response(
        status_code=204, headers=_cors_headers(request.headers.get("origin"))
    )


@router.options("/chunking/late", include_in_schema=False)
async def late_chunk_options(request: Request) -> Response:
    """Allow local static HTML to call the late chunking endpoint."""
    return Response(
        status_code=204, headers=_cors_headers(request.headers.get("origin"))
    )


@router.options("/chunking/adaptive-density", include_in_schema=False)
async def adaptive_density_chunk_options(request: Request) -> Response:
    """Allow local static HTML to call the adaptive density chunking endpoint."""
    return Response(
        status_code=204, headers=_cors_headers(request.headers.get("origin"))
    )


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
    provider_name = settings.SEMANTIC_CHUNKING_EMBEDDING_PROVIDER
    model_name = settings.SEMANTIC_CHUNKING_EMBEDDING_MODEL
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
        if isinstance(embedding_provider, SemanticOllamaEmbeddingProvider):
            try:
                raw_chunks = await run_in_threadpool(
                    _split_with_langchain_semantic_chunker,
                    request=chunk_request,
                    embedding_provider=LocalHashingEmbeddingProvider(),
                )
                provider_name = "local_hashing_fallback"
                model_name = "lexical_hash_128"
            except Exception as fallback_exc:
                detail = (
                    "Semantic chunking provider failed: "
                    f"{type(exc).__name__}: {str(exc)[:240]}; "
                    "local fallback failed: "
                    f"{type(fallback_exc).__name__}"
                )
                raise HTTPException(
                    status_code=502,
                    detail=detail,
                    headers=_cors_headers(origin),
                ) from fallback_exc
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Semantic chunking provider failed: {type(exc).__name__}",
                headers=_cors_headers(origin),
            ) from exc

    chunks = _map_chunks_to_source(
        raw_chunks,
        chunk_request.text,
        issue_label="langchain semantic",
    )
    return SemanticChunkResponse(
        strategy="langchain_semantic",
        provider=provider_name,
        model=model_name,
        chunks=chunks,
    )


@router.post("/chunking/adaptive-density", response_model=SemanticChunkResponse)
async def adaptive_density_chunk(
    chunk_request: AdaptiveDensityChunkRequest,
    http_request: Request,
    response: Response,
) -> SemanticChunkResponse:
    """Split text with benchmark adaptive semantic density chunking."""
    origin = http_request.headers.get("origin")
    _set_cors_headers(response, origin)
    try:
        chunks = await run_in_threadpool(
            _split_with_adaptive_semantic_density_chunker,
            request=chunk_request,
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
            detail=f"Adaptive density chunking failed: {type(exc).__name__}",
            headers=_cors_headers(origin),
        ) from exc

    return SemanticChunkResponse(
        strategy="adaptive_semantic_density",
        provider="benchmark_health_chunking",
        model="lexical_density_jaccard",
        chunks=chunks,
    )


@router.post("/chunking/late", response_model=SemanticChunkResponse)
async def late_chunk(
    chunk_request: LateChunkRequest,
    http_request: Request,
    response: Response,
) -> SemanticChunkResponse:
    """Split text with benchmark late chunking context augmentation."""
    origin = http_request.headers.get("origin")
    _set_cors_headers(response, origin)
    try:
        chunks = await run_in_threadpool(
            _split_with_late_chunker,
            request=chunk_request,
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
            detail=f"Late chunking failed: {type(exc).__name__}",
            headers=_cors_headers(origin),
        ) from exc

    return SemanticChunkResponse(
        strategy="late_chunking",
        provider="benchmark_health_chunking",
        model="recursive_boundary_contextual_index",
        chunks=chunks,
    )


@router.post("/chunking/llm", response_model=SemanticChunkResponse)
async def llm_chunk(
    chunk_request: LLMChunkRequest,
    http_request: Request,
    response: Response,
    llm_chunking_provider: Annotated[
        LLMChunkingProvider, Depends(build_llm_chunking_provider)
    ],
) -> SemanticChunkResponse:
    """Split text with an LLM-guided chunking provider."""
    origin = http_request.headers.get("origin")
    _set_cors_headers(response, origin)
    try:
        if len(chunk_request.text) > settings.LLM_CHUNKING_MAX_INPUT_CHARS:
            raise ValueError(
                "LLM chunking input exceeds "
                f"{settings.LLM_CHUNKING_MAX_INPUT_CHARS} characters. "
                "Use a smaller sample or raise LLM_CHUNKING_MAX_INPUT_CHARS."
            )
        raw_chunks = await run_in_threadpool(
            llm_chunking_provider.split_text,
            chunk_request,
        )
        chunks = _map_chunks_to_source(
            raw_chunks,
            chunk_request.text,
            issue_label="llm chunking",
            require_exact=True,
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
            detail=f"LLM chunking provider failed: {type(exc).__name__}",
            headers=_cors_headers(origin),
        ) from exc

    return SemanticChunkResponse(
        strategy="llm_chunking",
        provider=settings.LLM_CHUNKING_PROVIDER,
        model=settings.LLM_CHUNKING_MODEL,
        chunks=chunks,
    )


def _split_with_langchain_semantic_chunker(
    *,
    request: SemanticChunkRequest,
    embedding_provider: Embeddings,
) -> list[str]:
    if request.breakpoint_threshold_type not in SEMANTIC_BREAKPOINT_TYPES:
        raise ValueError("Unsupported semantic breakpoint threshold type.")
    splitter_kwargs: dict[str, Any] = {
        "embeddings": embedding_provider,
        "breakpoint_threshold_type": request.breakpoint_threshold_type,
        "min_chunk_size": request.min_chunk_chars,
    }
    if request.breakpoint_threshold_amount is not None:
        splitter_kwargs["breakpoint_threshold_amount"] = (
            request.breakpoint_threshold_amount
        )
    semantic_chunker = SemanticChunker(**splitter_kwargs)
    chunks = [chunk.strip() for chunk in semantic_chunker.split_text(request.text)]
    return [chunk for chunk in chunks if chunk]


def _split_with_late_chunker(*, request: LateChunkRequest) -> list[SemanticChunk]:
    chunk_size_chars = request.chunk_size_tokens * 4
    overlap_chars = request.overlap_tokens * 4
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    raw_chunks = [chunk.strip() for chunk in splitter.split_text(request.text) if chunk]
    source_chunks = _map_chunks_to_source(
        raw_chunks,
        request.text,
        issue_label="late chunking contextual index",
    )
    document_terms = ", ".join(_extract_keywords(request.text, limit=8))
    for chunk in source_chunks:
        section_context = _section_context_for_offset(request.text, chunk.start)
        context_lines = []
        if section_context:
            context_lines.append(f"Section context: {section_context}")
        if document_terms:
            context_lines.append(f"Document terms: {document_terms}")
        context_lines.append(chunk.text)
        chunk.display_text = chunk.text
        chunk.index_text = "\n".join(context_lines)
        chunk.text = chunk.index_text
    return source_chunks


def _split_with_adaptive_semantic_density_chunker(
    *,
    request: AdaptiveDensityChunkRequest,
) -> list[SemanticChunk]:
    units = _adaptive_density_units(request.text)
    if not units:
        return []
    target_chars = max(
        ADAPTIVE_DENSITY_MIN_CHARS,
        min(ADAPTIVE_DENSITY_LARGE_BLOCK_TARGET_CHARS, request.chunk_size_tokens * 4),
    )
    chunks: list[SemanticChunk] = []
    current_units: list[AdaptiveDensityUnit] = []
    current_terms: set[str] = set()
    current_chars = 0

    for unit in units:
        unit_terms = set(_content_terms(unit.text))
        heading_boundary = unit.block_type == "heading" and current_chars >= 350
        semantic_shift = (
            bool(current_terms)
            and bool(unit_terms)
            and _jaccard_similarity(current_terms, unit_terms) < 0.08
            and current_chars >= ADAPTIVE_DENSITY_MIN_CHARS
        )
        too_large = current_chars + len(unit.text) > target_chars * 1.35
        if current_units and (heading_boundary or semantic_shift or too_large):
            chunks.append(_chunk_from_adaptive_units(current_units, request.text))
            current_units = []
            current_terms = set()
            current_chars = 0
        current_units.append(unit)
        current_terms.update(unit_terms)
        current_chars += len(unit.text)
    if current_units:
        chunks.append(_chunk_from_adaptive_units(current_units, request.text))
    return chunks


def _build_llm_chunking_units(text: str) -> list[LLMChunkingUnit]:
    units: list[LLMChunkingUnit] = []
    paragraph_re = re.compile(r"(?:.+(?:\n|$))(?:(?:[ \t]*\n)+|$)")
    for match in paragraph_re.finditer(text):
        if not match.group(0).strip():
            continue
        for start, end in _split_large_source_span(text, match.start(), match.end()):
            unit_text = text[start:end].strip()
            if unit_text:
                units.append(
                    LLMChunkingUnit(
                        unit_id=len(units) + 1,
                        start=start,
                        end=end,
                        text=unit_text,
                    )
                )
    if not units and text.strip():
        units.append(
            LLMChunkingUnit(
                unit_id=1,
                start=0,
                end=len(text),
                text=text.strip(),
            )
        )
    return units


def _split_large_source_span(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if end - start <= LLM_CHUNKING_UNIT_MAX_CHARS:
        return [(start, end)]
    spans: list[tuple[int, int]] = []
    current_start = start
    current_end = start
    for line in text[start:end].splitlines(keepends=True):
        line_end = current_end + len(line)
        if (
            line_end - current_start > LLM_CHUNKING_UNIT_MAX_CHARS
            and current_end > current_start
        ):
            spans.append((current_start, current_end))
            current_start = current_end
        current_end = line_end
    if current_end > current_start:
        spans.append((current_start, current_end))
    return spans


def _build_llm_chunking_prompt(
    units: list[LLMChunkingUnit],
    *,
    target_chars: int,
    preview_chars: int,
) -> str:
    unit_payload = [
        {
            "unit_id": unit.unit_id,
            "chars": len(unit.text),
            "preview": _compact_preview(unit.text, limit=preview_chars),
        }
        for unit in units
    ]
    return (
        "You are selecting chunk boundaries for retrieval over Vietnamese health "
        "insurance and technical markdown. Return exactly one JSON object with "
        'shape {"chunks":[{"start_unit":1,"end_unit":3}]}. '
        "Use contiguous, non-overlapping ranges that cover every unit exactly once. "
        "Do not rewrite text. Prefer boundaries at headings, topic shifts, table "
        f"edges, and around {target_chars} characters per chunk.\n\n"
        f"Source units:\n{json.dumps(unit_payload, ensure_ascii=False)}"
    )


def _compact_preview(text: str, *, limit: int) -> str:
    preview = re.sub(r"\s+", " ", text).strip()
    return preview[:limit]


def _parse_llm_chunking_response(response_text: str) -> LLMChunkingPlan:
    data = _parse_json_object(response_text)
    try:
        return LLMChunkingPlan.model_validate(data)
    except Exception as exc:
        raise ValueError(
            "LLM response did not match the expected chunk schema."
        ) from exc


def _chunks_from_llm_boundaries(
    source_text: str,
    units: list[LLMChunkingUnit],
    boundaries: list[LLMChunkBoundary],
) -> list[str]:
    by_id = {unit.unit_id: unit for unit in units}
    expected_unit_id = 1
    chunks: list[str] = []
    for boundary in boundaries:
        if boundary.start_unit != expected_unit_id:
            raise ValueError("LLM chunk ranges must be contiguous and ordered.")
        if boundary.end_unit < boundary.start_unit:
            raise ValueError("LLM chunk range end must be after start.")
        if boundary.end_unit not in by_id:
            raise ValueError("LLM chunk range references an unknown source unit.")
        start_unit = by_id[boundary.start_unit]
        end_unit = by_id[boundary.end_unit]
        chunks.append(source_text[start_unit.start : end_unit.end].strip())
        expected_unit_id = boundary.end_unit + 1
    if expected_unit_id != len(units) + 1:
        raise ValueError("LLM chunk ranges must cover every source unit.")
    return chunks


def _google_genai_text_from_payload(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Google GenAI response did not include candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    ]
    text = "\n".join(part for part in text_parts if part)
    if not text:
        raise ValueError("Google GenAI response did not include answer text.")
    return text


def _parse_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("LLM response did not include a JSON object.")


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _llm_chunking_cache_key(
    *,
    model_name: str,
    request: LLMChunkRequest,
    unit_preview_chars: int,
) -> str:
    return ":".join(
        [
            "llm_chunking",
            LLM_CHUNKING_PROMPT_VERSION,
            model_name,
            str(request.chunk_size_tokens),
            str(unit_preview_chars),
            _source_hash(request.text),
        ]
    )


def _load_json_cache(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json_cache(cache_path: Path, cache: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_cached_llm_chunks(cache_path: Path, cache_key: str) -> list[str] | None:
    with _LLM_CHUNKING_CACHE_LOCK:
        cached_value = _load_json_cache(cache_path).get(cache_key)
    if not isinstance(cached_value, dict):
        return None
    chunks = cached_value.get("chunks")
    if not isinstance(chunks, list) or not all(
        isinstance(chunk, str) for chunk in chunks
    ):
        return None
    return list(chunks)


def _cache_llm_chunks(cache_path: Path, cache_key: str, chunks: list[str]) -> None:
    with _LLM_CHUNKING_CACHE_LOCK:
        cache = _load_json_cache(cache_path)
        cache[cache_key] = {
            "prompt_version": LLM_CHUNKING_PROMPT_VERSION,
            "chunks": chunks,
        }
        _save_json_cache(cache_path, cache)


def _map_chunks_to_source(
    raw_chunks: list[str],
    source_text: str,
    *,
    issue_label: str,
    require_exact: bool = False,
) -> list[SemanticChunk]:
    chunks: list[SemanticChunk] = []
    cursor = 0
    for raw_chunk in raw_chunks:
        chunk_text = raw_chunk.strip()
        if not chunk_text:
            continue
        start = source_text.find(chunk_text, cursor)
        if start < 0:
            start = source_text.find(chunk_text)
        if start < 0:
            if require_exact:
                raise ValueError(
                    "LLM chunking must return exact source substrings; "
                    "one returned chunk was rewritten."
                )
            start = cursor
            end = min(len(source_text), start + len(chunk_text))
        else:
            end = start + len(chunk_text)
        cursor = max(cursor, end)
        chunks.append(
            SemanticChunk(
                text=chunk_text,
                start=start,
                end=end,
                tokens=estimate_tokens(chunk_text),
                issues=[issue_label],
            )
        )
    return chunks


def _adaptive_density_units(text: str) -> list[AdaptiveDensityUnit]:
    units: list[AdaptiveDensityUnit] = []
    current_heading = ""
    paragraph_re = re.compile(r"(?:.+(?:\n|$))(?:(?:[ \t]*\n)+|$)")
    for match in paragraph_re.finditer(text):
        block_text = match.group(0).strip()
        if not block_text:
            continue
        heading_match = re.match(r"^#{1,6}\s+(.+)$", block_text)
        if heading_match:
            current_heading = heading_match.group(1).strip()
        units.append(
            AdaptiveDensityUnit(
                block_id=len(units),
                text=block_text,
                start=match.start(),
                end=match.end(),
                block_type=_classify_block(block_text),
                heading=current_heading,
            )
        )
    if not units and text.strip():
        units.append(
            AdaptiveDensityUnit(
                block_id=0,
                text=text.strip(),
                start=0,
                end=len(text),
                block_type="paragraph",
                heading="",
            )
        )
    return units


def _chunk_from_adaptive_units(
    units: list[AdaptiveDensityUnit],
    source_text: str,
) -> SemanticChunk:
    start = units[0].start
    end = units[-1].end
    chunk_text = source_text[start:end].strip()
    return SemanticChunk(
        text=chunk_text,
        start=start,
        end=end,
        tokens=estimate_tokens(chunk_text),
        issues=["adaptive semantic density"],
    )


def _classify_block(text: str) -> str:
    stripped = text.strip()
    if re.match(r"^#{1,6}\s+", stripped):
        return "heading"
    if "|" in stripped:
        return "table"
    if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", stripped):
        return "list"
    return "paragraph"


def _content_terms(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    terms = re.findall(r"[a-z0-9_]{3,}", normalized)
    return [term for term in terms if term not in _ADAPTIVE_DENSITY_STOP_WORDS]


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _extract_keywords(text: str, *, limit: int) -> list[str]:
    counts: dict[str, int] = {}
    for term in _content_terms(text):
        counts[term] = counts.get(term, 0) + 1
    return [
        term
        for term, _count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
    ]


def _section_context_for_offset(text: str, offset: int) -> str:
    headings: list[str] = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text[:offset], re.M):
        level = len(match.group(1))
        title = match.group(2).strip()
        headings = headings[: level - 1]
        headings.append(title)
    return " > ".join(headings)


def _get_cached_embedding(cache_key: tuple[str, int, str]) -> list[float] | None:
    with _SEMANTIC_EMBEDDING_LOCK:
        cached = _SEMANTIC_EMBEDDING_CACHE.get(cache_key)
        if cached is not None:
            _SEMANTIC_EMBEDDING_CACHE.move_to_end(cache_key)
            return list(cached)
    return None


def _cache_embedding(cache_key: tuple[str, int, str], embedding: list[float]) -> None:
    with _SEMANTIC_EMBEDDING_LOCK:
        _SEMANTIC_EMBEDDING_CACHE[cache_key] = list(embedding)
        _SEMANTIC_EMBEDDING_CACHE.move_to_end(cache_key)
        while len(_SEMANTIC_EMBEDDING_CACHE) > SEMANTIC_EMBEDDING_CACHE_SIZE:
            _SEMANTIC_EMBEDDING_CACHE.popitem(last=False)


def estimate_tokens(text: str) -> int:
    """Estimate token count for playground metrics."""
    return max(1, math.ceil(len(text) / 4))


def _cors_headers(origin: str | None) -> dict[str, str]:
    allow_origin = origin or "*"
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _set_cors_headers(response: Response, origin: str | None) -> None:
    for key, value in _cors_headers(origin).items():
        response.headers[key] = value


app = FastAPI(title="Chunking Compare API")
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
