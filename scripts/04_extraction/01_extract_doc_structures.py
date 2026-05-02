import os
import json
import logging
import traceback
from pathlib import Path
from typing import List, Dict, Any

from docling.document_converter import DocumentConverter
from docling_core.types.doc import TableItem, TextItem, PictureItem, SectionHeaderItem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("doc_structure_extraction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DocStructureExtractor:
    def __init__(self, output_base_dir: str):
        self.output_base_dir = Path(output_base_dir)
        self.converter = DocumentConverter()

    def process_pdf(self, pdf_path: Path):
        """
        Processes a single PDF to extract all elements and save to a JSON structure.
        """
        provider = pdf_path.parent.name
        pdf_stem = pdf_path.stem
        output_dir = self.output_base_dir / provider
        output_dir.mkdir(parents=True, exist_ok=True)
        
        json_path = output_dir / f"{pdf_stem}.json"

        # Skip if already processed
        if json_path.exists():
            logger.info(f"Skipping (already exists): {pdf_stem}")
            return

        logger.info(f"Analyzing structure: {pdf_path}")
        
        try:
            # 1. Convert with Docling
            result = self.converter.convert(pdf_path)
            doc = result.document
            
            elements = []
            
            # Iterate through all items
            for item, level in doc.iterate_items():
                label = item.label.value if hasattr(item.label, 'value') else str(item.label)
                
                element_data = {
                    "label": label,
                    "level": level,
                    "text": getattr(item, 'text', ""),
                    "page_no": None,
                    "bbox": None
                }
                
                # Extract coordinates and page number if available
                if hasattr(item, 'prov') and item.prov:
                    prov = item.prov[0]
                    element_data["page_no"] = prov.page_no
                    bbox = prov.bbox
                    element_data["bbox"] = {
                        "l": bbox.l,
                        "b": bbox.b,
                        "r": bbox.r,
                        "t": bbox.t
                    }
                
                # Special handling for tables (include Markdown)
                if isinstance(item, TableItem):
                    element_data["markdown"] = item.export_to_markdown(doc=doc)
                
                elements.append(element_data)
            
            # Prepare final structure
            output_data = {
                "metadata": {
                    "filename": pdf_path.name,
                    "provider": provider,
                    "total_elements": len(elements)
                },
                "elements": elements
            }
            
            # Save to JSON
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Saved structure to {json_path.name} ({len(elements)} elements)")
            
        except Exception as e:
            logger.error(f"Failed to analyze {pdf_path}: {e}")
            # logger.debug(traceback.format_exc())

    def run(self, input_dir: str):
        """
        Scans directory and processes all PDFs.
        """
        input_path = Path(input_dir)
        pdf_files = sorted(list(input_path.glob("**/*.pdf")))
        logger.info(f"Found {len(pdf_files)} PDF files.")
        
        for i, pdf_file in enumerate(pdf_files):
            logger.info(f"[{i+1}/{len(pdf_files)}] Starting...")
            self.process_pdf(pdf_file)

if __name__ == "__main__":
    INPUT_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_pdfs"
    OUTPUT_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_structures"
    
    extractor = DocStructureExtractor(OUTPUT_DIR)
    extractor.run(INPUT_DIR)
