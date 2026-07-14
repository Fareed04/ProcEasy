import PyPDF2
import pdfplumber
import pytesseract
from pdf2image import convert_from_path

# ✅ Tell pytesseract exactly where Tesseract OCR is installed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_pdf(pdf_path, use_layout=False):
    """
    Extract text from a PDF, using OCR only on pages that need it.
    """

    # ✅ Explicitly set your Poppler bin path
    poppler_path = r"C:\poppler\Library\bin"

    text = ""

    # Open PDF for page-by-page inspection
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        total_pages = len(reader.pages)

    # Convert to images only if needed
    images = None

    for i in range(total_pages):
        page_text = ""

        # Step 1: Try extracting text normally
        if use_layout:
            with pdfplumber.open(pdf_path) as pdf:
                page_text = pdf.pages[i].extract_text() or ""
        else:
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                page_text = reader.pages[i].extract_text() or ""

        # Step 2: If no text, OCR this page only
        if not page_text.strip():
            if images is None:  # convert all pages once, only if needed
                images = convert_from_path(pdf_path, poppler_path=poppler_path)
            page_text = pytesseract.image_to_string(images[i])

        text += page_text + "\n"

    return text
