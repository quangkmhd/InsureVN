"""JSON serialization for NetworkX knowledge graphs."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from src.services.observability import service_observe


class GraphJsonSerializer:
    """Persist and load graph JSON while preserving attributes."""

    @service_observe(
        name="service.knowledge_graph.serializer.save",
        component="graph_json_serializer",
    )
    def save(self, graph: nx.DiGraph, path: Path) -> None:
        """Write graph to node-link JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(json_graph.node_link_data(graph), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @service_observe(
        name="service.knowledge_graph.serializer.load",
        component="graph_json_serializer",
    )
    def load(self, path: Path) -> nx.DiGraph:
        """Load graph from node-link JSON."""
        data = json.loads(path.read_text(encoding="utf-8"))
        graph = json_graph.node_link_graph(data, directed=True, multigraph=False)
        return nx.DiGraph(graph)
