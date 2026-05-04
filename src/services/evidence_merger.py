import hashlib
from typing import List, Dict, Any, Set
from pydantic import BaseModel
from src.models.evidence import Evidence

class MergedEvidencePacket(BaseModel):
    evidences: List[Evidence]
    conflicts: List[str]

class EvidenceMerger:
    @staticmethod
    def merge(evidence_items: List[Evidence]) -> MergedEvidencePacket:
        unique_evidences: Dict[str, Evidence] = {}
        conflicts: List[str] = []
        source_contents: Dict[str, Set[str]] = {}
        
        for ev in evidence_items:
            content_hash = hashlib.md5(ev.content.encode('utf-8')).hexdigest()
            dedupe_key = f"{ev.source_type}_{ev.source_id}_{content_hash}"
            
            # Simple conflict detection based on different content for the same source_id
            if ev.source_id not in source_contents:
                source_contents[ev.source_id] = set()
            
            if ev.content not in source_contents[ev.source_id] and len(source_contents[ev.source_id]) > 0:
                conflicts.append(f"Conflict detected for source_id: {ev.source_id}")
            
            source_contents[ev.source_id].add(ev.content)
            
            if dedupe_key not in unique_evidences:
                unique_evidences[dedupe_key] = ev
                
        return MergedEvidencePacket(
            evidences=list(unique_evidences.values()),
            conflicts=conflicts
        )
