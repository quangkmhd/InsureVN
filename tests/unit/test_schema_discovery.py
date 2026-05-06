import asyncio
import csv
import json

import pytest

import sys
from pathlib import Path

# Add scripts directory to path to allow importing from the 07_knowledge_graph folder
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "scripts" / "07_knowledge_graph"))

from schema_discovery.discovery import (
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
    apply_canonical_map_to_summary,
    build_final_schema_v1,
    build_final_schema_v1_contract,
    filter_schema_summary,
    write_final_schema_v1_property_csvs,
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


class SlowSchemaCanonicalizationClient:
    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        _ = (node_items, relationship_items, slot)
        await asyncio.sleep(10)
        raise RuntimeError("unreachable")


class BatchSchemaCanonicalizationClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], list[str]]] = []

    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        _ = slot
        node_labels = [item.label for item in node_items]
        relationship_labels = [item.label for item in relationship_items]
        self.calls.append((node_labels, relationship_labels))
        return SchemaCanonicalizationMap(
            node_map={
                label: (
                    "InsuranceBenefit"
                    if "Benefit" in label or "QuyenLoi" in label
                    else "MedicalFacility"
                )
                for label in node_labels
            },
            relationship_map={
                label: (
                    "HAS_BENEFIT"
                    if "BENEFIT" in label or "QUYEN_LOI" in label
                    else "LOCATED_IN"
                )
                for label in relationship_labels
            },
        )


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


@pytest.mark.asyncio
async def test_canonicalizer_batches_labels_and_returns_complete_map() -> None:
    raw_summary = SchemaDiscoverySummary(
        nodes={
            "InsuranceBenefit": AggregatedSchemaItem(
                label="InsuranceBenefit",
                occurrence_count=8,
                source_files=["a.md", "b.md"],
                aliases=["Quyền lợi bảo hiểm"],
                examples=["quyền lợi nội trú"],
                average_confidence=0.9,
            ),
            "QuyenLoiBaoHiem": AggregatedSchemaItem(
                label="QuyenLoiBaoHiem",
                occurrence_count=3,
                source_files=["c.md"],
                aliases=["Quyền lợi"],
                examples=["quyền lợi ngoại trú"],
                average_confidence=0.88,
            ),
            "BenhVien": AggregatedSchemaItem(
                label="BenhVien",
                occurrence_count=2,
                source_files=["a.md"],
                aliases=["Bệnh viện"],
                examples=["bệnh viện công"],
                average_confidence=0.86,
            ),
        },
        relationships={
            "HAS_BENEFIT": AggregatedSchemaItem(
                label="HAS_BENEFIT",
                occurrence_count=4,
                source_files=["a.md"],
                aliases=["có quyền lợi"],
                examples=["gói có quyền lợi"],
                average_confidence=0.87,
            ),
            "CO_QUYEN_LOI": AggregatedSchemaItem(
                label="CO_QUYEN_LOI",
                occurrence_count=2,
                source_files=["b.md"],
                aliases=["có quyền lợi"],
                examples=["chương trình có quyền lợi"],
                average_confidence=0.85,
            ),
        },
        per_file={},
    )
    client = BatchSchemaCanonicalizationClient()

    canonical_map = await SchemaDiscoveryCanonicalizer().canonicalize_in_batches(
        raw_summary=raw_summary,
        client=client,
        slot=SchemaDiscoveryProviderSlot(
            slot_id="openrouter-0",
            provider="openrouter",
            model="test-model",
            api_key="router-key",
        ),
        batch_size=2,
    )

    assert len(client.calls) > 1
    assert set(canonical_map.node_map) == set(raw_summary.nodes)
    assert set(canonical_map.relationship_map) == set(raw_summary.relationships)
    assert canonical_map.node_map["QuyenLoiBaoHiem"] == "InsuranceBenefit"
    assert canonical_map.relationship_map["CO_QUYEN_LOI"] == "HAS_BENEFIT"


@pytest.mark.asyncio
async def test_canonicalizer_times_out_slow_batches_with_normalized_identity() -> None:
    raw_summary = SchemaDiscoverySummary(
        nodes={
            "Bệnh viện": AggregatedSchemaItem(
                label="Bệnh viện",
                occurrence_count=2,
                source_files=["a.md"],
                aliases=["Bệnh viện"],
                examples=[],
                average_confidence=0.9,
            )
        },
        relationships={
            "tọa lạc tại": AggregatedSchemaItem(
                label="tọa lạc tại",
                occurrence_count=2,
                source_files=["a.md"],
                aliases=["tọa lạc tại"],
                examples=[],
                average_confidence=0.9,
            )
        },
        per_file={},
    )

    canonical_map = await SchemaDiscoveryCanonicalizer().canonicalize_in_batches(
        raw_summary=raw_summary,
        client=SlowSchemaCanonicalizationClient(),
        slot=SchemaDiscoveryProviderSlot(
            slot_id="openrouter-0",
            provider="openrouter",
            model="test-model",
            api_key="router-key",
        ),
        batch_size=1,
        batch_timeout_seconds=0.01,
    )

    assert canonical_map.node_map == {"Bệnh viện": "BenhVien"}
    assert canonical_map.relationship_map == {"tọa lạc tại": "TOA_LAC_TAI"}


def test_apply_canonical_map_to_summary_merges_counts_and_files() -> None:
    raw_summary = SchemaDiscoverySummary(
        nodes={
            "InsuranceBenefit": AggregatedSchemaItem(
                label="InsuranceBenefit",
                occurrence_count=8,
                source_files=["a.md", "b.md"],
                aliases=["Quyền lợi bảo hiểm"],
                examples=["quyền lợi nội trú"],
                average_confidence=0.9,
            ),
            "Benefit": AggregatedSchemaItem(
                label="Benefit",
                occurrence_count=2,
                source_files=["b.md", "c.md"],
                aliases=["Quyền lợi"],
                examples=["quyền lợi ngoại trú"],
                average_confidence=0.8,
            ),
        },
        relationships={
            "HAS_BENEFIT": AggregatedSchemaItem(
                label="HAS_BENEFIT",
                occurrence_count=3,
                source_files=["a.md"],
                aliases=["có quyền lợi"],
                examples=["gói có quyền lợi"],
                average_confidence=0.9,
            ),
            "CO_QUYEN_LOI": AggregatedSchemaItem(
                label="CO_QUYEN_LOI",
                occurrence_count=1,
                source_files=["c.md"],
                aliases=["có quyền lợi"],
                examples=["sản phẩm có quyền lợi"],
                average_confidence=0.7,
            ),
        },
        per_file={
            "a.md": FileSchemaSummary(
                node_labels=["InsuranceBenefit"],
                relationship_labels=["HAS_BENEFIT"],
            ),
            "c.md": FileSchemaSummary(
                node_labels=["Benefit"],
                relationship_labels=["CO_QUYEN_LOI"],
            ),
        },
    )

    clean_summary = apply_canonical_map_to_summary(
        raw_summary,
        SchemaCanonicalizationMap(
            node_map={"Benefit": "InsuranceBenefit"},
            relationship_map={"CO_QUYEN_LOI": "HAS_BENEFIT"},
        ),
    )

    assert clean_summary.nodes["InsuranceBenefit"].occurrence_count == 10
    assert clean_summary.nodes["InsuranceBenefit"].source_files == [
        "a.md",
        "b.md",
        "c.md",
    ]
    assert clean_summary.nodes["InsuranceBenefit"].average_confidence == 0.88
    assert clean_summary.relationships["HAS_BENEFIT"].occurrence_count == 4
    assert clean_summary.per_file["c.md"].node_labels == ["InsuranceBenefit"]
    assert clean_summary.per_file["c.md"].relationship_labels == ["HAS_BENEFIT"]


def test_filter_schema_summary_keeps_frequent_and_protected_labels() -> None:
    raw_summary = SchemaDiscoverySummary(
        nodes={
            "InsurancePolicy": AggregatedSchemaItem(
                label="InsurancePolicy",
                occurrence_count=1,
                source_files=["a.md"],
                aliases=["Hợp đồng bảo hiểm"],
                examples=[],
                average_confidence=0.9,
            ),
            "InsuranceBenefit": AggregatedSchemaItem(
                label="InsuranceBenefit",
                occurrence_count=6,
                source_files=["a.md", "b.md"],
                aliases=["Quyền lợi"],
                examples=[],
                average_confidence=0.9,
            ),
            "MarketingSentence": AggregatedSchemaItem(
                label="MarketingSentence",
                occurrence_count=1,
                source_files=["a.md"],
                aliases=["khẩu hiệu"],
                examples=[],
                average_confidence=0.5,
            ),
        },
        relationships={
            "HAS_BENEFIT": AggregatedSchemaItem(
                label="HAS_BENEFIT",
                occurrence_count=5,
                source_files=["a.md", "b.md"],
                aliases=["có quyền lợi"],
                examples=[],
                average_confidence=0.9,
            ),
            "ISSUES": AggregatedSchemaItem(
                label="ISSUES",
                occurrence_count=1,
                source_files=["a.md"],
                aliases=["phát hành"],
                examples=[],
                average_confidence=0.9,
            ),
            "MENTIONS": AggregatedSchemaItem(
                label="MENTIONS",
                occurrence_count=1,
                source_files=["a.md"],
                aliases=["nhắc tới"],
                examples=[],
                average_confidence=0.4,
            ),
        },
        per_file={
            "a.md": FileSchemaSummary(
                node_labels=[
                    "InsurancePolicy",
                    "InsuranceBenefit",
                    "MarketingSentence",
                ],
                relationship_labels=["HAS_BENEFIT", "ISSUES", "MENTIONS"],
            )
        },
    )

    clean_summary = filter_schema_summary(
        raw_summary,
        min_node_occurrences=5,
        min_relationship_occurrences=5,
        min_source_files=2,
    )

    assert list(clean_summary.nodes) == ["InsuranceBenefit", "InsurancePolicy"]
    assert list(clean_summary.relationships) == ["HAS_BENEFIT", "ISSUES"]
    assert clean_summary.per_file["a.md"].node_labels == [
        "InsuranceBenefit",
        "InsurancePolicy",
    ]
    assert clean_summary.per_file["a.md"].relationship_labels == [
        "HAS_BENEFIT",
        "ISSUES",
    ]


def test_build_final_schema_v1_merges_domain_equivalent_labels() -> None:
    clean_summary = SchemaDiscoverySummary(
        nodes={
            "Insurer": AggregatedSchemaItem(
                label="Insurer",
                occurrence_count=5,
                source_files=["a.md"],
                aliases=["BIC"],
                examples=[],
                average_confidence=0.9,
            ),
            "InsuranceCompany": AggregatedSchemaItem(
                label="InsuranceCompany",
                occurrence_count=8,
                source_files=["b.md"],
                aliases=["Công ty bảo hiểm"],
                examples=[],
                average_confidence=0.8,
            ),
            "Plan": AggregatedSchemaItem(
                label="Plan",
                occurrence_count=4,
                source_files=["a.md"],
                aliases=["Gói"],
                examples=[],
                average_confidence=0.9,
            ),
            "InsurancePlan": AggregatedSchemaItem(
                label="InsurancePlan",
                occurrence_count=6,
                source_files=["b.md"],
                aliases=["Chương trình bảo hiểm"],
                examples=[],
                average_confidence=0.9,
            ),
            "Disease": AggregatedSchemaItem(
                label="Disease",
                occurrence_count=3,
                source_files=["a.md"],
                aliases=["Bệnh"],
                examples=[],
                average_confidence=0.8,
            ),
            "MarketingSentence": AggregatedSchemaItem(
                label="MarketingSentence",
                occurrence_count=100,
                source_files=["a.md"],
                aliases=["khẩu hiệu"],
                examples=[],
                average_confidence=0.5,
            ),
        },
        relationships={
            "APPLICABLE_TO": AggregatedSchemaItem(
                label="APPLICABLE_TO",
                occurrence_count=5,
                source_files=["a.md"],
                aliases=["áp dụng cho"],
                examples=[],
                average_confidence=0.9,
            ),
            "APPLIES_TO": AggregatedSchemaItem(
                label="APPLIES_TO",
                occurrence_count=7,
                source_files=["b.md"],
                aliases=["áp dụng"],
                examples=[],
                average_confidence=0.9,
            ),
            "LOCATED_IN_COUNTRY": AggregatedSchemaItem(
                label="LOCATED_IN_COUNTRY",
                occurrence_count=3,
                source_files=["a.md"],
                aliases=["ở quốc gia"],
                examples=[],
                average_confidence=0.9,
            ),
            "LOCATED_AT": AggregatedSchemaItem(
                label="LOCATED_AT",
                occurrence_count=4,
                source_files=["b.md"],
                aliases=["tọa lạc tại"],
                examples=[],
                average_confidence=0.9,
            ),
            "MENTIONS_MARKETING": AggregatedSchemaItem(
                label="MENTIONS_MARKETING",
                occurrence_count=100,
                source_files=["a.md"],
                aliases=["nhắc khẩu hiệu"],
                examples=[],
                average_confidence=0.5,
            ),
        },
        per_file={
            "a.md": FileSchemaSummary(
                node_labels=["Insurer", "Plan", "Disease", "MarketingSentence"],
                relationship_labels=[
                    "APPLICABLE_TO",
                    "LOCATED_IN_COUNTRY",
                    "MENTIONS_MARKETING",
                ],
            )
        },
    )

    final_summary = build_final_schema_v1(
        clean_summary,
        max_node_labels=60,
        max_relationship_labels=90,
    )

    assert final_summary.nodes["InsuranceCompany"].occurrence_count == 13
    assert final_summary.nodes["InsurancePlan"].occurrence_count == 10
    assert final_summary.nodes["MedicalCondition"].occurrence_count == 3
    assert "MarketingSentence" not in final_summary.nodes
    assert final_summary.relationships["APPLIES_TO"].occurrence_count == 12
    assert final_summary.relationships["LOCATED_AT"].occurrence_count == 7
    assert "MENTIONS_MARKETING" not in final_summary.relationships
    assert final_summary.per_file["a.md"].node_labels == [
        "InsuranceCompany",
        "InsurancePlan",
        "MedicalCondition",
    ]
    assert final_summary.per_file["a.md"].relationship_labels == [
        "APPLIES_TO",
        "LOCATED_AT",
    ]


def test_build_final_schema_v1_contract_exports_allowed_labels() -> None:
    final_summary = SchemaDiscoverySummary(
        nodes={
            "Benefit": AggregatedSchemaItem(
                label="Benefit",
                occurrence_count=10,
                source_files=["a.md"],
                aliases=["Quyền lợi"],
                examples=[],
                average_confidence=0.9,
            )
        },
        relationships={
            "HAS_BENEFIT": AggregatedSchemaItem(
                label="HAS_BENEFIT",
                occurrence_count=8,
                source_files=["a.md"],
                aliases=["có quyền lợi"],
                examples=[],
                average_confidence=0.9,
            )
        },
        per_file={},
    )

    contract = build_final_schema_v1_contract(final_summary)

    assert contract["schema_name"] == "health_insurance_kg_schema_v1"
    assert contract["node_count"] == 1
    assert contract["relationship_count"] == 1
    assert contract["allowed_node_labels"] == ["Benefit"]
    assert contract["allowed_relationship_types"] == ["HAS_BENEFIT"]


def test_build_final_schema_v1_contract_exports_property_definitions() -> None:
    final_summary = SchemaDiscoverySummary(
        nodes={
            "Benefit": AggregatedSchemaItem(
                label="Benefit",
                occurrence_count=10,
                source_files=["a.md"],
                aliases=["Quyền lợi"],
                examples=[],
                average_confidence=0.9,
            ),
            "Premium": AggregatedSchemaItem(
                label="Premium",
                occurrence_count=5,
                source_files=["a.md"],
                aliases=["Phí bảo hiểm"],
                examples=[],
                average_confidence=0.9,
            ),
        },
        relationships={
            "HAS_BENEFIT": AggregatedSchemaItem(
                label="HAS_BENEFIT",
                occurrence_count=8,
                source_files=["a.md"],
                aliases=["có quyền lợi"],
                examples=[],
                average_confidence=0.9,
            ),
            "HAS_PREMIUM": AggregatedSchemaItem(
                label="HAS_PREMIUM",
                occurrence_count=4,
                source_files=["a.md"],
                aliases=["có phí"],
                examples=[],
                average_confidence=0.9,
            ),
        },
        per_file={},
    )

    contract = build_final_schema_v1_contract(final_summary)

    assert set(contract["node_properties"]) == {"Benefit", "Premium"}
    assert set(contract["relationship_properties"]) == {
        "HAS_BENEFIT",
        "HAS_PREMIUM",
    }
    benefit_properties = {
        property_definition["name"]
        for property_definition in contract["node_properties"]["Benefit"]
    }
    premium_properties = {
        property_definition["name"]
        for property_definition in contract["node_properties"]["Premium"]
    }
    has_benefit_properties = {
        property_definition["name"]
        for property_definition in contract["relationship_properties"]["HAS_BENEFIT"]
    }
    has_premium_properties = {
        property_definition["name"]
        for property_definition in contract["relationship_properties"]["HAS_PREMIUM"]
    }

    assert {"id", "name", "source_document_id", "confidence"} <= benefit_properties
    assert {"benefit_code", "benefit_type"} <= benefit_properties
    assert {"amount", "currency", "payment_frequency"} <= premium_properties
    assert {"evidence_text", "confidence", "condition_text"} <= has_benefit_properties
    assert {"amount", "currency", "payment_frequency"} <= has_premium_properties


def test_write_final_schema_v1_property_csvs_writes_callable_files(tmp_path) -> None:
    final_summary = SchemaDiscoverySummary(
        nodes={
            "Benefit": AggregatedSchemaItem(
                label="Benefit",
                occurrence_count=10,
                source_files=["a.md"],
                aliases=["Quyền lợi"],
                examples=[],
                average_confidence=0.9,
            )
        },
        relationships={
            "HAS_BENEFIT": AggregatedSchemaItem(
                label="HAS_BENEFIT",
                occurrence_count=8,
                source_files=["a.md"],
                aliases=["có quyền lợi"],
                examples=[],
                average_confidence=0.9,
            )
        },
        per_file={},
    )
    contract = build_final_schema_v1_contract(final_summary)

    csv_paths = write_final_schema_v1_property_csvs(contract, tmp_path)

    node_rows = list(
        csv.DictReader(
            csv_paths["node_properties"].read_text(encoding="utf-8").splitlines()
        )
    )
    relationship_rows = list(
        csv.DictReader(
            csv_paths["relationship_properties"]
            .read_text(encoding="utf-8")
            .splitlines()
        )
    )
    assert node_rows[0] == {
        "node_label": "Benefit",
        "property_name": "id",
        "data_type": "string",
        "required": "true",
        "description": "Stable unique node id.",
    }
    assert {
        "relationship_type": "HAS_BENEFIT",
        "property_name": "evidence_text",
        "data_type": "string",
        "required": "true",
        "description": "Source text span supporting the relationship.",
    } in relationship_rows


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
