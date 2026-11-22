"""PDF handling with PyMuPDF: direct text for digital PDFs, OCR for scans."""
import os
import pymupdf
from PIL import Image
from .ocr import extract_text

MIN_TEXT_CHARS = 20  # below this a page is treated as scanned


def process_pdf(pdf_path, preview_dir):
    """Yield (page_number, text, preview_image_path, used_ocr) per page."""
    os.makedirs(preview_dir, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=150)
            preview = os.path.join(preview_dir, f"{i}.png")
            pix.save(preview)
            text = page.get_text().strip()
            used_ocr = False
            if len(text) < MIN_TEXT_CHARS:
                hi = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", (hi.width, hi.height), hi.samples)
                text = extract_text(img).strip()
                used_ocr = True
            yield i, text, preview, used_ocr
    finally:
        doc.close()
