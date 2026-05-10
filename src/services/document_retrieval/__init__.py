"""Document retrieval services backed by Qdrant and reranking adapters."""

from src.services.document_retrieval.filtered_hybrid_rerank_retriever import (
    FilteredHybridRerankRetriever,
    HardFilterRequiredError,
    build_default_filtered_hybrid_rerank_retriever,
)
from src.services.document_retrieval.huggingface_rerank_cross_encoder import (
    HuggingFaceRerankCrossEncoder,
)
from src.services.document_retrieval.qdrant_collection_manager import (
    QdrantCollectionConfig,
    QdrantCollectionManager,
)
from src.services.document_retrieval.qdrant_retriever import (
    QdrantRetriever,
    build_dense_embedding_provider,
)
from src.services.document_retrieval.qdrant_vector_store import (
    QdrantVectorStoreFactory,
)
from src.services.document_retrieval.qwen_embedding_provider import (
    Qwen3EmbeddingProvider,
)
from src.services.document_retrieval.rerank_cross_encoder import (
    build_default_rerank_cross_encoder,
    build_rerank_cross_encoder,
)
from src.services.document_retrieval.retrieval_readiness import (
    ProductionReadinessError,
    RetrievalReadinessReport,
)

__all__ = [
    "HuggingFaceRerankCrossEncoder",
    "FilteredHybridRerankRetriever",
    "HardFilterRequiredError",
    "ProductionReadinessError",
    "QdrantCollectionConfig",
    "QdrantCollectionManager",
    "QdrantRetriever",
    "QdrantVectorStoreFactory",
    "Qwen3EmbeddingProvider",
    "RetrievalReadinessReport",
    "build_default_rerank_cross_encoder",
    "build_default_filtered_hybrid_rerank_retriever",
    "build_dense_embedding_provider",
    "build_rerank_cross_encoder",
]
