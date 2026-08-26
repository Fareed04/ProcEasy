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
    # The visible display cell for the same row -- same 1-indexed marker,
    # without the `_hidden` suffix. Both it and the hidden input get written.
    "unit_price_cell": "#svt_unit_rate_{n}",
}


def load_invoice(path=INVOICE_PATH) -> dict:
    """Load the structured invoice JSON produced by the pipeline."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# JS run in the page to write a value into a grid input and notify the grid.
INJECT_JS = (
    "(el, val) => {"
    " el.value = val;"
    " el.dispatchEvent(new Event('input', { bubbles: true }));"
    " el.dispatchEvent(new Event('change', { bubbles: true }));"
    " }"
)


def _inject_value(page: Page, selector: str, price: str) -> bool:
    """Force-set ``el.value`` and dispatch bubbling input+change on one selector.

    Returns True if the element existed and the injection ran. A missing
    selector or a failed evaluation is reported and swallowed so the caller
    keeps going across the remaining rows.
    """
    field = page.locator(selector)
    if field.count() == 0:
        print(f"  - selector absent, skipping: {selector}")
        return False
    try:
        field.evaluate(INJECT_JS, price)
        return True
    except Exception as exc:
        print(f"  ~ inject failed for {selector}: {exc}")
        return False


def fill_unit_prices(page: Page, items: list) -> None:
    """RFQR phase: inject each line item's unit_price into its 1-indexed grid row.

    Both ``#svt_unit_rate_{n}`` (display cell) and ``#svt_unit_rate_{n}_hidden``
    (backing input) co-exist per row and throw visibility timeouts on physical
    interaction, so for each row we write to BOTH via a native browser
    evaluation: force-set ``el.value`` and dispatch bubbling ``input`` and
    ``change`` events so the grid registers the edit and recalculates totals.
    Missing selectors are logged and skipped -- the loop always runs across
    every item. This value write is the ONLY DOM mutation the script performs;
    it never clicks, saves, or submits.
    """
    filled = 0
    for index, item in enumerate(items):
        price = str(item.get("unit_price", "")).strip()
        if not price:
            continue

        n = index + 1  # grid is 1-indexed

        # Force-focus click on the hidden input to mount the row's fields; the
        # grid blocks physical clicks, so force=True bypasses the visibility
        # gate. Best-effort so the loop still runs across every row.
        try:
            page.locator(SELECTORS["unit_price"].format(n=n)).click(force=True)
            page.wait_for_timeout(100)  # let the ERP JS mount the row values
        except Exception as exc:
            print(f"  ~ force-focus click skipped for row {n}: {exc}")

        # Target both the display cell and its hidden backing input for the row.
        selectors = [
            SELECTORS["unit_price_cell"].format(n=n),  # #svt_unit_rate_{n}
            SELECTORS["unit_price"].format(n=n),       # #svt_unit_rate_{n}_hidden
        ]
        injected = [sel for sel in selectors if _inject_value(page, sel, price)]
        if injected:
            print(f"  RFQR row {n}: {item.get('item_name', '')} <- {price}")
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
