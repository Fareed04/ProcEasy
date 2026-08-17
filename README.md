# ProcEasy

**ProcEasy** is a Django-based procurement automation platform that turns messy purchase
invoices — born-digital PDFs, scanned images, even scans hidden behind an approval stamp —
into clean, structured, human-verified records.

Today it is a **human-in-the-loop invoice extraction and labelling tool**: upload a PDF, let
the pipeline extract and pre-fill the fields, review and correct them on a purpose-built
verification screen, and save a trustworthy record. Every verified invoice becomes a labelled
example in a growing dataset — the foundation for the longer-term goal of an intelligent
procurement assistant that reads documents automatically and populates ERP forms with no
manual keying.

---

## Table of contents

- [Why ProcEasy](#why-proceasy)
- [Key capabilities](#key-capabilities)
- [How it works](#how-it-works-the-pipeline)
- [The verification interface](#the-verification-interface)
- [Data model](#data-model)
- [Domain notes](#domain-notes-nigerian-procurement)
- [Project structure](#project-structure)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Usage walkthrough](#usage-walkthrough)
- [Admin](#admin)
- [Roadmap](#roadmap)
- [Limitations & notes](#limitations--notes)

---

## Why ProcEasy

Procurement teams spend hours retyping the same invoice fields — vendor, line items,
quantities, prices, taxes, payment milestones — into ERP systems. The source documents are
inconsistent: some are clean digital PDFs, many are scanned paper, and a frustrating number are
scans that carry only a tiny digital annotation stamp (e.g. *"OK to proceed"* + a date) on top
of an otherwise image-only page.

ProcEasy attacks this in two stages:

1. **Automate the reading.** A hybrid extraction pipeline pulls text from whichever kind of PDF
   you throw at it, and a rule-based parser pre-fills the structured fields.
2. **Keep a human in the loop.** A focused verification UI lets a person confirm and correct
   every value quickly, guaranteeing the saved data is correct while quietly accumulating a
   high-quality labelled dataset for future machine-learning models.

---

## Key capabilities

- **Universal PDF text extraction** — digital text layers *and* scanned images are handled by a
  single entry point, with per-page decisions about which path to take.
- **Stamp-aware OCR fallback** — pages whose only embedded text is a thin approval stamp are
  correctly recognised as scanned and sent to OCR, instead of being skipped.
- **Pluggable OCR backend** — local Tesseract by default, with a drop-in seam for cloud OCR
  (Google Document AI) that can also read handwriting.
- **Rule-based invoice parser** — best-effort pre-fill of vendor, currency, subtotal, grand
  total and line items, with guards against misreading phone/contact lines as items.
- **Structured verification form** — a two-pane screen showing raw extracted text beside an
  editable, validated invoice form.
- **Live client-side calculations** — line totals, subtotal and a tax-aware grand total are
  computed as you type; discounts are applied per unit.
- **Payment-terms validation** — milestone percentages must add up to exactly 100% before an
  invoice can be saved.
- **Draft staging** — nothing touches the database or the dataset folder until a human clicks
  *Mark as Verified*, so failed or abandoned uploads leave no trace.
- **Continuous labelling flow** — after saving, you land straight back on the upload screen with
  a running *verified / total* progress counter.
- **Handwritten flagging** — invoices can be tagged as handwritten for later model training.
- **Admin dashboard** — browse, search and filter all records by vendor, cost center,
  verification status and more.

---

## How it works (the pipeline)

A single upload flows through five stages. The first four are automatic; the fifth is the human
gate.

```
   Upload PDF                Extract                 Parse                Stage                 Verify & Save
 ┌────────────┐        ┌──────────────────┐    ┌──────────────┐    ┌──────────────┐      ┌────────────────────┐
 │ index page │  POST  │ per-page:        │    │ regex parser │    │ session +    │      │ human reviews,     │
 │ file input │ ─────▶ │  digital layer   │──▶ │ pre-fills    │──▶ │ OS temp file │ ───▶ │ corrects, submits  │
 │            │        │  or OCR fallback │    │ structured   │    │ (no DB yet)  │      │ → InvoiceRecord    │
 └────────────┘        └──────────────────┘    └──────────────┘    └──────────────┘      └────────────────────┘
```

### 1. Upload
The home page (`/`) accepts a single PDF. On submit, the file is written to an OS temp file so
the extractor — which needs a real filesystem path — can read it **without** yet touching the
`dataset/pdfs/` folder or the database.

### 2. Extract — [`core/extraction/utils.py`](core/extraction/utils.py)
`extract_text_from_pdf()` walks the PDF page by page and decides, per page, how to read it:

- **Digital fast path** — pages with a real embedded text layer are read directly via
  **pdfplumber** (with layout preservation) or **PyPDF2**.
- **OCR fallback** — a page is sent to OCR when its embedded text has fewer than
  `OCR_MIN_TEXT_CHARS` (default **40**) non-space characters — *not* merely when it is empty.
  This is the key insight: many invoices are scanned images carrying only a ~24-character
  annotation stamp, which older extractors mistook for "this page already has text" and then
  skipped OCR, reading nothing real. Pages needing OCR are rasterized once (lazily) with
  **pdf2image / Poppler** at a configurable DPI (default 300), preprocessed (grayscale +
  autocontrast), and run through the OCR backend.
- **Stamp-noise stripping** — approval-stamp lines (`OK to proceed`, `Approved`, `Paid`, bare
  dates, …) are removed from the output so they don't pollute the extracted text.

The OCR engine sits behind a small **pluggable backend** interface:

| Backend | Status | Notes |
|---|---|---|
| `tesseract` | ✅ Default, local | Uses `--psm 6` (uniform text block); good for printed invoices. |
| `google_docai` | 🚧 Stub (planned) | Seam in place for cloud OCR; also reads handwriting. Wire the client and switch `OCR_BACKEND` to enable — no caller changes needed. |

### 3. Parse — [`core/parsing/parser.py`](core/parsing/parser.py)
`parse_invoice_text()` runs tolerant regex patterns (see
[`patterns.py`](core/parsing/patterns.py)) to pre-fill:

- **Vendor** (or the first non-empty line as a fallback letterhead guess)
- **Currency** — by ISO code (`NGN`, `USD`, `GBP`, `EUR`) or symbol (`₦ $ £ €`)
- **Subtotal** and **Grand Total** / **Amount Due**
- **Line items** — description, quantity, unit price, optional line total

The parser deliberately rejects lines that look like contact info (`tel`, `phone`, `fax`,
`email`, `address`) and number runs of 7+ digits (phone numbers) so they aren't captured as line
items. This is strictly **best-effort pre-fill** — every value is confirmed by a human next.

### 4. Stage
The extracted text, parsed data and temp-file path are stored in the **session** under a single
draft key. Nothing is persisted yet, so a user who closes the tab or uploads a replacement
leaves no orphan records or files.

### 5. Verify & Save — [`core/views.py`](core/views.py)
On the verify screen the user reviews everything and clicks **Mark as Verified**. Only then does
ProcEasy move the staged PDF into `dataset/pdfs/`, create the `InvoiceRecord`
(`verified=True`, `verified_at=now`), clear the draft from the session, and redirect back to the
upload page for the next document.

---

## The verification interface

[`verify.html`](core/templates/core/verify.html) is a two-column workspace: the **raw extracted
text** on the left (so you can cross-check against the source), and an **editable, structured
form** on the right. It is tuned for high-repetition data entry — quiet surface, one accent
colour, legible values.

**Invoice header fields:** Vendor · Cost Center · Currency · Subtotal *(auto)* · Tax
*(N/A · Inclusive · Exclusive)* · Tax Group · WHT · Grand Total *(auto)*.

**Live calculations (client-side JS):**

- **Line total** = `quantity × (unit price − discount)`, where discount is a fixed amount off
  each unit's price and can never drive the price below zero.
- **Subtotal** = sum of all line totals (read-only, auto-filled).
- **Grand total** = subtotal, plus VAT on top when Tax is **Exclusive** (the VAT rate is parsed
  from the selected Tax Group label, e.g. *"VAT 7.5% - FIRS"* → 7.5%). Inclusive / N/A leave the
  subtotal unchanged.
- **Description auto-fill** — a helpful default description is generated from the item name until
  the user edits it manually.

**Dynamic rows:** line items and payment terms can be added and removed on the fly. The item and
payment-term rows are defined **once** as partials
([`_invoice_item_row.html`](core/templates/core/_invoice_item_row.html),
[`_payment_term_row.html`](core/templates/core/_payment_term_row.html)) and reused for
server-rendered rows *and* the `<template>` the JavaScript clones for new rows — no duplicated
markup.

**Payment-terms validation:** each term has a type (*Advance payment · On GR/SC · On Invoice*)
and a percentage; the percentage field unlocks only after a type is chosen. The form **blocks
submission** unless the percentages sum to exactly **100%**, with a live running total badge.

**Handwritten flag:** a checkbox marks the invoice as handwritten, recorded on the record for
downstream model training.

Saved records can be reopened and re-edited at `/verify/<id>/`.

---

## Data model

A single model, [`InvoiceRecord`](core/models.py), backs the whole app:

| Field | Type | Purpose |
|---|---|---|
| `pdf_file` | `FileField` | The source PDF, stored under `dataset/pdfs/`. |
| `extracted_text` | `TextField` | Raw text from the extraction pipeline. |
| `parsed_data` | `JSONField` | The full structured invoice (header + items + payment terms). |
| `verified` | `BooleanField` | Whether a human has confirmed the data. |
| `is_handwritten` | `BooleanField` | Flags handwritten invoices for model training. |
| `verified_at` | `DateTimeField` | When it was verified. |
| `created_at` | `DateTimeField` | When the record was created. |

The `parsed_data` JSON shape is defined in [`core/schema.py`](core/schema.py) and mirrors the
form exactly:

```jsonc
{
  "invoice": {
    "vendor": "", "cost_center": "", "currency": "",
    "subtotal": "", "tax": "", "tax_group": "", "wht": "", "grand_total": ""
  },
  "items": [
    { "item_name": "", "description": "", "quantity": "",
      "unit_price": "", "discount": "", "line_total": "" }
  ],
  "payment_terms": [
    { "type": "", "percentage": "" }
  ]
}
```

---

## Domain notes (Nigerian procurement)

The tax and payment options reflect a Nigerian procurement context:

- **Tax Group** presets are FIRS VAT bands (Federal Inland Revenue Service): 0%, 5%, 7.5%.
- **WHT** presets are FIRS withholding-tax bands: 2%, 5%, 10%, 15%.
- **Payment-term types** map to common procurement milestones — *Advance payment*,
  *On GR/SC* (goods receipt / service confirmation) and *On Invoice*.
- **NGN** is a first-class currency alongside USD, GBP and EUR.

These are presets in the templates and can be extended for other jurisdictions.

---

## Project structure

```
ProcEasy/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── ProcEasy/                     # Django project config
│   ├── settings.py               # incl. OCR / extraction settings
│   ├── urls.py                   # /admin + core routes
│   ├── wsgi.py / asgi.py
├── core/                         # the single app
│   ├── models.py                 # InvoiceRecord
│   ├── views.py                  # upload → verify_draft → verify_invoice
│   ├── urls.py
│   ├── admin.py                  # InvoiceRecord admin
│   ├── schema.py                 # empty_invoice() / empty_item()
│   ├── extraction/
│   │   └── utils.py              # extract_text_from_pdf + OCR backends
│   ├── parsing/
│   │   ├── parser.py             # parse_invoice_text
│   │   └── patterns.py           # regex patterns
│   ├── templates/core/
│   │   ├── index.html            # upload page
│   │   ├── verify.html           # verification workspace
│   │   ├── _invoice_item_row.html
│   │   └── _payment_term_row.html
│   └── static/core/styles.css
└── dataset/pdfs/                 # verified source PDFs (the dataset)
```

### Routes

| URL | View | Purpose |
|---|---|---|
| `/` | `pdf_upload` | Upload a PDF; on submit, extract + parse + stage, then redirect to verify. |
| `/verify/` | `verify_draft` | Review a staged (unsaved) upload; persist on submit. |
| `/verify/<id>/` | `verify_invoice` | View / re-edit an already-saved record. |
| `/admin/` | Django admin | Browse, search and filter records. |

---

## Tech stack

- **Python · Django 5.2** — web framework, ORM, admin, sessions.
- **SQLite** — default development database.
- **pdfplumber · PyPDF2 · pdfminer.six** — digital PDF text extraction.
- **Tesseract OCR (pytesseract)** — local OCR for scanned pages.
- **pdf2image + Poppler** — rasterizing PDF pages for OCR.
- **Pillow** — image preprocessing (grayscale, autocontrast).
- Vanilla **HTML / CSS / JavaScript** — no frontend framework.

See [`requirements.txt`](requirements.txt) for pinned versions.

---

## Getting started

### Prerequisites

- **Python 3.11+**
- **Tesseract OCR** — required for the local OCR backend.
  - Windows default expected at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Poppler** — required by `pdf2image` to rasterize pages.
  - Windows default expected at `C:\poppler\Library\bin`

> Both paths are configurable in `settings.py` (see [Configuration](#configuration)) — point them
> at your own install locations on macOS/Linux or a non-default Windows path.

### Install & run

```bash
# 1. Clone and enter the project
cd ProcEasy

# 2. Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply database migrations
python manage.py migrate

# 5. (Optional) create an admin user
python manage.py createsuperuser

# 6. Run the development server
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** to upload an invoice, or
**http://127.0.0.1:8000/admin/** for the admin dashboard.

---

## Configuration

OCR and extraction behaviour is centralised in [`ProcEasy/settings.py`](ProcEasy/settings.py):

| Setting | Default | Purpose |
|---|---|---|
| `OCR_BACKEND` | `"tesseract"` | Which OCR engine to use (`tesseract` or `google_docai`). |
| `TESSERACT_CMD` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | Path to the Tesseract binary. |
| `POPPLER_PATH` | `C:\poppler\Library\bin` | Path to Poppler's `bin` (used by `pdf2image`). |
| `OCR_DPI` | `300` | Rasterization DPI for scanned pages (accuracy vs. speed). |
| `OCR_MIN_TEXT_CHARS` | `40` | Below this many non-space characters, a page is treated as scanned and sent to OCR. This is what stops a thin approval stamp from masking a scanned invoice. |

> **Security note:** the shipped `SECRET_KEY` is a development placeholder and `DEBUG = True`.
> Set a real secret key, disable debug, and configure `ALLOWED_HOSTS` before any deployment.

---

## Usage walkthrough

1. **Upload** a PDF invoice on the home page and submit.
2. ProcEasy extracts the text (digital or OCR), parses it, and takes you to the
   **verification** screen.
3. **Review** the raw text on the left; correct the pre-filled fields on the right.
4. **Add or remove** line items and payment terms as needed. Watch the line totals, subtotal and
   grand total update live.
5. Make sure the **payment terms sum to 100%** (the form won't submit otherwise).
6. Tick **Handwritten invoice** if applicable.
7. Click **Mark as Verified**. The PDF is saved into the dataset, the record is created, and you
   return to the upload page — the progress counter ticks up.
8. Reopen any saved record later at `/verify/<id>/` to re-check or amend it.

---

## Admin

The Django admin ([`core/admin.py`](core/admin.py)) lists every `InvoiceRecord` with:

- **Columns:** Vendor · Cost Center · Status (Verified/Pending) · Handwritten · Created.
- **Filters:** verified, handwritten, creation date.
- **Search:** across the stored `parsed_data`.
- **Ordering:** newest first.

---

## Roadmap

ProcEasy is being developed toward a full intelligent procurement assistant:

- [x] Universal PDF text extraction (digital + OCR)
- [x] Stamp-aware OCR fallback
- [x] Rule-based invoice parser
- [x] Human verification interface
- [x] Verified-dataset collection
- [ ] Cloud OCR backend (Google Document AI) for handwriting
- [ ] Machine-learning document-understanding model trained on the verified dataset
- [ ] Chrome extension to auto-populate ERP procurement forms
- [ ] End-to-end procurement workflow automation

---

## Limitations & notes

- The rule-based parser is **best-effort pre-fill** for noisy OCR output — it is not meant to be
  correct on its own; the human verification step is what guarantees data quality.
- Local Tesseract does **not** read handwriting reliably; that is what the Google Document AI
  backend seam is reserved for.
- The default configuration targets a Windows development environment (Tesseract/Poppler paths)
  and SQLite. Adjust `settings.py` for other platforms or a production database.
