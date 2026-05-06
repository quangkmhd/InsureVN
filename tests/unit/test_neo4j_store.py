from src.services.knowledge_graph.neo4j_store import Neo4jKnowledgeGraphStore


class FakeNeo4jGraph:
    def __init__(self) -> None:
        self.queries = []
        self.graph_documents = []

    def query(self, query: str, params: dict | None = None):
        self.queries.append((query, params or {}))
        return []

    def add_graph_documents(self, graph_documents, **kwargs) -> None:
        self.graph_documents.extend(graph_documents)
        self.add_kwargs = kwargs


def test_neo4j_store_creates_v1_uniqueness_constraints() -> None:
    graph = FakeNeo4jGraph()
    store = Neo4jKnowledgeGraphStore(graph=graph)

    store.ensure_schema()

    queries = [query for query, _ in graph.queries]
    assert any("InsuranceCompany_id_unique" in query for query in queries)
    assert any("InsuranceDocument_id_unique" in query for query in queries)
    assert any("InsurancePlan_id_unique" in query for query in queries)
    assert not any(
        query.strip().startswith("CREATE CONSTRAINT Plan_id_unique ")
        for query in queries
    )
    assert all("CREATE CONSTRAINT" in query for query in queries)
    assert all("IF NOT EXISTS" in query for query in queries)


def test_neo4j_store_imports_graph_documents_with_source_linking() -> None:
    graph = FakeNeo4jGraph()
    store = Neo4jKnowledgeGraphStore(graph=graph)
    graph_documents = [object()]

    store.import_graph_documents(graph_documents)

    assert graph.graph_documents == graph_documents
    assert graph.add_kwargs == {
        "include_source": True,
        "baseEntityLabel": True,
    }
