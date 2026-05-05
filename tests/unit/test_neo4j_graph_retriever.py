from src.services.knowledge_graph.neo4j_graph_retriever import Neo4jGraphRetriever


class FakeNeo4jGraph:
    def __init__(self) -> None:
        self.queries = []

    def query(self, query: str, params: dict):
        self.queries.append((query, params))
        return [
            {
                "source_id": "plan:AIA:gold",
                "target_id": "exclusion:AIA:gold:pre_existing_condition",
                "relationship_type": "EXCLUDES",
                "document_id": "aia_health_2026",
                "source_path": "data/processed/aia_health_2026.md",
                "confidence": 0.9,
            }
        ]


def test_neo4j_graph_retriever_uses_read_only_parameterized_template() -> None:
    graph = FakeNeo4jGraph()
    retriever = Neo4jGraphRetriever(graph=graph)

    paths = retriever.retrieve(
        start_entities=["plan:AIA:gold"],
        relation_types=["EXCLUDES"],
        max_hops=1,
    )

    query, params = graph.queries[0]
    assert "MATCH path =" in query
    assert "DELETE" not in query
    assert "SET " not in query
    assert params == {
        "start_entities": ["plan:AIA:gold"],
        "relation_types": ["EXCLUDES"],
        "max_hops": 1,
    }
    assert paths[0].node_ids == [
        "plan:AIA:gold",
        "exclusion:AIA:gold:pre_existing_condition",
    ]
    assert paths[0].edges[0].relationship_type == "EXCLUDES"
