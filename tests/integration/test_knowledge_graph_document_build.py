"""Integration tests for building document-derived knowledge graphs."""

import json
import subprocess
import sys
from pathlib import Path

from src.services.knowledge_graph.builder import KnowledgeGraphBuilder
from src.services.knowledge_graph.document_extractor import GraphDocument
from src.services.knowledge_graph.quality import GraphQualityValidator
from src.services.knowledge_graph.retriever import GraphRetriever


def test_document_build_fixture_produces_quality_graph_under_latency_budget(
    tmp_path: Path,
) -> None:
    """Build a fixture graph from Markdown text and exported Qdrant payloads."""
    markdown_path = tmp_path / "aia_health_2026.md"
    markdown_path.write_text(
        """
        # AIA Health 2026

        ## Plan: Gold
        Benefits:
        - Inpatient care
        Exclusions:
        - Pre-existing condition
        Conditions:
        - Doctor referral required
        Waiting Periods:
        - 30 days for inpatient care
        Hospitals:
        - Vinmec Central Park
        """,
        encoding="utf-8",
    )
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "aia_health_2026",
                    "chunk_index": 1,
                    "company_code": "AIA",
                    "document_name": "AIA Health 2026 Policy Wording",
                    "plan_code": "gold",
                    "section_type": "exclusions",
                    "page_number": 7,
                    "source_path": str(markdown_path),
                    "text": "Pre-existing condition is excluded.",
                }
            ]
        ),
        encoding="utf-8",
    )
    documents = [
        GraphDocument(
            document_id="aia_health_2026",
            document_name="AIA Health 2026 Policy Wording",
            company_code="AIA",
            source_path=str(markdown_path),
            text=markdown_path.read_text(encoding="utf-8"),
        )
    ]
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))

    graph = KnowledgeGraphBuilder().build_from_documents(documents, chunks)
    report = GraphQualityValidator().validate(
        graph,
        document_counts={"aia_health_2026": 1},
        chunk_counts={"aia_health_2026": 1},
    )
    paths = GraphRetriever(graph).retrieve(
        ["plan:AIA:gold"], ["EXCLUDES", "APPLIES_TO"], max_hops=2
    )

    assert report.is_valid is True
    assert [
        "plan:AIA:gold",
        "exclusion:AIA:gold:pre_existing_condition",
        "condition:AIA:gold:doctor_referral_required",
    ] in [path.node_ids for path in paths]
    assert paths[0].latency_ms < 100


def test_build_script_runs_directly_and_matches_relative_chunk_source_path(
    tmp_path: Path,
) -> None:
    """Run the build script without manual PYTHONPATH and match chunk metadata."""
    document_dir = tmp_path / "processed"
    document_dir.mkdir()
    markdown_path = document_dir / "aia_health_2026.md"
    markdown_path.write_text(
        """
        ## Plan: Gold
        Exclusions:
        - Pre-existing condition
        """,
        encoding="utf-8",
    )
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "aia_health_2026",
                    "chunk_index": 1,
                    "company_code": "AIA",
                    "document_name": "AIA Health 2026 Policy Wording",
                    "plan_code": "gold",
                    "section_type": "exclusions",
                    "page_number": 3,
                    "source_path": markdown_path.name,
                    "text": "Pre-existing condition",
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "graph.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/04_extraction/05_build_knowledge_graph.py",
            "--input-document-path",
            str(document_dir),
            "--qdrant-payload-export-path",
            str(chunks_path),
            "--output-path",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(result.stdout)
    graph_payload = json.loads(output_path.read_text(encoding="utf-8"))
    company_node = next(
        node for node in graph_payload["nodes"] if node["id"] == "company:AIA"
    )
    assert report["is_valid"] is True
    assert company_node["company_code"] == "AIA"


def test_build_script_matches_duplicate_filenames_by_root_relative_source_path(
    tmp_path: Path,
) -> None:
    """Avoid assigning metadata by ambiguous basename when files are nested."""
    document_dir = tmp_path / "processed"
    gold_dir = document_dir / "gold"
    silver_dir = document_dir / "silver"
    gold_dir.mkdir(parents=True)
    silver_dir.mkdir(parents=True)
    gold_path = gold_dir / "policy.md"
    silver_path = silver_dir / "policy.md"
    gold_path.write_text(
        "## Plan: Gold\nBenefits:\n- Gold inpatient\n", encoding="utf-8"
    )
    silver_path.write_text(
        "## Plan: Silver\nBenefits:\n- Silver outpatient\n", encoding="utf-8"
    )
    chunks_path = tmp_path / "chunks.json"
    chunks_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "gold_doc",
                    "chunk_index": 1,
                    "company_code": "AIA",
                    "document_name": "Gold Policy",
                    "source_path": "gold/policy.md",
                    "text": "Gold inpatient",
                },
                {
                    "document_id": "silver_doc",
                    "chunk_index": 1,
                    "company_code": "BVH",
                    "document_name": "Silver Policy",
                    "source_path": "silver/policy.md",
                    "text": "Silver outpatient",
                },
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "graph.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/04_extraction/05_build_knowledge_graph.py",
            "--input-document-path",
            str(document_dir),
            "--qdrant-payload-export-path",
            str(chunks_path),
            "--output-path",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    graph_payload = json.loads(output_path.read_text(encoding="utf-8"))
    document_nodes = {
        node["id"]: node
        for node in graph_payload["nodes"]
        if node["id"].startswith("document:")
    }
    assert document_nodes["document:gold_doc"]["company_code"] == "AIA"
    assert document_nodes["document:silver_doc"]["company_code"] == "BVH"
