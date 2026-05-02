import os
import logging
import argparse
import concurrent.futures
import signal
import sys
import gc
import torch
from pathlib import Path
from dotenv import load_dotenv

# Set PyTorch memory optimization
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Marker imports
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from marker.output import save_output
except ImportError:
    print("Error: marker-pdf not fully installed.")
    sys.exit(1)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("marker_batch.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    logging.info("Interrupt received, shutting down...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)

def get_api_keys():
    keys = []
    for i in range(1, 6):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key: keys.append(key)
    if not keys:
        default_key = os.getenv("GEMINI_API_KEY")
        if default_key: keys.append(default_key)
    return keys

def get_output_dir(pdf_path: Path, base_input_dir: Path, base_output_dir: Path) -> Path:
    relative_path = pdf_path.parent.relative_to(base_input_dir)
    return base_output_dir / relative_path

def process_pdf_api(model_dict, pdf_path: Path, base_input_dir: Path, base_output_dir: Path, api_keys: list, use_llm: bool):
    if shutdown_requested:
        return False, "Shutdown requested"

    output_dir = get_output_dir(pdf_path, base_input_dir, base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = pdf_path.stem
    
    if (output_dir / f"{output_filename}.md").exists():
        return True, "Already exists"

    for attempt, key in enumerate(api_keys):
        if shutdown_requested: break
        
        try:
            # Create converter inside the loop but ensure we clear it after use
            config = {
                "use_llm": use_llm,
                "output_format": "markdown",
                "gemini_api_key": key
            }
            config_parser = ConfigParser(config)
            converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=model_dict,
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
                llm_service=config_parser.get_llm_service()
            )
            
            rendered = converter(str(pdf_path))
            save_output(rendered, str(output_dir), output_filename)
            
            # Cleanup to free VRAM
            del converter
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            
            logging.info(f"Done: {pdf_path.name} (Key {attempt + 1})")
            return True, "Success"
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "limit" in error_msg:
                logging.warning(f"Rate limit Key {attempt + 1} for {pdf_path.name}. Retrying...")
                continue
            elif "out of memory" in error_msg:
                logging.error(f"OOM on {pdf_path.name} with Key {attempt + 1}. Skipping file to avoid crash.")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
                return False, "OOM"
            else:
                logging.error(f"Error {pdf_path.name} Key {attempt + 1}: {str(e)}")
                continue
    
    return False, "Failed"

def main():
    parser = argparse.ArgumentParser(description="Batch convert PDFs using Marker - Optimized for 8GB VRAM")
    parser.add_argument("--input", type=str, default="data/health_insurance_pdfs", help="Input folder")
    parser.add_argument("--output", type=str, default="data/processed/marker_markdowns", help="Output folder")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (default 1 for CUDA)")
    parser.add_argument("--no-llm", action="store_true", help="Disable Hybrid Mode")
    
    args = parser.parse_args()
    
    base_input = Path(args.input)
    base_output = Path(args.output)
    use_llm = not args.no_llm
    
    if not base_input.exists():
        logging.error(f"Input dir not found: {base_input}")
        return

    api_keys = get_api_keys()
    
    logging.info("Loading models (CUDA)...")
    try:
        model_dict = create_model_dict()
    except Exception as e:
        logging.error(f"Failed to load models: {e}")
        return
    
    pdf_files = sorted(list(base_input.rglob("*.pdf")))
    logging.info(f"Processing {len(pdf_files)} PDFs...")

    successful = 0
    skipped = 0
    failed = 0

    # Sequential processing is MUCH safer for 8GB VRAM
    for pdf in pdf_files:
        if shutdown_requested: break
        is_success, status = process_pdf_api(model_dict, pdf, base_input, base_output, api_keys, use_llm)
        if is_success:
            if status == "Already exists": skipped += 1
            else: successful += 1
        else:
            failed += 1
        
        # Periodic cleanup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    logging.info(f"Summary: {successful} new, {skipped} skipped, {failed} failed.")

if __name__ == "__main__":
    main()
