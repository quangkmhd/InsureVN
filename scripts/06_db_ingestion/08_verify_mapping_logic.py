import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Mocking parts of the indexing script
def mock_lookup(document_path, metadata, mapping_data):
    document_metadata = {**metadata, "file_name": document_path.name}
    
    if mapping_data and "source_table_id" not in document_metadata:
        md_dir = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns"
        try:
            rel_path = str(document_path.relative_to(md_dir))
            if rel_path in mapping_data:
                tables = mapping_data[rel_path].get("tables", [])
                if tables:
                    document_metadata["source_table_id"] = tables[0]["source_table_id"]
                    print(f"DEBUG: Mapped {document_path.name} to {document_metadata['source_table_id']}")
        except ValueError:
            print(f"DEBUG: Path {document_path} not in {md_dir}")
            
    return document_metadata

def verify():
    mapping_path = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns" / "table_mapping.json"
    if not mapping_path.exists():
        print("Mapping file not found!")
        return
        
    mapping_data = json.loads(mapping_path.read_text())
    
    # Test AIA document
    aia_path = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns" / "aia.com.vn" / "021025-Quy-tac-va-dieu-khoan-Bao-hiem-Suc-khoe-Bung-Gia-Luc" / "021025-Quy-tac-va-dieu-khoan-Bao-hiem-Suc-khoe-Bung-Gia-Luc.md"
    
    metadata = {"company_code": "AIA"}
    result = mock_lookup(aia_path, metadata, mapping_data)
    
    if "source_table_id" in result:
        print(f"SUCCESS: Found source_table_id: {result['source_table_id']}")
    else:
        print("FAILURE: source_table_id not found")

if __name__ == "__main__":
    verify()
