from src.services.knowledge_graph import neo4j_cypher_qa
from src.services.knowledge_graph.neo4j_cypher_qa import (
    Neo4jCypherQAService,
    build_graph_cypher_qa_chain,
)


class FakeNeo4jGraph:
    def __init__(self) -> None:
        self.refreshed = False

    def refresh_schema(self) -> None:
        self.refreshed = True


class FakeGraphCypherQAChain:
    calls = []

    @classmethod
    def from_llm(cls, **kwargs):
        cls.calls.append(kwargs)
        return {"chain": "created", "kwargs": kwargs}


class FakeRunnableChain:
    def __init__(self) -> None:
        self.inputs = []

    def invoke(self, inputs):
        self.inputs.append(inputs)
        return {"result": "Tra loi tu graph"}


def test_build_graph_cypher_qa_chain_uses_langchain_neo4j_pattern(monkeypatch) -> None:
    FakeGraphCypherQAChain.calls = []
    monkeypatch.setattr(
        neo4j_cypher_qa,
        "GraphCypherQAChain",
        FakeGraphCypherQAChain,
    )
    graph = FakeNeo4jGraph()
    cypher_llm = object()
    qa_llm = object()

    chain = build_graph_cypher_qa_chain(
        graph=graph,
        cypher_llm=cypher_llm,
        qa_llm=qa_llm,
        verbose=True,
        return_intermediate_steps=True,
    )

    assert graph.refreshed is True
    assert chain["chain"] == "created"
    call = FakeGraphCypherQAChain.calls[0]
    assert call["graph"] is graph
    assert call["cypher_llm"] is cypher_llm
    assert call["qa_llm"] is qa_llm
    assert call["allow_dangerous_requests"] is True
    assert call["verbose"] is True
    assert call["return_intermediate_steps"] is True
    assert set(call["cypher_prompt"].input_variables) == {"schema", "question"}
    assert set(call["qa_prompt"].input_variables) == {"context", "question"}


def test_neo4j_cypher_qa_service_invokes_query_key() -> None:
    chain = FakeRunnableChain()
    service = Neo4jCypherQAService(chain=chain)

    answer = service.invoke("Bao hiem AIA co quyen loi noi tru khong?")

    assert answer == "Tra loi tu graph"
    assert chain.inputs == [{"query": "Bao hiem AIA co quyen loi noi tru khong?"}]
