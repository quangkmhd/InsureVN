"""Compatibility exports for graph evidence adapters."""

from src.services.knowledge_graph.graph_evidence import GraphEvidenceMapper

GraphEvidenceAdapter = GraphEvidenceMapper

__all__ = ["GraphEvidenceAdapter", "GraphEvidenceMapper"]
