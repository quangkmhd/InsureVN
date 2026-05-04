from src.models.evidence import Evidence, Citation

class CitationFormatter:
    @staticmethod
    def format(evidence: Evidence) -> Citation:
        CitationFormatter.validate_required_fields(evidence)
        return Citation(
            company_code=evidence.metadata["company_code"],
            document_id=evidence.metadata.get("document_id", "unknown"),
            document_name=evidence.metadata.get("document_name", "unknown"),
            source_file_path=evidence.metadata.get("source_file_path", "unknown"),
            source_table_id=evidence.metadata.get("source_table_id", "unknown"),
            page=evidence.metadata.get("page")
        )

    @staticmethod
    def validate_required_fields(evidence: Evidence) -> None:
        required_keys = ["company_code"]
        for key in required_keys:
            if key not in evidence.metadata:
                raise ValueError(f"Missing required citation field: {key}")
