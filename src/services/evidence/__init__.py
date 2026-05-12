"""Evidence normalization, citation, and reranking services.

Import concrete services from their submodules to keep package initialization
lightweight and independent from document retrieval.
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CitationFormatter": "src.services.evidence.citation_formatter",
    "EvidenceMerger": "src.services.evidence.evidence_merger",
    "EvidenceReranker": "src.services.evidence.evidence_merger",
    "MergedEvidencePacket": "src.services.evidence.evidence_merger",
    "QdrantEvidenceMapper": "src.services.evidence.qdrant_evidence",
    "SqliteEvidenceMapper": "src.services.evidence.sqlite_evidence",
    "SqliteProfileMapper": "src.services.evidence.sqlite_evidence",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Lazily expose legacy package-level service exports."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
