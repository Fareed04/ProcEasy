"""First browser-automation engine: push extracted invoice data into the web ERP.

Drives the RFQ and RFQR stages of the procurement ERP with Playwright, using
the structured JSON produced by the extraction/dedup pipeline
(``test_invoice.json``). The browser opens *visible* and login is manual: the
script pauses with ``input()`` so you authenticate yourself -- no credentials
are stored or typed by the automation.

Flow
----
1. Load the invoice JSON.
2. Launch a headed Chromium window and navigate to the ERP.
3. Pause for manual login (and to reach the RFQ screen).
4. RFQ phase  -- add + fill one payment-term row per ``payment_terms`` entry.
5. RFQR phase -- type each item's ``unit_price`` into its pre-pulled row.

Setup:
    pip install playwright
    playwright install chromium

Run:
    python core/automation/erp_sync.py
"""

import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


# --------------------------------------------------------------------------- #
# Configuration -- point these at your ERP before running.
# --------------------------------------------------------------------------- #
ERP_URL = "https://your-erp.example.com/"  # TODO: your ERP entry URL

# Repo root is two levels up from core/automation/.
INVOICE_PATH = Path(__file__).resolve().parents[2] / "test_invoice.json"

# DOM handles -- PLACEHOLDERS. Replace each with your ERP's real selector.
SELECTORS = {
    # RFQ screen:
    "add_payment_term": "button:has-text('+')",          # the [+] add-row button
    "payment_type": "input[name='payment_term_type']",   # type field in a term row
    "payment_percentage": "input[name='payment_term_percentage']",  # % field
    # RFQR pricing grid -- live: one 1-indexed hidden rate input per row.
    # {n} is the JSON row index + 1 (the grid numbering is 1-based).
    "unit_price": "#svt_unit_rate_{n}_hidden",
}


def load_invoice(path=INVOICE_PATH) -> dict:
    """Load the structured invoice JSON produced by the pipeline."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def fill_payment_terms(page: Page, payment_terms: list) -> None:
    """RFQ phase: add one row per payment term and fill its type + percentage.

    Clicks the [+] button for each term, then fills the newly added (last)
    row. A no-op when the invoice carries no payment terms.
    """
    for index, term in enumerate(payment_terms, start=1):
        page.locator(SELECTORS["add_payment_term"]).click()
        # The row just added is the last matching one on the page.
        page.locator(SELECTORS["payment_type"]).last.fill(str(term.get("type", "")).strip())
        page.locator(SELECTORS["payment_percentage"]).last.fill(str(term.get("percentage", "")).strip())
        print(f"  RFQ term {index}: {term.get('type', '')} / {term.get('percentage', '')}")
    print(f"RFQ phase: filled {len(payment_terms)} payment term(s).")


def fill_unit_prices(page: Page, items: list) -> None:
    """RFQR phase: inject each line item's unit_price into its 1-indexed grid input.

    The live pricing grid exposes one rate input per row, addressed by a
    1-indexed id: JSON row ``index`` (0-based) maps to
    ``#svt_unit_rate_{index + 1}_hidden``. Each targeted field is cleared and
    then filled with the JSON ``unit_price`` string.
    """
    filled = 0
    for index, item in enumerate(items):
        price = str(item.get("unit_price", "")).strip()
        if not price:
            continue

        selector = SELECTORS["unit_price"].format(n=index + 1)  # grid is 1-indexed
        field = page.locator(selector)
        if field.count() == 0:
            print(f"  ! no grid input at {selector}; stopping after {filled} filled")
            break

        field.clear()       # clear any existing value ...
        field.fill(price)   # ... then inject the JSON unit_price
        print(f"  RFQR row {index + 1}: {item.get('item_name', '')} <- {price}")
        filled += 1

    print(f"RFQR phase: filled {filled} price field(s).")


def main() -> None:
    data = load_invoice()
    items = data.get("items", [])
    payment_terms = data.get("payment_terms", [])
    vendor = data.get("invoice", {}).get("vendor", "?")
    print(f"Loaded '{vendor}' -- {len(items)} item(s), {len(payment_terms)} payment term(s).")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible window
        page = browser.new_page()
        page.goto(ERP_URL)

        input("\n[1/3] Log in, open the RFQ screen, then press Enter... ")
        fill_payment_terms(page, payment_terms)

        input("\n[2/3] Open the RFQR screen (item rows pre-pulled), then press Enter... ")
        fill_unit_prices(page, items)

        input("\n[3/3] Review the filled forms, then press Enter to close the browser... ")
        browser.close()


if __name__ == "__main__":
    main()
