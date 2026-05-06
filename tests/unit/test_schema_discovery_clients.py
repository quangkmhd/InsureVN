import json

import httpx
import pytest

from src.services.knowledge_graph.schema_discovery import (
    AggregatedSchemaItem,
    SchemaDiscoveryChunk,
    SchemaDiscoveryProviderSlot,
)
from src.services.knowledge_graph.schema_discovery_clients import (
    HttpSchemaDiscoveryClient,
)


@pytest.mark.asyncio
async def test_openai_compatible_clients_post_json_chat_completion_requests() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "nodes": [
                                        {
                                            "label": "QuyenLoiBaoHiem",
                                            "vietnamese_aliases": [
                                                "Quyền lợi bảo hiểm"
                                            ],
                                            "description": "Quyền lợi chi trả.",
                                            "evidence_text": "Quyền lợi nội trú",
                                            "confidence": 0.93,
                                        }
                                    ],
                                    "relationships": [],
                                }
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 123},
            },
        )

    client = HttpSchemaDiscoveryClient(
        transport=httpx.MockTransport(handler),
        timeout_seconds=3.0,
    )
    chunk = SchemaDiscoveryChunk(
        chunk_id="a-0",
        file_path="aia.md",
        chunk_index=0,
        text="Quyền lợi bảo hiểm nội trú",
        content_hash="hash",
    )
    slot = SchemaDiscoveryProviderSlot(
        slot_id="openrouter-0",
        provider="openrouter",
        model="google/gemini-flash",
        api_key="router-key",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )

    result = await client.discover_chunk_schema(chunk, slot)

    assert result.nodes[0].label == "QuyenLoiBaoHiem"
    assert result.provider_slot_id == "openrouter-0"
    assert requests[0].url == "https://openrouter.ai/api/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer router-key"
    request_payload = json.loads(requests[0].content)
    assert request_payload["model"] == "google/gemini-flash"
    assert request_payload["response_format"] == {"type": "json_object"}
    system_prompt = request_payload["messages"][0]["content"]
    assert "Pydantic JSON Schema" in system_prompt
    assert '"nodes"' in system_prompt
    assert '"relationships"' in system_prompt


@pytest.mark.asyncio
async def test_client_extracts_json_object_when_ai_wraps_response_in_text() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                "Đây là kết quả JSON:\n"
                                '{"nodes":[{"label":"Benefit","vietnamese_aliases":'
                                '["Quyền lợi"],"description":"Quyền lợi",'
                                '"evidence_text":"Quyền lợi","confidence":0.91}],'
                                '"relationships":[]}\n'
                                "Kết thúc."
                            )
                        }
                    }
                ]
            },
        )

    client = HttpSchemaDiscoveryClient(transport=httpx.MockTransport(handler))
    chunk = SchemaDiscoveryChunk(
        chunk_id="a-0",
        file_path="aia.md",
        chunk_index=0,
        text="Quyền lợi",
        content_hash="hash",
    )
    slot = SchemaDiscoveryProviderSlot(
        slot_id="openrouter-0",
        provider="openrouter",
        model="google/gemini-flash",
        api_key="router-key",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )

    result = await client.discover_chunk_schema(chunk, slot)

    assert result.nodes[0].label == "Benefit"
    assert result.nodes[0].vietnamese_aliases == ["Quyền lợi"]


@pytest.mark.asyncio
async def test_client_validates_ai_payload_with_pydantic_aliases_and_defaults() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "nodes": [
                                        {
                                            "label": "Benefit",
                                            "aliases": "Quyền lợi bảo hiểm",
                                            "description": "Quyền lợi.",
                                            "evidence_text": "Quyền lợi bảo hiểm",
                                            "confidence": "0.87",
                                            "extra": "ignored",
                                        }
                                    ],
                                    "relationships": [
                                        {
                                            "source_label": "Plan",
                                            "label": "INCLUDES",
                                            "target_label": "Benefit",
                                            "description": "Gói gồm quyền lợi.",
                                            "evidence_text": "bao gồm quyền lợi",
                                            "confidence": "0.8",
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = HttpSchemaDiscoveryClient(transport=httpx.MockTransport(handler))
    chunk = SchemaDiscoveryChunk(
        chunk_id="a-0",
        file_path="aia.md",
        chunk_index=0,
        text="Gói bảo hiểm bao gồm quyền lợi bảo hiểm",
        content_hash="hash",
    )
    slot = SchemaDiscoveryProviderSlot(
        slot_id="openrouter-0",
        provider="openrouter",
        model="google/gemini-flash",
        api_key="router-key",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )

    result = await client.discover_chunk_schema(chunk, slot)

    assert result.nodes[0].vietnamese_aliases == ["Quyền lợi bảo hiểm"]
    assert result.nodes[0].confidence == 0.87
    assert result.relationships[0].relationship_label == "INCLUDES"
    assert result.relationships[0].vietnamese_aliases == []


@pytest.mark.asyncio
async def test_ollama_client_posts_api_chat_with_json_format() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "nodes": [],
                            "relationships": [
                                {
                                    "source_label": "Plan",
                                    "relationship_label": "INCLUDES",
                                    "target_label": "Benefit",
                                    "vietnamese_aliases": ["bao gồm"],
                                    "description": "Gói bao gồm quyền lợi.",
                                    "evidence_text": "bao gồm quyền lợi",
                                    "confidence": 0.9,
                                }
                            ],
                        }
                    )
                }
            },
        )

    client = HttpSchemaDiscoveryClient(transport=httpx.MockTransport(handler))
    chunk = SchemaDiscoveryChunk(
        chunk_id="a-0",
        file_path="aia.md",
        chunk_index=0,
        text="bao gồm quyền lợi",
        content_hash="hash",
    )
    slot = SchemaDiscoveryProviderSlot(
        slot_id="ollama-0",
        provider="ollama",
        model="gemma4:31b-cloud",
        base_url="http://localhost:11434",
    )

    result = await client.discover_chunk_schema(chunk, slot)

    assert result.relationships[0].relationship_label == "INCLUDES"
    assert requests[0].url == "http://localhost:11434/api/chat"
    request_payload = json.loads(requests[0].content)
    assert request_payload["stream"] is False
    assert request_payload["format"] == "json"


@pytest.mark.asyncio
async def test_gemini_client_posts_generate_content_with_api_key_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "nodes": [],
                                            "relationships": [],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ],
                "usageMetadata": {"totalTokenCount": 42},
            },
        )

    client = HttpSchemaDiscoveryClient(transport=httpx.MockTransport(handler))
    chunk = SchemaDiscoveryChunk(
        chunk_id="a-0",
        file_path="aia.md",
        chunk_index=0,
        text="Điều khoản bảo hiểm",
        content_hash="hash",
    )
    slot = SchemaDiscoveryProviderSlot(
        slot_id="gemini-0",
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="gemini-key",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )

    result = await client.discover_chunk_schema(chunk, slot)

    assert result.nodes == []
    assert requests[0].url == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent"
    )
    assert requests[0].headers["x-goog-api-key"] == "gemini-key"
    request_payload = json.loads(requests[0].content)
    assert request_payload["generationConfig"]["responseMimeType"] == (
        "application/json"
    )


@pytest.mark.asyncio
async def test_gemini_http_error_includes_provider_response_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Request payload size exceeds the limit.",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )

    client = HttpSchemaDiscoveryClient(transport=httpx.MockTransport(handler))
    chunk = SchemaDiscoveryChunk(
        chunk_id="a-0",
        file_path="aia.md",
        chunk_index=0,
        text="Điều khoản bảo hiểm",
        content_hash="hash",
    )
    slot = SchemaDiscoveryProviderSlot(
        slot_id="gemini-0",
        provider="gemini",
        model="gemma-4-31b-it",
        api_key="gemini-key",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.discover_chunk_schema(chunk, slot)

    assert "Request payload size exceeds the limit" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_asks_ai_to_canonicalize_similar_schema_labels() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "canonical_node_map": {
                                        "QuyenLoiBaoHiem": "Benefit",
                                        "PhamViBaoHiem": "Benefit",
                                    },
                                    "canonical_relationship_map": {
                                        "BAO_GOM": "INCLUDES",
                                        "CO_QUYEN_LOI": "INCLUDES",
                                    },
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = HttpSchemaDiscoveryClient(transport=httpx.MockTransport(handler))
    slot = SchemaDiscoveryProviderSlot(
        slot_id="openrouter-0",
        provider="openrouter",
        model="google/gemini-flash",
        api_key="router-key",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )

    canonical_map = await client.canonicalize_schema_labels(
        node_items=[
            AggregatedSchemaItem(
                label="QuyenLoiBaoHiem",
                occurrence_count=3,
                source_files=["aia.md"],
                aliases=["Quyền lợi bảo hiểm"],
                examples=["Quyền lợi nội trú"],
                average_confidence=0.92,
            ),
            AggregatedSchemaItem(
                label="PhamViBaoHiem",
                occurrence_count=2,
                source_files=["aia.md"],
                aliases=["Phạm vi bảo hiểm"],
                examples=["Phạm vi nội trú"],
                average_confidence=0.9,
            ),
        ],
        relationship_items=[
            AggregatedSchemaItem(
                label="BAO_GOM",
                occurrence_count=3,
                source_files=["aia.md"],
                aliases=["bao gồm"],
                examples=["Gói bao gồm quyền lợi"],
                average_confidence=0.9,
            ),
            AggregatedSchemaItem(
                label="CO_QUYEN_LOI",
                occurrence_count=1,
                source_files=["bao_minh.md"],
                aliases=["có quyền lợi"],
                examples=["Sản phẩm có quyền lợi"],
                average_confidence=0.88,
            ),
        ],
        slot=slot,
    )

    assert canonical_map.node_map["PhamViBaoHiem"] == "Benefit"
    assert canonical_map.relationship_map["CO_QUYEN_LOI"] == "INCLUDES"
    request_payload = json.loads(requests[0].content)
    assert "QuyenLoiBaoHiem" in request_payload["messages"][1]["content"]
    assert "source_file_count" in request_payload["messages"][1]["content"]
    assert "source_files" not in request_payload["messages"][1]["content"]
