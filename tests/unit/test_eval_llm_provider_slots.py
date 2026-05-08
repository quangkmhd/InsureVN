import json
from concurrent.futures import ThreadPoolExecutor

import httpx

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
