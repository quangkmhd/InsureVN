from typing import Any, Dict
from src.models.evidence import Evidence, SourceType

class StructuredEvidenceAdapter:
    @staticmethod
    def from_mcp_result(tool_name: str, row: Dict[str, Any]) -> Evidence:
        source_id = row.get("source_table_id", row.get("id", "unknown"))
        
        # Build content excluding metadata fields
        metadata_keys = {"source_table_id", "document_id", "source_file_path", "company_code", "document_name"}
        content_parts = [f"{k}: {v}" for k, v in row.items() if k not in metadata_keys]
        content = ", ".join(content_parts)
        
        metadata = {k: v for k, v in row.items() if k in metadata_keys}
        metadata["tool_name"] = tool_name
        
        return Evidence(
            source_type=SourceType.SQLITE_ROW,
            source_id=str(source_id),
            content=content,
            metadata=metadata,
            confidence=1.0,
            retrieved_by="DatabaseAgent"
        )

class ProfileEvidenceAdapter:
    @staticmethod
    def from_profile_row(row: Dict[str, Any]) -> Evidence:
        source_id = row.get("user_id", "unknown")
        
        content_parts = [f"{k}: {v}" for k, v in row.items()]
        content = ", ".join(content_parts)
        
        return Evidence(
            source_type=SourceType.SQLITE_ROW,
            source_id=str(source_id),
            content=content,
            confidence=1.0,
            retrieved_by="ProfileAdapter"
        )
