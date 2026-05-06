import asyncio
import json

import pytest

from src.services.knowledge_graph.schema_discovery import (
    AggregatedSchemaItem,
    FileSchemaSummary,
    MarkdownSchemaDiscoveryChunker,
    SchemaCanonicalizationMap,
    SchemaChunkDiscoveryResult,
    SchemaDiscoveryAggregator,
    SchemaDiscoveryCanonicalizer,
    SchemaDiscoveryCheckpointStore,
    SchemaDiscoveryChunk,
    SchemaDiscoveryProviderSlot,
    SchemaDiscoveryRunner,
    SchemaDiscoverySummary,
    SchemaNodeProposal,
    SchemaRelationshipProposal,
    write_schema_discovery_markdown_report,
)


class FakeSchemaDiscoveryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def discover_chunk_schema(
        self,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaChunkDiscoveryResult:
        self.calls.append((chunk.chunk_id, slot.slot_id))
        if "fail" in chunk.text:
            raise RuntimeError("provider failed")
        return SchemaChunkDiscoveryResult(
            chunk_id=chunk.chunk_id,
            file_path=chunk.file_path,
            content_hash=chunk.content_hash,
            provider_slot_id=slot.slot_id,
            nodes=[
                SchemaNodeProposal(
                    label="QuyenLoiBaoHiem",
                    vietnamese_aliases=["Quyền lợi bảo hiểm"],
                    description="Các quyền lợi được chi trả.",
                    evidence_text="Quyền lợi bảo hiểm: nội trú",
                    confidence=0.91,
                )
            ],
            relationships=[
                SchemaRelationshipProposal(
                    source_label="Plan",
                    relationship_label="BAO_GOM",
                    target_label="QuyenLoiBaoHiem",
                    vietnamese_aliases=["bao gồm", "gồm"],
                    description="Gói bảo hiểm bao gồm quyền lợi.",
                    evidence_text="Gói bảo hiểm bao gồm quyền lợi nội trú",
                    confidence=0.9,
                )
            ],
        )


class FlakySchemaDiscoveryClient:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls: list[tuple[str, str]] = []

    async def discover_chunk_schema(
        self,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaChunkDiscoveryResult:
        self.calls.append((chunk.chunk_id, slot.slot_id))
        if len(self.calls) <= self.failures_before_success:
            raise RuntimeError("temporary provider failure")
        return SchemaChunkDiscoveryResult(
            chunk_id=chunk.chunk_id,
            file_path=chunk.file_path,
            content_hash=chunk.content_hash,
            provider_slot_id=slot.slot_id,
            nodes=[],
            relationships=[],
        )


class SlowSchemaDiscoveryClient:
    async def discover_chunk_schema(
        self,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaChunkDiscoveryResult:
        _ = (chunk, slot)
        await asyncio.sleep(10)
        raise RuntimeError("unreachable")


class FakeSchemaCanonicalizationClient:
    def __init__(self) -> None:
        self.called = False

    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        self.called = True
        assert slot.slot_id == "gemini-0"
        assert [item.label for item in node_items] == [
            "PhamViBaoHiem",
            "QuyenLoiBaoHiem",
        ]
        assert [item.label for item in relationship_items] == ["BAO_GOM"]
        return SchemaCanonicalizationMap(
            node_map={
                "PhamViBaoHiem": "Benefit",
                "QuyenLoiBaoHiem": "Benefit",
            },
            relationship_map={"BAO_GOM": "INCLUDES"},
        )


class FailingSchemaCanonicalizationClient:
    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        _ = (node_items, relationship_items, slot)
        raise RuntimeError("canonical provider failed")


@pytest.mark.asyncio
async def test_runner_skips_successful_chunks_and_retries_failed_chunks(
    tmp_path,
) -> None:
    checkpoint_store = SchemaDiscoveryCheckpointStore(
        tmp_path / "schema_discovery_checkpoint.jsonl"
    )
    completed_chunk = SchemaDiscoveryChunk(
        chunk_id="chunk-success",
        file_path="policy_a.md",
        chunk_index=0,
        text="done",
        content_hash="hash-success",
    )
    failed_chunk = SchemaDiscoveryChunk(
        chunk_id="chunk-failed",
        file_path="policy_a.md",
        chunk_index=1,
        text="retry now",
        content_hash="hash-failed",
    )
    new_chunk = SchemaDiscoveryChunk(
        chunk_id="chunk-new",
        file_path="policy_b.md",
        chunk_index=0,
        text="new",
        content_hash="hash-new",
    )
    checkpoint_store.record_success(
        completed_chunk,
        SchemaChunkDiscoveryResult(
            chunk_id=completed_chunk.chunk_id,
            file_path=completed_chunk.file_path,
            content_hash=completed_chunk.content_hash,
            provider_slot_id="ollama-0",
            nodes=[],
            relationships=[],
        ),
    )
    checkpoint_store.record_error(
        failed_chunk,
        provider_slot_id="openrouter-0",
        error_message="temporary failure",
    )
    client = FakeSchemaDiscoveryClient()
    runner = SchemaDiscoveryRunner(
        checkpoint_store=checkpoint_store,
        provider_slots=[
            SchemaDiscoveryProviderSlot(
                slot_id="ollama-0",
                provider="ollama",
                model="local-model",
                base_url="http://localhost:11434",
            ),
            SchemaDiscoveryProviderSlot(
                slot_id="openrouter-0",
                provider="openrouter",
                model="openrouter-model",
                api_key="router-key",
            ),
        ],
        max_concurrency=2,
    )

    results = await runner.run(
        chunks=[completed_chunk, failed_chunk, new_chunk],
        client=client,
    )

    assert [result.chunk_id for result in results] == [
        "chunk-success",
        "chunk-failed",
        "chunk-new",
    ]
    assert [call[0] for call in client.calls] == ["chunk-failed", "chunk-new"]
    assert checkpoint_store.successful_chunk_ids(
        [completed_chunk, failed_chunk, new_chunk]
    ) == {"chunk-success", "chunk-failed", "chunk-new"}


@pytest.mark.asyncio
async def test_runner_retries_chunk_twice_before_recording_success(tmp_path) -> None:
    checkpoint_store = SchemaDiscoveryCheckpointStore(
        tmp_path / "schema_discovery_checkpoint.jsonl"
    )
    chunk = SchemaDiscoveryChunk(
        chunk_id="chunk-flaky",
        file_path="policy.md",
        chunk_index=0,
        text="Quyền lợi bảo hiểm",
        content_hash="hash-flaky",
    )
    client = FlakySchemaDiscoveryClient(failures_before_success=2)
    runner = SchemaDiscoveryRunner(
        checkpoint_store=checkpoint_store,
        provider_slots=[
            SchemaDiscoveryProviderSlot(
                slot_id="gemini-0",
                provider="gemini",
                model="gemini-2.5-flash",
                api_key="gemini-key",
            )
        ],
        max_concurrency=1,
    )

    results = await runner.run(chunks=[chunk], client=client)

    assert [result.chunk_id for result in results] == ["chunk-flaky"]
    assert client.calls == [
        ("chunk-flaky", "gemini-0"),
        ("chunk-flaky", "gemini-0"),
        ("chunk-flaky", "gemini-0"),
    ]
    assert checkpoint_store.successful_chunk_ids([chunk]) == {"chunk-flaky"}


@pytest.mark.asyncio
async def test_runner_records_timeout_when_provider_attempt_stalls(tmp_path) -> None:
    checkpoint_path = tmp_path / "schema_discovery_checkpoint.jsonl"
    checkpoint_store = SchemaDiscoveryCheckpointStore(checkpoint_path)
    chunk = SchemaDiscoveryChunk(
        chunk_id="chunk-slow",
        file_path="policy.md",
        chunk_index=0,
        text="Quyền lợi bảo hiểm",
        content_hash="hash-slow",
    )
    runner = SchemaDiscoveryRunner(
        checkpoint_store=checkpoint_store,
        provider_slots=[
            SchemaDiscoveryProviderSlot(
                slot_id="openrouter-0",
                provider="openrouter",
                model="openrouter-model",
                api_key="router-key",
            )
        ],
        max_concurrency=1,
        max_retries=0,
        attempt_timeout_seconds=0.01,
    )

    results = await runner.run(chunks=[chunk], client=SlowSchemaDiscoveryClient())

    assert results == []
    records = [
        json.loads(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["status"] == "error"
    assert records[-1]["chunk_id"] == "chunk-slow"
    assert records[-1]["provider_slot_id"] == "openrouter-0"
    assert records[-1]["error_type"] == "TimeoutError"
    assert "exceeded 0.01s" in records[-1]["error_message"]


def test_aggregator_builds_per_file_and_canonical_schema_counts() -> None:
    results = [
        SchemaChunkDiscoveryResult(
            chunk_id="a-0",
            file_path="aia.md",
            content_hash="a0",
            provider_slot_id="gemini-0",
            nodes=[
                SchemaNodeProposal(
                    label="QuyenLoiBaoHiem",
                    vietnamese_aliases=["Quyền lợi bảo hiểm"],
                    description="Các quyền lợi được chi trả.",
                    evidence_text="Quyền lợi bảo hiểm nội trú",
                    confidence=0.95,
                ),
                SchemaNodeProposal(
                    label="PhamViBaoHiem",
                    vietnamese_aliases=["Phạm vi bảo hiểm"],
                    description="Phạm vi quyền lợi được bảo hiểm.",
                    evidence_text="Phạm vi bảo hiểm bao gồm nội trú",
                    confidence=0.88,
                ),
            ],
            relationships=[
                SchemaRelationshipProposal(
                    source_label="Plan",
                    relationship_label="BAO_GOM",
                    target_label="QuyenLoiBaoHiem",
                    vietnamese_aliases=["bao gồm"],
                    description="Gói bao gồm quyền lợi.",
                    evidence_text="Sản phẩm bao gồm quyền lợi nội trú",
                    confidence=0.9,
                )
            ],
        ),
        SchemaChunkDiscoveryResult(
            chunk_id="b-0",
            file_path="bao_minh.md",
            content_hash="b0",
            provider_slot_id="nvidia-0",
            nodes=[
                SchemaNodeProposal(
                    label="LoaiTruBaoHiem",
                    vietnamese_aliases=["Loại trừ bảo hiểm"],
                    description="Điều khoản không chi trả.",
                    evidence_text="Không chi trả bệnh có sẵn",
                    confidence=0.92,
                )
            ],
            relationships=[
                SchemaRelationshipProposal(
                    source_label="Plan",
                    relationship_label="KHONG_CHI_TRA",
                    target_label="LoaiTruBaoHiem",
                    vietnamese_aliases=["không chi trả", "loại trừ"],
                    description="Gói bị loại trừ bởi điều khoản.",
                    evidence_text="Sản phẩm không chi trả bệnh có sẵn",
                    confidence=0.86,
                )
            ],
        ),
    ]

    summary = SchemaDiscoveryAggregator().aggregate(
        results,
        canonical_node_map={
            "QuyenLoiBaoHiem": "Benefit",
            "PhamViBaoHiem": "Benefit",
            "LoaiTruBaoHiem": "Exclusion",
        },
        canonical_relationship_map={
            "BAO_GOM": "INCLUDES",
            "KHONG_CHI_TRA": "EXCLUDES",
        },
    )

    assert summary.nodes["Benefit"].occurrence_count == 2
    assert summary.nodes["Benefit"].source_files == ["aia.md"]
    assert summary.nodes["Exclusion"].occurrence_count == 1
    assert summary.relationships["INCLUDES"].occurrence_count == 1
    assert summary.relationships["EXCLUDES"].source_files == ["bao_minh.md"]
    assert summary.per_file["aia.md"].node_labels == ["Benefit"]
    assert summary.per_file["bao_minh.md"].relationship_labels == ["EXCLUDES"]


@pytest.mark.asyncio
async def test_canonicalizer_uses_ai_map_then_reaggregates_counts() -> None:
    raw_summary = SchemaDiscoveryAggregator().aggregate(
        [
            SchemaChunkDiscoveryResult(
                chunk_id="a-0",
                file_path="aia.md",
                content_hash="a0",
                provider_slot_id="gemini-0",
                nodes=[
                    SchemaNodeProposal(
                        label="QuyenLoiBaoHiem",
                        vietnamese_aliases=["Quyền lợi bảo hiểm"],
                        description="Quyền lợi.",
                        evidence_text="Quyền lợi nội trú",
                        confidence=0.95,
                    ),
                    SchemaNodeProposal(
                        label="PhamViBaoHiem",
                        vietnamese_aliases=["Phạm vi bảo hiểm"],
                        description="Phạm vi chi trả.",
                        evidence_text="Phạm vi nội trú",
                        confidence=0.91,
                    ),
                ],
                relationships=[
                    SchemaRelationshipProposal(
                        source_label="Plan",
                        relationship_label="BAO_GOM",
                        target_label="QuyenLoiBaoHiem",
                        vietnamese_aliases=["bao gồm"],
                        description="Bao gồm quyền lợi.",
                        evidence_text="bao gồm nội trú",
                        confidence=0.9,
                    )
                ],
            )
        ]
    )
    canonicalizer = SchemaDiscoveryCanonicalizer()

    canonical_map = await canonicalizer.canonicalize(
        raw_summary=raw_summary,
        client=FakeSchemaCanonicalizationClient(),
        slot=SchemaDiscoveryProviderSlot(
            slot_id="gemini-0",
            provider="gemini",
            model="gemini-2.5-flash",
            api_key="gemini-key",
        ),
    )

    assert canonical_map.node_map == {
        "PhamViBaoHiem": "Benefit",
        "QuyenLoiBaoHiem": "Benefit",
    }
    assert canonical_map.relationship_map == {"BAO_GOM": "INCLUDES"}


@pytest.mark.asyncio
async def test_canonicalizer_can_fallback_to_identity_map_when_provider_fails() -> None:
    raw_summary = SchemaDiscoverySummary(
        nodes={
            "Benefit": AggregatedSchemaItem(
                label="Benefit",
                occurrence_count=2,
                source_files=["aia.md"],
                aliases=["Quyền lợi"],
                examples=["Quyền lợi nội trú"],
                average_confidence=0.9,
            )
        },
        relationships={
            "INCLUDES": AggregatedSchemaItem(
                label="INCLUDES",
                occurrence_count=1,
                source_files=["aia.md"],
                aliases=["bao gồm"],
                examples=["bao gồm quyền lợi"],
                average_confidence=0.88,
            )
        },
        per_file={},
    )

    canonical_map = await SchemaDiscoveryCanonicalizer().canonicalize(
        raw_summary=raw_summary,
        client=FailingSchemaCanonicalizationClient(),
        slot=SchemaDiscoveryProviderSlot(
            slot_id="gemini-0",
            provider="gemini",
            model="gemma-4-31b-it",
            api_key="gemini-key",
        ),
        fallback_to_identity=True,
    )

    assert canonical_map.node_map == {"Benefit": "Benefit"}
    assert canonical_map.relationship_map == {"INCLUDES": "INCLUDES"}


def test_markdown_chunker_uses_stable_hashes_and_markdown_boundaries(tmp_path) -> None:
    markdown_path = tmp_path / "policy.md"
    markdown_path.write_text(
        "# Tài liệu\n\n## Quyền lợi\nNội trú\n\n## Loại trừ\nBệnh có sẵn",
        encoding="utf-8",
    )

    chunks = MarkdownSchemaDiscoveryChunker(
        max_chunk_chars=25,
        overlap_chars=0,
    ).chunk_files([markdown_path])

    assert len(chunks) == 3
    assert chunks[0].chunk_id.endswith(":0")
    assert chunks[0].content_hash
    assert "Quyền lợi" in chunks[1].text
    assert "Loại trừ" in chunks[2].text


def test_markdown_report_lists_totals_and_per_file_schema(tmp_path) -> None:
    summary = SchemaDiscoverySummary(
        nodes={
            "Benefit": AggregatedSchemaItem(
                label="Benefit",
                occurrence_count=2,
                source_files=["aia.md"],
                aliases=["Quyền lợi bảo hiểm"],
                examples=["Quyền lợi nội trú"],
                average_confidence=0.93,
            )
        },
        relationships={
            "INCLUDES": AggregatedSchemaItem(
                label="INCLUDES",
                occurrence_count=1,
                source_files=["aia.md"],
                aliases=["bao gồm"],
                examples=["Gói bao gồm quyền lợi"],
                average_confidence=0.9,
            )
        },
        per_file={
            "aia.md": FileSchemaSummary(
                node_labels=["Benefit"],
                relationship_labels=["INCLUDES"],
            )
        },
    )
    report_path = tmp_path / "report.md"

    write_schema_discovery_markdown_report(summary, report_path)

    report_text = report_path.read_text(encoding="utf-8")
    assert "# Knowledge Graph Schema Discovery Report" in report_text
    assert "| Benefit | 2 | 1 |" in report_text
    assert "| aia.md | Benefit | INCLUDES |" in report_text
