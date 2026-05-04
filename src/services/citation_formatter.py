from src.models.evidence import Evidence, Citation
from src.core.logger import get_logger

logger = get_logger("citation_formatter")

class CitationFormatter:
    @staticmethod
    def format(evidence: Evidence) -> Citation:
        CitationFormatter.validate_required_fields(evidence)
        
        citation = Citation(
            company_code=evidence.metadata["company_code"],
            document_id=evidence.metadata.get("document_id"),
            document_name=evidence.metadata.get("document_name"),
            source_file_path=evidence.metadata.get("source_file_path"),
            source_table_id=evidence.metadata.get("source_table_id"),
            page=evidence.metadata.get("page")
        )
        
        logger.info(
            f"Formatted citation for {citation.company_code}",
            extra={
                "component": "citation_formatter",
                "source_type": evidence.source_type.value,
                "source_id": evidence.source_id,
                "retrieved_by": evidence.retrieved_by,
                "company_code": citation.company_code
            }
        )
        
        return citation

    @staticmethod
    def validate_required_fields(evidence: Evidence) -> None:
        required_keys = ["company_code"]
        for key in required_keys:
            if key not in evidence.metadata:
                logger.error(
                    f"Validation failed: Missing {key} in evidence metadata",
                    extra={
                        "component": "citation_formatter",
                        "source_id": evidence.source_id,
                        "source_type": evidence.source_type.value
                    }
                )
                raise ValueError(f"Missing required citation field: {key}")
