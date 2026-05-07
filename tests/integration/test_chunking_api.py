import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.embeddings import Embeddings

from src.api.routes import chunking
from src.main import app


class RecordingTopicEmbeddings(Embeddings):
    """Deterministic embeddings for semantic chunking endpoint tests."""

    def __init__(self) -> None:
        self.document_batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_batches.append(texts)
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        normalized_text = text.lower()
        billing_score = sum(
            normalized_text.count(term)
            for term in ("billing", "invoice", "payment", "refund")
        )
        security_score = sum(
            normalized_text.count(term)
            for term in ("security", "password", "login", "token")
        )
        return [float(billing_score), float(security_score), 1.0]


class FailingEmbeddings(Embeddings):
    """Embedding fake that raises during semantic splitting."""

    def embed_documents(self, _texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding provider failed")

    def embed_query(self, _text: str) -> list[float]:
        raise RuntimeError("embedding provider failed")


@pytest.mark.asyncio
async def test_semantic_chunking_endpoint_uses_langchain_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embeddings = RecordingTopicEmbeddings()
    monkeypatch.setattr(chunking.settings, "RAG_EMBEDDING_MODEL", "other-model")
    monkeypatch.setattr(
        chunking.settings,
        "SEMANTIC_CHUNKING_EMBEDDING_MODEL",
        "qwen3-embedding:8b",
    )
    app.dependency_overrides[chunking.build_semantic_embedding_provider] = lambda: (
        embeddings
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/chunking/semantic",
                json={
                    "text": (
                        "Billing invoices are paid monthly. "
                        "Refund payment disputes are handled by billing support. "
                        "Billing teams audit invoice payment records every week. "
                        "Security login tokens rotate after password resets. "
                        "Password recovery requires a verified security email. "
                        "Security teams review login token activity every day."
                    ),
                    "chunk_size_tokens": 50,
                    "overlap_tokens": 0,
                    "min_chunk_chars": 40,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "langchain_semantic"
    assert data["provider"] == "ollama"
    assert data["model"] == "qwen3-embedding:8b"
    assert embeddings.document_batches
    assert len(data["chunks"]) >= 2
    assert all(chunk["text"] for chunk in data["chunks"])
    assert all(chunk["start"] <= chunk["end"] for chunk in data["chunks"])


@pytest.mark.asyncio
async def test_semantic_chunking_endpoint_rejects_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        chunking.settings,
        "SEMANTIC_CHUNKING_EMBEDDING_PROVIDER",
        "google_genai",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/chunking/semantic",
            headers={"Origin": "http://127.0.0.1:8000"},
            json={"text": "A valid text body for semantic chunking."},
        )

    assert response.status_code == 503
    assert "Only ollama is supported" in response.json()["detail"]
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8000"


@pytest.mark.asyncio
async def test_semantic_chunking_provider_failure_keeps_cors_headers() -> None:
    app.dependency_overrides[chunking.build_semantic_embedding_provider] = lambda: (
        FailingEmbeddings()
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/chunking/semantic",
                headers={"Origin": "http://localhost:5173"},
                json={"text": "First sentence. Second sentence. Third sentence."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert (
        response.json()["detail"] == "Semantic chunking provider failed: RuntimeError"
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
