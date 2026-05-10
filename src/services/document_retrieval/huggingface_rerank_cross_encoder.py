"""Local Hugging Face reranker adapter backed by sentence-transformers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from langchain_core.cross_encoders import BaseCrossEncoder
from sentence_transformers import CrossEncoder

from src.services.observability import add_current_service_metadata


class HuggingFaceRerankCrossEncoder(BaseCrossEncoder):
    """LangChain cross-encoder adapter for local Hugging Face rerankers.

    This adapter uses `sentence_transformers.CrossEncoder.rank()` so model-
    specific ranking logic from the upstream checkpoint is preserved. It groups
    pairs by query, reranks each candidate list, then maps scores back to the
    original pair order expected by `BaseCrossEncoder.score()`.
    """

    def __init__(
        self,
        *,
        model_name: str,
        batch_size: int = 8,
        max_length: int | None = None,
        device: str | None = None,
        trust_remote_code: bool = False,
        backend: str = "torch",
        model_kwargs: dict[str, Any] | None = None,
        config_kwargs: dict[str, Any] | None = None,
        cross_encoder_model: CrossEncoder | None = None,
    ) -> None:
        """Initialize the adapter without loading the model eagerly."""
        if not model_name:
            raise ValueError("model_name is required for local Hugging Face rerank.")
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero.")

        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.device = (device or "").strip() or None
        self.trust_remote_code = trust_remote_code
        self.backend = backend
        self.model_kwargs = dict(model_kwargs or {})
        self.config_kwargs = dict(config_kwargs or {})
        self._cross_encoder_model = cross_encoder_model

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        """Score query-document pairs with a local cross-encoder reranker."""
        if not text_pairs:
            return []

        scores = [0.0] * len(text_pairs)
        grouped_pairs: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for pair_index, (query, document_text) in enumerate(text_pairs):
            grouped_pairs[query].append((pair_index, document_text))

        cross_encoder_model = self._get_cross_encoder_model()
        for query, indexed_documents in grouped_pairs.items():
            rankings = cross_encoder_model.rank(
                query=query,
                documents=[document for _index, document in indexed_documents],
                top_k=len(indexed_documents),
                return_documents=False,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                device=self.device,
            )
            for ranking in rankings:
                document_index = int(ranking["corpus_id"])
                pair_index = indexed_documents[document_index][0]
                scores[pair_index] = float(ranking["score"])

        add_current_service_metadata(
            {
                "huggingface_rerank": {
                    "provider": "huggingface_local",
                    "model": self.model_name,
                    "query_count": len(grouped_pairs),
                    "document_count": len(text_pairs),
                    "batch_size": self.batch_size,
                    "max_length": self.max_length,
                    "score_min": min(scores, default=0.0),
                    "score_max": max(scores, default=0.0),
                }
            }
        )
        return scores

    def _get_cross_encoder_model(self) -> CrossEncoder:
        if self._cross_encoder_model is None:
            self._cross_encoder_model = CrossEncoder(
                self.model_name,
                device=self.device,
                trust_remote_code=self.trust_remote_code,
                model_kwargs=(self.model_kwargs or None),
                config_kwargs=(self.config_kwargs or None),
                backend=self.backend,
                max_length=self.max_length,
            )
        return self._cross_encoder_model
