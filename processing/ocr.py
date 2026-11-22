"""OCR module: EasyOCR first, then Tesseract, else graceful 'none'."""
import importlib.util
import os
import shutil
from PIL import Image, ImageOps

_reader = None
ENGINE = None  # 'easyocr' | 'tesseract' | 'none'


def _detect():
    global ENGINE, _reader
    if ENGINE:
        return
    try:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        ENGINE = "easyocr"
        return
    except Exception:
        pass
    try:
        import pytesseract
        win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if not shutil.which("tesseract") and os.path.exists(win):
            pytesseract.pytesseract.tesseract_cmd = win
        pytesseract.get_tesseract_version()
        ENGINE = "tesseract"
        return
    except Exception:
        pass
    ENGINE = "none"


def engine_name():
    """Cheap check (does not load models) so stats/dashboard stay fast."""
    if ENGINE:
        return ENGINE
    if importlib.util.find_spec("easyocr"):
        return "easyocr"
    if importlib.util.find_spec("pytesseract") and (
            shutil.which("tesseract") or os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe")):
        return "tesseract"
    return "none"


def preprocess(img: Image.Image) -> Image.Image:
    """Grayscale + autocontrast + cap size to improve OCR readability."""
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.autocontrast(img)
    if max(img.size) > 2400:
        img.thumbnail((2400, 2400))
    # white margin: OCR models often clip the first/last letters at the image edge
    return ImageOps.expand(img, border=60, fill=255)


def extract_text(img: Image.Image) -> str:
    _detect()
    if ENGINE == "none":
        return ""
    img = preprocess(img)
    if ENGINE == "easyocr":
        import numpy as np
        lines = _reader.readtext(np.array(img), detail=0, paragraph=True)
        return "\n".join(lines)
    import pytesseract
    return pytesseract.image_to_string(img)
