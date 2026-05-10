"""Extract schema-constrained LangChain graph documents from Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j.graphs.graph_document import (
    GraphDocument as LangChainGraphDocument,
)

from src.core.config import settings
from src.core.logger import get_logger
from src.services.knowledge_graph.graph_schema import (
    NODE_PROPERTY_NAMES,
    RELATIONSHIP_PROPERTY_NAMES,
    get_llm_graph_transformer_schema,
)
from src.services.observability import service_observe

ALLOWED_NODE_TYPES = tuple(get_llm_graph_transformer_schema()["allowed_nodes"])
ALLOWED_RELATIONSHIP_TYPES = tuple(
    get_llm_graph_transformer_schema()["allowed_relationships"]
)
NODE_PROPERTY_NAME_SET = set(NODE_PROPERTY_NAMES)
RELATIONSHIP_PROPERTY_NAME_SET = set(RELATIONSHIP_PROPERTY_NAMES)
DEFAULT_EXTRACTION_CONFIDENCE = 0.8
EXTRACTION_METHOD = "langchain_llm_graph_transformer"

logger = get_logger(__name__)


@dataclass(frozen=True)
class GraphDocument:
    """Normalized source document used to seed LangChain graph extraction."""

    document_id: str
    document_name: str
    company_code: str
    source_path: str
    text: str


class DocumentGraphExtractor:
    """Extract graph documents with LangChain LLMGraphTransformer."""

    def __init__(
        self,
        *,
        transformer: Any | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            transformer: LLMGraphTransformer-compatible converter.
            max_retries: Number of retries per chunk after the first failed attempt.
        """
        self._transformer = transformer or build_llm_graph_transformer()
        self._max_retries = (
            settings.KG_EXTRACTION_MAX_RETRIES if max_retries is None else max_retries
        )

    @service_observe(
        name="service.knowledge_graph.llm_graph_document_extractor.extract",
        component="llm_graph_document_extractor",
    )
    def extract(
        self,
        document: GraphDocument,
        chunks: list[dict[str, Any]],
    ) -> list[LangChainGraphDocument]:
        """Extract LangChain graph documents from one source document.

        Args:
            document: Normalized Markdown source document.
            chunks: Qdrant chunk payloads associated with the document.

        Returns:
            Schema-constrained graph documents ready for Neo4jGraph.add_graph_documents.
        """
        graph_documents: list[LangChainGraphDocument] = []
        for source_document in _source_documents_for(document, chunks):
            graph_documents.extend(self._convert_with_retries(source_document))
        return graph_documents

    async def aextract(
        self,
        document: GraphDocument,
        chunks: list[dict[str, Any]],
    ) -> list[LangChainGraphDocument]:
        """Asynchronously extract LangChain graph documents from one document."""
        graph_documents: list[LangChainGraphDocument] = []
        for source_document in _source_documents_for(document, chunks):
            graph_documents.extend(await self._aconvert_with_retries(source_document))
        return graph_documents

    def _convert_with_retries(
        self,
        source_document: Document,
    ) -> list[LangChainGraphDocument]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                converted = self._transformer.convert_to_graph_documents(
                    [source_document]
                )
                return [_enrich_graph_document(item) for item in converted]
            except Exception as exc:  # pragma: no cover - logged branch
                last_error = exc
                if attempt >= self._max_retries:
                    break
        _log_failed_chunk(source_document, last_error)
        return []

    async def _aconvert_with_retries(
        self,
        source_document: Document,
    ) -> list[LangChainGraphDocument]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                converted = await self._transformer.aconvert_to_graph_documents(
                    [source_document]
                )
                return [_enrich_graph_document(item) for item in converted]
            except Exception as exc:  # pragma: no cover - logged branch
                last_error = exc
                if attempt >= self._max_retries:
                    break
        _log_failed_chunk(source_document, last_error)
        return []


def build_llm_graph_transformer() -> LLMGraphTransformer:
    """Build the default schema-constrained LangChain graph transformer."""
    schema = get_llm_graph_transformer_schema()
    knowledge_graph_extraction_llm = build_knowledge_graph_extraction_llm()
    prompt = build_knowledge_graph_extraction_prompt()
    try:
        return LLMGraphTransformer(
            llm=knowledge_graph_extraction_llm,
            allowed_nodes=schema["allowed_nodes"],
            allowed_relationships=schema["allowed_relationships"],
            node_properties=schema["node_properties"],
            relationship_properties=schema["relationship_properties"],
            strict_mode=True,
            prompt=prompt,
        )
    except ValueError as exc:
        logger.warning(
            "falling back to graph extraction without property schema",
            extra={
                "component": "document_graph_extractor",
                "error_type": type(exc).__name__,
            },
        )
        return LLMGraphTransformer(
            llm=knowledge_graph_extraction_llm,
            allowed_nodes=schema["allowed_nodes"],
            allowed_relationships=schema["allowed_relationships"],
            strict_mode=True,
            prompt=prompt,
            ignore_tool_usage=True,
        )


def build_knowledge_graph_extraction_llm() -> Any:
    """Build the configured LangChain chat model for KG extraction."""
    model_config: dict[str, Any] = {
        "temperature": settings.KG_EXTRACTION_LLM_TEMPERATURE,
        "top_p": settings.KG_EXTRACTION_LLM_TOP_P,
        "top_k": settings.KG_EXTRACTION_LLM_TOP_K,
    }
    if settings.KG_EXTRACTION_LLM_API_KEY:
        model_config["api_key"] = settings.KG_EXTRACTION_LLM_API_KEY
    if settings.KG_EXTRACTION_LLM_BASE_URL:
        model_config["base_url"] = settings.KG_EXTRACTION_LLM_BASE_URL
    if (
        _uses_ollama(
            settings.KG_EXTRACTION_LLM_PROVIDER,
            settings.KG_EXTRACTION_LLM_MODEL,
        )
        and settings.KG_EXTRACTION_LLM_API_KEY
    ):
        model_config["client_kwargs"] = {
            "headers": {"Authorization": f"Bearer {settings.KG_EXTRACTION_LLM_API_KEY}"}
        }
    return init_chat_model(
        settings.KG_EXTRACTION_LLM_MODEL,
        model_provider=settings.KG_EXTRACTION_LLM_PROVIDER,
        **model_config,
    )


def build_knowledge_graph_extraction_prompt() -> ChatPromptTemplate:
    """Build the Vietnamese insurance graph extraction prompt."""
    schema = get_llm_graph_transformer_schema()
    allowed_nodes = ", ".join(schema["allowed_nodes"])
    allowed_relationships = ", ".join(schema["allowed_relationships"])
    node_properties = ", ".join(schema["node_properties"])
    relationship_properties = ", ".join(schema["relationship_properties"])
    system_prompt = f"""You extract a Vietnamese health-insurance knowledge graph.

Use ONLY these node labels:
{allowed_nodes}

Use ONLY these relationship types:
{allowed_relationships}

Use ONLY these node properties when relevant:
{node_properties}

Use ONLY these relationship properties when relevant:
{relationship_properties}

Rules:
- Preserve Vietnamese names and legal insurance wording.
- Prefer concrete insurance entities, benefits, exclusions, limits, premiums,
  waiting periods, claims, medical services, medical facilities, and documents.
- Do not invent facts that are not grounded in the text.
- Keep node IDs short but stable and human-readable.
- Extract the most useful relationships for GraphRAG retrieval."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "Document text:\n{input}"),
        ]
    )


def _source_documents_for(
    document: GraphDocument,
    chunks: list[dict[str, Any]],
) -> list[Document]:
    matching_chunks = [
        chunk for chunk in chunks if chunk.get("document_id") == document.document_id
    ]
    if not matching_chunks:
        return [
            Document(
                page_content=document.text,
                metadata=_source_metadata(document, None),
            )
        ]
    source_documents: list[Document] = []
    for chunk in matching_chunks:
        text = str(chunk.get("text") or chunk.get("parent_text") or "").strip()
        if not text:
            continue
        source_documents.append(
            Document(
                page_content=text,
                metadata=_source_metadata(document, chunk),
            )
        )
    return source_documents or [
        Document(
            page_content=document.text,
            metadata=_source_metadata(document, None),
        )
    ]


def _source_metadata(
    document: GraphDocument,
    chunk: dict[str, Any] | None,
) -> dict[str, Any]:
    source_chunk_id = _source_chunk_id(chunk)
    chunk_source_path = chunk.get("source_path") if chunk else None
    metadata = {
        "id": (
            f"{document.document_id}:{source_chunk_id}"
            if source_chunk_id
            else document.document_id
        ),
        "document_id": document.document_id,
        "document_name": document.document_name,
        "company_code": document.company_code,
        "source_path": str(chunk_source_path or document.source_path),
        "source_chunk_id": source_chunk_id,
        "ingestion_version": chunk.get("ingestion_version") if chunk else None,
    }
    if chunk and chunk.get("chunk_index") is not None:
        metadata["chunk_index"] = chunk["chunk_index"]
    return metadata


def _source_chunk_id(chunk: dict[str, Any] | None) -> str | None:
    if not chunk:
        return None
    if chunk.get("chunk_id"):
        return str(chunk["chunk_id"])
    if chunk.get("id"):
        return str(chunk["id"])
    if chunk.get("chunk_index") is not None:
        return str(chunk["chunk_index"])
    return None


def _enrich_graph_document(
    graph_document: LangChainGraphDocument,
) -> LangChainGraphDocument:
    source = graph_document.source
    metadata = source.metadata if source is not None else {}
    for node in graph_document.nodes:
        node.properties = _node_properties(node.properties, metadata, source)
    for relationship in graph_document.relationships:
        relationship.properties = _relationship_properties(
            relationship.properties,
            metadata,
            source,
        )
    return graph_document


def _node_properties(
    properties: dict[str, Any] | None,
    metadata: dict[str, Any],
    source: Document | None,
) -> dict[str, Any]:
    filtered = _filter_properties(properties or {}, NODE_PROPERTY_NAME_SET)
    filtered.update(
        _filter_properties(
            {
                "source_document_id": metadata.get("document_id"),
                "source_chunk_id": metadata.get("source_chunk_id"),
                "source_path": metadata.get("source_path"),
                "evidence_text": _evidence_text(source),
                "company_code": metadata.get("company_code"),
                "document_id": metadata.get("document_id"),
                "document_name": metadata.get("document_name"),
                "extraction_method": EXTRACTION_METHOD,
                "ingestion_version": metadata.get("ingestion_version"),
            },
            NODE_PROPERTY_NAME_SET,
        )
    )
    return filtered


def _relationship_properties(
    properties: dict[str, Any] | None,
    metadata: dict[str, Any],
    source: Document | None,
) -> dict[str, Any]:
    filtered = _filter_properties(properties or {}, RELATIONSHIP_PROPERTY_NAME_SET)
    confidence = (
        properties.get("confidence", DEFAULT_EXTRACTION_CONFIDENCE)
        if properties
        else DEFAULT_EXTRACTION_CONFIDENCE
    )
    filtered.update(
        _filter_properties(
            {
                "source_document_id": metadata.get("document_id"),
                "source_chunk_id": metadata.get("source_chunk_id"),
                "source_path": metadata.get("source_path"),
                "evidence_text": _evidence_text(source),
                "confidence": confidence,
                "extraction_method": EXTRACTION_METHOD,
                "ingestion_version": metadata.get("ingestion_version"),
            },
            RELATIONSHIP_PROPERTY_NAME_SET,
        )
    )
    return filtered


def _filter_properties(
    properties: dict[str, Any],
    allowed_properties: set[str],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in properties.items()
        if key in allowed_properties and key != "id" and value is not None
    }


def _evidence_text(source: Document | None) -> str | None:
    if source is None:
        return None
    evidence_text = source.page_content.strip()
    return evidence_text[:1000] if evidence_text else None


def _log_failed_chunk(
    source_document: Document,
    last_error: Exception | None,
) -> None:
    logger.warning(
        "skipped knowledge graph chunk after extraction retries",
        extra={
            "component": "document_graph_extractor",
            "document_id": source_document.metadata.get("document_id"),
            "source_chunk_id": source_document.metadata.get("source_chunk_id"),
            "error_type": type(last_error).__name__ if last_error else None,
        },
    )


def _uses_ollama(provider: str, model: str) -> bool:
    return provider.lower() == "ollama" or "ollama" in model.lower()
