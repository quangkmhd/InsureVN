import json

import httpx
import pytest

from src.services.jina_rerank_cross_encoder import JinaRerankCrossEncoder


def test_jina_rerank_cross_encoder_maps_scores_to_input_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert request.headers["Authorization"] == "Bearer test-key"
        assert payload == {
            "model": "jina-reranker-v3",
            "query": "hạn mức nội trú?",
            "documents": ["unrelated", "limit_amount: 100000000"],
            "top_n": 2,
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.12},
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cross_encoder = JinaRerankCrossEncoder(
        api_key="test-key",
        model="jina-reranker-v3",
        base_url="https://api.jina.ai/v1/rerank",
        client=client,
    )

    scores = cross_encoder.score(
        [
            ("hạn mức nội trú?", "unrelated"),
            ("hạn mức nội trú?", "limit_amount: 100000000"),
        ]
    )

    assert scores == [0.12, 0.91]


def test_jina_rerank_cross_encoder_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        JinaRerankCrossEncoder(api_key="")


def test_jina_rerank_cross_encoder_adds_safe_langfuse_metadata(monkeypatch) -> None:
    captured_metadata: list[dict] = []

    def capture_metadata(metadata: dict) -> None:
        captured_metadata.append(metadata)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "usage": {"total_tokens": 42},
                "results": [
                    {"index": 0, "relevance_score": 0.91},
                    {"index": 1, "relevance_score": 0.12},
                ],
            },
        )

    monkeypatch.setattr(
        "src.services.jina_rerank_cross_encoder.add_current_service_metadata",
        capture_metadata,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    cross_encoder = JinaRerankCrossEncoder(
        api_key="test-key",
        model="jina-reranker-v3",
        base_url="https://api.jina.ai/v1/rerank",
        client=client,
    )

    cross_encoder.score(
        [
            ("hạn mức nội trú?", "unrelated"),
            ("hạn mức nội trú?", "limit_amount: 100000000"),
        ]
    )

    assert captured_metadata == [
        {
            "jina_rerank": {
                "provider": "jina",
                "model": "jina-reranker-v3",
                "document_count": 2,
                "result_count": 2,
                "usage_total_tokens": 42,
                "score_min": 0.12,
                "score_max": 0.91,
            }
        }
    ]
