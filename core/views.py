from django.shortcuts import render
from django.core.files.storage import default_storage

from .models import InvoiceRecord
from .extraction.utils import extract_text_from_pdf
from .parsing.parser import parse_invoice_text


def pdf_upload(request):
    extracted_text = None
    parsed_data = None

    if request.method == "POST" and request.FILES.get("pdf_file"):
        uploaded_file = request.FILES["pdf_file"]

        # Save uploaded PDF
        file_path = default_storage.save(
            f"dataset/pdfs/{uploaded_file.name}",
            uploaded_file
        )

        abs_path = default_storage.path(file_path)

        # Extract and parse
        extracted_text = extract_text_from_pdf(abs_path, use_layout=True)
        parsed_data = parse_invoice_text(extracted_text)

        # Save dataset record
        InvoiceRecord.objects.create(
            pdf_file=file_path,
            extracted_text=extracted_text,
            parsed_data=parsed_data,
        )

    return render(
        request,
        "core/index.html",
        {
            "extracted_text": extracted_text,
            "parsed_data": parsed_data,
        },
    )