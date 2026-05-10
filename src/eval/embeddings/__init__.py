"""Embedding adapters and cache utilities for evaluation workflows."""

from src.eval.embeddings.adapters import (
    BenchmarkEmbeddings,
    CachedEmbeddings,
    GoogleGenAIEmbeddings,
    Qwen3AutoModelEmbeddings,
    SentenceTransformerEmbeddings,
    build_retrieval_embeddings,
    build_semantic_chunking_embeddings,
    prepare_qwen3_retrieval_texts,
    prepare_sentence_transformer_texts,
    require_complete_vectors,
)
from src.eval.embeddings.cache import (
    EmbeddingCache,
    EmbeddingCacheRequest,
    EmbeddingCacheStats,
    build_embedding_requests,
    embedding_config_hash,
    sha256_text,
    stable_json,
)

__all__ = [
    "BenchmarkEmbeddings",
    "CachedEmbeddings",
    "EmbeddingCache",
    "EmbeddingCacheRequest",
    "EmbeddingCacheStats",
    "GoogleGenAIEmbeddings",
    "prepare_qwen3_retrieval_texts",
    "prepare_sentence_transformer_texts",
    "Qwen3AutoModelEmbeddings",
    "SentenceTransformerEmbeddings",
    "build_embedding_requests",
    "build_retrieval_embeddings",
    "build_semantic_chunking_embeddings",
    "embedding_config_hash",
    "require_complete_vectors",
    "sha256_text",
    "stable_json",
]
