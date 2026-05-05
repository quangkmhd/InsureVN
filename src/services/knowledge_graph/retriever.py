"""Traversal utilities for document-derived knowledge graphs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import networkx as nx

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GraphPathEdge:
    """A single relationship traversed in the graph."""

    source_id: str
    target_id: str
    relationship_type: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class GraphPath:
    """A graph traversal path and timing metadata."""

    node_ids: list[str]
    edges: list[GraphPathEdge]
    latency_ms: float


class NetworkxGraphPathRetriever:
    """Retrieve N-hop relationship paths from a NetworkX graph."""

    def __init__(self, graph: nx.DiGraph) -> None:
        """Initialize retriever with a directed knowledge graph."""
        self._graph = graph

    def retrieve(
        self,
        start_entities: list[str],
        relation_types: list[str],
        max_hops: int,
    ) -> list[GraphPath]:
        """Retrieve paths matching relationship types within a hop limit."""
        start = time.perf_counter()
        allowed_relations = set(relation_types)
        paths: list[GraphPath] = []
        for entity_id in start_entities:
            if entity_id not in self._graph:
                continue
            self._walk(
                entity_id,
                allowed_relations,
                max_hops,
                node_path=[entity_id],
                edge_path=[],
                output=paths,
                start_time=start,
            )
        paths.sort(key=lambda path: len(path.edges), reverse=True)
        latency_ms = (time.perf_counter() - start) * 1000
        for entity_id in start_entities:
            logger.info(
                "retrieved graph paths",
                extra={
                    "component": "graph_retriever",
                    "query_start_entity": entity_id,
                    "query_relation_types": relation_types,
                    "max_hops": max_hops,
                    "latency_ms": latency_ms,
                },
            )
        return paths

    def explain_path(self, path: GraphPath) -> dict[str, Any]:
        """Return serializable path details for debugging."""
        return {
            "node_ids": path.node_ids,
            "relationships": [edge.relationship_type for edge in path.edges],
            "latency_ms": path.latency_ms,
        }

    def _walk(
        self,
        current_id: str,
        relation_types: set[str],
        max_hops: int,
        *,
        node_path: list[str],
        edge_path: list[GraphPathEdge],
        output: list[GraphPath],
        start_time: float,
    ) -> None:
        if edge_path:
            output.append(
                GraphPath(
                    node_ids=list(node_path),
                    edges=list(edge_path),
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                )
            )
        if len(edge_path) >= max_hops:
            return

        for _, target_id, attributes in self._graph.edges(current_id, data=True):
            relationship_type = attributes.get("relationship_type")
            if relationship_type not in relation_types or target_id in node_path:
                continue
            self._walk(
                target_id,
                relation_types,
                max_hops,
                node_path=[*node_path, target_id],
                edge_path=[
                    *edge_path,
                    GraphPathEdge(
                        source_id=current_id,
                        target_id=target_id,
                        relationship_type=relationship_type,
                        attributes=dict(attributes),
                    ),
                ],
                output=output,
                start_time=start_time,
            )
