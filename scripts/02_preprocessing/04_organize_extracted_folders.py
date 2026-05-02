import os
import shutil
import re
from pathlib import Path
from ollama import Client

# Config from 02_find_health_insurance_pdfs.py
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = "gemma4:31b-cloud"
API_KEY = "c88b8eaf85224829b730a63f4ac0ce1e.hD2qEw4Owc-zwnI5E0RJXqaM"

# Khởi tạo client của thư viện ollama
client = Client(
    host=OLLAMA_API_URL,
    headers={'Authorization': f'Bearer {API_KEY}'}
)

# Categories mapping
CATEGORIES = {
    "terms_and_rules": "Quy tắc và Điều khoản",
    "premium_tables": "Biểu phí",
    "hospital_lists": "Danh sách bệnh viện",
    "others": "Tài liệu khác (Tóm tắt, Brochure, Tờ khai...)"
}

def classify_folder_by_rules(folder_name: str) -> str | None:
    """Kiểm tra nhanh dựa trên từ khóa trong tên folder."""
    name_lower = folder_name.lower()
    
    # 1. Quy tắc và Điều khoản
    # Thêm các viết tắt phổ biến: qt (Quy Tắc), dk (Điều Khoản), tc (Terms & Conditions)
    # Dùng regex linh hoạt hơn để bắt QT_, QTBH, DK_, v.v.
    terms_keywords = [r'quy[-_]?tac', r'dieu[-_]?khoan', r't[-_]?c', r'terms', r'conditions', r'policy', r'\bqt', r'\bdk']
    if any(re.search(kw, name_lower) for kw in terms_keywords):
        # Loại trừ nếu là tóm tắt hoặc brochure
        if not any(re.search(kw, name_lower) for kw in [r'tom[-_]?tat', r'summary', r'gioi[-_]?thieu', r'brochure']):
            return "terms_and_rules"
            
    # 2. Biểu phí
    # Thêm viết tắt bp (Biểu Phí), rate (Tỉ lệ phí)
    premium_keywords = [r'bieu[-_]?phi', r'bang[-_]?phi', r'premium', r'fee', r'rate', r'\bbp']
    if any(re.search(kw, name_lower) for kw in premium_keywords):
        return "premium_tables"
        
    # 3. Danh sách bệnh viện
    # Thêm viết tắt dsbv (Danh Sách Bệnh Viện), network
    hospital_keywords = [r'benh[-_]?vien', r'hospital', r'clinic', r'provider', r'co[-_]?so[-_]?y[-_]?te', r'mang[-_]?luoi', r'network', r'\bdsbv']
    if any(re.search(kw, name_lower) for kw in hospital_keywords):
        return "hospital_lists"
        
    # 4. Others (nếu có từ khóa rõ ràng)
    other_keywords = [r'tom[-_]?tat', r'summary', r'gioi[-_]?thieu', r'brochure', r'thong[-_]?bao', r'press', r'to[-_]?khai', r'form']
    if any(re.search(kw, name_lower) for kw in other_keywords):
        return "others"
        
    return None

def classify_folder_with_ollama(folder_name: str) -> str:
    """Sử dụng LLM để phân loại folder bảo hiểm."""
    # Thử phân loại bằng từ khóa trước
    rule_result = classify_folder_by_rules(folder_name)
    if rule_result is not None:
        return rule_result

    prompt = f"""You are an expert insurance document classifier.
Classify the following folder name into one of these 4 categories:
1. "terms_and_rules": For full terms, conditions, rules of the insurance product.
2. "premium_tables": For premium tables, price lists, fee schedules.
3. "hospital_lists": For lists of hospitals, clinics, direct billing networks.
4. "others": For summaries, brochures, marketing materials, forms, health declarations, press releases.

Respond ONLY with the category key (terms_and_rules, premium_tables, hospital_lists, or others). Do not output any other text.

Folder name: {folder_name}
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
        
        response_text = response.get('response', '').strip().lower()
        
        for key in CATEGORIES.keys():
            if key in response_text:
                return key
                
        return "others"
        
    except Exception as e:
        print(f"\n[Error] Failed to call Ollama for {folder_name}: {e}")
        return "others"

def main():
    source_dir = Path("data/health_insurance/health_insurance_extracted")
    target_root = Path("data/health_insurance/health_insurance_organized")
    
    if not source_dir.exists():
        print(f"Thư mục nguồn {source_dir} không tồn tại.")
        return

    # Quét qua các thư mục công ty (e.g., aia.com.vn)
    for company_dir in source_dir.iterdir():
        if not company_dir.is_dir():
            continue
            
        company_name = company_dir.name
        print(f"\n{'='*60}\nĐang xử lý công ty: {company_name}\n{'='*60}")
        
        # Quét các folder con (mỗi folder là một file PDF đã giải nén)
        for folder in company_dir.iterdir():
            if not folder.is_dir():
                continue
            
            folder_name = folder.name
            print(f"Phân loại: {folder_name[:60]}... ", end="", flush=True)
            
            category = classify_folder_with_ollama(folder_name)
            print(f"-> [{category}]")
            
            # Tạo cấu trúc: organized / category / company / folder_name
            dest_dir = target_root / category / company_name / folder_name
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy folder sang vị trí mới
            if not dest_dir.exists():
                # Sử dụng copytree để copy cả thư mục
                shutil.copytree(folder, dest_dir)
            else:
                print(f"  (Đã tồn tại, bỏ qua)")

if __name__ == "__main__":
    main()
