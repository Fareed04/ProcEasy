from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import default_storage

from .models import InvoiceRecord
from .extraction.utils import extract_text_from_pdf
from .parsing.parser import parse_invoice_text


def pdf_upload(request):

    if request.method == "POST" and request.FILES.get("pdf_file"):

        uploaded_file = request.FILES["pdf_file"]

        # Save uploaded PDF
        file_path = default_storage.save(
            f"dataset/pdfs/{uploaded_file.name}",
            uploaded_file
        )

        # Get absolute file path
        abs_path = default_storage.path(file_path)

        # Extract text
        extracted_text = extract_text_from_pdf(
            abs_path,
            use_layout=True
        )

        # Parse extracted text
        parsed_data = parse_invoice_text(extracted_text)

        # Create invoice record
        invoice_record = InvoiceRecord.objects.create(
            pdf_file=file_path,
            extracted_text=extracted_text,
            parsed_data=parsed_data,
            verified=False
        )

        # Go to verification page
        return redirect(
            "verify_invoice",
            pk=invoice_record.id
        )

    return render(
        request,
        "core/index.html"
    )


def verify_invoice(request, pk):

    invoice = get_object_or_404(
        InvoiceRecord,
        id=pk
    )

    # =========================
    # SAVE VERIFIED DATA
    # =========================

    if request.method == "POST":

        # Invoice-level fields
        vendor = request.POST.get(
            "vendor",
            ""
        ).strip()

        currency = request.POST.get(
            "currency",
            ""
        ).strip()

        subtotal = request.POST.get(
            "subtotal",
            ""
        ).strip()

        tax = request.POST.get(
            "tax",
            ""
        ).strip()

        grand_total = request.POST.get(
            "grand_total",
            ""
        ).strip()

        payment_terms = request.POST.get(
            "payment_terms",
            ""
        ).strip()

        # =========================
        # ITEM DATA
        # =========================

        item_names = request.POST.getlist(
            "item_name[]"
        )

        item_descriptions = request.POST.getlist(
            "item_description[]"
        )

        item_quantities = request.POST.getlist(
            "item_quantity[]"
        )

        item_unit_prices = request.POST.getlist(
            "item_unit_price[]"
        )

        item_line_totals = request.POST.getlist(
            "item_line_total[]"
        )

        items = []

        # Build structured items
        for i in range(len(item_names)):

            item_name = (
                item_names[i].strip()
                if i < len(item_names)
                else ""
            )

            description = (
                item_descriptions[i].strip()
                if i < len(item_descriptions)
                else ""
            )

            quantity = (
                item_quantities[i].strip()
                if i < len(item_quantities)
                else ""
            )

            unit_price = (
                item_unit_prices[i].strip()
                if i < len(item_unit_prices)
                else ""
            )

            line_total = (
                item_line_totals[i].strip()
                if i < len(item_line_totals)
                else ""
            )

            # Ignore completely empty item rows
            if not any([
                item_name,
                description,
                quantity,
                unit_price,
                line_total,
            ]):
                continue

            items.append({
                "item_name": item_name,
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            })

        # =========================
        # FINAL VERIFIED DATASET
        # =========================

        verified_data = {
            "invoice": {
                "vendor": vendor,
                "currency": currency,
                "subtotal": subtotal,
                "tax": tax,
                "grand_total": grand_total,
                "payment_terms": payment_terms,
            },
            "items": items,
        }

        # Save verified data
        invoice.parsed_data = verified_data
        invoice.verified = True
        invoice.save()

        # Stay on verification page
        return redirect(
            "verify_invoice",
            pk=invoice.id
        )

    # =========================
    # DISPLAY VERIFICATION FORM
    # =========================

    parsed_data = invoice.parsed_data or {}

    return render(
        request,
        "core/verify.html",
        {
            "invoice": invoice,
            "invoice_data": parsed_data,
        }
    )