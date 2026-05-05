import json
import sqlite3
import sys
from pathlib import Path

# Thêm PROJECT_ROOT vào sys.path để import được src
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.core.config import settings
from src.core.database import get_db_connection

def generate_mapping():
    """
    Script tạo file mapping giữa các file Markdown và các source_table_id trong SQLite.
    Giúp xác định metadata 'source_table_id' khi thực hiện indexing vào Qdrant.
    """
    markdown_dir = PROJECT_ROOT / "data" / "health_insurance" / "health_insurance_markdowns"
    output_file = markdown_dir / "table_mapping.json"
    
    mapping = {}
    
    # Kết nối database
    try:
        with get_db_connection(read_only=True) as conn:
            cursor = conn.cursor()
            
            # Lấy tất cả file markdown
            md_files = list(markdown_dir.glob("**/*.md"))
            print(f"Found {len(md_files)} markdown documents.")
            
            for md_path in md_files:
                # Trích xuất folder name (document identifier)
                # Ví dụ: aia.com.vn/021025-Quy-tac-va-dieu-khoan-Bao-hiem-Suc-khoe-Bung-Gia-Luc/
                doc_folder = md_path.parent.name
                company_folder = md_path.parent.parent.name
                relative_doc_path = f"{company_folder}/{doc_folder}"
                
                # Truy vấn source_tables cho document này
                # Tìm tất cả các bảng (JSON files) thuộc document folder này
                cursor.execute(
                    "SELECT id, file_path, table_type, page_number FROM source_tables WHERE file_path LIKE ?",
                    (f"%{relative_doc_path}%",)
                )
                rows = cursor.fetchall()
                
                if not rows:
                    print(f"  [!] No source tables found for: {relative_doc_path}")
                    continue
                
                # Lưu thông tin vào mapping
                mapping[str(md_path.relative_to(markdown_dir))] = {
                    "document_path": relative_doc_path,
                    "tables": [
                        {
                            "source_table_id": row["id"],
                            "file_name": Path(row["file_path"]).name,
                            "table_type": row["table_type"],
                            "page_number": row["page_number"]
                        }
                        for row in rows
                    ]
                }
                print(f"  [+] Mapped {len(rows)} tables for: {md_path.name}")
                
        # Lưu file mapping JSON
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ Mapping saved successfully to: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Error generating mapping: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_mapping()
