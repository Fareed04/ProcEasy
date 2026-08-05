"""PDF text extraction for invoices.

The public entry point is :func:`extract_text_from_pdf`. Callers (see
core/views.py) are unchanged -- everything below is internal.

Design notes
------------
Many invoices in this project are *scanned images* that also carry a tiny
digital annotation stamp (e.g. "OK to proceed" + a date). The old extractor
treated any embedded text as "this page already has text" and skipped OCR --
so the ~24-char stamp masked the entire scanned body and nothing real was ever
read. The fix: a page is sent to OCR when its embedded text is below a small
character threshold (settings.OCR_MIN_TEXT_CHARS), not merely non-empty.

OCR itself goes through a pluggable backend so a cloud engine (Google Document
AI) can be dropped in later via settings.OCR_BACKEND without touching callers.
"""

import re

import PyPDF2
import pdfplumber
import pytesseract
from PIL import ImageOps
from pdf2image import convert_from_path

try:
    from django.conf import settings as _dj_settings
except Exception:  # pragma: no cover - allows standalone use without Django
    _dj_settings = None


def _cfg(name, default):
    """Read a setting, falling back to `default` outside a Django context."""
    if _dj_settings is not None:
        return getattr(_dj_settings, name, default)
    return default


# Lines that are pure annotation-stamp noise rather than invoice content.
_STAMP_NOISE = re.compile(
    r"^\s*(ok to proceed|approved|paid|received|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\s*$",
    re.IGNORECASE,
)


def _strip_stamp_noise(text: str) -> str:
    """Drop approval-stamp lines so they don't pollute the extracted text."""
    kept = [ln for ln in text.splitlines() if not _STAMP_NOISE.match(ln)]
    return "\n".join(kept)


# --------------------------------------------------------------------------- #
# OCR backends
# --------------------------------------------------------------------------- #
class OcrBackend:
    """Interface for turning a rendered page image into text."""

    def image_to_text(self, pil_image) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class TesseractBackend(OcrBackend):
    """Local OCR via Tesseract, with light preprocessing for scanned pages."""

    def __init__(self):
        cmd = _cfg("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = cmd

    def image_to_text(self, pil_image) -> str:
        # Grayscale + autocontrast sharpens printed text against scan noise.
        prepped = ImageOps.autocontrast(pil_image.convert("L"))
        # --psm 6: assume a uniform block of text (typical for invoice bodies).
        return pytesseract.image_to_string(prepped, config="--psm 6")


class GoogleDocAiBackend(OcrBackend):
    """Placeholder for Google Document AI.

    Left as a stub so the backend seam exists now; wire the actual client here
    (endpoint, processor id, credentials from settings) when moving to cloud
    OCR. Google Document AI reads handwriting, which local Tesseract cannot.
    """

    def image_to_text(self, pil_image) -> str:  # pragma: no cover - stub
        raise NotImplementedError(
            "Google Document AI backend is not wired yet. "
            "Set OCR_BACKEND='tesseract' or implement this method."
        )


_BACKENDS = {
    "tesseract": TesseractBackend,
    "google_docai": GoogleDocAiBackend,
}


def get_ocr_backend() -> OcrBackend:
    """Instantiate the OCR backend named by settings.OCR_BACKEND."""
    name = _cfg("OCR_BACKEND", "tesseract")
    backend_cls = _BACKENDS.get(name, TesseractBackend)
    return backend_cls()


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def _embedded_page_text(pdf_path, index, use_layout):
    """Return the digital (non-OCR) text for one page, or ''."""
    if use_layout:
        with pdfplumber.open(pdf_path) as pdf:
            return pdf.pages[index].extract_text() or ""
    with open(pdf_path, "rb") as fh:
        reader = PyPDF2.PdfReader(fh)
        return reader.pages[index].extract_text() or ""


def _needs_ocr(page_text: str) -> bool:
    """True when the embedded text is too thin to be the real invoice body."""
    meaningful = _strip_stamp_noise(page_text)
    non_space = re.sub(r"\s+", "", meaningful)
    return len(non_space) < int(_cfg("OCR_MIN_TEXT_CHARS", 40))


def extract_text_from_pdf(pdf_path, use_layout=False):
    """Extract text from a PDF, using OCR on pages that need it.

    Digital pages with a real text layer take the fast path; scanned pages
    (including those masked by a thin annotation stamp) are rendered and sent
    to the configured OCR backend.
    """
    poppler_path = _cfg("POPPLER_PATH", r"C:\poppler\Library\bin")
    dpi = int(_cfg("OCR_DPI", 300))

    with open(pdf_path, "rb") as fh:
        total_pages = len(PyPDF2.PdfReader(fh).pages)

    ocr_backend = None
    images = None  # rendered lazily, once, only if any page needs OCR
    out_pages = []

    for i in range(total_pages):
        page_text = _embedded_page_text(pdf_path, i, use_layout)

        if _needs_ocr(page_text):
            if images is None:
                images = convert_from_path(
                    pdf_path, dpi=dpi, poppler_path=poppler_path
                )
            if ocr_backend is None:
                ocr_backend = get_ocr_backend()
            page_text = ocr_backend.image_to_text(images[i])

        out_pages.append(_strip_stamp_noise(page_text))

    return "\n".join(out_pages).strip() + "\n"
