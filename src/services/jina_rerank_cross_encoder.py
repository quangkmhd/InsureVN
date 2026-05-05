from collections import defaultdict

import httpx
from langchain_core.cross_encoders import BaseCrossEncoder

from src.core.config import settings
from src.services.observability import add_current_service_metadata


class JinaRerankCrossEncoder(BaseCrossEncoder):
    """LangChain cross-encoder adapter for Jina's rerank API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "jina-reranker-v3",
        base_url: str = "https://api.jina.ai/v1/rerank",
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialize the Jina rerank cross-encoder adapter."""
        if not api_key:
            raise ValueError("api_key is required for Jina rerank.")
        if not model:
            raise ValueError("model is required for Jina rerank.")
        if not base_url:
            raise ValueError("base_url is required for Jina rerank.")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def score(self, text_pairs: list[tuple[str, str]]) -> list[float]:
        """Score query-document pairs using Jina's rerank endpoint."""
        if not text_pairs:
            return []

        scores = [0.0] * len(text_pairs)
        grouped_pairs: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for pair_index, (query, document_text) in enumerate(text_pairs):
            grouped_pairs[query].append((pair_index, document_text))

        for query, indexed_documents in grouped_pairs.items():
            documents = [document for _index, document in indexed_documents]
            query_scores = self._score_query_documents(query=query, documents=documents)
            for (pair_index, _document), score in zip(
                indexed_documents,
                query_scores,
                strict=True,
            ):
                scores[pair_index] = score

        return scores

    def _score_query_documents(
        self, *, query: str, documents: list[str]
    ) -> list[float]:
        response = self._client.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": len(documents),
            },
        )
        response.raise_for_status()
        response_payload = response.json()
        scores = _parse_jina_rerank_scores(
            response_payload=response_payload,
            document_count=len(documents),
        )
        add_current_service_metadata(
            {
                "jina_rerank": _jina_rerank_metadata(
                    model=self.model,
                    response_payload=response_payload,
                    scores=scores,
                    document_count=len(documents),
                )
            }
        )
        return scores


def build_default_rerank_cross_encoder() -> BaseCrossEncoder:
    """Build the configured production rerank cross-encoder."""
    if settings.RAG_RERANK_PROVIDER != "jina":
        raise ValueError("Only the jina rerank provider is currently supported.")

    return JinaRerankCrossEncoder(
        api_key=settings.JINA_API_KEY,
        model=settings.RAG_RERANK_MODEL,
        base_url=settings.RAG_RERANK_BASE_URL,
        timeout_seconds=settings.RAG_RERANK_TIMEOUT_SECONDS,
    )


def _jina_rerank_metadata(
    *,
    model: str,
    response_payload: dict,
    scores: list[float],
    document_count: int,
) -> dict:
    return {
        "provider": "jina",
        "model": model,
        "document_count": document_count,
        "result_count": len(response_payload.get("results", [])),
        "usage_total_tokens": response_payload.get("usage", {}).get("total_tokens"),
        "score_min": min(scores, default=0.0),
        "score_max": max(scores, default=0.0),
    }


def _parse_jina_rerank_scores(
    *,
    response_payload: dict,
    document_count: int,
) -> list[float]:
    scores = [0.0] * document_count
    try:
        results = response_payload["results"]
        for result in results:
            document_index = int(result["index"])
            if 0 <= document_index < document_count:
                scores[document_index] = float(result["relevance_score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid Jina rerank response payload.") from exc
    return scores
