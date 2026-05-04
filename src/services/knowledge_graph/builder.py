"""Build deterministic NetworkX knowledge graphs from SQLite."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import PurePosixPath
from typing import Any

import networkx as nx


class KnowledgeGraphBuilder:
    """Build a directed insurance knowledge graph from SQLite data."""

    def build_from_sqlite(self, connection: sqlite3.Connection) -> nx.DiGraph:
        """Build a deterministic directed graph from a SQLite connection.

        Args:
            connection: Open SQLite connection containing insurance source tables.

        Returns:
            A NetworkX directed graph with stable node IDs and lineage attributes.
        """
        graph = nx.DiGraph()
        companies = self._add_companies(connection, graph)
        plans = self._add_plans(connection, graph, companies)
        benefits = self._add_benefits(connection, graph)
        hospitals = self._add_hospitals(connection, graph)

        self._add_plan_benefit_edges(connection, graph, plans, benefits)
        self._add_waiting_periods(connection, graph, plans, benefits)
        self._add_plan_hospital_edges(connection, graph, plans, hospitals)
        self._add_documents(connection, graph, plans)
        return graph

    def _add_companies(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
    ) -> dict[int, str]:
        if not _table_exists(connection, "companies"):
            return {}

        company_nodes: dict[int, str] = {}
        rows = _fetch_all(
            connection,
            """
            SELECT id, code, name
            FROM companies
            ORDER BY code, id
            """,
        )
        for row in rows:
            node_id = f"company:{row['code']}"
            graph.add_node(
                node_id,
                entity_type="Company",
                source_table="companies",
                source_table_id=row["id"],
                code=row["code"],
                name=row["name"],
            )
            company_nodes[row["id"]] = node_id
        return company_nodes

    def _add_plans(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
        companies: dict[int, str],
    ) -> dict[int, str]:
        if not _table_exists(connection, "plans"):
            return {}

        plan_nodes: dict[int, str] = {}
        rows = _fetch_all(
            connection,
            """
            SELECT plans.id, plans.company_id, plans.slug, plans.name, companies.code
            FROM plans
            JOIN companies ON companies.id = plans.company_id
            ORDER BY companies.code, plans.slug, plans.id
            """,
        )
        for row in rows:
            node_id = f"plan:{row['code']}:{row['slug']}"
            graph.add_node(
                node_id,
                entity_type="Plan",
                source_table="plans",
                source_table_id=row["id"],
                company_code=row["code"],
                slug=row["slug"],
                name=row["name"],
            )
            plan_nodes[row["id"]] = node_id

            company_node_id = companies.get(row["company_id"])
            if company_node_id is not None:
                graph.add_edge(
                    company_node_id,
                    node_id,
                    relationship_type="OFFERS",
                    source_table="plans",
                    source_table_id=row["id"],
                )
        return plan_nodes

    def _add_benefits(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
    ) -> dict[int, str]:
        if not _table_exists(connection, "benefits"):
            return {}

        benefit_nodes: dict[int, str] = {}
        rows = _fetch_all(
            connection,
            """
            SELECT id, slug, name
            FROM benefits
            ORDER BY slug, id
            """,
        )
        for row in rows:
            node_id = f"benefit:{row['slug']}"
            graph.add_node(
                node_id,
                entity_type="Benefit",
                source_table="benefits",
                source_table_id=row["id"],
                slug=row["slug"],
                name=row["name"],
            )
            benefit_nodes[row["id"]] = node_id
        return benefit_nodes

    def _add_hospitals(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
    ) -> dict[int, str]:
        if not _table_exists(connection, "hospitals"):
            return {}

        hospital_nodes: dict[int, str] = {}
        rows = _fetch_all(
            connection,
            """
            SELECT id, name, city
            FROM hospitals
            ORDER BY city, name, id
            """,
        )
        for row in rows:
            hospital_slug = _stable_slug(row["name"])
            city_slug = _stable_slug(row["city"])
            node_id = f"hospital:{hospital_slug}:{city_slug}"
            graph.add_node(
                node_id,
                entity_type="Hospital",
                source_table="hospitals",
                source_table_id=row["id"],
                name=row["name"],
                city=row["city"],
            )
            hospital_nodes[row["id"]] = node_id
        return hospital_nodes

    def _add_plan_benefit_edges(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
        plans: dict[int, str],
        benefits: dict[int, str],
    ) -> None:
        if not _table_exists(connection, "plan_benefits"):
            return

        rows = _fetch_all(
            connection,
            """
            SELECT id, plan_id, benefit_id
            FROM plan_benefits
            ORDER BY plan_id, benefit_id, id
            """,
        )
        for row in rows:
            plan_node_id = plans.get(row["plan_id"])
            benefit_node_id = benefits.get(row["benefit_id"])
            if plan_node_id is None or benefit_node_id is None:
                continue
            graph.add_edge(
                plan_node_id,
                benefit_node_id,
                relationship_type="INCLUDES",
                source_table="plan_benefits",
                source_table_id=row["id"],
            )

    def _add_waiting_periods(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
        plans: dict[int, str],
        benefits: dict[int, str],
    ) -> None:
        if not _table_exists(connection, "waiting_periods"):
            return

        rows = _fetch_all(
            connection,
            """
            SELECT id, plan_id, benefit_id, duration_days, description
            FROM waiting_periods
            ORDER BY plan_id, benefit_id, duration_days, id
            """,
        )
        for row in rows:
            plan_node_id = plans.get(row["plan_id"])
            benefit_node_id = benefits.get(row["benefit_id"])
            if plan_node_id is None:
                continue

            node_id = (
                "waiting_period:"
                f"{row['plan_id']}:{row['benefit_id']}:{row['duration_days']}"
            )
            graph.add_node(
                node_id,
                entity_type="WaitingPeriod",
                source_table="waiting_periods",
                source_table_id=row["id"],
                duration_days=row["duration_days"],
                description=row["description"],
                benefit_node_id=benefit_node_id,
            )
            graph.add_edge(
                plan_node_id,
                node_id,
                relationship_type="HAS_WAITING_PERIOD",
                source_table="waiting_periods",
                source_table_id=row["id"],
            )

    def _add_plan_hospital_edges(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
        plans: dict[int, str],
        hospitals: dict[int, str],
    ) -> None:
        if not _table_exists(connection, "plan_hospitals"):
            return

        rows = _fetch_all(
            connection,
            """
            SELECT id, plan_id, hospital_id
            FROM plan_hospitals
            ORDER BY plan_id, hospital_id, id
            """,
        )
        for row in rows:
            plan_node_id = plans.get(row["plan_id"])
            hospital_node_id = hospitals.get(row["hospital_id"])
            if plan_node_id is None or hospital_node_id is None:
                continue
            graph.add_edge(
                plan_node_id,
                hospital_node_id,
                relationship_type="USES_NETWORK",
                source_table="plan_hospitals",
                source_table_id=row["id"],
            )

    def _add_documents(
        self,
        connection: sqlite3.Connection,
        graph: nx.DiGraph,
        plans: dict[int, str],
    ) -> None:
        if not _table_exists(connection, "documents"):
            return

        rows = _fetch_all(
            connection,
            """
            SELECT id, plan_id, title, source_uri
            FROM documents
            ORDER BY plan_id, source_uri, id
            """,
        )
        for row in rows:
            plan_node_id = plans.get(row["plan_id"])
            if plan_node_id is None:
                continue

            document_key = PurePosixPath(row["source_uri"]).name or str(row["id"])
            node_id = f"document:{_stable_document_key(document_key)}"
            graph.add_node(
                node_id,
                entity_type="Document",
                source_table="documents",
                source_table_id=row["id"],
                title=row["title"],
                source_uri=row["source_uri"],
            )
            graph.add_edge(
                plan_node_id,
                node_id,
                relationship_type="GOVERNED_BY",
                source_table="documents",
                source_table_id=row["id"],
            )


def _fetch_all(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    cursor = connection.execute(query, parameters)
    column_names = [description[0] for description in cursor.description]
    return [dict(zip(column_names, row, strict=True)) for row in cursor.fetchall()]


def _stable_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "unknown"


def _stable_document_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9._-]+", "_", ascii_value.lower()).strip("_")
    return slug or "unknown"


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None
