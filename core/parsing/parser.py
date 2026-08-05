import re
import json

from ..schema import empty_invoice, empty_item
from . import patterns


def _detect_currency(text: str) -> str:
    """Best-effort currency from an ISO code or a symbol in the text."""
    code = re.search(patterns.CURRENCY_CODE, text, re.IGNORECASE)
    if code:
        return code.group(1).upper()

    for symbol, iso in patterns.CURRENCY_SYMBOLS.items():
        if symbol in text:
            return iso

    return ""


def parse_invoice_text(text: str) -> dict:
    """Parse invoice text into the structured shape the verify form expects.

    Best-effort only: this pre-fills the form from noisy OCR output; the human
    verifies and corrects every field before saving.
    """

    invoice_data = empty_invoice()

    # ---- Header fields ----
    vendor_match = re.search(patterns.VENDOR, text, re.IGNORECASE)
    if vendor_match:
        invoice_data["invoice"]["vendor"] = vendor_match.group(1).strip()
    else:
        # Fall back to the first non-empty line (often the vendor letterhead).
        first_line = next((l for l in text.splitlines() if l.strip()), "")
        invoice_data["invoice"]["vendor"] = first_line.strip()

    invoice_data["invoice"]["currency"] = _detect_currency(text)

    subtotal_match = re.search(patterns.SUBTOTAL, text, re.IGNORECASE)
    if subtotal_match:
        invoice_data["invoice"]["subtotal"] = subtotal_match.group(1).strip()

    total_match = re.search(patterns.TOTAL, text, re.IGNORECASE)
    if total_match:
        invoice_data["invoice"]["grand_total"] = total_match.group(2).strip()

    # ---- Line items ----
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Skip contact-info lines (Tel/Phone/Address) and rows whose numbers
        # look like phone numbers rather than quantities/prices.
        if patterns.ITEM_REJECT.search(line):
            continue

        item_match = re.match(patterns.ITEM, line)
        if not item_match:
            continue

        # A 7+ digit run in the quantity/price captures means a phone number
        # slipped through -- reject the row.
        if patterns.PHONE_LIKE.search(item_match.group(2)) or patterns.PHONE_LIKE.search(item_match.group(3)):
            continue

        description = item_match.group(1).strip()
        item = empty_item()
        item["item_name"] = description
        item["description"] = description
        item["quantity"] = item_match.group(2).strip()
        item["unit_price"] = item_match.group(3).strip()
        if item_match.group(4):
            item["line_total"] = item_match.group(4).strip()

        invoice_data["items"].append(item)

    return invoice_data


if __name__ == "__main__":
    sample_text = """
    Vendor: ABC Supplies Ltd.
    Currency: NGN
    Item            Qty   Price   Total
    Steel Rod       20    50.00   1000.00
    Cement Bags     50    10.00   500.00
    Subtotal: 1500.00
    Grand Total: 1575.00
    """

    parsed = parse_invoice_text(sample_text)
    print(json.dumps(parsed, indent=2))
