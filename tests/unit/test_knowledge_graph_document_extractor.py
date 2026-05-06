from langchain_core.documents import Document
from langchain_neo4j.graphs.graph_document import (
    GraphDocument as LangChainGraphDocument,
)
from langchain_neo4j.graphs.graph_document import Node, Relationship

from src.services.knowledge_graph.llm_graph_document_extractor import (
    DocumentGraphExtractor,
    GraphDocument,
    build_knowledge_graph_extraction_prompt,
)


class FakeTransformer:
    def __init__(self, *, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.calls: list[list[Document]] = []

    def convert_to_graph_documents(
        self,
        documents: list[Document],
        _config=None,
    ) -> list[LangChainGraphDocument]:
        self.calls.append(documents)
        if len(self.calls) <= self.failures_before_success:
            raise RuntimeError("temporary provider error")
        company = Node(
            id="AIA",
            type="InsuranceCompany",
            properties={
                "id": "should-be-dropped",
                "name": "AIA",
                "unknown": "ignored",
            },
        )
        benefit = Node(
            id="Noi tru",
            type="Benefit",
            properties={"description": "Chi phi nam vien"},
        )
        relationship = Relationship(
            source=company,
            target=benefit,
            type="HAS_BENEFIT",
            properties={"unknown": "ignored"},
        )
        return [
            LangChainGraphDocument(
                nodes=[company, benefit],
                relationships=[relationship],
                source=documents[0],
            )
        ]


def _source_document() -> GraphDocument:
    return GraphDocument(
        document_id="aia_health_2026",
        document_name="AIA Health 2026",
        company_code="AIA",
        source_path="aia/policy.md",
        text="## Quyen loi\n\nNoi dung toan van.",
    )


def test_extractor_builds_langchain_documents_from_matching_chunks() -> None:
    transformer = FakeTransformer()
    extractor = DocumentGraphExtractor(transformer=transformer)
    chunks = [
        {
            "document_id": "other",
            "text": "Bo qua.",
        },
        {
            "document_id": "aia_health_2026",
            "chunk_id": "chunk-0",
            "chunk_index": 0,
            "text": "AIA chi tra chi phi noi tru.",
            "source_path": "aia/policy.md",
            "ingestion_version": "test-v1",
        },
    ]

    graph_documents = extractor.extract(_source_document(), chunks)

    assert len(graph_documents) == 1
    assert len(transformer.calls) == 1
    source = transformer.calls[0][0]
    assert source.page_content == "AIA chi tra chi phi noi tru."
    assert source.metadata["id"] == "aia_health_2026:chunk-0"
    assert source.metadata["document_id"] == "aia_health_2026"
    assert source.metadata["source_chunk_id"] == "chunk-0"


def test_extractor_enriches_and_constrains_extracted_properties() -> None:
    graph_documents = DocumentGraphExtractor(transformer=FakeTransformer()).extract(
        _source_document(),
        [
            {
                "document_id": "aia_health_2026",
                "chunk_id": "chunk-0",
                "text": "Noi dung.",
            }
        ],
    )

    graph_document = graph_documents[0]
    company = next(
        node for node in graph_document.nodes if node.type == "InsuranceCompany"
    )
    relationship = graph_document.relationships[0]

    assert company.properties["name"] == "AIA"
    assert company.properties["source_document_id"] == "aia_health_2026"
    assert company.properties["source_chunk_id"] == "chunk-0"
    assert company.properties["source_path"] == "aia/policy.md"
    assert company.properties["company_code"] == "AIA"
    assert company.properties["extraction_method"] == "langchain_llm_graph_transformer"
    assert "id" not in company.properties
    assert "unknown" not in company.properties
    assert relationship.properties["source_document_id"] == "aia_health_2026"
    assert relationship.properties["source_chunk_id"] == "chunk-0"
    assert relationship.properties["confidence"] == 0.8
    assert "unknown" not in relationship.properties


def test_extractor_retries_failed_chunk_conversions() -> None:
    transformer = FakeTransformer(failures_before_success=1)
    extractor = DocumentGraphExtractor(transformer=transformer, max_retries=2)

    graph_documents = extractor.extract(
        _source_document(),
        [
            {
                "document_id": "aia_health_2026",
                "chunk_id": "chunk-0",
                "text": "Noi dung.",
            }
        ],
    )

    assert len(graph_documents) == 1
    assert len(transformer.calls) == 2


def test_extractor_uses_full_document_when_chunks_are_absent() -> None:
    transformer = FakeTransformer()
    extractor = DocumentGraphExtractor(transformer=transformer)

    graph_documents = extractor.extract(_source_document(), chunks=[])

    assert len(graph_documents) == 1
    source = transformer.calls[0][0]
    assert source.page_content == "## Quyen loi\n\nNoi dung toan van."
    assert source.metadata["id"] == "aia_health_2026"
    assert source.metadata["source_chunk_id"] is None


def test_extraction_prompt_inlines_schema_without_double_brace_placeholders() -> None:
    prompt = build_knowledge_graph_extraction_prompt()

    rendered = prompt.format(input="Noi dung mau")

    assert prompt.input_variables == ["input"]
    assert "InsurancePolicy" in rendered
    assert "HAS_BENEFIT" in rendered
    assert "{{allowed_nodes}}" not in rendered
    assert "{{allowed_relationships}}" not in rendered
    assert "{input}" not in rendered
