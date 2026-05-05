from typing import Any

from langchain_neo4j import Neo4jGraph

from src.services.knowledge_graph.schema import NEO4J_UNIQUENESS_CONSTRAINTS
from src.services.observability import service_observe


class Neo4jKnowledgeGraphStore:
    """Neo4j graph store wrapper for schema setup and graph imports."""

    def __init__(self, *, graph: Any) -> None:
        """Initialize with a Neo4jGraph-compatible object."""
        self._graph = graph

    @classmethod
    @service_observe(
        name="service.knowledge_graph.neo4j_store.from_connection",
        component="neo4j_store",
    )
    def from_connection(
        cls,
        *,
        url: str,
        username: str,
        password: str,
        database: str | None = None,
    ) -> "Neo4jKnowledgeGraphStore":
        """Create store from Neo4j connection settings."""
        kwargs: dict[str, Any] = {
            "url": url,
            "username": username,
            "password": password,
        }
        if database:
            kwargs["database"] = database
        return cls(graph=Neo4jGraph(**kwargs))

    @service_observe(
        name="service.knowledge_graph.neo4j_store.ensure_schema",
        component="neo4j_store",
    )
    def ensure_schema(self) -> None:
        """Create Neo4j uniqueness constraints required for idempotent import."""
        for label, property_name in NEO4J_UNIQUENESS_CONSTRAINTS:
            self._graph.query(
                f"""
                CREATE CONSTRAINT {label}_{property_name}_unique IF NOT EXISTS
                FOR (node:{label})
                REQUIRE node.{property_name} IS UNIQUE
                """
            )

    @service_observe(
        name="service.knowledge_graph.neo4j_store.import_graph_documents",
        component="neo4j_store",
    )
    def import_graph_documents(self, graph_documents: list[Any]) -> None:
        """Import LangChain GraphDocument objects with source linkage."""
        self._graph.add_graph_documents(
            graph_documents,
            include_source=True,
            baseEntityLabel=True,
        )
