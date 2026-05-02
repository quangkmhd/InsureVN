import os
import shutil
import re
from pathlib import Path
from ollama import Client

# URL mặc định được dùng cho thư viện ollama, không cần "/api/generate" ở cuối
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = "gemma4:31b-cloud"
API_KEY = "c88b8eaf85224829b730a63f4ac0ce1e.hD2qEw4Owc-zwnI5E0RJXqaM"

# Khởi tạo client của thư viện ollama
client = Client(
    host=OLLAMA_API_URL,
    headers={'Authorization': f'Bearer {API_KEY}'}
)

CATEGORIES = [
    "1_quy_tac_dieu_khoan",
    "2_bieu_phi_he_so",
    "3_bang_minh_hoa",
    "4_tai_lieu_san_pham",
    "5_bao_cao_tai_chinh",
    "6_thong_tin_lai_suat_quy",
    "7_bieu_mau_huong_dan",
    "8_khac"
]

def classify_by_rules(filename: str) -> str:
    """Phân loại nhanh dựa trên từ khóa trong tên file."""
    name_lower = filename.lower()
    
    if re.search(r'quy[-_]?tac|dieu[-_]?khoan|tom[-_]?tat', name_lower):
        return "1_quy_tac_dieu_khoan"
    if re.search(r'bieu[-_]?phi|he[-_]?so|bang[-_]?le[-_]?phi', name_lower):
        return "2_bieu_phi_he_so"
    if re.search(r'bang[-_]?minh[-_]?hoa|minh[-_]?hoa', name_lower):
        return "3_bang_minh_hoa"
    if re.search(r'tai[-_]?lieu[-_]?(san[-_]?pham|gioi[-_]?thieu)|brochure', name_lower):
        return "4_tai_lieu_san_pham"
    if re.search(r'bao[-_]?cao[-_]?(tai[-_]?chinh|thuong[-_]?nien)|sustainability', name_lower):
        return "5_bao_cao_tai_chinh"
    if re.search(r'lai[-_]?suat|lai[-_]?chia', name_lower):
        return "6_thong_tin_lai_suat_quy"
    if re.search(r'bieu[-_]?mau|huong[-_]?dan|tuong[-_]?trinh|thong[-_]?bao|thoi[-_]?gian[-_]?xu[-_]?ly|pos', name_lower):
        return "7_bieu_mau_huong_dan"
        
    return None # Không khớp rule nào thì trả về None để dùng LLM

def classify_filename_with_ollama(filename: str) -> str:
    # Thử phân loại bằng từ khóa trước để tiết kiệm thời gian
    rule_category = classify_by_rules(filename)
    if rule_category:
        return rule_category

    # Chỉ gọi LLM nếu rule-based thất bại
    prompt = f"""You are an expert file classifier for a Vietnamese insurance system.
Classify the given filename into EXACTLY ONE of the following categories:
- 1_quy_tac_dieu_khoan: Quy tắc, điều khoản, tóm tắt điều khoản
- 2_bieu_phi_he_so: Biểu phí, hệ số, bảng lệ phí
- 3_bang_minh_hoa: Bảng minh họa quyền lợi
- 4_tai_lieu_san_pham: Tài liệu giới thiệu, brochure sản phẩm, tài liệu sản phẩm
- 5_bao_cao_tai_chinh: Báo cáo tài chính, báo cáo thường niên
- 6_thong_tin_lai_suat_quy: Lãi suất, lãi chia, báo cáo quỹ
- 7_bieu_mau_huong_dan: Biểu mẫu, bản tường trình, hướng dẫn, thông báo, thời gian xử lý
- 8_khac: Các tài liệu khác không thuộc các nhóm trên (luật, cẩm nang sức khỏe...)

Respond ONLY with the EXACT category name from the list above. Do not output any other text, prefix, or explanation.

Filename: {filename}
Category:"""

    try:
        response = client.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            stream=False,
            options={
                "temperature": 0.0,
                "seed": 42
            }
        )
        
        response_text = response.get('response', '').strip()
        
        # Cố gắng tìm category trong chuỗi trả về để tránh LLM output thêm text thừa
        for cat in CATEGORIES:
            if cat in response_text:
                return cat
                
        # Nếu LLM trả về kết quả không khớp, fallback về nhóm 8
        print(f"\n[Warning] Unexpected output from LLM: '{response_text}'")
        return "8_khac"
        
    except Exception as e:
        print(f"\n[Error] Failed to call Ollama for {filename}: {e}")
        return "8_khac"

def main():
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    
    if not raw_dir.exists():
        print(f"Thư mục nguồn {raw_dir} không tồn tại.")
        return

    # Quét qua các thư mục công ty
    for company_dir in raw_dir.iterdir():
        if not company_dir.is_dir():
            continue
            
        company_name = company_dir.name
        print(f"\n{'='*50}\nĐang xử lý công ty: {company_name}\n{'='*50}")
        
        target_company_dir = processed_dir / company_name
        
        # Quét tất cả các file trong thư mục công ty
        for file_path in company_dir.rglob('*'):
            if not file_path.is_file():
                continue
                
            filename = file_path.name
            
            # Kiểm tra xem file đã tồn tại trong bất kỳ thư mục category nào của công ty này chưa
            already_processed = False
            if target_company_dir.exists():
                # Lặp qua các thư mục category (1_quy_tac..., 2_bieu_phi...)
                for cat_dir in target_company_dir.iterdir():
                    if cat_dir.is_dir() and (cat_dir / filename).exists():
                        already_processed = True
                        break
            
            if already_processed:
                print(f"Bỏ qua (đã xử lý): {filename[:50]}...")
                continue
                
            print(f"Phân loại: {filename[:50]}... ", end="", flush=True)
            
            category = classify_filename_with_ollama(filename)
            print(f"-> {category}")
            
            # Tạo thư mục đích
            target_dir = target_company_dir / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy file (dùng copy thay vì move để giữ nguyên dữ liệu gốc)
            target_path = target_dir / filename
            if not target_path.exists():
                shutil.copy2(file_path, target_path)

if __name__ == "__main__":
    main()