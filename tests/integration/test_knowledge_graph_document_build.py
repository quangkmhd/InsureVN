"""Integration tests for building document-derived knowledge graphs."""

import importlib.util
import json
import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_neo4j.graphs.graph_document import (
    GraphDocument as LangChainGraphDocument,
)
from langchain_neo4j.graphs.graph_document import Node, Relationship

from src.services.knowledge_graph.graph_quality_validator import GraphQualityValidator
from src.services.knowledge_graph.llm_graph_document_extractor import GraphDocument
from src.services.knowledge_graph.networkx_graph_builder import NetworkxGraphBuilder


def _load_build_script():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "07_knowledge_graph"
        / "04_build_knowledge_graph.py"
    )
    spec = importlib.util.spec_from_file_location("build_knowledge_graph", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeGraphExtractor:
    def extract(self, _document, _chunks):
        policy = Node(
            id="insurance_policy:aia:gold",
            type="InsurancePolicy",
            properties={"name": "AIA Health 2026 Gold"},
        )
        exclusion = Node(
            id="exclusion:aia:pre_existing_condition",
            type="Exclusion",
            properties={"name": "Pre-existing condition"},
        )
        return [
            LangChainGraphDocument(
                nodes=[policy, exclusion],
                relationships=[
                    Relationship(
                        source=policy,
                        target=exclusion,
                        type="HAS_EXCLUSION",
                        properties={
                            "source_document_id": "aia_health_2026",
                            "source_path": "aia_health_2026.md",
                            "source_chunk_id": "chunk-1",
                            "confidence": 0.9,
                        },
                    )
                ],
                source=Document(page_content="Pre-existing condition is excluded."),
            )
        ]


def test_document_build_fixture_produces_quality_graph_from_extractor(
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

    graph = NetworkxGraphBuilder(extractor=FakeGraphExtractor()).build_from_documents(
        documents,
        chunks,
    )
    report = GraphQualityValidator().validate(
        graph,
        document_counts={"aia_health_2026": 1},
        chunk_counts={"aia_health_2026": 1},
    )

    assert report.is_valid is True
    assert graph.has_edge(
        "insurance_policy:aia:gold",
        "exclusion:aia:pre_existing_condition",
    )


def test_build_script_loads_documents_with_relative_chunk_source_path(
    tmp_path: Path,
) -> None:
    """Match chunk metadata before LLM graph extraction runs."""
    script = _load_build_script()
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

    chunks = script._load_chunks(chunks_path)
    documents = script._load_documents(document_dir, chunks)

    assert documents == [
        GraphDocument(
            document_id="aia_health_2026",
            document_name="AIA Health 2026 Policy Wording",
            company_code="AIA",
            source_path=str(markdown_path),
            text=markdown_path.read_text(encoding="utf-8"),
        )
    ]


def test_build_script_matches_duplicate_filenames_by_root_relative_source_path(
    tmp_path: Path,
) -> None:
    """Avoid assigning metadata by ambiguous basename when files are nested."""
    script = _load_build_script()
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

    chunks = script._load_chunks(chunks_path)
    documents = script._load_documents(document_dir, chunks)
    document_by_id = {document.document_id: document for document in documents}

    assert document_by_id["gold_doc"].company_code == "AIA"
    assert document_by_id["gold_doc"].document_name == "Gold Policy"
    assert document_by_id["gold_doc"].source_path == str(gold_path)
    assert document_by_id["silver_doc"].company_code == "BVH"
    assert document_by_id["silver_doc"].document_name == "Silver Policy"
    assert document_by_id["silver_doc"].source_path == str(silver_path)
