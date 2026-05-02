import os
import json
import shutil

SOURCE_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/good_content"
TARGET_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/trash_content"

def move_empty_json():
    # Ensure source directory exists
    if not os.path.exists(SOURCE_DIR):
        print(f"Source directory not found: {SOURCE_DIR}")
        return

    # Ensure target directory exists
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR, exist_ok=True)
        print(f"Created target directory: {TARGET_DIR}")

    files = [f for f in os.listdir(SOURCE_DIR) if f.endswith('.json')]
    count = 0

    print(f"Scanning {len(files)} files in {SOURCE_DIR}...")

    for filename in files:
        file_path = os.path.join(SOURCE_DIR, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if structured_data is missing or empty
            structured_data = data.get("structured_data")
            
            if structured_data is None or (isinstance(structured_data, list) and len(structured_data) == 0):
                shutil.move(file_path, os.path.join(TARGET_DIR, filename))
                count += 1
                # Only print every 10 files to avoid cluttering if there are thousands
                if count % 10 == 0:
                    print(f"Moved {count} files so far...")
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"\n✅ Finished. Moved {count} files to trash_content.")

if __name__ == "__main__":
    move_empty_json()
