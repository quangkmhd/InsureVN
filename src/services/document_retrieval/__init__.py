"""Document retrieval services backed by Qdrant and reranking adapters.

Import concrete services from their submodules to avoid package-level import
cycles between retrieval and evidence services.
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "FilteredHybridRerankRetriever": (
        "src.services.document_retrieval.filtered_hybrid_rerank_retriever"
    ),
    "HardFilterRequiredError": (
        "src.services.document_retrieval.filtered_hybrid_rerank_retriever"
    ),
    "HuggingFaceRerankCrossEncoder": (
        "src.services.document_retrieval.huggingface_rerank_cross_encoder"
    ),
    "ProductionReadinessError": ("src.services.document_retrieval.retrieval_readiness"),
    "QdrantCollectionConfig": (
        "src.services.document_retrieval.qdrant_collection_manager"
    ),
    "QdrantCollectionManager": (
        "src.services.document_retrieval.qdrant_collection_manager"
    ),
    "QdrantRetriever": "src.services.document_retrieval.qdrant_retriever",
    "QdrantVectorStoreFactory": ("src.services.document_retrieval.qdrant_vector_store"),
    "Qwen3EmbeddingProvider": (
        "src.services.document_retrieval.qwen_embedding_provider"
    ),
    "RetrievalReadinessReport": ("src.services.document_retrieval.retrieval_readiness"),
    "build_default_filtered_hybrid_rerank_retriever": (
        "src.services.document_retrieval.filtered_hybrid_rerank_retriever"
    ),
    "build_default_rerank_cross_encoder": (
        "src.services.document_retrieval.rerank_cross_encoder"
    ),
    "build_dense_embedding_provider": (
        "src.services.document_retrieval.qdrant_retriever"
    ),
    "build_rerank_cross_encoder": (
        "src.services.document_retrieval.rerank_cross_encoder"
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Lazily expose legacy package-level retrieval exports."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
