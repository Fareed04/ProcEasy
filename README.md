# ProcEasy

**Zero-typing procurement.** Drop an invoice PDF anywhere in the browser → a free Gemini 2.5 Flash vision pass returns structured JSON → drag or click the values straight into any ERP grid.

`Django 5.2` · `Chrome MV3` · `Gemini 2.5 Flash` · `SQLite` · `Playwright`

---

## Pipeline

```
 PDF / image                Chrome Extension (MV3)              Django backend
 ───────────       ┌──────────────────────────────┐      ┌──────────────────────┐
  drop ──────────▶ │  AssistiveTouch dot → card   │─POST▶│  /?format=json       │
  Ctrl+V ────────▶ │  Shadow DOM · edge-snap      │      │  Gemini 2.5 Flash    │
  browse ────────▶ │  conic loading ring          │◀JSON─│  inline-bytes vision │
                   └──────────────┬───────────────┘      └──────────┬───────────┘
                                  │                                 │
                   chrome.storage.local (all tabs)          InvoiceRecord (SQLite)
                                  │
                   draggable chips → click-to-inject → ERP cell
```

---

## Core features

### 🧠 Free Gemini 2.5 Flash vision backend
`core/views.py` → `_extract_via_gateway()`

| | |
|---|---|
| **Transport** | Raw bytes as a native `types.Part.from_bytes()` inline part — no base64 URI, no OCR pre-pass |
| **Schema lock** | System prompt is generated from `core/schema.py` at import time; `response_mime_type="application/json"` forces bare JSON |
| **Determinism** | `temperature=0`, `max_output_tokens=8192` |
| **Resilience** | Three-tier JSON salvage (raw → de-fenced → brace-slice); graceful `502`/`503` on auth, network, or safety-block failure |
| **Cost** | AI Studio free tier — handles scans, photos, and handwriting that local Tesseract cannot |

### 🗄️ Django database logging
Every gateway extraction is persisted **best-effort** as an `InvoiceRecord` — source PDF to `dataset/pdfs/`, raw model reply to `extracted_text`, structured payload to `parsed_data` (JSONField). Failures are logged, never raised: a storage/DB error can't turn a good extraction into a 500. Extension rows land `verified=False`; only the human verify flow sets `verified=True` + `verified_at`, so every row accrues to a labelled training dataset.

### 🔵 AssistiveTouch floating dot
`core/extension/content.js` — iOS-style 44px puck, Shadow-DOM isolated so host CSS never bleeds in.

- **Idle fade** to 40% after 5s, wakes on hover
- **Edge-snap physics** — `cubic-bezier(.22,1,.36,1)` settle to the nearer vertical edge, with an rAF follow loop gluing the card during flight
- **Conic-gradient loading ring** masked to a 3px annulus while the upload is in flight
- **Three capture paths** — drop directly on the puck, drop in the card, or hover + `Ctrl+V` (native `paste` event *and* async Clipboard API)

### 🔗 Cross-tab persistence
Successful extractions are written to `chrome.storage.local` and rehydrated on every content-script load. A `storage.onChanged` listener live-syncs already-open tabs, with an echo guard (`lastStored`) so the writing tab doesn't re-render its own payload. Parse once — every tab has the data.

### ⚡ Framework-level click-to-inject & cell bypassing
The hard problem: AG-Grid / Handsontable-style ERPs render cells as **static text** and only swap in a real `<input>` on click, so a native HTML5 drop lands on a dead node.

**Drag path** — while a ProcEasy chip is airborne, a capture-phase `dragenter`/`dragover` interceptor `focus()`+`click()`s the hovered cell to spin up its editor *before* the drop lands. Three guards: armed only during a chip drag, fires once per cell entry, and only ever wakes editable targets (an `UNSAFE_INPUT_TYPES` deny-list keeps synthetic clicks off buttons, submits, checkboxes, and file inputs).

**Click path** — for ERPs that reject native drop payloads. `Copy` stages a value; the next click into an editable field writes it via the **prototype's native `value` setter** (`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set`), so React/Vue value trackers actually observe the change, then dispatches `input` + `change` so controlled components and dependent totals recompute. Deliberately non-blocking: the write defers one tick and re-resolves to the live editor, letting the grid's own click through. One-shot — the buffer clears after a single injection.

---

## Installation

```bash
git clone <repo-url> && cd ProcEasy
python -m venv venv && venv\Scripts\activate      # PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
```

**Configure the key** (never commit it):

```powershell
$env:GEMINI_API_KEY = "your-ai-studio-key"        # aistudio.google.com/apikey
$env:GEMINI_MODEL   = "gemini-2.5-flash"          # optional; -pro for higher accuracy
python manage.py runserver
```

**Load the extension:** `chrome://extensions` → Developer mode → **Load unpacked** → `core/extension/`

**Optional** (local OCR path for the browser form only — the Gemini path needs neither):
Tesseract → `C:\Program Files\Tesseract-OCR` · Poppler → `C:\poppler\Library\bin` (override via `TESSERACT_CMD` / `POPPLER_PATH` in `settings.py`).

| Endpoint | Purpose |
|---|---|
| `POST /?format=json` | Gemini extraction API (extension; CSRF-exempt) |
| `GET /` | Browser upload form (local OCR + regex parser) |
| `/verify/` · `/verify/<pk>/` | Human verification of a draft / saved record |
| `/admin/` | Browse, filter, and audit all records |

---

## Roadmap

| Phase | Name | Scope | Status |
|:--|:--|:--|:--|
| **1** | 🧙 **Wizard** | Floating-dot capture overlay · Gemini vision extraction · DB logging · cross-tab sync · click-to-inject cell bypass | ✅ **Shipped** |
| **2** | 🦸 **Hero** | Full-grid autofill via Playwright (`core/automation/erp_sync.py`) · batch line-item dedup · Google Document AI handwriting backend · confidence scoring + review queue | 🚧 In progress |
| **3** | ☁️ **SaaS** | Multi-tenant auth & orgs · Postgres + object storage · hosted API keys · usage billing · audit trails · production CORS/`DEBUG` hardening | 📋 Planned |

---

## Layout

```
core/
├── views.py            Gemini gateway, upload, verify, DB logging
├── models.py           InvoiceRecord
├── schema.py           Canonical invoice shape (drives the LLM prompt)
├── extraction/utils.py Pluggable OCR (Tesseract | Document AI stub)
├── parsing/            Rule-based fallback parser + regex patterns
├── automation/         deduplicate.py · erp_sync.py (Playwright)
└── extension/          manifest.json · content.js · popup.js
```

> **Dev-only defaults:** `DEBUG=True`, `CORS_ALLOW_ALL_ORIGINS=True`, and SQLite are convenience settings for local work — replace all three before any deployment.
