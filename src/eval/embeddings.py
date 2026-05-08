"""Embedding adapters used by chunking benchmarks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from sentence_transformers import SentenceTransformer

from src.eval.embedding_cache import (
    EmbeddingCache,
    build_embedding_requests,
    embedding_config_hash,
)


class BenchmarkEmbeddings(Protocol):
    """Embedding interface required by the benchmark vector store."""

    batch_size: int

    @property
    def dimension(self) -> int:
        """Return vector dimension."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed one query string."""
        ...


class SentenceTransformerEmbeddings(Embeddings):
    """LangChain Embeddings adapter backed by SentenceTransformers."""

    def __init__(
        self,
        model_name: str,
        batch_size: int = 64,
        normalize_embeddings: bool = True,
        device: str | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.device = device
        self.cache = cache
        self.config_hash = embedding_config_hash(
            {
                "adapter": "sentence_transformers",
                "normalize_embeddings": normalize_embeddings,
            }
        )
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        """Return embedding dimension for collection creation."""

        if self._dimension is None:
            self._dimension = len(self.embed_query("dimension probe"))
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""

        return self._encode(texts, purpose="retrieval_document")

    def embed_query(self, text: str) -> list[float]:
        """Embed one query string."""

        return self._encode([text], purpose="retrieval_query")[0]

    def _encode(self, texts: Sequence[str], purpose: str) -> list[list[float]]:
        text_batch = list(texts)
        if self.cache is None:
            return self._encode_uncached(text_batch)
        requests = build_embedding_requests(
            provider="sentence_transformers",
            model=self.model_name,
            purpose=purpose,
            config_hash=self.config_hash,
            texts=text_batch,
        )
        cached_vectors = self.cache.get_many(
            requests,
            expected_dimension=self._dimension,
        )
        vectors: list[list[float] | None] = [None] * len(text_batch)
        missing_indices: list[int] = []
        missing_texts: list[str] = []
        for index, request in enumerate(requests):
            vector = cached_vectors.get(request.cache_key)
            if vector is None:
                missing_indices.append(index)
                missing_texts.append(text_batch[index])
            else:
                vectors[index] = vector
        if missing_texts:
            embedded_texts = self._encode_uncached(missing_texts)
            self.cache.set_many(
                [
                    (requests[index], vector)
                    for index, vector in zip(
                        missing_indices,
                        embedded_texts,
                        strict=True,
                    )
                ]
            )
            for index, vector in zip(missing_indices, embedded_texts, strict=True):
                vectors[index] = vector
        concrete_vectors = require_complete_vectors(vectors)
        if concrete_vectors and self._dimension is None:
            self._dimension = len(concrete_vectors[0])
        return concrete_vectors

    def _encode_uncached(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings = self._get_model().encode(
            list(texts),
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model


class CachedEmbeddings(Embeddings):
    """Cache wrapper for generic LangChain embeddings."""

    def __init__(
        self,
        embeddings: Embeddings,
        cache: EmbeddingCache | None,
        provider: str,
        model_name: str,
        config: dict[str, object],
        document_purpose: str,
        query_purpose: str,
        batch_size: int = 64,
    ) -> None:
        self.embeddings = embeddings
        self.cache = cache
        self.provider = provider
        self.model_name = model_name
        self.config_hash = embedding_config_hash(config)
        self.document_purpose = document_purpose
        self.query_purpose = query_purpose
        self.batch_size = batch_size
        self._dimension: int | None = None

    @property
    def dimension(self) -> int:
        """Return embedding dimension for collection creation."""

        if self._dimension is None:
            self._dimension = len(self.embed_query("dimension probe"))
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents with cache."""

        return self._embed(
            texts=texts,
            purpose=self.document_purpose,
            embed=lambda missing_texts: self.embeddings.embed_documents(missing_texts),
        )

    def embed_query(self, text: str) -> list[float]:
        """Embed one query with cache."""

        return self._embed(
            texts=[text],
            purpose=self.query_purpose,
            embed=lambda missing_texts: [self.embeddings.embed_query(missing_texts[0])],
        )[0]

    def _embed(
        self,
        texts: list[str],
        purpose: str,
        embed: Callable[[list[str]], list[list[float]]],
    ) -> list[list[float]]:
        if self.cache is None:
            return embed(texts)
        requests = build_embedding_requests(
            provider=self.provider,
            model=self.model_name,
            purpose=purpose,
            config_hash=self.config_hash,
            texts=texts,
        )
        cached_vectors = self.cache.get_many(
            requests,
            expected_dimension=self._dimension,
        )
        vectors: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []
        for index, request in enumerate(requests):
            vector = cached_vectors.get(request.cache_key)
            if vector is None:
                missing_indices.append(index)
                missing_texts.append(texts[index])
            else:
                vectors[index] = vector
        if missing_texts:
            embedded_texts = embed(missing_texts)
            self.cache.set_many(
                [
                    (requests[index], vector)
                    for index, vector in zip(
                        missing_indices,
                        embedded_texts,
                        strict=True,
                    )
                ]
            )
            for index, vector in zip(missing_indices, embedded_texts, strict=True):
                vectors[index] = vector
        concrete_vectors = require_complete_vectors(vectors)
        if concrete_vectors and self._dimension is None:
            self._dimension = len(concrete_vectors[0])
        return concrete_vectors


def build_semantic_chunking_embeddings(
    provider: str,
    model_name: str,
    ollama_base_url: str,
    batch_size: int,
    device: str | None = None,
    cache: EmbeddingCache | None = None,
) -> Embeddings:
    """Build embeddings used only by semantic chunking strategies."""

    normalized_provider = provider.strip().lower()
    if normalized_provider == "ollama":
        return CachedEmbeddings(
            embeddings=OllamaEmbeddings(
                model=model_name,
                base_url=ollama_base_url,
            ),
            cache=cache,
            provider="ollama",
            model_name=model_name,
            config={
                "adapter": "langchain_ollama",
                "base_url": ollama_base_url,
            },
            document_purpose="semantic_breakpoint_document",
            query_purpose="semantic_breakpoint_query",
            batch_size=batch_size,
        )
    if normalized_provider in {"sentence_transformer", "sentence_transformers"}:
        return SentenceTransformerEmbeddings(
            model_name=model_name,
            batch_size=batch_size,
            device=device,
            cache=cache,
        )
    msg = (
        "Unsupported SEMANTIC_CHUNKING_EMBEDDING_PROVIDER="
        f"{provider!r}. Supported providers: ollama, sentence_transformers."
    )
    raise ValueError(msg)


def require_complete_vectors(
    vectors: list[list[float] | None],
) -> list[list[float]]:
    """Return vectors after verifying the batch has no gaps."""

    if any(vector is None for vector in vectors):
        msg = "Embedding cache wrapper did not produce every requested vector."
        raise ValueError(msg)
    return [vector for vector in vectors if vector is not None]
