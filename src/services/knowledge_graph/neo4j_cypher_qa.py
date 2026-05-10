"""LangChain Neo4j Cypher QA helpers for the health-insurance graph."""

from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from langchain_neo4j import GraphCypherQAChain

from src.core.config import settings
from src.services.observability import service_observe

CYPHER_GENERATION_TEMPLATE = """Generate ONLY a valid read-only Cypher query.
No explanations.

Strategy:
1. Use the actual graph schema below.
2. Use only labels, relationship types, and properties shown in the schema.
3. Prefer broad matching on name-like properties for Vietnamese text.
4. Explore relationships in either direction when the direction is unclear.
5. Return useful node and relationship properties for the answer.

Schema:
{schema}

Question:
{question}

Cypher:"""

QA_TEMPLATE = """Answer the question using only the graph query context.
If the context is empty, say that the graph has no matching evidence.

Context:
{context}

Question:
{question}

Answer:"""


def build_graph_cypher_qa_chain(
    *,
    graph: Any,
    cypher_llm: Any,
    qa_llm: Any | None = None,
    verbose: bool = False,
    return_intermediate_steps: bool = False,
) -> Any:
    """Build a LangChain GraphCypherQAChain for Neo4j graph retrieval."""
    if hasattr(graph, "refresh_schema"):
        graph.refresh_schema()
    cypher_prompt = PromptTemplate(
        template=CYPHER_GENERATION_TEMPLATE,
        input_variables=["schema", "question"],
    )
    qa_prompt = PromptTemplate(
        template=QA_TEMPLATE,
        input_variables=["context", "question"],
    )
    return GraphCypherQAChain.from_llm(
        cypher_llm=cypher_llm,
        qa_llm=qa_llm or cypher_llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        qa_prompt=qa_prompt,
        allow_dangerous_requests=True,
        verbose=verbose,
        return_intermediate_steps=return_intermediate_steps,
    )


def build_knowledge_graph_qa_llm() -> Any:
    """Build the configured LangChain chat model for graph Cypher QA."""
    model_config: dict[str, Any] = {
        "temperature": settings.KG_CYPHER_QA_LLM_TEMPERATURE,
        "top_p": settings.KG_CYPHER_QA_LLM_TOP_P,
        "top_k": settings.KG_CYPHER_QA_LLM_TOP_K,
    }
    if settings.KG_CYPHER_QA_LLM_API_KEY:
        model_config["api_key"] = settings.KG_CYPHER_QA_LLM_API_KEY
    if settings.KG_CYPHER_QA_LLM_BASE_URL:
        model_config["base_url"] = settings.KG_CYPHER_QA_LLM_BASE_URL
    if (
        _uses_ollama(
            settings.KG_CYPHER_QA_LLM_PROVIDER,
            settings.KG_CYPHER_QA_LLM_MODEL,
        )
        and settings.KG_CYPHER_QA_LLM_API_KEY
    ):
        model_config["client_kwargs"] = {
            "headers": {"Authorization": f"Bearer {settings.KG_CYPHER_QA_LLM_API_KEY}"}
        }
    return init_chat_model(
        settings.KG_CYPHER_QA_LLM_MODEL,
        model_provider=settings.KG_CYPHER_QA_LLM_PROVIDER,
        **model_config,
    )


class Neo4jCypherQAService:
    """Answer graph questions through LangChain GraphCypherQAChain."""

    def __init__(self, *, chain: Any) -> None:
        """Initialize with a GraphCypherQAChain-compatible runnable."""
        self._chain = chain

    @classmethod
    def from_graph(
        cls,
        *,
        graph: Any,
        cypher_llm: Any | None = None,
        qa_llm: Any | None = None,
        verbose: bool = False,
        return_intermediate_steps: bool = False,
    ) -> Neo4jCypherQAService:
        """Create the service from a Neo4jGraph-compatible object."""
        graph_qa_llm = cypher_llm or build_knowledge_graph_qa_llm()
        chain = build_graph_cypher_qa_chain(
            graph=graph,
            cypher_llm=graph_qa_llm,
            qa_llm=qa_llm,
            verbose=verbose,
            return_intermediate_steps=return_intermediate_steps,
        )
        return cls(chain=chain)

    @service_observe(
        name="service.knowledge_graph.neo4j_cypher_qa.invoke",
        component="neo4j_cypher_qa",
    )
    def invoke(self, question: str) -> str:
        """Answer a natural-language question from the Neo4j graph."""
        result = self._chain.invoke({"query": question})
        if isinstance(result, dict) and "result" in result:
            return str(result["result"])
        return str(result)


def _uses_ollama(provider: str, model: str) -> bool:
    return provider.lower() == "ollama" or "ollama" in model.lower()
