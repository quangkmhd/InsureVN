import os
import logging
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Datalab SDK import
try:
    from datalab_sdk import DatalabClient
    from datalab_sdk.models import ConvertOptions
    from datalab_sdk.exceptions import DatalabAPIError
except ImportError:
    print("Error: datalab-python-sdk not installed. Run 'pip install datalab-python-sdk'")
    sys.exit(1)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("marker_datalab_hosted.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Load DATALAB_KEYs from environment
def get_datalab_keys():
    keys = []
    # Check for DATALAB_KEY_1, DATALAB_KEY_2, etc.
    i = 1
    while True:
        key = os.getenv(f"DATALAB_KEY_{i}")
        if not key:
            break
        keys.append(key)
        i += 1
    
    # Fallback to single DATALAB_KEY if no numbered keys found
    if not keys:
        default_key = os.getenv("DATALAB_KEY")
        if default_key:
            keys.append(default_key)
    return keys

class DatalabManager:
    def __init__(self, keys: list[str], use_llm: bool = True):
        self.clients = [DatalabClient(api_key=k) for k in keys]
        self.current_index = 0
        # Map use_llm to accurate mode for higher quality
        mode = "accurate" if use_llm else "balanced"
        self.options = ConvertOptions(mode=mode, output_format="markdown")
        
    def get_client(self) -> DatalabClient:
        return self.clients[self.current_index]
        
    def rotate_client(self) -> bool:
        if len(self.clients) > 1:
            self.current_index = (self.current_index + 1) % len(self.clients)
            logging.warning(f"Rate limited. Switching to API Key #{self.current_index + 1}")
            return True
        return False

def clean_pdf_name(pdf_path: Path) -> str:
    """Removes junk suffixes like .pdf, .coredownload, .inline from filename."""
    name = pdf_path.name
    suffixes_to_remove = [".pdf", ".coredownload", ".inline"]
    
    changed = True
    while changed:
        changed = False
        lower_name = name.lower()
        for suffix in suffixes_to_remove:
            if lower_name.endswith(suffix):
                name = name[:-len(suffix)]
                lower_name = name.lower()
                changed = True
    return name

def process_pdf_datalab_hosted(manager: DatalabManager, pdf_path: Path, base_output_dir: Path):
    # Create a unique subfolder for each PDF
    provider_name = pdf_path.parent.name
    cleaned_name = clean_pdf_name(pdf_path)
    
    pdf_output_dir = base_output_dir / provider_name / cleaned_name
    pdf_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if already processed (look for metadata.json inside the folder)
    if (pdf_output_dir / f"{cleaned_name}.metadata.json").exists():
        logging.info(f"Skipping (Already exists): {pdf_path.name}")
        return True

    import time
    max_retries = len(manager.clients) + 3 # Add buffer for server errors
    retries = 0
    
    while retries < max_retries:
        try:
            client = manager.get_client()
            logging.info(f"Converting (Hosted API - Mode: {manager.options.mode}) [Key #{manager.current_index + 1}]: {pdf_path.name}")
            
            # Use ConvertOptions instead of direct keyword arguments
            result = client.convert(str(pdf_path), options=manager.options)
            
            # Save output using cleaned_name as prefix inside the folder
            save_prefix = str(pdf_output_dir / cleaned_name)
            result.save_output(save_prefix)
            
            logging.info(f"Done: {pdf_path.name} -> {pdf_output_dir}")
            return True
            
        except DatalabAPIError as e:
            if e.status_code in (429, 403): # Rate limit or quota exhausted
                if manager.rotate_client():
                    retries += 1
                    continue
                else:
                    logging.error(f"Rate limited or quota exhausted and no more keys to rotate: {str(e)}")
                    return False
            elif e.status_code in (500, 502, 503, 504): # Server errors
                logging.warning(f"Server error {e.status_code} for {pdf_path.name}. Retrying in 5 seconds... ({retries + 1}/{max_retries})")
                time.sleep(5)
                retries += 1
                continue
            else:
                logging.error(f"API Error {pdf_path.name}: {str(e)}")
                return False
        except Exception as e:
            logging.error(f"Error {pdf_path.name}: {str(e)}")
            return False
    
    return False

def main():
    parser = argparse.ArgumentParser(description="Batch convert PDFs using Datalab Hosted API (Product Standard)")
    parser.add_argument("--input", type=str, default="data/health_insurance_pdfs", help="Input folder")
    parser.add_argument("--output", type=str, default="data/datalab_hosted_markdowns", help="Output folder")
    parser.add_argument("--use-llm", action=argparse.BooleanOptionalAction, default=True, help="Enable/disable LLM-powered cleanup and table merging (Default: True)")
    
    args = parser.parse_args()
    
    keys = get_datalab_keys()

    base_input = Path(args.input)
    base_output = Path(args.output)
    
    if not base_input.exists():
        logging.error(f"Input dir not found: {base_input}")
        return

    # Initialize Datalab Manager
    manager = DatalabManager(keys, use_llm=args.use_llm)
    
    pdf_files = sorted(list(base_input.rglob("*.pdf")))
    logging.info(f"Processing {len(pdf_files)} PDFs with Datalab Hosted API (using {len(keys)} keys)...")

    for pdf in pdf_files:
        process_pdf_datalab_hosted(manager, pdf, base_output)

if __name__ == "__main__":
    main()
