from django.shortcuts import render
from django.core.files.storage import default_storage
from .utils import extract_text_from_pdf
from .parser import parse_invoice_text  # import the parser


def pdf_upload(request):
    extracted_text = None
    parsed_data = None

    if request.method == "POST" and request.FILES.get("pdf_file"):
        uploaded_file = request.FILES["pdf_file"]

        # Save uploaded file temporarily
        file_path = default_storage.save(uploaded_file.name, uploaded_file)
        abs_path = default_storage.path(file_path)

        # Step 1: Extract text
        extracted_text = extract_text_from_pdf(abs_path, use_layout=True)

        # Step 2: Parse into structured data
        parsed_data = parse_invoice_text(extracted_text)

        # Clean up
        default_storage.delete(file_path)

    return render(
        request,
        "core/index.html",
        {
            "extracted_text": extracted_text,
            "parsed_data": parsed_data,
        },
    )