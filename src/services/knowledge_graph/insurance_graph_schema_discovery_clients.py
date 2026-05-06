"""HTTP clients for AI-assisted knowledge graph schema discovery."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from src.services.knowledge_graph.insurance_graph_schema_discovery import (
    AggregatedSchemaItem,
    SchemaCanonicalizationMap,
    SchemaChunkDiscoveryResult,
    SchemaDiscoveryChunk,
    SchemaDiscoveryProviderSlot,
    SchemaNodeProposal,
    SchemaRelationshipProposal,
)
from src.services.observability import service_observe

_JSON_DECODER = json.JSONDecoder()
_HTTP_ERROR_BODY_PREVIEW_CHARS = 1000
_CANONICALIZATION_ALIAS_LIMIT = 8
_CANONICALIZATION_EXAMPLE_LIMIT = 3


class _SchemaDiscoveryNodePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(description="Reusable graph node schema label.")
    vietnamese_aliases: list[str] = Field(
        default_factory=list,
        description="Vietnamese terms from the document for this node type.",
        validation_alias=AliasChoices(
            "vietnamese_aliases",
            "aliases",
            "alias",
            "vietnamese_terms",
        ),
    )
    description: str = Field(default="", description="Short schema description.")
    evidence_text: str = Field(
        default="",
        description="Short exact source phrase grounding the proposal.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0.",
    )

    @field_validator("vietnamese_aliases", mode="before")
    @classmethod
    def _normalize_aliases(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [value]
        return value


class _SchemaDiscoveryRelationshipPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_label: str = Field(description="Source node schema label.")
    relationship_label: str = Field(
        description="Reusable graph relationship schema label.",
        validation_alias=AliasChoices(
            "relationship_label",
            "label",
            "type",
            "relation",
            "relationship_type",
        ),
    )
    target_label: str = Field(description="Target node schema label.")
    vietnamese_aliases: list[str] = Field(
        default_factory=list,
        description="Vietnamese relation phrases from the document.",
        validation_alias=AliasChoices(
            "vietnamese_aliases",
            "aliases",
            "alias",
            "vietnamese_terms",
        ),
    )
    description: str = Field(default="", description="Short schema description.")
    evidence_text: str = Field(
        default="",
        description="Short exact source phrase grounding the proposal.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0.",
    )

    @field_validator("vietnamese_aliases", mode="before")
    @classmethod
    def _normalize_aliases(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [value]
        return value


class _SchemaDiscoveryResponsePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nodes: list[_SchemaDiscoveryNodePayload] = Field(default_factory=list)
    relationships: list[_SchemaDiscoveryRelationshipPayload] = Field(
        default_factory=list
    )

    @field_validator("nodes", "relationships", mode="before")
    @classmethod
    def _normalize_lists(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        return value


class _SchemaCanonicalizationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    canonical_node_map: dict[str, str] = Field(default_factory=dict)
    canonical_relationship_map: dict[str, str] = Field(default_factory=dict)


def _json_schema_for_prompt(model_type: type[BaseModel]) -> str:
    return json.dumps(
        model_type.model_json_schema(mode="validation"),
        ensure_ascii=False,
        indent=2,
    )


SCHEMA_DISCOVERY_SYSTEM_PROMPT = f"""
You extract graph schema candidates from Vietnamese insurance policy text.

Return exactly one JSON object that validates against this Pydantic JSON Schema:
{_json_schema_for_prompt(_SchemaDiscoveryResponsePayload)}

Rules:
- Output raw JSON only. Do not wrap it in markdown fences. Do not add
  explanations before or after the JSON.
- Propose schema types, not individual insurance records.
- Prefer Vietnamese insurance concepts from the source text.
- Keep labels stable and reusable across files.
- Include only candidates grounded by evidence_text from the chunk.
- If no useful schema appears, return empty arrays.
""".strip()

SCHEMA_CANONICALIZATION_SYSTEM_PROMPT = f"""
You merge similar graph schema labels from Vietnamese insurance documents.

Return exactly one JSON object that validates against this Pydantic JSON Schema:
{_json_schema_for_prompt(_SchemaCanonicalizationPayload)}

Rules:
- Output raw JSON only. Do not wrap it in markdown fences. Do not add
  explanations before or after the JSON.
- Merge labels that represent the same reusable graph concept.
- Prefer concise English canonical names for nodes: Benefit, Exclusion, Plan.
- Prefer UPPER_SNAKE_CASE canonical names for relationships.
- Keep distinct concepts separate.
- Every raw label in the input must appear in exactly one map entry.
""".strip()


class HttpSchemaDiscoveryClient:
    """Call Ollama, OpenAI-compatible, and Gemini APIs for schema discovery."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        """Initialize an async HTTP schema discovery client."""
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery_clients.discover_chunk_schema",
        component="schema_discovery_client",
    )
    async def discover_chunk_schema(
        self,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaChunkDiscoveryResult:
        """Discover schema candidates from a chunk using the given provider slot."""
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=self._timeout_seconds,
        ) as client:
            if slot.provider == "ollama":
                response_payload = await self._post_ollama(client, chunk, slot)
                content = _extract_ollama_content(response_payload)
                usage = _ollama_usage(response_payload)
            elif slot.provider in {"openrouter", "nvidia"}:
                response_payload = await self._post_openai_compatible(
                    client,
                    chunk,
                    slot,
                )
                content = _extract_openai_compatible_content(response_payload)
                usage = dict(response_payload.get("usage", {}))
            elif slot.provider == "gemini":
                response_payload = await self._post_gemini(client, chunk, slot)
                content = _extract_gemini_content(response_payload)
                usage = dict(response_payload.get("usageMetadata", {}))
            else:
                raise ValueError(
                    f"Unsupported schema discovery provider: {slot.provider}"
                )

        return _parse_schema_discovery_content(
            content=content,
            chunk=chunk,
            provider_slot_id=slot.slot_id,
            usage=usage,
        )

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery_clients.canonicalize",
        component="schema_discovery_client",
    )
    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        """Ask an AI provider to merge similar discovered schema labels."""
        content = _schema_canonicalization_user_prompt(
            node_items=node_items,
            relationship_items=relationship_items,
        )
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=self._timeout_seconds,
        ) as client:
            if slot.provider == "gemini":
                response_payload = await self._post_gemini_content(
                    client,
                    slot,
                    system_prompt=SCHEMA_CANONICALIZATION_SYSTEM_PROMPT,
                    user_prompt=content,
                )
                response_content = _extract_gemini_content(response_payload)
            elif slot.provider == "ollama":
                response_payload = await self._post_ollama_messages(
                    client,
                    slot,
                    messages=[
                        {
                            "role": "system",
                            "content": SCHEMA_CANONICALIZATION_SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": content},
                    ],
                )
                response_content = _extract_ollama_content(response_payload)
            elif slot.provider in {"openrouter", "nvidia"}:
                response_payload = await self._post_openai_compatible_messages(
                    client,
                    slot,
                    messages=[
                        {
                            "role": "system",
                            "content": SCHEMA_CANONICALIZATION_SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": content},
                    ],
                )
                response_content = _extract_openai_compatible_content(response_payload)
            else:
                raise ValueError(
                    f"Unsupported schema discovery provider: {slot.provider}"
                )

        payload = _SchemaCanonicalizationPayload.model_validate(
            _loads_json_object(response_content)
        )
        return SchemaCanonicalizationMap(
            node_map=dict(payload.canonical_node_map),
            relationship_map=dict(payload.canonical_relationship_map),
        )

    async def _post_openai_compatible(
        self,
        client: httpx.AsyncClient,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> dict[str, Any]:
        if not slot.base_url:
            raise ValueError(f"{slot.provider} base_url is required.")
        if not slot.api_key:
            raise ValueError(f"{slot.provider} api_key is required.")

        response = await client.post(
            slot.base_url,
            headers={
                "Authorization": f"Bearer {slot.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model": slot.model,
                "messages": _schema_discovery_messages(chunk),
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        _raise_for_status_with_body(response)
        return dict(response.json())

    async def _post_openai_compatible_messages(
        self,
        client: httpx.AsyncClient,
        slot: SchemaDiscoveryProviderSlot,
        *,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        if not slot.base_url:
            raise ValueError(f"{slot.provider} base_url is required.")
        if not slot.api_key:
            raise ValueError(f"{slot.provider} api_key is required.")
        response = await client.post(
            slot.base_url,
            headers={
                "Authorization": f"Bearer {slot.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "model": slot.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
        _raise_for_status_with_body(response)
        return dict(response.json())

    async def _post_ollama(
        self,
        client: httpx.AsyncClient,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> dict[str, Any]:
        if not slot.base_url:
            raise ValueError("ollama base_url is required.")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if slot.api_key:
            headers["Authorization"] = f"Bearer {slot.api_key}"
        return await self._post_ollama_messages(
            client,
            slot,
            messages=_schema_discovery_messages(chunk),
        )

    async def _post_ollama_messages(
        self,
        client: httpx.AsyncClient,
        slot: SchemaDiscoveryProviderSlot,
        *,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        if not slot.base_url:
            raise ValueError("ollama base_url is required.")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if slot.api_key:
            headers["Authorization"] = f"Bearer {slot.api_key}"
        response = await client.post(
            f"{slot.base_url.rstrip('/')}/api/chat",
            headers=headers,
            json={
                "model": slot.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
        )
        _raise_for_status_with_body(response)
        return dict(response.json())

    async def _post_gemini(
        self,
        client: httpx.AsyncClient,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> dict[str, Any]:
        if not slot.base_url:
            raise ValueError("gemini base_url is required.")
        if not slot.api_key:
            raise ValueError("gemini api_key is required.")
        return await self._post_gemini_content(
            client,
            slot,
            system_prompt=SCHEMA_DISCOVERY_SYSTEM_PROMPT,
            user_prompt=_schema_discovery_user_prompt(chunk),
        )

    async def _post_gemini_content(
        self,
        client: httpx.AsyncClient,
        slot: SchemaDiscoveryProviderSlot,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        if not slot.base_url:
            raise ValueError("gemini base_url is required.")
        if not slot.api_key:
            raise ValueError("gemini api_key is required.")
        response = await client.post(
            f"{slot.base_url.rstrip('/')}/models/{slot.model}:generateContent",
            headers={
                "x-goog-api-key": slot.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": user_prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                },
            },
        )
        _raise_for_status_with_body(response)
        return dict(response.json())


def _schema_discovery_messages(chunk: SchemaDiscoveryChunk) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SCHEMA_DISCOVERY_SYSTEM_PROMPT},
        {"role": "user", "content": _schema_discovery_user_prompt(chunk)},
    ]


def _schema_discovery_user_prompt(chunk: SchemaDiscoveryChunk) -> str:
    return (
        "Discover reusable graph schema candidates from this Vietnamese "
        "insurance policy markdown chunk.\n\n"
        f"file_path: {chunk.file_path}\n"
        f"chunk_id: {chunk.chunk_id}\n"
        f"chunk_index: {chunk.chunk_index}\n\n"
        "TEXT:\n"
        f"{chunk.text}"
    )


def _schema_canonicalization_user_prompt(
    *,
    node_items: list[AggregatedSchemaItem],
    relationship_items: list[AggregatedSchemaItem],
) -> str:
    payload = {
        "nodes": [_aggregated_item_payload(item) for item in node_items],
        "relationships": [
            _aggregated_item_payload(item) for item in relationship_items
        ],
    }
    return (
        "Merge similar node and relationship schema labels from this corpus "
        "summary. Return complete canonical maps for every raw label.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _aggregated_item_payload(item: AggregatedSchemaItem) -> dict[str, Any]:
    return {
        "label": item.label,
        "occurrence_count": item.occurrence_count,
        "source_file_count": len(item.source_files),
        "aliases": item.aliases[:_CANONICALIZATION_ALIAS_LIMIT],
        "examples": item.examples[:_CANONICALIZATION_EXAMPLE_LIMIT],
        "average_confidence": item.average_confidence,
    }


def _raise_for_status_with_body(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body_preview = response.text.strip()
        if len(body_preview) > _HTTP_ERROR_BODY_PREVIEW_CHARS:
            body_preview = (
                body_preview[:_HTTP_ERROR_BODY_PREVIEW_CHARS] + "...[truncated]"
            )
        if body_preview:
            message = f"{exc}. Provider response body: {body_preview}"
        else:
            message = str(exc)
        raise httpx.HTTPStatusError(
            message,
            request=exc.request,
            response=exc.response,
        ) from exc


def _extract_openai_compatible_content(response_payload: dict[str, Any]) -> str:
    try:
        return str(response_payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            "Invalid OpenAI-compatible schema discovery response."
        ) from exc


def _extract_ollama_content(response_payload: dict[str, Any]) -> str:
    try:
        return str(response_payload["message"]["content"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid Ollama schema discovery response.") from exc


def _extract_gemini_content(response_payload: dict[str, Any]) -> str:
    try:
        return str(response_payload["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid Gemini schema discovery response.") from exc


def _ollama_usage(response_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: response_payload[key]
        for key in (
            "prompt_eval_count",
            "eval_count",
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
        )
        if key in response_payload
    }


def _parse_schema_discovery_content(
    *,
    content: str,
    chunk: SchemaDiscoveryChunk,
    provider_slot_id: str,
    usage: dict[str, Any],
) -> SchemaChunkDiscoveryResult:
    payload = _SchemaDiscoveryResponsePayload.model_validate(
        _loads_json_object(content)
    )
    nodes = [
        SchemaNodeProposal(
            label=item.label,
            vietnamese_aliases=item.vietnamese_aliases,
            description=item.description,
            evidence_text=item.evidence_text,
            confidence=item.confidence,
        )
        for item in payload.nodes
    ]
    relationships = [
        SchemaRelationshipProposal(
            source_label=item.source_label,
            relationship_label=item.relationship_label,
            target_label=item.target_label,
            vietnamese_aliases=item.vietnamese_aliases,
            description=item.description,
            evidence_text=item.evidence_text,
            confidence=item.confidence,
        )
        for item in payload.relationships
    ]
    return SchemaChunkDiscoveryResult(
        chunk_id=chunk.chunk_id,
        file_path=chunk.file_path,
        content_hash=chunk.content_hash,
        provider_slot_id=provider_slot_id,
        nodes=nodes,
        relationships=relationships,
        usage=usage,
    )


def _loads_json_object(content: str) -> dict[str, Any]:
    stripped_content = content.strip()
    fenced_match = re.search(
        r"```(?:json)?\s*(.*?)```",
        stripped_content,
        flags=re.DOTALL,
    )
    if fenced_match:
        stripped_content = fenced_match.group(1).strip()
    try:
        payload = json.loads(stripped_content)
    except json.JSONDecodeError as exc:
        payload = _loads_first_embedded_json_object(stripped_content, exc)
    if not isinstance(payload, dict):
        raise ValueError("Schema discovery response must be a JSON object.")
    return payload


def _loads_first_embedded_json_object(
    content: str,
    original_error: json.JSONDecodeError,
) -> dict[str, Any]:
    for match in re.finditer(r"\{", content):
        try:
            payload, _end_index = _JSON_DECODER.raw_decode(content[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError(
        "Schema discovery response was not valid JSON."
    ) from original_error
