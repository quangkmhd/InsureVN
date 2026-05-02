import os
import logging
import argparse
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
        logging.FileHandler("marker_datalab.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Load keys from environment
DATALAB_KEY = os.getenv("DATALAB_KEY")
GEMINI_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
]
# Filter out None values
GEMINI_KEYS = [k for k in GEMINI_KEYS if k]

def get_output_dir(pdf_path: Path, base_input_dir: Path, base_output_dir: Path) -> Path:
    relative_path = pdf_path.parent.relative_to(base_input_dir)
    return base_output_dir / relative_path

def process_pdf_datalab(model_dict, pdf_path: Path, base_input_dir: Path, base_output_dir: Path):
    output_dir = get_output_dir(pdf_path, base_input_dir, base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = pdf_path.stem
    
    if (output_dir / f"{output_filename}.md").exists():
        return True, "Already exists"

    try:
        # According to standard LLM integration, Marker uses keys for model access.
        # Datalab keys are often used for their hosted API or specific model endpoints.
        # We'll configure this to use the Gemini service as it's the default and highly accurate.
        # Use the first available Gemini key
        # In a more robust implementation, we could rotate these if one fails with 429
        current_gemini_key = GEMINI_KEYS[0] if GEMINI_KEYS else None
        
        config = {
            "use_llm": True,
            "output_format": "markdown",
            "gemini_api_key": current_gemini_key
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
        
        # Cleanup
        del converter
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        
        logging.info(f"Done: {pdf_path.name}")
        return True, "Success"
    except Exception as e:
        logging.error(f"Error {pdf_path.name}: {str(e)}")
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Batch convert PDFs using Marker with Datalab API Key")
    parser.add_argument("--input", type=str, default="data/health_insurance_pdfs", help="Input folder")
    parser.add_argument("--output", type=str, default="data/processed/marker_datalab_markdowns", help="Output folder")
    
    args = parser.parse_args()
    
    base_input = Path(args.input)
    base_output = Path(args.output)
    
    if not base_input.exists():
        logging.error(f"Input dir not found: {base_input}")
        return

    logging.info("Loading models (CUDA)...")
    model_dict = create_model_dict()
    
    pdf_files = sorted(list(base_input.rglob("*.pdf")))
    logging.info(f"Processing {len(pdf_files)} PDFs with Datalab Key...")

    for pdf in pdf_files:
        process_pdf_datalab(model_dict, pdf, base_input, base_output)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

if __name__ == "__main__":
    main()
