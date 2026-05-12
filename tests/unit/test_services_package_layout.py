from src.services.chunking.document_chunker import DocumentChunker
from src.services.document_retrieval.qdrant_retriever import QdrantRetriever
from src.services.evidence.evidence_merger import EvidenceMerger


def test_services_package_layout_imports() -> None:
    assert DocumentChunker is not None
    assert EvidenceMerger is not None
    assert QdrantRetriever is not None


def test_service_packages_keep_lazy_public_exports() -> None:
    from src.services.document_retrieval import QdrantRetriever as ExportedRetriever
    from src.services.evidence import EvidenceMerger as ExportedMerger

    assert ExportedMerger is EvidenceMerger
    assert ExportedRetriever is QdrantRetriever
