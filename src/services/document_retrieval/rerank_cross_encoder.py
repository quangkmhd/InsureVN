"""Factory helpers for production rerank cross-encoders."""

from __future__ import annotations

from typing import Any

import torch
from langchain_core.cross_encoders import BaseCrossEncoder

from src.core.config import settings
from src.services.document_retrieval.huggingface_rerank_cross_encoder import (
    HuggingFaceRerankCrossEncoder,
)

LOCAL_HUGGINGFACE_RERANK_PROVIDERS = {
    "huggingface",
    "huggingface_local",
    "local",
    "sentence_transformers",
}


def build_rerank_cross_encoder(
    *,
    provider: str,
    model_name: str,
    batch_size: int = 8,
    max_length: int | None = None,
    device: str | None = None,
    trust_remote_code: bool = False,
    backend: str = "torch",
    load_in_4bit: bool = False,
    device_map: str = "",
    attn_implementation: str = "",
    torch_dtype_name: str = "",
) -> BaseCrossEncoder:
    """Build a rerank cross-encoder from explicit runtime settings."""
    normalized_provider = provider.strip().lower()
    if normalized_provider in LOCAL_HUGGINGFACE_RERANK_PROVIDERS:
        model_kwargs = _build_local_model_kwargs(
            load_in_4bit=load_in_4bit,
            device_map=device_map,
            attn_implementation=attn_implementation,
            torch_dtype_name=torch_dtype_name,
        )
        return HuggingFaceRerankCrossEncoder(
            model_name=model_name,
            batch_size=batch_size,
            max_length=max_length,
            device=device,
            trust_remote_code=trust_remote_code,
            backend=backend,
            model_kwargs=model_kwargs,
        )
    raise ValueError(
        "Unsupported RAG_RERANK_PROVIDER. "
        f"Expected one of {sorted(LOCAL_HUGGINGFACE_RERANK_PROVIDERS)}, "
        f"got {provider!r}."
    )


def build_default_rerank_cross_encoder() -> BaseCrossEncoder:
    """Build the configured production rerank cross-encoder."""
    return build_rerank_cross_encoder(
        provider=settings.RAG_RERANK_PROVIDER,
        model_name=settings.RAG_RERANK_MODEL,
        batch_size=settings.RAG_RERANK_BATCH_SIZE,
        max_length=settings.RAG_RERANK_MAX_LENGTH,
        device=settings.RAG_RERANK_DEVICE,
        trust_remote_code=settings.RAG_RERANK_TRUST_REMOTE_CODE,
        backend=settings.RAG_RERANK_BACKEND,
        load_in_4bit=settings.RAG_RERANK_LOAD_IN_4BIT,
        device_map=settings.RAG_RERANK_DEVICE_MAP,
        attn_implementation=settings.RAG_RERANK_ATTN_IMPLEMENTATION,
        torch_dtype_name=settings.RAG_RERANK_TORCH_DTYPE,
    )


def _build_local_model_kwargs(
    *,
    load_in_4bit: bool,
    device_map: str,
    attn_implementation: str,
    torch_dtype_name: str,
) -> dict[str, Any]:
    model_kwargs: dict[str, Any] = {}
    if load_in_4bit:
        model_kwargs["load_in_4bit"] = True
    normalized_device_map = device_map.strip()
    if normalized_device_map:
        model_kwargs["device_map"] = normalized_device_map
    normalized_attn_implementation = attn_implementation.strip()
    if normalized_attn_implementation:
        model_kwargs["attn_implementation"] = normalized_attn_implementation
    resolved_torch_dtype = _resolve_torch_dtype(torch_dtype_name)
    if resolved_torch_dtype is not None:
        model_kwargs["torch_dtype"] = resolved_torch_dtype
    return model_kwargs


def _resolve_torch_dtype(torch_dtype_name: str) -> str | torch.dtype | None:
    normalized_value = torch_dtype_name.strip().lower()
    if not normalized_value:
        return None
    if normalized_value == "auto":
        return "auto"
    torch_dtype = getattr(torch, normalized_value, None)
    if isinstance(torch_dtype, torch.dtype):
        return torch_dtype
    raise ValueError(
        "Unsupported RAG_RERANK_TORCH_DTYPE. "
        f"Expected a torch dtype name or 'auto', got {torch_dtype_name!r}."
    )
