import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from src.eval.chunking.insurance_contract_hybrid_late import (
    summarize_table,
    summarize_table_chunks,
)
from src.eval.llamaindex_llms import ConcurrentProviderPoolLLM
from src.eval.llm_provider_slots import (
    EvalLLMProviderSlot,
    collect_markdown_element_llm_provider_slots,
)


def test_collect_markdown_element_llm_provider_slots_reads_all_provider_keys() -> None:
    environ = {
        "MARKDOWN_ELEMENT_GEMINI_API_KEYS": "gemini-a,gemini-b",
        "MARKDOWN_ELEMENT_GEMINI_MODEL": "gemma-4-31b-it",
        "MARKDOWN_ELEMENT_OLLAMA_API_KEYS": "ollama-a",
        "MARKDOWN_ELEMENT_OLLAMA_BASE_URL": "https://ollama.com",
        "MARKDOWN_ELEMENT_OLLAMA_MODEL": "gemma4:31b-cloud",
        "OPENROUTER_API_KEY_1": "router-a",
        "OPENROUTER_API_KEY_2": "router-b",
        "OPENROUTER_LLM_MODEL": "openrouter/free",
        "NVIDIA_NIM_API_1": "nvidia-a",
        "KG_SCHEMA_DISCOVERY_NVIDIA_MODEL": "google/gemma-4-31b-it",
    }

    slots = collect_markdown_element_llm_provider_slots(environ)

    assert [(slot.provider, slot.api_key) for slot in slots] == [
        ("gemini", "gemini-a"),
        ("gemini", "gemini-b"),
        ("ollama", "ollama-a"),
        ("openrouter", "router-a"),
        ("openrouter", "router-b"),
        ("nvidia", "nvidia-a"),
    ]
    assert slots[3].model == "openrouter/free"
    assert slots[5].base_url == "https://integrate.api.nvidia.com/v1/chat/completions"


def test_concurrent_provider_pool_uses_different_available_slots() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": f"ok:{payload['messages'][0]['content']}"}}
                ]
            },
        )

    llm = ConcurrentProviderPoolLLM(
        slots=(
            EvalLLMProviderSlot(
                slot_id="openrouter-0",
                provider="openrouter",
                model="openrouter/free",
                api_key="key-a",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
            EvalLLMProviderSlot(
                slot_id="openrouter-1",
                provider="openrouter",
                model="openrouter/free",
                api_key="key-b",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
        ),
        transport=httpx.MockTransport(handler),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda text: llm.complete(text).text, ["a", "b"]))

    assert sorted(results) == ["ok:a", "ok:b"]
    assert sorted(request.headers["Authorization"] for request in requests) == [
        "Bearer key-a",
        "Bearer key-b",
    ]


def test_concurrent_provider_pool_fails_over_when_slot_errors() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.headers["Authorization"] == "Bearer busy-key":
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fallback-ok"}}]},
        )

    llm = ConcurrentProviderPoolLLM(
        slots=(
            EvalLLMProviderSlot(
                slot_id="openrouter-0",
                provider="openrouter",
                model="openrouter/free",
                api_key="busy-key",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
            EvalLLMProviderSlot(
                slot_id="openrouter-1",
                provider="openrouter",
                model="openrouter/free",
                api_key="fallback-key",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
        ),
        transport=httpx.MockTransport(handler),
    )

    assert llm.complete("prompt").text == "fallback-ok"
    assert [request.headers["Authorization"] for request in requests] == [
        "Bearer busy-key",
        "Bearer fallback-key",
    ]


def test_concurrent_provider_pool_limits_slot_attempts_per_prompt() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(429, json={"error": "rate limited"})

    llm = ConcurrentProviderPoolLLM(
        slots=(
            EvalLLMProviderSlot(
                slot_id="openrouter-0",
                provider="openrouter",
                model="openrouter/free",
                api_key="key-a",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
            EvalLLMProviderSlot(
                slot_id="openrouter-1",
                provider="openrouter",
                model="openrouter/free",
                api_key="key-b",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
            EvalLLMProviderSlot(
                slot_id="openrouter-2",
                provider="openrouter",
                model="openrouter/free",
                api_key="key-c",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
        ),
        max_slot_attempts=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError, match="2/3"):
        llm.complete("prompt")

    assert len(requests) == 2


def test_concurrent_provider_pool_caps_openai_compatible_output_tokens() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    llm = ConcurrentProviderPoolLLM(
        slots=(
            EvalLLMProviderSlot(
                slot_id="openrouter-0",
                provider="openrouter",
                model="openrouter/free",
                api_key="key-a",
                base_url="https://openrouter.ai/api/v1/chat/completions",
            ),
        ),
        transport=httpx.MockTransport(handler),
    )

    assert llm.complete("default cap").text == "ok"
    assert llm.complete("short cap", max_tokens=160).text == "ok"

    assert payloads[0]["max_tokens"] == 2048
    assert payloads[1]["max_tokens"] == 160


def test_hybrid_table_summary_uses_short_output_limit() -> None:
    class RecordingLLM:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def complete(self, _prompt: str, **kwargs: object) -> str:
            self.kwargs = kwargs
            return "summary"

    recording_llm = RecordingLLM()

    assert summarize_table("| A |\n|---|\n| B |", recording_llm) == "summary"
    assert recording_llm.kwargs["max_tokens"] == 160


def test_large_table_chunk_sets_use_deterministic_summary_without_llm() -> None:
    class FailingLLM:
        def complete(self, _prompt: str, **_kwargs: object) -> str:
            raise AssertionError("LLM should not be called for large table sets.")

    table_chunks = [
        f"| Provider | Address |\n|---|---|\n| Hospital {index} | Hanoi |"
        for index in range(13)
    ]

    summaries = summarize_table_chunks(table_chunks, FailingLLM(), max_workers=4)

    assert len(summaries) == 13
    assert all("Provider" in summary for summary in summaries)
    assert all("Address" in summary for summary in summaries)


def test_hybrid_table_chunks_use_deterministic_summary_by_default() -> None:
    class FailingLLM:
        def complete(self, _prompt: str, **_kwargs: object) -> str:
            raise AssertionError("LLM should not be called by default.")

    summaries = summarize_table_chunks(
        ["| Provider | Address |\n|---|---|\n| Hospital | Hanoi |"],
        FailingLLM(),
        max_workers=1,
    )

    assert summaries == [
        "Bảng Markdown gồm 1 dòng dữ liệu với các cột: Provider, Address."
    ]
