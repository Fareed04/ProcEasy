import os
import tempfile

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.files import File
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import InvoiceRecord
from .extraction.utils import extract_text_from_pdf
from .parsing.parser import parse_invoice_text


# Session key under which an unsaved upload is staged until verification.
DRAFT_SESSION_KEY = "draft_invoice"


def _remove_temp_file(path):
    """Delete a staged temp file if it still exists (best effort)."""
    if path and os.path.exists(path):
        os.remove(path)


def _progress_counts():
    """Verified-vs-total tallies for the labelling progress counter.

    Total is intentionally dynamic -- there is no fixed target, since new
    invoices arrive continuously.
    """
    total = InvoiceRecord.objects.count()
    verified = InvoiceRecord.objects.filter(verified=True).count()
    return {"verified_count": verified, "total_count": total}


def _collect_invoice_data(request):
    """Build the structured verified-data dict from the POSTed form.

    Shared by the draft (session) and saved (pk) verify paths so both
    persist exactly the fields the form submits.
    """

    def field(name):
        return request.POST.get(name, "").strip()

    # ---- Items ----
    item_names = request.POST.getlist("item_name[]")
    item_descriptions = request.POST.getlist("item_description[]")
    item_quantities = request.POST.getlist("item_quantity[]")
    item_unit_prices = request.POST.getlist("item_unit_price[]")
    item_discounts = request.POST.getlist("item_discount[]")
    item_line_totals = request.POST.getlist("item_line_total[]")

    items = []
    for i in range(len(item_names)):
        item = {
            "item_name": item_names[i].strip() if i < len(item_names) else "",
            "description": item_descriptions[i].strip() if i < len(item_descriptions) else "",
            "quantity": item_quantities[i].strip() if i < len(item_quantities) else "",
            "unit_price": item_unit_prices[i].strip() if i < len(item_unit_prices) else "",
            "discount": item_discounts[i].strip() if i < len(item_discounts) else "",
            "line_total": item_line_totals[i].strip() if i < len(item_line_totals) else "",
        }

        # Ignore completely empty rows.
        if any(item.values()):
            items.append(item)

    # ---- Payment terms ----
    term_types = request.POST.getlist("payment_term_type[]")
    term_percentages = request.POST.getlist("payment_term_percentage[]")

    payment_terms = []
    for i in range(len(term_types)):
        term_type = term_types[i].strip() if i < len(term_types) else ""
        percentage = term_percentages[i].strip() if i < len(term_percentages) else ""

        if term_type or percentage:
            payment_terms.append({
                "type": term_type,
                "percentage": percentage,
            })

    return {
        "invoice": {
            "vendor": field("vendor"),
            "cost_center": field("cost_center"),
            "currency": field("currency"),
            "subtotal": field("subtotal"),
            "tax": field("tax"),
            "tax_group": field("tax_group"),
            "wht": field("wht"),
            "grand_total": field("grand_total"),
        },
        "items": items,
        "payment_terms": payment_terms,
    }


def pdf_upload(request):

    if request.method == "POST" and request.FILES.get("pdf_file"):

        uploaded_file = request.FILES["pdf_file"]

        # Clean up any previously staged draft that was never verified.
        old_draft = request.session.get(DRAFT_SESSION_KEY)
        if old_draft:
            _remove_temp_file(old_draft.get("temp_path"))

        # Write to an OS temp file so the extractor (which needs a real path)
        # can read it -- WITHOUT touching dataset/pdfs or the database yet.
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, "wb") as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)

        extracted_text = extract_text_from_pdf(temp_path, use_layout=True)
        parsed_data = parse_invoice_text(extracted_text)

        # Stage everything in the session. Nothing is persisted until the
        # user hits "Mark as Verified" on the verify page.
        request.session[DRAFT_SESSION_KEY] = {
            "temp_path": temp_path,
            "original_name": uploaded_file.name,
            "extracted_text": extracted_text,
            "parsed_data": parsed_data,
        }

        return redirect("verify_draft")

    return render(request, "core/index.html", _progress_counts())


def verify_draft(request):
    """Review a staged (unsaved) upload; persist it only on submit."""

    draft = request.session.get(DRAFT_SESSION_KEY)

    if not draft:
        # Nothing staged -- send the user back to upload.
        return redirect("pdf_upload")

    if request.method == "POST":

        verified_data = _collect_invoice_data(request)

        # Now -- and only now -- persist. Move the staged PDF from the OS
        # temp dir into dataset/pdfs and create the InvoiceRecord.
        temp_path = draft.get("temp_path")
        saved_path = ""

        if temp_path and os.path.exists(temp_path):
            with open(temp_path, "rb") as fh:
                saved_path = default_storage.save(
                    f"dataset/pdfs/{draft['original_name']}",
                    File(fh),
                )

        invoice = InvoiceRecord.objects.create(
            pdf_file=saved_path,
            extracted_text=draft["extracted_text"],
            parsed_data=verified_data,
            verified=True,
            is_handwritten=bool(request.POST.get("is_handwritten")),
            verified_at=timezone.now(),
        )

        # Clean up the staged file and drop the draft from the session.
        _remove_temp_file(temp_path)
        del request.session[DRAFT_SESSION_KEY]

        # Continuous flow: confirm, then go straight back to upload so the
        # next invoice can be labelled without extra navigation.
        vendor = verified_data["invoice"]["vendor"] or f"Invoice #{invoice.id}"
        messages.success(request, f"Verified and saved: {vendor}.")
        return redirect("pdf_upload")

    return render(
        request,
        "core/verify.html",
        {
            # A dict stands in for the model instance so the template's
            # {{ invoice.extracted_text }} lookup works unchanged.
            "invoice": {"extracted_text": draft["extracted_text"]},
            "invoice_data": draft["parsed_data"] or {},
            **_progress_counts(),
        },
    )


def verify_invoice(request, pk):
    """View / re-edit an already-saved record."""

    invoice = get_object_or_404(InvoiceRecord, id=pk)

    if request.method == "POST":
        invoice.parsed_data = _collect_invoice_data(request)
        invoice.is_handwritten = bool(request.POST.get("is_handwritten"))
        invoice.verified = True
        invoice.verified_at = timezone.now()
        invoice.save()

        return redirect("verify_invoice", pk=invoice.id)

    return render(
        request,
        "core/verify.html",
        {
            "invoice": invoice,
            "invoice_data": invoice.parsed_data or {},
            **_progress_counts(),
        },
    )
