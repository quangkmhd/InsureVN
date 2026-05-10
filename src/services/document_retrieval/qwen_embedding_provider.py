"""Local Qwen embedding provider for production retrieval/indexing."""

from __future__ import annotations

from typing import Any

import torch
from langchain_core.embeddings import Embeddings
from torch import Tensor
from torch.nn import functional as torch_functional
from transformers import AutoModel, AutoTokenizer, BitsAndBytesConfig

QWEN3_DEFAULT_QUERY_TASK_DESCRIPTION = (
    "Given a web search query, retrieve relevant passages that answer the query"
)


class Qwen3EmbeddingProvider(Embeddings):
    """Qwen3 embedding provider backed by direct `transformers` inference.

    LangChain's official local Hugging Face embedding integration uses
    `sentence_transformers`. For `Qwen/Qwen3-Embedding-8B` on the current
    project hardware, the direct `transformers` path with 4-bit quantization is
    the stable option that completed full-corpus benchmarking.
    """

    def __init__(
        self,
        *,
        model_name: str,
        vector_size: int,
        batch_size: int = 4,
        max_length: int = 8192,
        query_task_description: str = QWEN3_DEFAULT_QUERY_TASK_DESCRIPTION,
        load_in_4bit: bool = True,
        device_map: str = "auto",
        attn_implementation: str | None = None,
    ) -> None:
        """Initialize the provider without loading the model eagerly."""
        self.model_name = model_name
        self.vector_size = vector_size
        self.batch_size = batch_size
        self.max_length = max_length
        self.query_task_description = query_task_description
        self.load_in_4bit = load_in_4bit
        self.device_map = device_map
        self.attn_implementation = attn_implementation
        self._model: Any | None = None
        self._tokenizer: Any | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document texts into dense vectors."""
        if not texts:
            return []
        return self._embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed one query text into a dense vector."""
        return self._embed_texts([self._prepare_query_text(text)])[0]

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        tokenizer = self._get_tokenizer()
        model_device = _model_device(model)
        vectors: list[list[float]] = []

        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(model_device) for key, value in encoded.items()}
            with torch.inference_mode():
                outputs = model(**encoded)
            batch_embeddings = _last_token_pool(
                outputs.last_hidden_state,
                encoded["attention_mask"],
            )
            batch_embeddings = _resize_embeddings(
                batch_embeddings,
                expected_size=self.vector_size,
            )
            batch_embeddings = torch_functional.normalize(
                batch_embeddings,
                p=2,
                dim=1,
            )
            batch_vectors = batch_embeddings.float().cpu().tolist()
            vectors.extend(batch_vectors)
        return vectors

    def _prepare_query_text(self, text: str) -> str:
        if text.startswith("Instruct:"):
            return text
        return (
            f"Instruct: {self.query_task_description}\n"
            f"Query:{text}"
        )

    def _get_model(self) -> Any:
        if self._model is None:
            model_kwargs: dict[str, Any] = {
                "device_map": (
                    None if self.device_map.lower() == "cpu" else self.device_map
                ),
                "dtype": (
                    torch.float32
                    if self.device_map.lower() == "cpu"
                    else torch.float16
                ),
                "quantization_config": self._build_quantization_config(),
            }
            if self.attn_implementation:
                model_kwargs["attn_implementation"] = self.attn_implementation
            self._model = AutoModel.from_pretrained(
                self.model_name,
                **model_kwargs,
            )
        return self._model

    def _get_tokenizer(self) -> Any:
        if self._tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                padding_side="left",
            )
            if tokenizer.pad_token is None and tokenizer.eos_token is not None:
                tokenizer.pad_token = tokenizer.eos_token
            self._tokenizer = tokenizer
        return self._tokenizer

    def _build_quantization_config(self) -> BitsAndBytesConfig | None:
        if not self.load_in_4bit or self.device_map.lower() == "cpu":
            return None
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )


def is_qwen3_embedding_model_name(model_name: str) -> bool:
    """Return whether the model name refers to a Qwen3 embedding checkpoint."""
    return "qwen3-embedding" in model_name.strip().lower()


def _last_token_pool(last_hidden_states: Tensor, attention_mask: Tensor) -> Tensor:
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


def _model_device(model: Any) -> torch.device:
    """Return the best runtime device for tokenizer tensors."""
    if hasattr(model, "get_input_embeddings"):
        embeddings = model.get_input_embeddings()
        if embeddings is not None and hasattr(embeddings, "weight"):
            return embeddings.weight.device
    if hasattr(model, "device"):
        return model.device
    return next(model.parameters()).device


def _resize_embeddings(embeddings: Tensor, *, expected_size: int) -> Tensor:
    """Resize Qwen embeddings to the configured MRL dimension if needed."""
    actual_size = embeddings.shape[1]
    if expected_size > actual_size:
        raise ValueError(
            "Qwen embedding vector size mismatch. "
            f"Expected {expected_size}, got {actual_size}."
        )
    if expected_size == actual_size:
        return embeddings
    return embeddings[:, :expected_size]
