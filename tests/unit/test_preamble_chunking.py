from src.services.chunking.document_chunker import DocumentChunker

def test_document_chunker_captures_pre_heading_preamble() -> None:
    markdown_text = """AIA logo featuring a stylized mountain.

SỐNG KHỎE HƠN, LÂU HƠN

## Quyen loi nam vien

Chi tra chi phi nam vien.
"""
    chunker = DocumentChunker(child_chunk_chars=200, child_chunk_overlap=20)
    metadata = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "file_name": "health.md",
    }

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=metadata)

    # We expect at least 2 parent sections: "Introduction" (or similar) and "Quyen loi nam vien"
    headings = [section.heading for section in document_chunks.parent_sections]
    assert "AIA Health Policy" in headings or "Introduction" in headings or any("AIA logo" in section.text for section in document_chunks.parent_sections)
    
    # Check if the preamble text is actually in any chunk
    all_chunk_text = " ".join([chunk.text for chunk in document_chunks.child_chunks])
    assert "SỐNG KHỎE HƠN" in all_chunk_text
    assert "AIA logo" in all_chunk_text
