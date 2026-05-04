"""Unit tests for deterministic knowledge graph building."""

import sqlite3

import networkx as nx

from src.services.knowledge_graph.builder import KnowledgeGraphBuilder


def _create_graph_fixture() -> sqlite3.Connection:
    """Create a minimal SQLite fixture for graph builder tests."""
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        );

        CREATE TABLE plans (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            name TEXT NOT NULL
        );

        CREATE TABLE benefits (
            id INTEGER PRIMARY KEY,
            slug TEXT NOT NULL,
            name TEXT NOT NULL
        );

        CREATE TABLE plan_benefits (
            id INTEGER PRIMARY KEY,
            plan_id INTEGER NOT NULL,
            benefit_id INTEGER NOT NULL,
            coverage_limit TEXT
        );

        CREATE TABLE waiting_periods (
            id INTEGER PRIMARY KEY,
            plan_id INTEGER NOT NULL,
            benefit_id INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE hospitals (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT NOT NULL
        );

        CREATE TABLE plan_hospitals (
            id INTEGER PRIMARY KEY,
            plan_id INTEGER NOT NULL,
            hospital_id INTEGER NOT NULL
        );

        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            plan_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            source_uri TEXT NOT NULL
        );
        """
    )
    connection.executemany(
        "INSERT INTO companies (id, code, name) VALUES (?, ?, ?)",
        [(1, "AIA", "AIA Vietnam")],
    )
    connection.executemany(
        "INSERT INTO plans (id, company_id, slug, name) VALUES (?, ?, ?, ?)",
        [(10, 1, "gold", "Gold Health Plan")],
    )
    connection.executemany(
        "INSERT INTO benefits (id, slug, name) VALUES (?, ?, ?)",
        [(20, "inpatient", "Inpatient care")],
    )
    connection.executemany(
        """
        INSERT INTO plan_benefits (id, plan_id, benefit_id, coverage_limit)
        VALUES (?, ?, ?, ?)
        """,
        [(30, 10, 20, "100000000")],
    )
    connection.executemany(
        """
        INSERT INTO waiting_periods (
            id, plan_id, benefit_id, duration_days, description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [(40, 10, 20, 30, "30 days for inpatient care")],
    )
    connection.executemany(
        "INSERT INTO hospitals (id, name, city) VALUES (?, ?, ?)",
        [(50, "Vinmec Central Park", "Ho Chi Minh City")],
    )
    connection.executemany(
        "INSERT INTO plan_hospitals (id, plan_id, hospital_id) VALUES (?, ?, ?)",
        [(60, 10, 50)],
    )
    connection.executemany(
        """
        INSERT INTO documents (id, plan_id, title, source_uri)
        VALUES (?, ?, ?, ?)
        """,
        [(70, 10, "Gold Policy Wording", "s3://insurevn/aia-gold.pdf")],
    )
    connection.commit()
    return connection


def test_build_from_sqlite_creates_stable_searchable_node_ids() -> None:
    """Build graph nodes with deterministic, searchable IDs."""
    connection = _create_graph_fixture()

    graph = KnowledgeGraphBuilder().build_from_sqlite(connection)

    assert isinstance(graph, nx.DiGraph)
    assert set(graph.nodes) == {
        "company:AIA",
        "plan:AIA:gold",
        "benefit:inpatient",
        "waiting_period:10:20:30",
        "hospital:vinmec_central_park:ho_chi_minh_city",
        "document:aia-gold.pdf",
    }
    assert graph.nodes["company:AIA"] == {
        "entity_type": "Company",
        "source_table": "companies",
        "source_table_id": 1,
        "code": "AIA",
        "name": "AIA Vietnam",
    }
    assert graph.nodes["plan:AIA:gold"]["entity_type"] == "Plan"
    assert graph.nodes["benefit:inpatient"]["name"] == "Inpatient care"


def test_build_from_sqlite_extracts_required_relationships_with_lineage() -> None:
    """Build graph edges for Task 1 relationships with row lineage."""
    connection = _create_graph_fixture()

    graph = KnowledgeGraphBuilder().build_from_sqlite(connection)

    expected_edges = {
        ("company:AIA", "plan:AIA:gold"): {
            "relationship_type": "OFFERS",
            "source_table": "plans",
            "source_table_id": 10,
        },
        ("plan:AIA:gold", "benefit:inpatient"): {
            "relationship_type": "INCLUDES",
            "source_table": "plan_benefits",
            "source_table_id": 30,
        },
        ("plan:AIA:gold", "waiting_period:10:20:30"): {
            "relationship_type": "HAS_WAITING_PERIOD",
            "source_table": "waiting_periods",
            "source_table_id": 40,
        },
        ("plan:AIA:gold", "hospital:vinmec_central_park:ho_chi_minh_city"): {
            "relationship_type": "USES_NETWORK",
            "source_table": "plan_hospitals",
            "source_table_id": 60,
        },
        ("plan:AIA:gold", "document:aia-gold.pdf"): {
            "relationship_type": "GOVERNED_BY",
            "source_table": "documents",
            "source_table_id": 70,
        },
    }
    assert graph.number_of_edges() == len(expected_edges)
    for edge, attributes in expected_edges.items():
        assert graph.edges[edge] == attributes
