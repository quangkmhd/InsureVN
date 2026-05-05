"""Unit tests for knowledge graph traversal, serialization, and evidence."""

import logging
from pathlib import Path

from src.models.evidence import SourceType
from src.services.knowledge_graph.builder import KnowledgeGraphBuilder
from src.services.knowledge_graph.document_extractor import GraphDocument
from src.services.knowledge_graph.evidence_adapter import GraphEvidenceAdapter
from src.services.knowledge_graph.retriever import NetworkxGraphPathRetriever
from src.services.knowledge_graph.serializer import GraphJsonSerializer


def _build_fixture_graph():
    documents = [
        GraphDocument(
            document_id="aia_health_2026",
            document_name="AIA Health 2026 Policy Wording",
            company_code="AIA",
            source_path="data/processed/aia_health_2026.md",
            text="""
            ## Plan: Gold
            Exclusions:
            - Pre-existing condition
            Conditions:
            - Doctor referral required
            Waiting Periods:
            - 30 days for inpatient care
            """,
        )
    ]
    return KnowledgeGraphBuilder().build_from_documents(documents, chunks=[])


def test_retriever_returns_n_hop_relationship_paths() -> None:
    """Traverse plan exclusion and condition paths within max hops."""
    graph = _build_fixture_graph()

    paths = NetworkxGraphPathRetriever(graph).retrieve(
        start_entities=["plan:AIA:gold"],
        relation_types=["EXCLUDES", "APPLIES_TO"],
        max_hops=2,
    )

    assert [edge.relationship_type for edge in paths[0].edges] == [
        "EXCLUDES",
        "APPLIES_TO",
    ]
    assert paths[0].node_ids == [
        "plan:AIA:gold",
        "exclusion:AIA:gold:pre_existing_condition",
        "condition:AIA:gold:doctor_referral_required",
    ]


def test_retriever_returns_direct_and_multi_hop_paths_within_limit() -> None:
    """Return all matching paths up to max_hops, not only terminal paths."""
    graph = _build_fixture_graph()

    paths = NetworkxGraphPathRetriever(graph).retrieve(
        start_entities=["plan:AIA:gold"],
        relation_types=["EXCLUDES", "APPLIES_TO"],
        max_hops=2,
    )

    path_ids = [path.node_ids for path in paths]
    assert ["plan:AIA:gold", "exclusion:AIA:gold:pre_existing_condition"] in path_ids
    assert [
        "plan:AIA:gold",
        "exclusion:AIA:gold:pre_existing_condition",
        "condition:AIA:gold:doctor_referral_required",
    ] in path_ids


def test_json_reload_preserves_traversal_results(tmp_path: Path) -> None:
    """Serialize and reload graph JSON without changing traversal behavior."""
    graph = _build_fixture_graph()
    graph_path = tmp_path / "insurevn_graph.json"

    GraphJsonSerializer().save(graph, graph_path)
    loaded_graph = GraphJsonSerializer().load(graph_path)

    original_paths = NetworkxGraphPathRetriever(graph).retrieve(
        ["plan:AIA:gold"], ["EXCLUDES", "APPLIES_TO"], max_hops=2
    )
    loaded_paths = NetworkxGraphPathRetriever(loaded_graph).retrieve(
        ["plan:AIA:gold"], ["EXCLUDES", "APPLIES_TO"], max_hops=2
    )
    assert [path.node_ids for path in loaded_paths] == [
        path.node_ids for path in original_paths
    ]


def test_graph_evidence_adapter_returns_graph_triple_evidence() -> None:
    """Convert traversal paths into shared Evidence records."""
    graph = _build_fixture_graph()
    paths = NetworkxGraphPathRetriever(graph).retrieve(
        ["plan:AIA:gold"], ["EXCLUDES"], max_hops=1
    )

    evidence = GraphEvidenceAdapter().to_evidence(paths)

    assert evidence[0].source_type == SourceType.GRAPH_TRIPLE
    assert (
        evidence[0].source_id
        == "plan:AIA:gold->exclusion:AIA:gold:pre_existing_condition"
    )
    assert evidence[0].retrieved_by == "graph_retriever"
    assert evidence[0].metadata["graph_path"] == [
        "plan:AIA:gold",
        "exclusion:AIA:gold:pre_existing_condition",
    ]
    assert evidence[0].metadata["relationship_types"] == ["EXCLUDES"]


def test_retriever_logs_required_query_metadata(caplog) -> None:
    """Emit graph retriever query metadata for observability."""
    graph = _build_fixture_graph()

    with caplog.at_level(logging.INFO):
        NetworkxGraphPathRetriever(graph).retrieve(
            ["plan:AIA:gold"], ["EXCLUDES", "APPLIES_TO"], max_hops=2
        )

    record = next(
        item
        for item in caplog.records
        if getattr(item, "component", "") == "graph_retriever"
    )
    assert record.query_start_entity == "plan:AIA:gold"
    assert record.query_relation_types == ["EXCLUDES", "APPLIES_TO"]
    assert record.max_hops == 2
    assert record.latency_ms >= 0
