import json
import os
import argparse
from collections import defaultdict

def analyze_keys(directory_path, output_file=None):
    """
    Phân tích các key trong structured_data của các file JSON trong thư mục.
    """
    if not os.path.exists(directory_path):
        print(f"Error: Thư mục '{directory_path}' không tồn tại.")
        return

    key_to_files = defaultdict(list)
    file_to_keys = {}
    
    json_files = []
    for root, _, files in os.walk(directory_path):
        for f in files:
            if f.endswith('.json'):
                json_files.append(os.path.join(root, f))

    print(f"--- Đang phân tích {len(json_files)} file JSON... ---")

    for file_path in json_files:
        rel_path = os.path.relpath(file_path, directory_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                structured_data = data.get('structured_data', {})
                
                keys = set()
                if isinstance(structured_data, dict):
                    keys = set(structured_data.keys())
                elif isinstance(structured_data, list):
                    for item in structured_data:
                        if isinstance(item, dict):
                            keys.update(item.keys())
                
                if keys:
                    file_to_keys[rel_path] = sorted(list(keys))
                    for key in keys:
                        key_to_files[key].append(rel_path)
                else:
                    file_to_keys[rel_path] = []
        except Exception as e:
            print(f"Lỗi khi đọc file {rel_path}: {e}")

    # Thống kê
    total_unique_keys = len(key_to_files)
    overlapping_keys = {k: v for k, v in key_to_files.items() if len(v) > 1}
    
    # Chuẩn bị nội dung Markdown
    md = f"# 📋 Báo cáo Phân tích Key JSON\n\n"
    md += "## 📊 Tóm tắt Tổng quan\n"
    md += f"- **Tổng số file phân tích:** {len(json_files)}\n"
    md += f"- **Tổng số key duy nhất:** {total_unique_keys}\n"
    md += f"- **Số key bị trùng lặp:** {len(overlapping_keys)}\n\n"

    md += "## 🔍 Top Key trùng lặp nhiều nhất\n"
    md += "| Key | Số lượng file | Ví dụ file |\n| :--- | :--- | :--- |\n"
    sorted_overlaps = sorted(overlapping_keys.items(), key=lambda x: len(x[1]), reverse=True)
    for key, files in sorted_overlaps[:20]:
        files_preview = ", ".join(files[:3]) + ("..." if len(files) > 3 else "")
        md += f"| `{key}` | {len(files)} | {files_preview} |\n"
    
    md += "\n## 🤝 Các nhóm file trùng khớp cấu trúc 100%\n"
    schema_to_files = defaultdict(list)
    for filename, keys in file_to_keys.items():
        if keys:
            schema_tuple = tuple(keys)
            schema_to_files[schema_tuple].append(filename)
    
    group_count = 0
    for schema, files in schema_to_files.items():
        if len(files) > 1:
            group_count += 1
            md += f"### Nhóm {group_count} ({len(files)} file)\n"
            md += f"- **Keys:** `{', '.join(schema)}`\n"
            md += f"- **Files:** {', '.join(files)}\n\n"

    md += "## 📂 Chi tiết từng File\n"
    md += "| Tên File | Danh sách Key |\n| :--- | :--- |\n"
    for rel_path in sorted(file_to_keys.keys()):
        keys_str = ", ".join(file_to_keys[rel_path])
        md += f"| `{rel_path}` | {keys_str} |\n"

    # In ra console
    print("\n" + "="*50)
    print("📊 PHÂN TÍCH HOÀN TẤT")
    print(f"Tổng số file: {len(json_files)} | Key duy nhất: {total_unique_keys}")
    print("="*50)

    # Lưu file nếu có yêu cầu
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"\n✅ Đã lưu báo cáo tại: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phân tích key trong file JSON.")
    parser.add_argument("--dir", default="/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_extracted_good_content", 
                        help="Đường dẫn đến thư mục chứa file JSON")
    parser.add_argument("--output", "-o", default="docs/json_data_schema_analysis_report.md", 
                        help="Tên file Markdown đầu ra")
    
    args = parser.parse_args()
    analyze_keys(args.dir, args.output)
