import os
import shutil

SOURCE_DIR = "pacific_cross_all_pdfs"
BASE_DIR = os.path.join(SOURCE_DIR)

CATEGORIES = {
    "1_Danh_sach_Benh_vien": ["Medical-Provider-List", "Danh-sach-benh-vien", "CSYT"],
    "2_Bieu_mau_Don_tu": [
        "Application", "DON-", "GIAY-YEU-CAU", "MAU-DON", "THONG-BAO-TON-THAT", 
        "BANG-KE-KHAI", "TO-KHAI", "TUONG-TRINH", "BANG-BAO-CAO-SUC-KHOE", 
        "BANG-CAU-HOI", "KE-HOACH-DIEU-TRI", "Questionnaire", "Registration", "TK1_TS",
        "Bao-Cao-Cua-Bac-Si", "BAO-CAO-KIEM-TRA", "BAO-CAO-TIEN-TRINH", "THONG-TIN-NGUOI-THU-HUONG"
    ],
    "3_Dieu_khoan_Quy_tac": [
        "Policy-Wording", "DIEU-KHOAN", "QUY-TAC", "TOM-TAT-DIEU-KIEN", "Dieu-khoan", "Tom-tat"
    ],
    "4_To_roi_Gioi_thieu": ["Brochure", "10Reasons", "Chuong-trinh-uu-dai", "10_Reason"],
    "5_Cam_nang_Suc_khoe": [
        "HABITS", "SYMPTOMS", "PAIN", "DISEASE", "ARTHRITIS", "ASTHMA", "CANCER", 
        "DIABETES", "FIRST_AID", "TIPS", "ADVICE", "GUIDE", "HEALTH", "EYE", "HEART",
        "INFECTION", "JAUNDICE", "MIGRAINE", "OSTEOPOROSIS", "PARKINSON", "ULCER", 
        "FOODS", "WATER", "BODY", "WALK", "PAIN", "SWELLING", "ARTHRITIS", "BURN",
        "CUT", "GAS", "MASSAGE", "ITCH", "LOSS", "INJURY", "HIV", "AIDS", "JAUNDICE",
        "FLU", "WETTING", "BLEEDING", "CONDITIONS", "DIFFICULTY", "CATARACTS", "GLAUCOMA", 
        "HYPERTENSION", "DONG-KINH", "GUT", "CAO-HUYET-AP", "TIEU-DUONG", "DUONG-HO-HAP", 
        "DAU-NGUC", "OBSTRUCTIVE", "FORGETFULNESS", "CORNS", "HEARING", "MS", 
        "SCLEROSIS", "STIFFNESS", "TINGLING", "SICKNESS", "STRESS", "FEVER", "SORE",
        "ABDOMINAL", "ALZHEIMER", "ANKLE", "BACK", "BED", "BOWEL", "BREATHING", "CATARACTS",
        "CONFUSION", "CONGESTIVE", "CORONARY", "DIARRHEA", "DROWSINESS", "FATIGUE", "FINGER",
        "GROIN", "HAIR", "HEAD", "HEARING", "HEARTBURN", "HIP", "HOARSENESS", "JOINT", "LEG",
        "MEN_S", "WOMEN_S", "MOLE", "MULTIPLE", "NAIL", "NECK", "NUMBNESS", "PEPTIC", "PORTION",
        "PROSTATE", "RASH", "RECTAL", "SCRAPE", "SEXUALLY", "SHOULDER", "SINUSITIS", "WATER_BORNE"
    ],
    "6_Huong_dan_Su_dung": ["Huong-dan", "Quy-Trinh-Boi-Thuong"]
}

def categorize_file(filename):
    filename_upper = filename.upper()
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword.upper() in filename_upper:
                return category
    return "7_Khac"

# First, move all files back to SOURCE_DIR to re-categorize
for folder in os.listdir(SOURCE_DIR):
    folder_path = os.path.join(SOURCE_DIR, folder)
    if os.path.isdir(folder_path):
        for f in os.listdir(folder_path):
            shutil.move(os.path.join(folder_path, f), os.path.join(SOURCE_DIR, f))

# Re-categorize
files = [f for f in os.listdir(SOURCE_DIR) if os.path.isfile(os.path.join(SOURCE_DIR, f)) and f.endswith('.pdf')]

for f in files:
    category = categorize_file(f)
    os.makedirs(os.path.join(SOURCE_DIR, category), exist_ok=True)
    shutil.move(os.path.join(SOURCE_DIR, f), os.path.join(SOURCE_DIR, category, f))

# Clean up empty folders
for folder in os.listdir(SOURCE_DIR):
    folder_path = os.path.join(SOURCE_DIR, folder)
    if os.path.isdir(folder_path) and not os.listdir(folder_path):
        os.rmdir(folder_path)

print("Re-organization complete.")
