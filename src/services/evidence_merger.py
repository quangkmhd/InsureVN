import hashlib

from pydantic import BaseModel

from src.core.logger import get_logger
from src.models.evidence import Evidence
from src.services.observability import service_observe

logger = get_logger("evidence_merger")


class MergedEvidencePacket(BaseModel):
    evidences: list[Evidence]
    conflicts: list[str]


class EvidenceMerger:
    @staticmethod
    @service_observe(name="service.evidence_merger.merge", component="evidence_merger")
    def merge(evidence_items: list[Evidence]) -> MergedEvidencePacket:
        unique_evidences: dict[str, Evidence] = {}
        conflicts: list[str] = []
        source_contents: dict[str, set[str]] = {}

        for ev in evidence_items:
            content_hash = hashlib.md5(ev.content.encode("utf-8")).hexdigest()
            dedupe_key = f"{ev.source_type}_{ev.source_id}_{content_hash}"

            # Detect different content for the same source_id.
            if ev.source_id not in source_contents:
                source_contents[ev.source_id] = set()

            if (
                ev.content not in source_contents[ev.source_id]
                and len(source_contents[ev.source_id]) > 0
            ):
                existing_contents = list(source_contents[ev.source_id])
                conflicts.append(
                    f"Conflict detected for source_id '{ev.source_id}'. "
                    f"New content snippet: '{ev.content[:50]}...'. "
                    f"Existing content snippet: '{existing_contents[0][:50]}...'."
                )

            source_contents[ev.source_id].add(ev.content)

            if dedupe_key not in unique_evidences:
                unique_evidences[dedupe_key] = ev

        logger.info(
            "Merged evidence",
            extra={
                "component": "evidence_merger",
                "total_evidence_count": len(evidence_items),
                "conflict_count": len(conflicts),
                "merged_evidence_count": len(unique_evidences),
            },
        )

        return MergedEvidencePacket(
            evidences=list(unique_evidences.values()), conflicts=conflicts
        )
