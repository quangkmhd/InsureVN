from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.embeddings import Embeddings

MODULE_PATH = Path(__file__).with_name("chunking_compare_api.py")
MODULE_SPEC = importlib.util.spec_from_file_location(
    "chunking_compare_api",
    MODULE_PATH,
)
assert MODULE_SPEC is not None
assert MODULE_SPEC.loader is not None
chunking = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = chunking
MODULE_SPEC.loader.exec_module(chunking)
app = chunking.app


class RecordingSemanticEmbeddings(Embeddings):
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


class RecordingLLMChunkingProvider:
    """Deterministic fake for LLM chunking endpoint tests."""

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.requests: list[chunking.LLMChunkRequest] = []

    def split_text(self, request: chunking.LLMChunkRequest) -> list[str]:
        self.requests.append(request)
        return self.chunks


@pytest.mark.asyncio
async def test_semantic_chunking_endpoint_uses_langchain_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embeddings = RecordingSemanticEmbeddings()
    monkeypatch.setattr(
        chunking.settings,
        "SEMANTIC_CHUNKING_EMBEDDING_MODEL",
        "bge-m3",
    )
    app.dependency_overrides[chunking.build_semantic_embedding_provider] = lambda: (
        embeddings
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
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
    assert data["model"] == "bge-m3"
    assert embeddings.document_batches
    assert len(data["chunks"]) >= 1
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
        transport=ASGITransport(app=app),
        base_url="http://test",
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
            transport=ASGITransport(app=app),
            base_url="http://test",
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


@pytest.mark.asyncio
async def test_semantic_chunking_falls_back_when_ollama_runner_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama_provider = object.__new__(chunking.SemanticOllamaEmbeddingProvider)

    def fake_splitter(
        *,
        request: chunking.SemanticChunkRequest,
        embedding_provider: Embeddings,
    ) -> list[str]:
        if isinstance(embedding_provider, chunking.SemanticOllamaEmbeddingProvider):
            raise RuntimeError("ollama runner terminated")
        assert isinstance(embedding_provider, chunking.LocalHashingEmbeddingProvider)
        return [request.text]

    monkeypatch.setattr(
        chunking,
        "_split_with_langchain_semantic_chunker",
        fake_splitter,
    )
    app.dependency_overrides[chunking.build_semantic_embedding_provider] = lambda: (
        ollama_provider
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/chunking/semantic",
                json={"text": "Billing and security text."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "local_hashing_fallback"
    assert data["model"] == "lexical_hash_128"
    assert data["chunks"][0]["text"] == "Billing and security text."


@pytest.mark.asyncio
async def test_adaptive_semantic_density_endpoint_uses_benchmark_heuristic() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/chunking/adaptive-density",
            json={
                "text": (
                    "## Billing\n\n"
                    + (
                        "Billing invoices are paid monthly. "
                        "Refund payment disputes are handled by billing support. "
                        "Invoice payment records are audited every week. " * 6
                    )
                    + "\n\n"
                    "## Security\n\n"
                    + (
                        "Security login tokens rotate after password resets. "
                        "Password recovery requires a verified security email. "
                        "Login token activity is reviewed every day. " * 6
                    )
                ),
                "chunk_size_tokens": 70,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "adaptive_semantic_density"
    assert data["provider"] == "benchmark_health_chunking"
    assert data["model"] == "lexical_density_jaccard"
    assert len(data["chunks"]) >= 1
    assert all(
        chunk["issues"] == ["adaptive semantic density"] for chunk in data["chunks"]
    )
    assert any("Billing" in chunk["text"] for chunk in data["chunks"])
    assert any("Security" in chunk["text"] for chunk in data["chunks"])


@pytest.mark.asyncio
async def test_late_chunking_endpoint_returns_contextual_index_text() -> None:
    text = (
        "# Product Handbook\n\n"
        "Coverage is available for inpatient care and emergency treatment.\n\n"
        "## Claims\n\n"
        "Submit claim forms with invoices and discharge papers. "
        "The claim team reviews documents within ten working days. "
        "Missing invoices can delay the claim decision.\n\n"
        "## Exclusions\n\n"
        "Cosmetic treatment and undeclared pre-existing conditions are excluded."
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/chunking/late",
            json={"text": text, "chunk_size_tokens": 50, "overlap_tokens": 0},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "late_chunking"
    assert data["provider"] == "benchmark_health_chunking"
    assert data["model"] == "recursive_boundary_contextual_index"
    assert len(data["chunks"]) >= 1
    assert all(chunk["display_text"] in text for chunk in data["chunks"])
    assert any(
        "Section context: Product Handbook > Claims" in chunk["text"]
        for chunk in data["chunks"]
    )
    assert all(chunk["index_text"] == chunk["text"] for chunk in data["chunks"])
    assert any(
        chunk["issues"] == ["late chunking contextual index"]
        for chunk in data["chunks"]
    )


@pytest.mark.asyncio
async def test_llm_chunking_endpoint_uses_google_genai_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = (
        "## Billing\n\n"
        "Billing invoices are paid monthly. Refunds stay with billing support.\n\n"
        "## Security\n\n"
        "Security login tokens rotate after password resets."
    )
    security_start = text.index("## Security")
    provider = RecordingLLMChunkingProvider(
        [
            text[:security_start].strip(),
            text[security_start:].strip(),
        ]
    )
    monkeypatch.setattr(chunking.settings, "LLM_CHUNKING_PROVIDER", "google_genai")
    monkeypatch.setattr(chunking.settings, "LLM_CHUNKING_MODEL", "gemma-4-31b-it")
    app.dependency_overrides[chunking.build_llm_chunking_provider] = lambda: provider
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/chunking/llm",
                json={"text": text, "chunk_size_tokens": 80},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "llm_chunking"
    assert data["provider"] == "google_genai"
    assert data["model"] == "gemma-4-31b-it"
    assert provider.requests[0].chunk_size_tokens == 80
    assert [chunk["issues"] for chunk in data["chunks"]] == [
        ["llm chunking"],
        ["llm chunking"],
    ]
    assert data["chunks"][0]["start"] == 0
    assert data["chunks"][1]["start"] == security_start


@pytest.mark.asyncio
async def test_llm_chunking_rejects_rewritten_chunks() -> None:
    provider = RecordingLLMChunkingProvider(["This was rewritten by the model."])
    app.dependency_overrides[chunking.build_llm_chunking_provider] = lambda: provider
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/chunking/llm",
                json={"text": "Original source text for chunking."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "exact source substrings" in response.json()["detail"]


def test_llm_chunking_boundary_plan_maps_units_without_text_echo() -> None:
    text = (
        "## Billing\n\nBilling paragraph one.\n\nBilling paragraph two.\n\n"
        "## Security\n\nSecurity paragraph one.\n\nSecurity paragraph two."
    )
    units = chunking._build_llm_chunking_units(text)
    plan = chunking.LLMChunkingPlan(
        chunks=[
            chunking.LLMChunkBoundary(start_unit=1, end_unit=3),
            chunking.LLMChunkBoundary(start_unit=4, end_unit=6),
        ]
    )

    chunks = chunking._chunks_from_llm_boundaries(text, units, plan.chunks)

    assert chunks == [
        "## Billing\n\nBilling paragraph one.\n\nBilling paragraph two.",
        "## Security\n\nSecurity paragraph one.\n\nSecurity paragraph two.",
    ]


def test_llm_chunking_provider_caches_successful_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = (
        "## Billing\n\nBilling paragraph one.\n\n"
        "## Security\n\nSecurity paragraph one."
    )
    provider = chunking.GoogleGenAILLMChunkingProvider(
        api_key="test-key",
        model_name="gemma-4-31b-it",
        timeout_seconds=1,
        cache_path=tmp_path / "llm_chunk_cache.json",
        unit_preview_chars=80,
    )
    calls = {"count": 0}

    def fake_generate_text(_prompt: str) -> str:
        calls["count"] += 1
        return json.dumps(
            {
                "chunks": [
                    {"start_unit": 1, "end_unit": 2},
                    {"start_unit": 3, "end_unit": 4},
                ]
            }
        )

    monkeypatch.setattr(provider, "_generate_text", fake_generate_text)
    request = chunking.LLMChunkRequest(text=text, chunk_size_tokens=80)

    first_chunks = provider.split_text(request)
    second_chunks = provider.split_text(request)

    assert calls["count"] == 1
    assert first_chunks == second_chunks
    assert len(first_chunks) == 2


def test_llm_chunking_prompt_uses_previews_not_full_units() -> None:
    long_text = "A" * 500
    units = [
        chunking.LLMChunkingUnit(
            unit_id=1,
            start=0,
            end=len(long_text),
            text=long_text,
        )
    ]

    prompt = chunking._build_llm_chunking_prompt(
        units,
        target_chars=1_000,
        preview_chars=40,
    )

    assert "A" * 40 in prompt
    assert "A" * 80 not in prompt


@pytest.mark.asyncio
async def test_remote_chunking_options_keep_cors_headers() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        for path in (
            "/chunking/semantic",
            "/chunking/adaptive-density",
            "/chunking/late",
            "/chunking/llm",
        ):
            response = await client.options(
                path,
                headers={"Origin": "http://localhost:8000"},
            )
            assert response.status_code == 204
            assert (
                response.headers["access-control-allow-origin"]
                == "http://localhost:8000"
            )
