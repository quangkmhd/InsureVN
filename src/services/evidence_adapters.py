from typing import Any

from src.core.logger import get_logger
from src.models.evidence import Evidence, SourceType
from src.services.observability import service_observe

logger = get_logger("evidence_adapters")


class StructuredEvidenceAdapter:
    @staticmethod
    @service_observe(
        name="service.evidence_adapters.from_mcp_result",
        component="structured_evidence_adapter",
    )
    def from_mcp_result(tool_name: str, row: dict[str, Any]) -> Evidence:
        source_id = row.get("source_table_id", row.get("id", "unknown"))

        # Build content excluding metadata fields
        metadata_keys = {
            "source_table_id",
            "document_id",
            "source_file_path",
            "company_code",
            "document_name",
        }
        content_parts = [f"{k}: {v}" for k, v in row.items() if k not in metadata_keys]
        content = ", ".join(content_parts)

        metadata = {k: v for k, v in row.items() if k in metadata_keys}
        metadata["tool_name"] = tool_name

        logger.info(
            f"Converted MCP result to Evidence using {tool_name}",
            extra={
                "component": "structured_evidence_adapter",
                "source_type": SourceType.SQLITE_ROW.value,
                "source_id": str(source_id),
                "retrieved_by": "DatabaseAgent",
            },
        )

        return Evidence(
            source_type=SourceType.SQLITE_ROW,
            source_id=str(source_id),
            content=content,
            metadata=metadata,
            confidence=1.0,
            retrieved_by="DatabaseAgent",
        )


class ProfileEvidenceAdapter:
    @staticmethod
    @service_observe(
        name="service.evidence_adapters.from_profile_row",
        component="profile_evidence_adapter",
    )
    def from_profile_row(row: dict[str, Any]) -> Evidence:
        source_id = row.get("user_id", "unknown")

        content_parts = [f"{k}: {v}" for k, v in row.items()]
        content = ", ".join(content_parts)

        logger.info(
            "Converted Profile row to Evidence",
            extra={
                "component": "profile_evidence_adapter",
                "source_type": SourceType.SQLITE_ROW.value,
                "source_id": str(source_id),
                "retrieved_by": "ProfileAdapter",
            },
        )

        return Evidence(
            source_type=SourceType.SQLITE_ROW,
            source_id=str(source_id),
            content=content,
            confidence=1.0,
            retrieved_by="ProfileAdapter",
        )
