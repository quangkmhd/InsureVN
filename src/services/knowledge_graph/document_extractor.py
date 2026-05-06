"""Extract document-grounded entities and relationships for Knowledge Graph."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from src.services.knowledge_graph.schema import (
    ALLOWED_NODE_LABELS,
)
from src.services.knowledge_graph.schema import (
    ALLOWED_RELATIONSHIP_TYPES as SCHEMA_ALLOWED_RELATIONSHIP_TYPES,
)
from src.services.observability import service_observe

ALLOWED_NODE_TYPES = ALLOWED_NODE_LABELS
ALLOWED_RELATIONSHIP_TYPES = SCHEMA_ALLOWED_RELATIONSHIP_TYPES


@dataclass(frozen=True)
class GraphDocument:
    """Normalized source document used to seed the knowledge graph."""

    document_id: str
    document_name: str
    company_code: str
    source_path: str
    text: str


@dataclass(frozen=True)
class GraphEdge:
    """Document-grounded graph relationship candidate."""

    source_id: str
    target_id: str
    relationship_type: str
    document_id: str
    source_path: str
    confidence: float
    chunk_id: str | None = None
    section_type: str | None = None


@dataclass(frozen=True)
class GraphExtraction:
    """Extracted graph nodes and edges."""

    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass(frozen=True)
class _PlanBlock:
    plan_name: str
    body: str


class DocumentGraphExtractor:
    """Extract strict graph entities and relationships from policy documents."""

    @service_observe(
        name="service.knowledge_graph.document_extractor.extract",
        component="document_graph_extractor",
    )
    def extract(
        self,
        document: GraphDocument,
        chunks: list[dict[str, Any]],
    ) -> GraphExtraction:
        """Extract document-grounded graph nodes and edges.

        Args:
            document: Normalized Markdown or converted PDF text.
            chunks: Qdrant chunk payloads associated with the document.

        Returns:
            GraphExtraction containing allowed node and relationship types only.
        """
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[GraphEdge] = []
        company_id = f"company:{document.company_code}"
        document_id = f"document:{_stable_slug(document.document_id)}"

        nodes[company_id] = {
            "entity_type": "Company",
            "company_code": document.company_code,
            "name": document.company_code,
            "document_id": document.document_id,
            "source_path": document.source_path,
        }
        nodes[document_id] = {
            "entity_type": "Document",
            "document_id": document.document_id,
            "document_name": document.document_name,
            "company_code": document.company_code,
            "source_path": document.source_path,
        }
        edges.append(
            _edge(
                document_id,
                company_id,
                "DOCUMENT_DEFINES",
                document,
                confidence=1.0,
            )
        )

        plan_blocks = _extract_plan_blocks(document.text)
        all_exclusion_ids: list[str] = []
        all_condition_ids: list[str] = []
        for plan_block in plan_blocks:
            plan_id = _plan_id(document.company_code, plan_block.plan_name)
            nodes[plan_id] = {
                "entity_type": "Plan",
                "company_code": document.company_code,
                "plan_code": _stable_slug(plan_block.plan_name),
                "name": plan_block.plan_name,
                "document_id": document.document_id,
                "source_path": document.source_path,
            }
            edges.append(
                _edge(company_id, plan_id, "OFFERS", document, confidence=0.95)
            )
            self._extract_plan_block(nodes, edges, document, plan_id, plan_block)
            all_exclusion_ids.extend(
                _node_ids_for_items(
                    "exclusion",
                    document.company_code,
                    _plan_slug(plan_id),
                    plan_block.body,
                    "Exclusions",
                )
            )
            all_condition_ids.extend(
                _node_ids_for_items(
                    "condition",
                    document.company_code,
                    _plan_slug(plan_id),
                    plan_block.body,
                    "Conditions",
                )
            )

        self._extract_glossary(nodes, document)
        self._extract_chunks(
            nodes,
            edges,
            document,
            chunks,
            all_exclusion_ids,
            all_condition_ids,
        )
        return GraphExtraction(nodes=nodes, edges=edges)

    def _extract_plan_block(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[GraphEdge],
        document: GraphDocument,
        plan_id: str,
        plan_block: _PlanBlock,
    ) -> None:
        self._extract_items(
            nodes,
            edges,
            document,
            plan_block.body,
            plan_id,
            section_name="Benefits",
            entity_type="Benefit",
            node_prefix="benefit",
            relationship_type="INCLUDES",
        )
        exclusion_ids = self._extract_items(
            nodes,
            edges,
            document,
            plan_block.body,
            plan_id,
            section_name="Exclusions",
            entity_type="Exclusion",
            node_prefix="exclusion",
            relationship_type="EXCLUDES",
        )
        self._extract_items(
            nodes,
            edges,
            document,
            plan_block.body,
            plan_id,
            section_name="Conditions",
            entity_type="Condition",
            node_prefix="condition",
            relationship_type="APPLIES_TO",
            parent_ids=exclusion_ids,
        )
        self._extract_waiting_periods(
            nodes,
            edges,
            document,
            plan_block.body,
            plan_id,
            _plan_slug(plan_id),
        )
        self._extract_items(
            nodes,
            edges,
            document,
            plan_block.body,
            plan_id,
            section_name="Hospitals",
            entity_type="Hospital",
            node_prefix="hospital",
            relationship_type="USES_NETWORK",
        )

    def _extract_items(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[GraphEdge],
        document: GraphDocument,
        text: str,
        plan_id: str,
        *,
        section_name: str,
        entity_type: str,
        node_prefix: str,
        relationship_type: str,
        parent_ids: list[str] | None = None,
    ) -> list[str]:
        item_ids: list[str] = []
        for item in _section_items(text, section_name):
            node_id = _item_node_id(node_prefix, plan_id, item)
            nodes[node_id] = {
                "entity_type": entity_type,
                "name": item,
                "company_code": _plan_company_code(plan_id),
                "plan_code": _plan_slug(plan_id),
                "document_id": document.document_id,
                "source_path": document.source_path,
            }
            item_ids.append(node_id)
            for parent_id in parent_ids or [plan_id]:
                edges.append(
                    _edge(
                        parent_id,
                        node_id,
                        relationship_type,
                        document,
                        confidence=0.9,
                        section_type=section_name.lower(),
                    )
                )
        return item_ids

    def _extract_waiting_periods(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[GraphEdge],
        document: GraphDocument,
        text: str,
        plan_id: str,
        plan_slug: str,
    ) -> None:
        for item in _section_items(text, "Waiting Periods"):
            duration_match = re.search(r"(\d+)\s+days?", item, flags=re.IGNORECASE)
            duration_days = int(duration_match.group(1)) if duration_match else None
            duration_slug = (
                f"{duration_days}_days" if duration_days else _stable_slug(item)
            )
            node_id = (
                f"waiting_period:{document.company_code}:{plan_slug}:{duration_slug}"
            )
            nodes[node_id] = {
                "entity_type": "WaitingPeriod",
                "name": item,
                "duration_days": duration_days,
                "document_id": document.document_id,
                "source_path": document.source_path,
            }
            edges.append(
                _edge(
                    plan_id,
                    node_id,
                    "HAS_WAITING_PERIOD",
                    document,
                    confidence=0.9,
                    section_type="waiting_periods",
                )
            )

    def _extract_glossary(
        self,
        nodes: dict[str, dict[str, Any]],
        document: GraphDocument,
    ) -> None:
        for item in _section_items(document.text, "Glossary"):
            term, _, definition = item.partition(":")
            if not term:
                continue
            node_id = f"glossary_term:{_stable_slug(term)}"
            nodes[node_id] = {
                "entity_type": "GlossaryTerm",
                "name": term.strip(),
                "definition": definition.strip(),
                "document_id": document.document_id,
                "source_path": document.source_path,
            }

    def _extract_chunks(
        self,
        nodes: dict[str, dict[str, Any]],
        edges: list[GraphEdge],
        document: GraphDocument,
        chunks: list[dict[str, Any]],
        exclusion_ids: list[str],
        condition_ids: list[str],
    ) -> None:
        known_mentions = exclusion_ids + condition_ids
        document_node_id = f"document:{_stable_slug(document.document_id)}"
        for chunk in chunks:
            if chunk.get("document_id") != document.document_id:
                continue
            chunk_id = f"chunk:{document.document_id}:{chunk['chunk_index']}"
            nodes[chunk_id] = {
                "entity_type": "Chunk",
                "document_id": document.document_id,
                "chunk_index": chunk["chunk_index"],
                "company_code": chunk.get("company_code"),
                "document_name": chunk.get("document_name"),
                "plan_code": chunk.get("plan_code"),
                "section_type": chunk.get("section_type"),
                "source_path": chunk.get("source_path"),
            }
            edges.append(
                _edge(
                    document_node_id,
                    chunk_id,
                    "DOCUMENT_CONTAINS",
                    document,
                    confidence=1.0,
                    chunk_id=chunk_id,
                    section_type=chunk.get("section_type"),
                )
            )
            chunk_text = str(chunk.get("text", "")).lower()
            chunk_plan_code = chunk.get("plan_code")
            for target_id in known_mentions:
                target_plan_code = nodes[target_id].get("plan_code")
                if chunk_plan_code and target_plan_code != chunk_plan_code:
                    continue
                name = nodes[target_id]["name"].lower()
                if name in chunk_text:
                    edges.append(
                        _edge(
                            chunk_id,
                            target_id,
                            "MENTIONED_IN",
                            document,
                            confidence=0.95,
                            chunk_id=chunk_id,
                            section_type=chunk.get("section_type"),
                        )
                    )


def _extract_plan_blocks(text: str) -> list[_PlanBlock]:
    matches = list(re.finditer(r"^\s*#+\s*Plan:\s*(.+?)\s*$", text, flags=re.MULTILINE))
    blocks: list[_PlanBlock] = []
    for index, match in enumerate(matches):
        next_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        )
        blocks.append(
            _PlanBlock(
                plan_name=match.group(1).strip(),
                body=text[match.end() : next_start],
            )
        )
    return blocks


def _node_ids_for_items(
    node_prefix: str,
    company_code: str,
    plan_slug: str,
    text: str,
    section_name: str,
) -> list[str]:
    return [
        f"{node_prefix}:{company_code}:{plan_slug}:{_stable_slug(item)}"
        for item in _section_items(text, section_name)
    ]


def _section_items(text: str, section_name: str) -> list[str]:
    next_section_pattern = r"(?=^\s*[A-Z][A-Za-z ]+:\s*$|^\s*#+\s|\Z)"
    pattern = rf"^\s*{re.escape(section_name)}:\s*$([\s\S]*?){next_section_pattern}"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return []
    items: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _plan_id(company_code: str, plan_name: str) -> str:
    return f"plan:{company_code}:{_stable_slug(plan_name)}"


def _item_node_id(node_prefix: str, plan_id: str, item: str) -> str:
    if node_prefix in {"benefit", "exclusion", "condition"}:
        return (
            f"{node_prefix}:{_plan_company_code(plan_id)}:"
            f"{_plan_slug(plan_id)}:{_stable_slug(item)}"
        )
    return f"{node_prefix}:{_stable_slug(item)}"


def _plan_company_code(plan_id: str) -> str:
    parts = plan_id.split(":")
    return parts[1] if len(parts) >= 3 else "UNKNOWN"


def _plan_slug(plan_id: str) -> str:
    return plan_id.rsplit(":", maxsplit=1)[-1]


def _edge(
    source_id: str,
    target_id: str,
    relationship_type: str,
    document: GraphDocument,
    *,
    confidence: float,
    chunk_id: str | None = None,
    section_type: str | None = None,
) -> GraphEdge:
    return GraphEdge(
        source_id=source_id,
        target_id=target_id,
        relationship_type=relationship_type,
        document_id=document.document_id,
        source_path=document.source_path,
        confidence=confidence,
        chunk_id=chunk_id,
        section_type=section_type,
    )


def _stable_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "unknown"
