import pytest
from src.services.evidence_merger import EvidenceMerger
from src.models.evidence import Evidence, SourceType

def test_evidence_merger_deduplication():
    ev1 = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="1",
        content="Same content",
        confidence=1.0,
        retrieved_by="AgentA"
    )
    ev2 = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="1",
        content="Same content",
        confidence=1.0,
        retrieved_by="AgentB"
    )
    ev3 = Evidence(
        source_type=SourceType.QDRANT_DOC,
        source_id="chunk_2",
        content="Different content",
        confidence=0.8,
        retrieved_by="AgentC"
    )
    
    merged = EvidenceMerger.merge([ev1, ev2, ev3])
    
    assert len(merged.evidences) == 2
    assert merged.evidences[0].source_id == "1"

def test_evidence_merger_conflict_detection():
    # Same source, different content
    ev1 = Evidence(
        source_type=SourceType.SQLITE_ROW,
        source_id="price_1",
        content="Premium: 5M",
        confidence=1.0,
        retrieved_by="AgentA"
    )
    ev2 = Evidence(
        source_type=SourceType.QDRANT_DOC,
        source_id="price_1",
        content="Premium: 6M",
        confidence=0.8,
        retrieved_by="AgentB"
    )
    
    merged = EvidenceMerger.merge([ev1, ev2])
    
    # Ideally we flag a conflict or keep both depending on rules, 
    # but the blueprint says: "detect simple conflicts"
    assert len(merged.conflicts) > 0
    assert "price_1" in merged.conflicts[0]
