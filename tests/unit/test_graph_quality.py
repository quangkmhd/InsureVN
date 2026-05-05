"""Unit tests for knowledge graph quality validation."""

import logging

import networkx as nx

from src.services.knowledge_graph.quality import GraphQualityValidator


def test_quality_validator_detects_orphans_and_invalid_relationships() -> None:
    """Catch orphan nodes and relationships outside the allowed schema."""
    graph = nx.DiGraph()
    graph.add_node("plan:AIA:gold", entity_type="Plan", document_id="doc-1")
    graph.add_node("benefit:inpatient", entity_type="Benefit", document_id="doc-1")
    graph.add_node("orphan:node", entity_type="Benefit", document_id="doc-1")
    graph.add_edge(
        "plan:AIA:gold",
        "benefit:inpatient",
        relationship_type="MAKES_UP",
        document_id="doc-1",
        source_path="policy.md",
        confidence=0.9,
    )

    report = GraphQualityValidator().validate(
        graph,
        document_counts={"doc-1": 1},
        chunk_counts={},
    )

    assert report.is_valid is False
    assert report.orphan_nodes == ["orphan:node"]
    assert report.invalid_relationships == ["MAKES_UP"]


def test_quality_validator_detects_missing_lineage_and_low_confidence() -> None:
    """Catch missing document lineage, dangling chunks, and weak triples."""
    graph = nx.DiGraph()
    graph.add_node("plan:AIA:gold", entity_type="Plan")
    graph.add_node("exclusion:pre_existing_condition", entity_type="Exclusion")
    graph.add_node("chunk:missing_doc:99", entity_type="Chunk", document_id="missing")
    graph.add_edge(
        "plan:AIA:gold",
        "exclusion:pre_existing_condition",
        relationship_type="EXCLUDES",
        confidence=0.4,
    )
    graph.add_edge(
        "chunk:missing_doc:99",
        "exclusion:pre_existing_condition",
        relationship_type="MENTIONED_IN",
        document_id="missing",
        source_path="missing.md",
        chunk_id="chunk:missing_doc:99",
        confidence=0.95,
    )

    report = GraphQualityValidator(min_confidence=0.75).validate(
        graph,
        document_counts={"aia_health_2026": 1},
        chunk_counts={"aia_health_2026": 10},
    )

    assert report.is_valid is False
    assert report.missing_document_lineage == [
        "plan:AIA:gold->exclusion:pre_existing_condition"
    ]
    assert report.low_confidence_edges == [
        "plan:AIA:gold->exclusion:pre_existing_condition"
    ]
    assert report.dangling_chunk_references == ["chunk:missing_doc:99"]


def test_quality_validator_detects_chunk_id_missing_from_graph() -> None:
    """Catch edges that cite a chunk ID absent from graph chunk nodes."""
    graph = nx.DiGraph()
    graph.add_node("plan:AIA:gold", entity_type="Plan", document_id="doc-1")
    graph.add_node("exclusion:pre_existing_condition", entity_type="Exclusion")
    graph.add_edge(
        "plan:AIA:gold",
        "exclusion:pre_existing_condition",
        relationship_type="EXCLUDES",
        document_id="doc-1",
        source_path="policy.md",
        chunk_id="chunk:doc-1:999",
        confidence=0.95,
    )

    report = GraphQualityValidator().validate(
        graph,
        document_counts={"doc-1": 1},
        chunk_counts={"doc-1": 1},
    )

    assert report.is_valid is False
    assert report.dangling_chunk_references == ["chunk:doc-1:999"]


def test_quality_validator_logs_required_quality_metadata(caplog) -> None:
    """Emit graph quality metadata for observability."""
    graph = nx.DiGraph()
    graph.add_node("document:doc-1", entity_type="Document", document_id="doc-1")
    graph.add_node("company:AIA", entity_type="Company", document_id="doc-1")
    graph.add_edge(
        "document:doc-1",
        "company:AIA",
        relationship_type="DOCUMENT_DEFINES",
        document_id="doc-1",
        source_path="policy.md",
        confidence=1.0,
    )

    with caplog.at_level(logging.INFO):
        GraphQualityValidator().validate(
            graph,
            document_counts={"doc-1": 1},
            chunk_counts={},
        )

    record = next(
        item
        for item in caplog.records
        if getattr(item, "component", "") == "graph_quality"
    )
    assert record.node_count == 2
    assert record.edge_count == 1
    assert record.orphan_count == 0
    assert record.entity_type_counts["Document"] == 1
    assert record.relationship_type_counts["DOCUMENT_DEFINES"] == 1
