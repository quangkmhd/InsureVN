"""Unit tests for knowledge graph quality validation."""

import logging

import networkx as nx

from src.services.knowledge_graph.graph_quality_validator import GraphQualityValidator


def test_quality_validator_detects_orphans_and_invalid_relationships() -> None:
    graph = nx.DiGraph()
    graph.add_node(
        "policy:aia:gold", entity_type="InsurancePolicy", document_id="doc-1"
    )
    graph.add_node("benefit:inpatient", entity_type="Benefit", document_id="doc-1")
    graph.add_node("orphan:node", entity_type="Benefit", document_id="doc-1")
    graph.add_edge(
        "policy:aia:gold",
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
    graph = nx.DiGraph()
    graph.add_node("policy:aia:gold", entity_type="InsurancePolicy")
    graph.add_node("exclusion:pre_existing", entity_type="Exclusion")
    graph.add_node(
        "source_chunk:missing_doc:99",
        entity_type="SourceChunk",
        document_id="missing",
    )
    graph.add_edge(
        "policy:aia:gold",
        "exclusion:pre_existing",
        relationship_type="HAS_EXCLUSION",
        confidence=0.4,
    )
    graph.add_edge(
        "source_chunk:missing_doc:99",
        "exclusion:pre_existing",
        relationship_type="CONTAINS",
        document_id="missing",
        source_path="missing.md",
        source_chunk_id="source_chunk:missing_doc:99",
        confidence=0.95,
    )

    report = GraphQualityValidator(min_confidence=0.75).validate(
        graph,
        document_counts={"aia_health_2026": 1},
        chunk_counts={"aia_health_2026": 10},
    )

    assert report.is_valid is False
    assert report.missing_document_lineage == [
        "policy:aia:gold->exclusion:pre_existing"
    ]
    assert report.low_confidence_edges == ["policy:aia:gold->exclusion:pre_existing"]
    assert report.dangling_chunk_references == ["source_chunk:missing_doc:99"]


def test_quality_validator_allows_chunk_lineage_without_chunk_nodes() -> None:
    graph = nx.DiGraph()
    graph.add_node(
        "policy:aia:gold", entity_type="InsurancePolicy", document_id="doc-1"
    )
    graph.add_node("exclusion:pre_existing", entity_type="Exclusion")
    graph.add_edge(
        "policy:aia:gold",
        "exclusion:pre_existing",
        relationship_type="HAS_EXCLUSION",
        document_id="doc-1",
        source_path="policy.md",
        source_chunk_id="source_chunk:doc-1:999",
        confidence=0.95,
    )

    report = GraphQualityValidator().validate(
        graph,
        document_counts={"doc-1": 1},
        chunk_counts={"doc-1": 1},
    )

    assert report.is_valid is True
    assert report.dangling_chunk_references == []


def test_quality_validator_logs_required_quality_metadata(caplog) -> None:
    graph = nx.DiGraph()
    graph.add_node(
        "insurance_document:doc-1",
        entity_type="InsuranceDocument",
        document_id="doc-1",
    )
    graph.add_node(
        "insurance_company:AIA",
        entity_type="InsuranceCompany",
        document_id="doc-1",
    )
    graph.add_edge(
        "insurance_document:doc-1",
        "insurance_company:AIA",
        relationship_type="DEFINES",
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
        if getattr(item, "component", "") == "graph_quality_validator"
    )
    assert record.node_count == 2
    assert record.edge_count == 1
    assert record.orphan_count == 0
    assert record.entity_type_counts["InsuranceDocument"] == 1
    assert record.relationship_type_counts["DEFINES"] == 1
