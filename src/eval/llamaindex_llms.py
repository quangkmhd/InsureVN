"""LlamaIndex LLM adapters for evaluation chunkers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Sequence
from threading import Condition, Lock
from typing import Any, TypeVar

import httpx
from llama_index.core.base.llms.types import (
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
)
from llama_index.core.llms import LLM, LLMMetadata
from llama_index.llms.google_genai import GoogleGenAI
from pydantic import PrivateAttr

from src.eval.llm_provider_slots import EvalLLMProviderSlot, provider_slot_counts

ResponseT = TypeVar("ResponseT")
DEFAULT_PROVIDER_POOL_MAX_TOKENS = 2048


class RoundRobinGoogleGenAILLM(LLM):
    """LlamaIndex LLM wrapper that load-balances Google GenAI keys."""

    model_name: str
    client_count: int

    _clients: list[GoogleGenAI] = PrivateAttr(default_factory=list)
    _lock: Lock = PrivateAttr(default_factory=Lock)
    _next_index: int = PrivateAttr(default=0)

    def __init__(
        self,
        model_name: str,
        api_keys: Sequence[str],
        temperature: float = 0.0,
        max_retries: int = 2,
    ) -> None:
        unique_keys = list(
            dict.fromkeys(key.strip() for key in api_keys if key.strip())
        )
        if not unique_keys:
            msg = "No Gemini API keys configured for MarkdownElementNodeParser."
            raise ValueError(msg)
        super().__init__(
            model_name=model_name,
            client_count=len(unique_keys),
        )
        self._clients = [
            GoogleGenAI(
                model=model_name,
                api_key=api_key,
                temperature=temperature,
                max_retries=max_retries,
            )
            for api_key in unique_keys
        ]

    @property
    def metadata(self) -> LLMMetadata:
        """Return metadata from the first backing LLM client."""

        return self._clients[0].metadata

    def complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Complete with round-robin key selection and failover."""

        return self._call_with_failover(
            lambda client: client.complete(prompt, formatted=formatted, **kwargs)
        )

    async def acomplete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Async complete with round-robin key selection and failover."""

        return await self._acall_with_failover(
            lambda client: client.acomplete(prompt, formatted=formatted, **kwargs)
        )

    def stream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> CompletionResponseGen:
        """Stream completion using a selected Gemini client."""

        return self._call_with_failover(
            lambda client: client.stream_complete(
                prompt,
                formatted=formatted,
                **kwargs,
            )
        )

    async def astream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[CompletionResponse, None]:
        """Async stream completion using a selected Gemini client."""

        async for response in await self._acall_with_failover(
            lambda client: client.astream_complete(
                prompt,
                formatted=formatted,
                **kwargs,
            )
        ):
            yield response

    def chat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponse:
        """Chat with round-robin key selection and failover."""

        return self._call_with_failover(
            lambda client: client.chat(messages=messages, **kwargs)
        )

    async def achat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponse:
        """Async chat with round-robin key selection and failover."""

        return await self._acall_with_failover(
            lambda client: client.achat(messages=messages, **kwargs)
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponseGen:
        """Stream chat using a selected Gemini client."""

        return self._call_with_failover(
            lambda client: client.stream_chat(messages=messages, **kwargs)
        )

    async def astream_chat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[ChatResponse, None]:
        """Async stream chat using a selected Gemini client."""

        async for response in await self._acall_with_failover(
            lambda client: client.astream_chat(messages=messages, **kwargs)
        ):
            yield response

    def _ordered_clients(self) -> list[GoogleGenAI]:
        """Return clients in round-robin order."""

        with self._lock:
            start_index = self._next_index
            self._next_index = (self._next_index + 1) % len(self._clients)
        return [
            self._clients[(start_index + offset) % len(self._clients)]
            for offset in range(len(self._clients))
        ]

    def _call_with_failover(
        self,
        call: Callable[[GoogleGenAI], ResponseT],
    ) -> ResponseT:
        """Call clients in order until one succeeds."""

        last_error: Exception | None = None
        for client in self._ordered_clients():
            try:
                return call(client)
            except Exception as exc:
                last_error = exc
        msg = f"All {len(self._clients)} Gemini clients failed."
        raise RuntimeError(msg) from last_error

    async def _acall_with_failover(
        self,
        call: Callable[[GoogleGenAI], Any],
    ) -> Any:
        """Async call clients in order until one succeeds."""

        last_error: Exception | None = None
        for client in self._ordered_clients():
            try:
                return await call(client)
            except Exception as exc:
                last_error = exc
        msg = f"All {len(self._clients)} Gemini clients failed."
        raise RuntimeError(msg) from last_error


class ConcurrentProviderPoolLLM(LLM):
    """LlamaIndex LLM wrapper that uses all configured provider slots concurrently."""

    model_name: str
    client_count: int
    provider_counts: dict[str, int]
    request_timeout_seconds: float
    max_slot_attempts: int

    _slots: list[EvalLLMProviderSlot] = PrivateAttr(default_factory=list)
    _available: list[bool] = PrivateAttr(default_factory=list)
    _condition: Condition = PrivateAttr(default_factory=Condition)
    _next_index: int = PrivateAttr(default=0)
    _transport: httpx.BaseTransport | None = PrivateAttr(default=None)

    def __init__(
        self,
        slots: Sequence[EvalLLMProviderSlot],
        request_timeout_seconds: float = 120.0,
        max_slot_attempts: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        unique_slots = list(dict.fromkeys(slots))
        if not unique_slots:
            msg = "No LLM provider slots configured for MarkdownElementNodeParser."
            raise ValueError(msg)
        super().__init__(
            model_name="multi-provider-llm-pool",
            client_count=len(unique_slots),
            provider_counts=provider_slot_counts(unique_slots),
            request_timeout_seconds=request_timeout_seconds,
            max_slot_attempts=max(1, max_slot_attempts or len(unique_slots)),
        )
        self._slots = unique_slots
        self._available = [True] * len(unique_slots)
        self._transport = transport

    @property
    def metadata(self) -> LLMMetadata:
        """Return generic metadata for the mixed provider pool."""

        return LLMMetadata(
            context_window=32768,
            num_output=DEFAULT_PROVIDER_POOL_MAX_TOKENS,
            is_chat_model=True,
            model_name=self.model_name,
        )

    def complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Complete one prompt using one available slot with failover."""

        _ = formatted
        content = self._call_with_failover(
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return CompletionResponse(text=content)

    async def acomplete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> CompletionResponse:
        """Async completion using a worker thread for sync HTTP providers."""

        return await asyncio.to_thread(
            self.complete,
            prompt,
            formatted=formatted,
            **kwargs,
        )

    def stream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> CompletionResponseGen:
        """Return a single-response completion stream."""

        response = self.complete(prompt, formatted=formatted, **kwargs)

        def response_gen() -> CompletionResponseGen:
            yield CompletionResponse(text=response.text, delta=response.text)

        return response_gen()

    async def astream_complete(
        self,
        prompt: str,
        formatted: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[CompletionResponse, None]:
        """Async single-response completion stream."""

        response = await self.acomplete(prompt, formatted=formatted, **kwargs)
        yield CompletionResponse(text=response.text, delta=response.text)

    def chat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponse:
        """Chat using one available slot with failover."""

        content = self._call_with_failover(
            messages=chat_messages_payload(messages),
            **kwargs,
        )
        return ChatResponse(
            message=ChatMessage(role="assistant", content=content),
        )

    async def achat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponse:
        """Async chat using a worker thread for sync HTTP providers."""

        return await asyncio.to_thread(self.chat, messages, **kwargs)

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponseGen:
        """Return a single-response chat stream."""

        response = self.chat(messages=messages, **kwargs)
        response_text = str(response.message.content or "")

        def response_gen() -> ChatResponseGen:
            yield ChatResponse(message=response.message, delta=response_text)

        return response_gen()

    async def astream_chat(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> AsyncGenerator[ChatResponse, None]:
        """Async single-response chat stream."""

        response = await self.achat(messages=messages, **kwargs)
        yield ChatResponse(
            message=response.message,
            delta=str(response.message.content or ""),
        )

    def _call_with_failover(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Call one available slot and retry other slots on provider errors."""

        attempted_indices: set[int] = set()
        errors: list[str] = []
        attempt_limit = min(len(self._slots), self.max_slot_attempts)
        while len(attempted_indices) < attempt_limit:
            slot_index = self._acquire_slot(attempted_indices)
            slot = self._slots[slot_index]
            attempted_indices.add(slot_index)
            try:
                return self._call_slot(slot, messages, **kwargs)
            except Exception as exc:
                errors.append(f"{slot.slot_id}: {type(exc).__name__}: {exc}")
            finally:
                self._release_slot(slot_index)
        msg = (
            "All attempted LLM provider slots failed "
            f"({len(attempted_indices)}/{len(self._slots)}): " + "; ".join(errors)
        )
        raise RuntimeError(msg)

    def _acquire_slot(self, excluded_indices: set[int]) -> int:
        """Acquire an available slot not yet attempted for this prompt."""

        with self._condition:
            while True:
                if len(excluded_indices) >= len(self._slots):
                    msg = "No unattempted LLM provider slots remain."
                    raise RuntimeError(msg)
                for offset in range(len(self._slots)):
                    slot_index = (self._next_index + offset) % len(self._slots)
                    if (
                        slot_index not in excluded_indices
                        and self._available[slot_index]
                    ):
                        self._available[slot_index] = False
                        self._next_index = (slot_index + 1) % len(self._slots)
                        return slot_index
                self._condition.wait(timeout=0.1)

    def _release_slot(self, slot_index: int) -> None:
        """Mark a slot as available and wake waiting callers."""

        with self._condition:
            self._available[slot_index] = True
            self._condition.notify_all()

    def _call_slot(
        self,
        slot: EvalLLMProviderSlot,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Call a concrete provider slot."""

        temperature = float(kwargs.get("temperature", 0.0))
        max_tokens = int(
            kwargs.get("max_tokens", DEFAULT_PROVIDER_POOL_MAX_TOKENS),
        )
        with httpx.Client(
            transport=self._transport,
            timeout=self.request_timeout_seconds,
        ) as client:
            if slot.provider in {"openrouter", "nvidia"}:
                response_payload = post_openai_compatible_messages(
                    client=client,
                    slot=slot,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return extract_openai_compatible_content(response_payload)
            if slot.provider == "ollama":
                response_payload = post_ollama_messages(
                    client=client,
                    slot=slot,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return extract_ollama_content(response_payload)
            if slot.provider == "gemini":
                response_payload = post_gemini_messages(
                    client=client,
                    slot=slot,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return extract_gemini_content(response_payload)
        msg = f"Unsupported LLM provider slot: {slot.provider}"
        raise ValueError(msg)


def chat_messages_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    """Convert LlamaIndex chat messages to provider chat payload messages."""

    payload: list[dict[str, str]] = []
    for message in messages:
        role = getattr(message.role, "value", message.role)
        payload.append(
            {
                "role": str(role),
                "content": str(message.content or ""),
            }
        )
    return payload


def post_openai_compatible_messages(
    client: httpx.Client,
    slot: EvalLLMProviderSlot,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Post a chat completion request to OpenRouter or NVIDIA NIM."""

    if not slot.base_url:
        msg = f"{slot.provider} base_url is required."
        raise ValueError(msg)
    if not slot.api_key:
        msg = f"{slot.provider} api_key is required."
        raise ValueError(msg)
    response = client.post(
        openai_compatible_chat_url(slot.base_url),
        headers={
            "Authorization": f"Bearer {slot.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={
            "model": slot.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
    )
    raise_for_status_with_body(response)
    return dict(response.json())


def post_ollama_messages(
    client: httpx.Client,
    slot: EvalLLMProviderSlot,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Post a chat request to an Ollama-compatible endpoint."""

    if not slot.base_url:
        msg = "ollama base_url is required."
        raise ValueError(msg)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if slot.api_key:
        headers["Authorization"] = f"Bearer {slot.api_key}"
    response = client.post(
        f"{slot.base_url.rstrip('/')}/api/chat",
        headers=headers,
        json={
            "model": slot.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
    )
    raise_for_status_with_body(response)
    return dict(response.json())


def post_gemini_messages(
    client: httpx.Client,
    slot: EvalLLMProviderSlot,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Post a generateContent request to Gemini Studio."""

    if not slot.base_url:
        msg = "gemini base_url is required."
        raise ValueError(msg)
    if not slot.api_key:
        msg = "gemini api_key is required."
        raise ValueError(msg)
    system_text = "\n\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )
    contents = [
        {
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["content"]}],
        }
        for message in messages
        if message["role"] != "system"
    ]
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    response = client.post(
        f"{slot.base_url.rstrip('/')}/models/{slot.model}:generateContent",
        headers={
            "x-goog-api-key": slot.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
    )
    raise_for_status_with_body(response)
    return dict(response.json())


def openai_compatible_chat_url(base_url: str) -> str:
    """Return a full OpenAI-compatible chat completions URL."""

    normalized_base_url = base_url.rstrip("/")
    if normalized_base_url.endswith("/chat/completions"):
        return normalized_base_url
    return f"{normalized_base_url}/chat/completions"


def extract_openai_compatible_content(response_payload: dict[str, Any]) -> str:
    """Extract assistant text from an OpenAI-compatible response."""

    try:
        return str(response_payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        msg = "Invalid OpenAI-compatible LLM response."
        raise ValueError(msg) from exc


def extract_ollama_content(response_payload: dict[str, Any]) -> str:
    """Extract assistant text from an Ollama response."""

    try:
        return str(response_payload["message"]["content"])
    except (KeyError, TypeError) as exc:
        msg = "Invalid Ollama LLM response."
        raise ValueError(msg) from exc


def extract_gemini_content(response_payload: dict[str, Any]) -> str:
    """Extract assistant text from a Gemini response."""

    try:
        return str(response_payload["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        msg = "Invalid Gemini LLM response."
        raise ValueError(msg) from exc


def raise_for_status_with_body(response: httpx.Response) -> None:
    """Raise HTTP errors with a small response-body preview."""

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body_preview = response.text.strip()
        if len(body_preview) > 500:
            body_preview = body_preview[:500] + "...[truncated]"
        if body_preview:
            message = f"{exc}. Provider response body: {body_preview}"
        else:
            message = str(exc)
        raise httpx.HTTPStatusError(
            message,
            request=exc.request,
            response=exc.response,
        ) from exc


def build_markdown_element_llm(
    provider: str,
    gemini_model: str,
    gemini_api_keys: Sequence[str],
    provider_slots: Sequence[EvalLLMProviderSlot] = (),
    request_timeout_seconds: float = 120.0,
    max_slot_attempts: int | None = None,
) -> LLM | None:
    """Build the LLM used by LlamaIndex MarkdownElementNodeParser."""

    normalized_provider = provider.strip().lower()
    if normalized_provider in {"", "none", "disabled"}:
        return None
    if normalized_provider in {"multi", "pool", "all", "all_keys"}:
        return ConcurrentProviderPoolLLM(
            slots=provider_slots,
            request_timeout_seconds=request_timeout_seconds,
            max_slot_attempts=max_slot_attempts,
        )
    if normalized_provider in {"gemini", "google_genai"}:
        return RoundRobinGoogleGenAILLM(
            model_name=gemini_model,
            api_keys=gemini_api_keys,
        )
    msg = (
        "Unsupported MARKDOWN_ELEMENT_LLM_PROVIDER="
        f"{provider!r}. Supported providers: multi, gemini, none."
    )
    raise ValueError(msg)
