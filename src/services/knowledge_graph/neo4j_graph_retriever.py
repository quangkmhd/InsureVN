import time
from typing import Any

from src.services.knowledge_graph.retriever import GraphPath, GraphPathEdge
from src.services.observability import service_observe

READ_ONLY_PATH_QUERY = """
MATCH path = (start)-[relationships*1..$max_hops]->(target)
WHERE start.id IN $start_entities
  AND all(relationship IN relationships
          WHERE type(relationship) IN $relation_types)
RETURN
  start.id AS source_id,
  target.id AS target_id,
  type(last(relationships)) AS relationship_type,
  last(relationships).source_document_id AS document_id,
  last(relationships).source_path AS source_path,
  last(relationships).source_chunk_id AS chunk_id,
  last(relationships).page_number AS page_number,
  last(relationships).section_type AS section_type,
  last(relationships).confidence AS confidence
"""


class Neo4jGraphRetriever:
    """Read-only Neo4j relationship path retriever."""

    def __init__(self, *, graph: Any) -> None:
        """Initialize retriever with a Neo4jGraph-compatible object."""
        self._graph = graph

    @service_observe(
        name="service.knowledge_graph.neo4j_graph_retriever.retrieve",
        component="neo4j_graph_retriever",
    )
    def retrieve(
        self,
        start_entities: list[str],
        relation_types: list[str],
        max_hops: int,
    ) -> list[GraphPath]:
        """Retrieve read-only graph paths from Neo4j."""
        started_at = time.perf_counter()
        records = self._graph.query(
            READ_ONLY_PATH_QUERY,
            params={
                "start_entities": start_entities,
                "relation_types": relation_types,
                "max_hops": max_hops,
            },
        )
        latency_ms = (time.perf_counter() - started_at) * 1000
        return [
            GraphPath(
                node_ids=[str(record["source_id"]), str(record["target_id"])],
                edges=[
                    GraphPathEdge(
                        source_id=str(record["source_id"]),
                        target_id=str(record["target_id"]),
                        relationship_type=str(record["relationship_type"]),
                        attributes={
                            "document_id": record.get("document_id"),
                            "source_path": record.get("source_path"),
                            "chunk_id": record.get("chunk_id"),
                            "page_number": record.get("page_number"),
                            "section_type": record.get("section_type"),
                            "confidence": record.get("confidence", 0.0),
                        },
                    )
                ],
                latency_ms=latency_ms,
            )
            for record in records
        ]
