import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

def get_company_code(path_str):
    if "aia.com.vn" in path_str:
        return "AIA"
    if "pvicare.net" in path_str:
        return "PVI"
    if "pacific_cross" in path_str:
        return "PacificCross"
    if "liberty" in path_str:
        return "Liberty"
    if "baominh" in path_str:
        return "BaoMinh"
    if "pti.com.vn" in path_str:
        return "PTI"
    if "bic.vn" in path_str:
        return "BIC"
    return "UNKNOWN"

def index_all():
    markdown_dir = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns"
    md_files = list(markdown_dir.glob("**/*.md"))
    
    indexer_script = PROJECT_ROOT / "scripts" / "06_db_ingestion" / "04_index_qdrant_documents.py"
    
    print(f"Found {len(md_files)} markdown documents to index.")
    
    for md_path in md_files:
        print(f"\n>>> Indexing: {md_path.name}")
        
        # Tạo metadata tạm thời cho file này
        company_code = get_company_code(str(md_path))
        doc_id = md_path.stem.lower().replace(" ", "_")
        
        metadata = {
            "company_code": company_code,
            "document_id": doc_id,
            "document_type": "policy",
            "document_name": md_path.stem,
            "product_line": "health",
            "plan_code": "general",
            "effective_date": "2024-01-01", # Fallback
            "ingestion_version": "v1.0"
        }
        
        meta_tmp = PROJECT_ROOT / "scripts" / "06_db_ingestion" / "meta_auto_tmp.json"
        meta_tmp.write_text(json.dumps(metadata, ensure_ascii=False))
        
        # Đường dẫn lưu file chunks JSON
        output_chunks_dir = PROJECT_ROOT / "data" / "processed" / "qdrant_chunks"
        output_chunks_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_chunks_dir / f"{md_path.stem}.chunks.json"
        
        # Chạy lệnh index và lưu ra file
        # Ép buộc sử dụng strategy 'recursive' để chạy nhanh
        cmd = [
            sys.executable,
            str(indexer_script),
            "--document", str(md_path),
            "--metadata-json", str(meta_tmp),
            "--output-json", str(output_file)
        ]
        
        import os
        env = os.environ.copy()
        env["RAG_CHUNKING_STRATEGY"] = "recursive"
        
        try:
            result = subprocess.run(cmd, check=True, text=True, capture_output=True, env=env)
            print(f"  [OK] Saved chunks for {md_path.name} to {output_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"  [ERR] Failed to process {md_path.name}: {e.stderr}")

if __name__ == "__main__":
    index_all()
