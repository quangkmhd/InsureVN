"""Embedding adapters used by chunking benchmarks."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from typing import Protocol

import torch
from google import genai
from google.genai import types as genai_types
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from sentence_transformers import SentenceTransformer
from torch.nn import functional as torch_functional
from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig

from src.eval.embeddings.cache import (
    EmbeddingCache,
    build_embedding_requests,
    embedding_config_hash,
)

QWEN3_EMBEDDING_QUERY_PROMPT = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery:"
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
        prepared_text_batch = prepare_sentence_transformer_texts(
            model_name=self.model_name,
            texts=text_batch,
            purpose=purpose,
        )
        if self.cache is None:
            return self._encode_uncached(prepared_text_batch)
        requests = build_embedding_requests(
            provider="sentence_transformers",
            model=self.model_name,
            purpose=purpose,
            config_hash=self.config_hash,
            texts=prepared_text_batch,
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
                missing_texts.append(prepared_text_batch[index])
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


class Qwen3AutoModelEmbeddings(Embeddings):
    """Embedding adapter for Qwen3 embedding models via transformers."""

    def __init__(
        self,
        model_name: str,
        batch_size: int = 4,
        device: str | None = None,
        cache: EmbeddingCache | None = None,
        normalize_embeddings: bool = True,
        max_length: int = 8192,
        query_prompt: str = QWEN3_EMBEDDING_QUERY_PROMPT,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self.cache = cache
        self.normalize_embeddings = normalize_embeddings
        self.max_length = max_length
        self.query_prompt = query_prompt
        self.config_hash = embedding_config_hash(
            {
                "adapter": "qwen3_transformers",
                "normalize_embeddings": normalize_embeddings,
                "max_length": max_length,
                "query_prompt": query_prompt,
            }
        )
        self._model: AutoModel | None = None
        self._tokenizer = None
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
        prepared_text_batch = prepare_qwen3_retrieval_texts(
            texts=text_batch,
            purpose=purpose,
            query_prompt=self.query_prompt,
        )
        if self.cache is None:
            return self._encode_uncached(prepared_text_batch)
        requests = build_embedding_requests(
            provider="sentence_transformers",
            model=self.model_name,
            purpose=purpose,
            config_hash=self.config_hash,
            texts=prepared_text_batch,
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
                missing_texts.append(prepared_text_batch[index])
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
        model = self._get_model()
        tokenizer = self._get_tokenizer()
        vectors: list[list[float]] = []
        for batch_start in range(0, len(texts), self.batch_size):
            batch = list(texts[batch_start : batch_start + self.batch_size])
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {
                key: value.to(model.device)
                for key, value in encoded.items()
            }
            with torch.inference_mode():
                outputs = model(**encoded)
            batch_embeddings = last_token_pool(
                outputs.last_hidden_state,
                encoded["attention_mask"],
            )
            if self.normalize_embeddings:
                batch_embeddings = torch_functional.normalize(
                    batch_embeddings,
                    p=2,
                    dim=1,
                )
            vectors.extend(batch_embeddings.float().cpu().tolist())
        return vectors

    def _get_model(self):
        if self._model is None:
            self._model = AutoModel.from_pretrained(
                self.model_name,
                device_map="auto" if self.device != "cpu" else None,
                local_files_only=False,
                quantization_config=(
                    BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                    )
                    if self.device != "cpu"
                    else None
                ),
                dtype=torch.float16 if self.device != "cpu" else torch.float32,
            )
        return self._model

    def _get_tokenizer(self):
        if self._tokenizer is None:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                padding_side="left",
                local_files_only=False,
            )
        return self._tokenizer


class GoogleGenAIEmbeddings(Embeddings):
    """LangChain Embeddings adapter backed by Google Gemini embeddings."""

    def __init__(
        self,
        model_name: str,
        google_api_key: str,
        google_api_keys: tuple[str, ...] = (),
        batch_size: int = 16,
        output_dimensionality: int | None = None,
        cache: EmbeddingCache | None = None,
        document_task_type: str = "RETRIEVAL_DOCUMENT",
        query_task_type: str = "RETRIEVAL_QUERY",
    ) -> None:
        resolved_google_api_keys = tuple(
            key.strip()
            for key in (google_api_keys or (google_api_key,))
            if key and key.strip()
        )
        if not resolved_google_api_keys:
            msg = "Google API key is required for Google Gemini eval embeddings."
            raise ValueError(msg)
        self.model_name = model_name
        self.google_api_key = resolved_google_api_keys[0]
        self.google_api_keys = resolved_google_api_keys
        self.batch_size = batch_size
        self.output_dimensionality = output_dimensionality
        self.cache = cache
        self.document_task_type = document_task_type
        self.query_task_type = query_task_type
        self.config_hash = embedding_config_hash(
            {
                "adapter": "langchain_google_genai",
                "output_dimensionality": output_dimensionality,
                "document_task_type": document_task_type,
                "query_task_type": query_task_type,
                "google_api_key_count": len(resolved_google_api_keys),
            }
        )
        self._clients = [
            genai.Client(api_key=api_key) for api_key in resolved_google_api_keys
        ]
        self._client_index = 0
        self._client_retry_after = [0.0 for _ in self._clients]
        self._client_disabled = [False for _ in self._clients]
        self._dimension: int | None = output_dimensionality

    @property
    def dimension(self) -> int:
        """Return embedding dimension for collection creation."""

        if self._dimension is None:
            self._dimension = len(self.embed_query("dimension probe"))
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""

        return self._encode(
            texts=texts,
            purpose="retrieval_document",
            task_type=self.document_task_type,
            embed=self._embed_documents_uncached,
        )

    def embed_query(self, text: str) -> list[float]:
        """Embed one query string."""

        return self._encode(
            texts=[text],
            purpose="retrieval_query",
            task_type=self.query_task_type,
            embed=self._embed_queries_uncached,
        )[0]

    def _encode(
        self,
        texts: list[str],
        purpose: str,
        task_type: str,
        embed: Callable[[genai.Client, list[str], str], list[list[float]]],
    ) -> list[list[float]]:
        if self.cache is None:
            return self._embed_with_failover(embed, texts, task_type)
        requests = build_embedding_requests(
            provider="google_genai",
            model=self.model_name,
            purpose=purpose,
            config_hash=embedding_config_hash(
                {
                    "config_hash": self.config_hash,
                    "task_type": task_type,
                }
            ),
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
            embedded_texts = self._embed_with_failover(embed, missing_texts, task_type)
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

    def _embed_with_failover(
        self,
        embed: Callable[[genai.Client, list[str], str], list[list[float]]],
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        last_error: Exception | None = None
        while True:
            next_retry_at: float | None = None
            now = time.monotonic()
            for offset in range(len(self._clients)):
                client_index = (self._client_index + offset) % len(self._clients)
                if self._client_disabled[client_index]:
                    continue
                retry_after = self._client_retry_after[client_index]
                if retry_after > now:
                    next_retry_at = min(next_retry_at or retry_after, retry_after)
                    continue
                client = self._clients[client_index]
                try:
                    embedded_texts = embed(client, texts, task_type)
                except Exception as exc:  # pragma: no cover - exercised in live runs
                    last_error = exc
                    if should_retry_google_embedding_with_next_key(exc):
                        if is_google_invalid_api_key_error(exc):
                            self._client_disabled[client_index] = True
                            continue
                        candidate_delay = extract_google_retry_delay_seconds(exc)
                        if candidate_delay is not None:
                            retry_after = time.monotonic() + max(candidate_delay, 1.0)
                            self._client_retry_after[client_index] = retry_after
                            next_retry_at = min(
                                next_retry_at or retry_after,
                                retry_after,
                            )
                        continue
                    raise
                self._client_index = client_index
                self._client_retry_after[client_index] = 0.0
                return embedded_texts
            if last_error is None:
                msg = "Google Gemini embedding provider had no available clients."
                raise RuntimeError(msg)
            if next_retry_at is not None:
                time.sleep(max(next_retry_at - time.monotonic(), 1.0))
                continue
            raise last_error

    def _embed_documents_uncached(
        self,
        client: genai.Client,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            config = self._build_google_config(task_type)
            result = client.models.embed_content(
                model=self.model_name,
                contents=[{"parts": [{"text": text}]} for text in batch],
                config=config,
            )
            batch_vectors = [list(embedding.values) for embedding in result.embeddings]
            if len(batch_vectors) != len(batch):
                msg = (
                    "Google Gemini embedding batch returned "
                    f"{len(batch_vectors)} vectors for {len(batch)} texts."
                )
                raise ValueError(msg)
            vectors.extend(batch_vectors)
        return vectors

    def _embed_queries_uncached(
        self,
        client: genai.Client,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            config = self._build_google_config(task_type)
            result = client.models.embed_content(
                model=self.model_name,
                contents=[{"parts": [{"text": text}]}],
                config=config,
            )
            if len(result.embeddings) != 1:
                msg = (
                    "Google Gemini query embedding returned "
                    f"{len(result.embeddings)} vectors for one text."
                )
                raise ValueError(msg)
            vectors.append(list(result.embeddings[0].values))
        return vectors

    def _build_google_config(
        self,
        task_type: str,
    ) -> genai_types.EmbedContentConfig:
        return genai_types.EmbedContentConfig(
            http_options=genai_types.HttpOptions(
                timeout=30_000,
                retry_options=genai_types.HttpRetryOptions(attempts=1),
            ),
            task_type=task_type,
            output_dimensionality=self.output_dimensionality,
        )


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


def build_retrieval_embeddings(
    provider: str,
    model_name: str,
    batch_size: int,
    device: str | None = None,
    cache: EmbeddingCache | None = None,
    google_api_key: str = "",
    google_api_keys: tuple[str, ...] = (),
    google_output_dimensionality: int | None = None,
) -> BenchmarkEmbeddings:
    """Build retrieval embeddings for benchmark indexing and querying."""

    normalized_provider = provider.strip().lower()
    if normalized_provider in {"sentence_transformer", "sentence_transformers"}:
        if is_qwen3_embedding_model_name(model_name):
            return Qwen3AutoModelEmbeddings(
                model_name=model_name,
                batch_size=batch_size,
                device=device,
                cache=cache,
            )
        return SentenceTransformerEmbeddings(
            model_name=model_name,
            batch_size=batch_size,
            device=device,
            cache=cache,
        )
    if normalized_provider in {"google", "google_genai", "gemini"}:
        return GoogleGenAIEmbeddings(
            model_name=model_name,
            google_api_key=google_api_key,
            google_api_keys=google_api_keys,
            batch_size=batch_size,
            output_dimensionality=google_output_dimensionality,
            cache=cache,
        )
    msg = (
        "Unsupported CHUNKING_EVAL_EMBEDDING_PROVIDER="
        f"{provider!r}. Supported providers: sentence_transformers, google_genai."
    )
    raise ValueError(msg)


def prepare_sentence_transformer_texts(
    *,
    model_name: str,
    texts: Sequence[str],
    purpose: str,
) -> list[str]:
    """Prepare texts for model families that require retrieval prefixes."""

    if not is_e5_model_name(model_name):
        return list(texts)
    prefix = "query: " if purpose == "retrieval_query" else "passage: "
    return [
        text if text.startswith(("query: ", "passage: ")) else f"{prefix}{text}"
        for text in texts
    ]


def prepare_qwen3_retrieval_texts(
    *,
    texts: Sequence[str],
    purpose: str,
    query_prompt: str = QWEN3_EMBEDDING_QUERY_PROMPT,
) -> list[str]:
    """Prepare texts for Qwen3 embedding retrieval prompts."""

    if purpose != "retrieval_query":
        return list(texts)
    return [
        text if text.startswith(query_prompt) else f"{query_prompt} {text}"
        for text in texts
    ]


def is_e5_model_name(model_name: str) -> bool:
    """Return whether the model expects E5 retrieval prefixes."""

    normalized_model_name = model_name.strip().lower()
    return "e5" in normalized_model_name


def is_qwen3_embedding_model_name(model_name: str) -> bool:
    """Return whether the model is a Qwen3 embedding checkpoint."""

    normalized_model_name = model_name.strip().lower()
    return "qwen3-embedding" in normalized_model_name


def last_token_pool(last_hidden_states, attention_mask):
    """Pool the last non-padding token following the Qwen3 model card."""

    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0]).item()
    if left_padding:
        return last_hidden_states[:, -1]
    sequence_lengths = attention_mask.sum(dim=1) - 1
    batch_size = last_hidden_states.shape[0]
    return last_hidden_states[
        torch.arange(batch_size, device=last_hidden_states.device),
        sequence_lengths,
    ]


def should_retry_google_embedding_with_next_key(error: Exception) -> bool:
    """Return whether a Google embedding error should rotate to the next key."""

    message = str(error).upper()
    return any(
        marker in message
        for marker in (
            "RESOURCE_EXHAUSTED",
            "QUOTA",
            "429",
            "API_KEY_INVALID",
            "API KEY NOT VALID",
        )
    )


def is_google_invalid_api_key_error(error: Exception) -> bool:
    """Return whether a Google embedding error indicates a permanently bad key."""

    message = str(error).upper()
    return any(
        marker in message
        for marker in (
            "API_KEY_INVALID",
            "API KEY NOT VALID",
        )
    )


def extract_google_retry_delay_seconds(error: Exception) -> float | None:
    """Extract Google quota retry delay from an exception message when present."""

    message = str(error)
    for pattern in (
        r"Please retry in ([0-9]+(?:\.[0-9]+)?)s",
        r"'retryDelay': '([0-9]+(?:\.[0-9]+)?)s'",
    ):
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match is None:
            continue
        return float(match.group(1))
    return None


def require_complete_vectors(
    vectors: list[list[float] | None],
) -> list[list[float]]:
    """Return vectors after verifying the batch has no gaps."""

    if any(vector is None for vector in vectors):
        msg = "Embedding cache wrapper did not produce every requested vector."
        raise ValueError(msg)
    return [vector for vector in vectors if vector is not None]
