"""Unit tests for document-derived knowledge graph extraction."""

from src.services.knowledge_graph.document_extractor import (
    DocumentGraphExtractor,
    GraphDocument,
)


def test_extracts_allowed_entities_from_markdown_with_stable_ids() -> None:
    """Extract allowed graph entities from normalized Markdown text."""
    document = GraphDocument(
        document_id="aia_health_2026",
        document_name="AIA Health 2026 Policy Wording",
        company_code="AIA",
        source_path="data/processed/aia_health_2026.md",
        text="""
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
        Glossary:
        - Deductible: Amount paid before coverage starts.
        """,
    )

    extraction = DocumentGraphExtractor().extract(document, chunks=[])

    assert extraction.nodes["company:AIA"]["entity_type"] == "Company"
    assert extraction.nodes["document:aia_health_2026"]["entity_type"] == "Document"
    assert extraction.nodes["plan:AIA:gold"]["name"] == "Gold"
    assert extraction.nodes["benefit:AIA:gold:inpatient_care"]["entity_type"] == (
        "Benefit"
    )
    assert (
        extraction.nodes["exclusion:AIA:gold:pre_existing_condition"]["entity_type"]
        == "Exclusion"
    )
    assert (
        extraction.nodes["condition:AIA:gold:doctor_referral_required"]["entity_type"]
        == "Condition"
    )
    assert extraction.nodes["waiting_period:AIA:gold:30_days"]["duration_days"] == 30
    assert extraction.nodes["hospital:vinmec_central_park"]["entity_type"] == (
        "Hospital"
    )
    assert extraction.nodes["glossary_term:deductible"]["definition"] == (
        "Amount paid before coverage starts."
    )


def test_extracts_document_grounded_relationships_with_citations() -> None:
    """Extract strict allowed relationships with document lineage."""
    document = GraphDocument(
        document_id="aia_health_2026",
        document_name="AIA Health 2026 Policy Wording",
        company_code="AIA",
        source_path="data/processed/aia_health_2026.md",
        text="""
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
    )
    chunks = [
        {
            "document_id": "aia_health_2026",
            "chunk_index": 12,
            "company_code": "AIA",
            "document_name": "AIA Health 2026 Policy Wording",
            "plan_code": "gold",
            "section_type": "exclusions",
            "page_number": 7,
            "source_path": "data/processed/aia_health_2026.md",
            "text": "Exclusions: Pre-existing condition.",
        }
    ]

    extraction = DocumentGraphExtractor().extract(document, chunks=chunks)
    edge_map = {(edge.source_id, edge.target_id): edge for edge in extraction.edges}

    assert edge_map[("document:aia_health_2026", "company:AIA")].relationship_type == (
        "DOCUMENT_DEFINES"
    )
    assert edge_map[("company:AIA", "plan:AIA:gold")].relationship_type == "OFFERS"
    assert (
        edge_map[("plan:AIA:gold", "benefit:AIA:gold:inpatient_care")].relationship_type
        == "INCLUDES"
    )
    assert (
        edge_map[
            ("plan:AIA:gold", "exclusion:AIA:gold:pre_existing_condition")
        ].relationship_type
        == "EXCLUDES"
    )
    assert (
        edge_map[
            (
                "exclusion:AIA:gold:pre_existing_condition",
                "condition:AIA:gold:doctor_referral_required",
            )
        ].relationship_type
        == "APPLIES_TO"
    )
    assert (
        edge_map[("plan:AIA:gold", "waiting_period:AIA:gold:30_days")].relationship_type
        == "HAS_WAITING_PERIOD"
    )
    assert (
        edge_map[("plan:AIA:gold", "hospital:vinmec_central_park")].relationship_type
        == "USES_NETWORK"
    )
    assert (
        edge_map[
            ("chunk:aia_health_2026:12", "exclusion:AIA:gold:pre_existing_condition")
        ].relationship_type
        == "MENTIONED_IN"
    )
    assert (
        edge_map[
            ("plan:AIA:gold", "exclusion:AIA:gold:pre_existing_condition")
        ].document_id
        == "aia_health_2026"
    )
    assert (
        edge_map[
            ("plan:AIA:gold", "exclusion:AIA:gold:pre_existing_condition")
        ].confidence
        >= 0.8
    )
    assert all(not hasattr(edge, "page_number") for edge in extraction.edges)
    assert "page_number" not in extraction.nodes["chunk:aia_health_2026:12"]


def test_extracts_plan_scoped_sections_without_cross_plan_contamination() -> None:
    """Attach each section to the plan block where it appears."""
    document = GraphDocument(
        document_id="aia_health_2026",
        document_name="AIA Health 2026 Policy Wording",
        company_code="AIA",
        source_path="data/processed/aia_health_2026.md",
        text="""
        ## Plan: Gold
        Benefits:
        - Gold inpatient
        Exclusions:
        - Gold dental exclusion

        ## Plan: Silver
        Benefits:
        - Silver outpatient
        Exclusions:
        - Silver maternity exclusion
        Waiting Periods:
        - 60 days for maternity
        """,
    )

    extraction = DocumentGraphExtractor().extract(document, chunks=[])
    edge_map = {(edge.source_id, edge.target_id): edge for edge in extraction.edges}

    assert ("plan:AIA:gold", "benefit:AIA:gold:gold_inpatient") in edge_map
    assert ("plan:AIA:silver", "benefit:AIA:silver:silver_outpatient") in edge_map
    assert ("plan:AIA:silver", "waiting_period:AIA:silver:60_days") in edge_map
    assert ("plan:AIA:silver", "benefit:AIA:gold:gold_inpatient") not in edge_map
    assert ("plan:AIA:gold", "benefit:AIA:silver:silver_outpatient") not in edge_map


def test_shared_exclusion_names_keep_plan_specific_conditions_isolated() -> None:
    """Do not let shared exclusion names leak conditions across plans."""
    document = GraphDocument(
        document_id="aia_health_2026",
        document_name="AIA Health 2026 Policy Wording",
        company_code="AIA",
        source_path="data/processed/aia_health_2026.md",
        text="""
        ## Plan: Gold
        Exclusions:
        - Pre-existing condition
        Conditions:
        - Gold approval required

        ## Plan: Silver
        Exclusions:
        - Pre-existing condition
        Conditions:
        - Silver review required
        """,
    )

    extraction = DocumentGraphExtractor().extract(document, chunks=[])
    edge_map = {(edge.source_id, edge.target_id): edge for edge in extraction.edges}

    assert (
        "exclusion:AIA:gold:pre_existing_condition",
        "condition:AIA:gold:gold_approval_required",
    ) in edge_map
    assert (
        "exclusion:AIA:silver:pre_existing_condition",
        "condition:AIA:silver:silver_review_required",
    ) in edge_map
    assert (
        "exclusion:AIA:gold:pre_existing_condition",
        "condition:AIA:silver:silver_review_required",
    ) not in edge_map
