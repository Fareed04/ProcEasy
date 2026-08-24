"""Browser-automation engine: push extracted RFQ pricing into the web ERP.

Drives only the RFQR pricing grid of the procurement ERP with Playwright,
using the structured JSON produced by the extraction/dedup pipeline
(``test_invoice.json``). The browser opens *visible* and everything up to the
populated pricing grid is done by hand: the script pauses with ``input()`` so
you log in, reach your RFQ dashboard, and open the target record yourself --
no credentials are stored or typed by the automation.

Safety guards
-------------
* Fills ONLY the 1-indexed ``#svt_unit_rate_{n}_hidden`` rate inputs.
* Issues NO clicks, saves, or submit/complete actions of any kind.
* After the rows are filled it hands control back and leaves the browser open
  for manual human validation and manual submission.

Flow
----
1. Load the invoice JSON.
2. Launch a headed Chromium window and navigate to the ERP.
3. Pause: you log in, open the RFQ dashboard, and load the record so the
   pricing grid is fully populated on screen.
4. Fill each item's ``unit_price`` into its 1-indexed rate input.
5. Standby: browser stays open; you validate and submit manually.

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
ERP_URL = "https://proc.mrsholdings.com/"  # TODO: your ERP entry URL

# Repo root is two levels up from core/automation/.
INVOICE_PATH = Path(__file__).resolve().parents[2] / "test_invoice.json"

# DOM handles -- PLACEHOLDER. Replace with your ERP's real selector.
SELECTORS = {
    # RFQR pricing grid -- live: one 1-indexed hidden rate input per row.
    # {n} is the JSON row index + 1 (the grid numbering is 1-based).
    "unit_price": "#svt_unit_rate_{n}_hidden",
}


def load_invoice(path=INVOICE_PATH) -> dict:
    """Load the structured invoice JSON produced by the pipeline."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def fill_unit_prices(page: Page, items: list) -> None:
    """RFQR phase: inject each line item's unit_price into its 1-indexed grid input.

    The live pricing grid exposes one rate input per row, addressed by a
    1-indexed id: JSON row ``index`` (0-based) maps to
    ``#svt_unit_rate_{index + 1}_hidden``. These inputs stay hidden until
    focused, so Playwright's visibility-gated ``fill()`` cannot reach the
    rows past the first. Instead we run a native browser evaluation that force-
    injects the price into ``el.value`` and manually dispatches ``input`` and
    ``change`` (both bubbling) so the grid registers the edit and recalculates
    totals. This value write is the ONLY DOM mutation the script performs --
    it never clicks, saves, or submits.
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

        # Force-inject the value: these inputs are hidden until focused, so
        # fill() is blocked on visibility. Set el.value directly, then fire the
        # bubbling input+change events the grid listens on to recalc totals.
        field.evaluate(
            "(el, val) => {"
            " el.value = val;"
            " el.dispatchEvent(new Event('input', { bubbles: true }));"
            " el.dispatchEvent(new Event('change', { bubbles: true }));"
            " }",
            price,
        )
        print(f"  RFQR row {index + 1}: {item.get('item_name', '')} <- {price}")
        filled += 1

    print(f"RFQR phase: filled {filled} price field(s).")


def main() -> None:
    data = load_invoice()
    items = data.get("items", [])
    vendor = data.get("invoice", {}).get("vendor", "?")
    print(f"Loaded '{vendor}' -- {len(items)} item(s).")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible window
        page = browser.new_page()
        page.goto(ERP_URL)

        # Single manual-setup pause: the human logs in, navigates, and selects
        # the record so the pricing grid is fully populated before we touch it.
        input(
            "\nPlease log into the ERP, navigate to your pending RFQ dashboard, "
            "and select the specific 4-item file you want to process. Once the "
            "pricing grid populates completely on your monitor, return here and "
            "press Enter."
        )

        fill_unit_prices(page, items)

        # System standby -- the automation is done and deliberately inert: no
        # clicks, no save, no submit were ever issued. The browser is left fully
        # open so a human can validate the grid and submit manually.
        print("\n[STANDBY] All pricing rows filled. No save/submit was triggered.")
        print("Review the pricing grid in the open browser window.")
        input("Press Enter here only when you are finished validating... ")


if __name__ == "__main__":
    main()
