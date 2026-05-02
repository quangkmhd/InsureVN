import os
import json
import logging
from pathlib import Path
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ImageCropper:
    def __init__(self, json_base_dir: str, pdf_base_dir: str, output_base_dir: str):
        self.json_base_dir = Path(json_base_dir)
        self.pdf_base_dir = Path(pdf_base_dir)
        self.output_base_dir = Path(output_base_dir)

    def convert_coords(self, bbox_dict: dict, page_height: float) -> fitz.Rect:
        """
        Converts Docling BBox (bottom-left) to PyMuPDF Rect (top-left).
        """
        l = bbox_dict["l"]
        b = bbox_dict["b"]
        r = bbox_dict["r"]
        t = bbox_dict["t"]
        
        y0 = page_height - t
        y1 = page_height - b
        return fitz.Rect(l, y0, r, y1)

    def process_json(self, json_path: Path):
        """
        Reads a JSON structure and crops images from the corresponding PDF.
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        metadata = data.get("metadata", {})
        provider = metadata.get("provider")
        pdf_name = metadata.get("filename")
        pdf_stem = Path(pdf_name).stem
        
        # Locate the original PDF
        # We search recursively in the provider directory in case of subfolders
        pdf_path = self.pdf_base_dir / provider / pdf_name
        if not pdf_path.exists():
            # Try to find it if naming is slightly different
            logger.warning(f"PDF not found at {pdf_path}, searching...")
            found_pdfs = list((self.pdf_base_dir / provider).glob(f"**/{pdf_name}"))
            if not found_pdfs:
                logger.error(f"Could not find PDF: {pdf_name}")
                return
            pdf_path = found_pdfs[0]

        output_dir = self.output_base_dir / provider / pdf_stem
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cropping elements from: {pdf_stem}")
        
        try:
            fitz_doc = fitz.open(pdf_path)
            
            # Counters for naming
            counters = {"table": 0, "picture": 0}
            
            for element in data.get("elements", []):
                label = element.get("label")
                
                # Only process tables and pictures
                if label in ["table", "picture"]:
                    counters[label] += 1
                    page_no = element.get("page_no")
                    bbox_dict = element.get("bbox")
                    
                    if not page_no or not bbox_dict:
                        continue
                        
                    # fitz uses 0-indexed page numbers
                    fitz_page = fitz_doc[page_no - 1]
                    page_height = fitz_page.rect.height
                    
                    # Convert coordinates
                    rect = self.convert_coords(bbox_dict, page_height)
                    
                    # Ensure rect is valid and not zero-sized
                    if rect.width <= 0 or rect.height <= 0:
                        continue

                    # Naming: table_p1_n1.png or picture_p1_n1.png
                    img_filename = f"{label}_p{page_no}_n{counters[label]}.png"
                    meta_filename = f"{label}_p{page_no}_n{counters[label]}.json"
                    img_path = output_dir / img_filename
                    meta_path = output_dir / meta_filename
                    
                    # Skip if BOTH image and metadata already exist
                    if img_path.exists() and meta_path.exists():
                        continue

                    # fitz uses 0-indexed page numbers
                    fitz_page = fitz_doc[page_no - 1]
                    page_height = fitz_page.rect.height
                    
                    # Convert coordinates
                    rect = self.convert_coords(bbox_dict, page_height)
                    
                    # Ensure rect is valid and not zero-sized
                    if rect.width <= 0 or rect.height <= 0:
                        continue

                    # Use 300 DPI for clarity (zoom=300/72)
                    zoom = 300 / 72
                    mat = fitz.Matrix(zoom, zoom)
                    
                    # Crop and save
                    pix = fitz_page.get_pixmap(matrix=mat, clip=rect)
                    pix.save(str(img_path))
                    
                    # Save a small individual metadata file for this image
                    # Include the markdown for tables
                    element_meta = {
                        "source_pdf": str(pdf_path),
                        "page_no": page_no,
                        "label": label,
                        "bbox_original": bbox_dict,
                        "text": element.get("text", "")
                    }
                    if label == "table":
                        element_meta["markdown"] = element.get("markdown", "")
                        
                    with open(meta_path, "w", encoding="utf-8") as mf:
                        json.dump(element_meta, mf, ensure_ascii=False, indent=2)

            fitz_doc.close()
            logger.info(f"Finished {pdf_stem}: {counters['table']} tables, {counters['picture']} pictures.")
            
        except Exception as e:
            logger.error(f"Error processing {pdf_stem}: {e}")

    def run(self):
        json_files = sorted(list(self.json_base_dir.glob("**/*.json")))
        logger.info(f"Found {len(json_files)} JSON structure files.")
        
        for json_file in json_files:
            self.process_json(json_file)

if __name__ == "__main__":
    JSON_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_structures"
    PDF_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_pdfs"
    OUTPUT_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_images_table"
    
    cropper = ImageCropper(JSON_DIR, PDF_DIR, OUTPUT_DIR)
    cropper.run()
