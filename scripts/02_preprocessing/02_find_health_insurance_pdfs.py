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

def is_health_insurance_by_rules(filename: str) -> bool | None:
    """Kiểm tra nhanh dựa trên từ khóa trong tên file."""
    name_lower = filename.lower()
    
    # Từ khóa chắc chắn là bảo hiểm sức khỏe
    health_keywords = [
        r'suc[-_]?khoe', 
        r'health', 
        r'y[-_]?te', 
        r'medical',
        r'bhsk',
        r'cham[-_]?soc[-_]?suc[-_]?khoe',
        r'bao[-_]?hiem[-_]?suc[-_]?khoe'
    ]
    
    for kw in health_keywords:
        if re.search(kw, name_lower):
            return True
            
    return None # Không khớp rule nào thì trả về None để dùng LLM

def is_health_insurance_with_ollama(filename: str) -> bool:
    """Sử dụng LLM để kiểm tra xem file có liên quan tới bảo hiểm sức khỏe hay không."""
    # Thử phân loại bằng từ khóa trước để tiết kiệm thời gian
    rule_result = is_health_insurance_by_rules(filename)
    if rule_result is not None:
        return rule_result

    # Chỉ gọi LLM nếu rule-based thất bại
    prompt = f"""You are an expert file classifier for a Vietnamese insurance system.
Determine if the given insurance document filename is related to HEALTH INSURANCE (bảo hiểm sức khỏe, chăm sóc sức khỏe, y tế, medical).
Examples of health insurance files:
- "Quy tắc bảo hiểm sức khỏe.pdf"
- "Bieu phi Bao hiem suc khoe toan dien.pdf"
- "health-care-brochure.pdf"
- "BHSK_Giay-yeu-cau.pdf"

Respond ONLY with "True" if it is related to health insurance, or "False" if it is not. Do not output any other text, prefix, or explanation.

Filename: {filename}
Is Health Insurance:"""

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
        
        if 'true' in response_text:
            return True
        elif 'false' in response_text:
            return False
            
        print(f"\n[Warning] Unexpected output from LLM: '{response_text}'")
        return False
        
    except Exception as e:
        print(f"\n[Error] Failed to call Ollama for {filename}: {e}")
        return False

def main():
    raw_dir = Path("data/raw")
    target_dir = Path("data/health_insurance_pdfs")
    
    if not raw_dir.exists():
        print(f"Thư mục nguồn {raw_dir} không tồn tại.")
        return

    # Tạo thư mục đích chứa các file bảo hiểm sức khỏe
    target_dir.mkdir(parents=True, exist_ok=True)

    # Quét qua các thư mục công ty
    for company_dir in raw_dir.iterdir():
        if not company_dir.is_dir():
            continue
            
        company_name = company_dir.name
        print(f"\n{'='*50}\nĐang quét công ty: {company_name}\n{'='*50}")
        
        target_company_dir = target_dir / company_name
        
        # Quét tất cả các file trong thư mục công ty
        for file_path in company_dir.rglob('*'):
            if not file_path.is_file():
                continue
                
            filename = file_path.name
            
            # Kiểm tra xem file đã tồn tại trong thư mục đích chưa
            target_path = target_company_dir / filename
            if target_path.exists():
                print(f"Bỏ qua (đã xử lý): {filename[:50]}...")
                continue
                
            print(f"Kiểm tra: {filename[:50]}... ", end="", flush=True)
            
            is_health = is_health_insurance_with_ollama(filename)
            print(f"-> {'Có' if is_health else 'Không'}")
            
            if is_health:
                # Nếu là bảo hiểm sức khỏe thì copy sang thư mục đích
                target_company_dir.mkdir(parents=True, exist_ok=True)
                if not target_path.exists():
                    shutil.copy2(file_path, target_path)

if __name__ == "__main__":
    main()
