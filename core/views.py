import base64
import json
import mimetypes
import os
import re
import tempfile

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.files import File
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import InvoiceRecord
from .extraction.utils import extract_text_from_pdf
from .parsing.parser import parse_invoice_text
from .schema import empty_invoice, empty_item


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


def _wants_json(request):
    """True when the caller wants a JSON payload over the HTML verify redirect.

    Signalled by any of: an ``application/json`` Accept header, a
    ``?format=json`` query param, or our Chrome extension's own
    ``X-ProcEasy-Client`` request header.
    """
    if request.GET.get("format") == "json":
        return True
    if request.headers.get("X-ProcEasy-Client"):
        return True
    return "application/json" in request.headers.get("Accept", "")


# ---------------------------------------------------------------------------
# Agent Router (LLM gateway) extraction
#
# Extension / API callers have their documents extracted by an OpenAI-compatible
# gateway (settings.AGENT_ROUTER_*) instead of the local OCR + regex parser. The
# model is asked for bare JSON in exactly the shape core/schema.py defines, and
# that JSON is handed straight back to the caller.
# ---------------------------------------------------------------------------

def _build_extraction_prompt():
    """Minified system prompt pinned to the core/schema.py structure."""
    template = empty_invoice()
    template["items"] = [empty_item()]
    template["payment_terms"] = [{"type": "", "percentage": ""}]
    schema = json.dumps(template, separators=(",", ":"))
    return (
        "You extract data from an invoice document. "
        "Respond with ONE minified JSON object and nothing else: "
        "no prose, no markdown, no code fences. "
        "Use exactly these keys and nesting, one object per line item and per "
        "payment term, and empty strings where a value is missing: " + schema
    )


_EXTRACTION_SYSTEM_PROMPT = _build_extraction_prompt()


def _model_media_type(uploaded_file):
    """Best-effort MIME type for the upload (falls back to the file name)."""
    media_type = (uploaded_file.content_type or "").lower()
    if not media_type or media_type == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(uploaded_file.name or "")
        media_type = (guessed or "application/pdf").lower()
    return media_type


def _document_content_part(uploaded_file):
    """Encode the upload as an OpenAI-compatible file / vision content part."""
    b64 = base64.standard_b64encode(uploaded_file.read()).decode("ascii")
    media_type = _model_media_type(uploaded_file)
    name = uploaded_file.name or "document"

    if media_type == "application/pdf" or name.lower().endswith(".pdf"):
        return {
            "type": "file",
            "file": {
                "filename": name,
                "file_data": f"data:application/pdf;base64,{b64}",
            },
        }
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{b64}"},
    }


def _parse_model_json(text):
    """Load the model reply as JSON, tolerating stray fences or prose."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    fenced = re.sub(r"\n?```$", "", fenced).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    start, end = fenced.find("{"), fenced.rfind("}")
    if 0 <= start < end:
        return json.loads(fenced[start:end + 1])
    raise ValueError("model response contained no JSON object")


def _extract_via_gateway(uploaded_file):
    """Send the document to the Agent Router gateway; return its JSON reply."""
    base_url = settings.AGENT_ROUTER_BASE_URL
    api_key = settings.AGENT_ROUTER_API_KEY
    if not base_url or not api_key:
        return JsonResponse(
            {"ok": False, "error": "Agent Router is not configured (set "
             "AGENT_ROUTER_BASE_URL and AGENT_ROUTER_API_KEY)."},
            status=503,
        )

    try:
        from openai import OpenAI
    except ImportError:
        return JsonResponse(
            {"ok": False, "error": "The 'openai' package is not installed."},
            status=500,
        )

    content_part = _document_content_part(uploaded_file)
    client = OpenAI(base_url=base_url, api_key=api_key)

    try:
        completion = client.chat.completions.create(
            model=settings.AGENT_ROUTER_MODEL,
            temperature=0,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": [
                    content_part,
                    {"type": "text", "text": "Extract this invoice."},
                ]},
            ],
        )
    except Exception as exc:  # gateway / network / auth failure
        return JsonResponse(
            {"ok": False, "error": f"Agent Router request failed: {exc}"},
            status=502,
        )

    raw = completion.choices[0].message.content if completion.choices else ""
    try:
        data = _parse_model_json(raw)
    except (ValueError, json.JSONDecodeError):
        return JsonResponse(
            {"ok": False, "error": "Model did not return valid JSON.",
             "raw": raw},
            status=502,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"ok": False, "error": "Model JSON was not an object.", "raw": raw},
            status=502,
        )

    # Hand the model's JSON straight back to the extension caller.
    return JsonResponse(data)


@csrf_exempt  # let the Chrome extension POST pdf_file without a CSRF token
def pdf_upload(request):

    if request.method == "POST" and request.FILES.get("pdf_file"):

        uploaded_file = request.FILES["pdf_file"]

        # Extension / API callers: extract via the Agent Router gateway and
        # return the model's JSON verbatim. The browser form flow below keeps
        # using the local OCR + parser and the staged-draft verify page.
        if _wants_json(request):
            return _extract_via_gateway(uploaded_file)

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
