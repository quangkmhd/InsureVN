"""LLM provider slot collection for evaluation chunkers."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalLLMProviderSlot:
    """One callable LLM endpoint/key pair for chunking evaluation."""

    slot_id: str
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""


def collect_markdown_element_llm_provider_slots(
    environ: Mapping[str, str | None] = os.environ,
) -> tuple[EvalLLMProviderSlot, ...]:
    """Collect Gemini, Ollama, OpenRouter, and NVIDIA slots from env vars."""

    slots_by_provider = {
        "gemini": _collect_gemini_slots(environ),
        "ollama": _collect_ollama_slots(environ),
        "openrouter": _collect_openrouter_slots(environ),
        "nvidia": _collect_nvidia_slots(environ),
    }
    provider_order = _env_csv(
        environ,
        "MARKDOWN_ELEMENT_LLM_PROVIDER_ORDER",
    ) or ("gemini", "ollama", "openrouter", "nvidia")
    slots: list[EvalLLMProviderSlot] = []
    for provider in provider_order:
        slots.extend(slots_by_provider.get(provider.strip().lower(), ()))
    return tuple(slots)


def provider_slot_counts(
    slots: Sequence[EvalLLMProviderSlot],
) -> dict[str, int]:
    """Count configured slots by provider without exposing keys."""

    counts: dict[str, int] = {}
    for slot in slots:
        counts[slot.provider] = counts.get(slot.provider, 0) + 1
    return counts


def _collect_gemini_slots(
    environ: Mapping[str, str | None],
) -> tuple[EvalLLMProviderSlot, ...]:
    keys = _collect_values(
        environ,
        csv_names=(
            "MARKDOWN_ELEMENT_GEMINI_API_KEYS",
            "KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS",
            "GEMINI_API_KEYS",
        ),
        numbered_prefixes=(
            "MARKDOWN_ELEMENT_GEMINI_API_KEY",
            "KG_SCHEMA_DISCOVERY_GEMINI_API_KEY",
            "GEMINI_API_KEY",
        ),
        single_names=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    model = _first_env(
        environ,
        (
            "MARKDOWN_ELEMENT_GEMINI_MODEL",
            "LLM_CHUNKING_MODEL",
            "KG_SCHEMA_DISCOVERY_GEMINI_MODEL",
            "LLM_MODEL",
        ),
        "gemma-4-31b-it",
    )
    base_url = _first_env(
        environ,
        ("MARKDOWN_ELEMENT_GEMINI_BASE_URL", "KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL"),
        "https://generativelanguage.googleapis.com/v1beta",
    )
    return tuple(
        EvalLLMProviderSlot(
            slot_id=f"gemini-{index}",
            provider="gemini",
            model=model,
            api_key=key,
            base_url=base_url,
        )
        for index, key in enumerate(keys)
    )


def _collect_ollama_slots(
    environ: Mapping[str, str | None],
) -> tuple[EvalLLMProviderSlot, ...]:
    keys = _collect_values(
        environ,
        csv_names=(
            "MARKDOWN_ELEMENT_OLLAMA_API_KEYS",
            "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS",
            "OLLAMA_API_KEYS",
        ),
        numbered_prefixes=(
            "MARKDOWN_ELEMENT_OLLAMA_API_KEY",
            "KG_SCHEMA_DISCOVERY_OLLAMA_API_KEY",
            "OLLAMA_API_KEY",
        ),
        single_names=("OLLAMA_API_KEY",),
    )
    base_urls = _collect_values(
        environ,
        csv_names=(
            "MARKDOWN_ELEMENT_OLLAMA_BASE_URLS",
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS",
        ),
        single_names=(
            "MARKDOWN_ELEMENT_OLLAMA_BASE_URL",
            "KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URL",
            "LLM_BASE_URL",
        ),
    ) or ("http://localhost:11434",)
    model = _first_env(
        environ,
        (
            "MARKDOWN_ELEMENT_OLLAMA_MODEL",
            "KG_SCHEMA_DISCOVERY_OLLAMA_MODEL",
            "LLM_MODEL",
        ),
        "gemma4:31b-cloud",
    )
    if keys:
        return tuple(
            EvalLLMProviderSlot(
                slot_id=f"ollama-{index}",
                provider="ollama",
                model=model,
                api_key=key,
                base_url=base_urls[index % len(base_urls)],
            )
            for index, key in enumerate(keys)
        )
    return tuple(
        EvalLLMProviderSlot(
            slot_id=f"ollama-{index}",
            provider="ollama",
            model=model,
            base_url=base_url,
        )
        for index, base_url in enumerate(base_urls)
    )


def _collect_openrouter_slots(
    environ: Mapping[str, str | None],
) -> tuple[EvalLLMProviderSlot, ...]:
    keys = _collect_values(
        environ,
        csv_names=(
            "MARKDOWN_ELEMENT_OPENROUTER_API_KEYS",
            "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS",
            "OPENROUTER_API_KEYS",
        ),
        numbered_prefixes=(
            "MARKDOWN_ELEMENT_OPENROUTER_API_KEY",
            "KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEY",
            "OPENROUTER_API_KEY",
        ),
        single_names=("OPENROUTER_API_KEY",),
    )
    model = _first_env(
        environ,
        (
            "MARKDOWN_ELEMENT_OPENROUTER_MODEL",
            "OPENROUTER_LLM_MODEL",
            "KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL",
        ),
        "openrouter/free",
    )
    base_url = _first_env(
        environ,
        (
            "MARKDOWN_ELEMENT_OPENROUTER_BASE_URL",
            "KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL",
        ),
        "https://openrouter.ai/api/v1/chat/completions",
    )
    return tuple(
        EvalLLMProviderSlot(
            slot_id=f"openrouter-{index}",
            provider="openrouter",
            model=model,
            api_key=key,
            base_url=base_url,
        )
        for index, key in enumerate(keys)
    )


def _collect_nvidia_slots(
    environ: Mapping[str, str | None],
) -> tuple[EvalLLMProviderSlot, ...]:
    keys = _collect_values(
        environ,
        csv_names=(
            "MARKDOWN_ELEMENT_NVIDIA_API_KEYS",
            "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS",
            "NVIDIA_NIM_API_KEYS",
            "NVIDIA_API_KEYS",
        ),
        numbered_prefixes=(
            "MARKDOWN_ELEMENT_NVIDIA_API_KEY",
            "KG_SCHEMA_DISCOVERY_NVIDIA_API_KEY",
            "NVIDIA_NIM_API",
            "NVIDIA_NIM_API_KEY",
            "NVIDIA_API_KEY",
            "NVIDIA_PAI_KEY",
        ),
        single_names=("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY", "NVIDIA_PAI_KEY"),
    )
    model = _first_env(
        environ,
        ("MARKDOWN_ELEMENT_NVIDIA_MODEL", "KG_SCHEMA_DISCOVERY_NVIDIA_MODEL"),
        "google/gemma-4-31b-it",
    )
    base_url = _first_env(
        environ,
        ("MARKDOWN_ELEMENT_NVIDIA_BASE_URL", "KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL"),
        "https://integrate.api.nvidia.com/v1/chat/completions",
    )
    return tuple(
        EvalLLMProviderSlot(
            slot_id=f"nvidia-{index}",
            provider="nvidia",
            model=model,
            api_key=key,
            base_url=base_url,
        )
        for index, key in enumerate(keys)
    )


def _collect_values(
    environ: Mapping[str, str | None],
    *,
    csv_names: Sequence[str] = (),
    numbered_prefixes: Sequence[str] = (),
    single_names: Sequence[str] = (),
    max_numbered_values: int = 50,
) -> tuple[str, ...]:
    values: list[str] = []
    for name in csv_names:
        values.extend(_env_csv(environ, name))
    for prefix in numbered_prefixes:
        for index in range(1, max_numbered_values + 1):
            value = _env_value(environ, f"{prefix}_{index}")
            if value:
                values.append(value)
    for name in single_names:
        value = _env_value(environ, name)
        if value:
            values.append(value)
    return _dedupe(values)


def _env_csv(
    environ: Mapping[str, str | None],
    name: str,
) -> tuple[str, ...]:
    value = _env_value(environ, name)
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _first_env(
    environ: Mapping[str, str | None],
    names: Sequence[str],
    default: str,
) -> str:
    for name in names:
        value = _env_value(environ, name)
        if value:
            return value
    return default


def _env_value(environ: Mapping[str, str | None], name: str) -> str:
    value = environ.get(name)
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'")


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    unique_values: list[str] = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return tuple(unique_values)
