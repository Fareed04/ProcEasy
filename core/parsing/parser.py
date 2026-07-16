import re
import json
from .schema import empty_invoice, empty_item
from . import patterns


def parse_invoice_text(text: str) -> dict:
    """
    Parse invoice text and return structured invoice data.
    """

    invoice_data = empty_invoice()

    # Field extraction
    vendor_match = re.search(patterns.VENDOR, text, re.IGNORECASE)

    invoice_number_match = re.search(
        patterns.INVOICE_NUMBER,
        text,
        re.IGNORECASE,
    )

    date_match = re.search(
        patterns.DATE,
        text,
        re.IGNORECASE,
    )

    subtotal_match = re.search(
        patterns.SUBTOTAL,
        text,
        re.IGNORECASE,
    )

    tax_match = re.search(
        patterns.TAX,
        text,
        re.IGNORECASE,
    )

    total_match = re.search(
        patterns.TOTAL,
        text,
        re.IGNORECASE,
    )

    payment_terms_match = re.search(
        patterns.PAYMENT_TERMS,
        text,
        re.IGNORECASE,
    )

    # Populate invoice section
    if vendor_match:
        invoice_data["invoice"]["vendor"] = vendor_match.group(1).strip()
    else:
        first_line = next((l for l in text.splitlines() if l.strip()), "")
        invoice_data["invoice"]["vendor"] = first_line.strip()

    if invoice_number_match:
        invoice_data["invoice"]["invoice_number"] = invoice_number_match.group(1).strip()

    if date_match:
        invoice_data["invoice"]["invoice_date"] = date_match.group(1).strip()

    if subtotal_match:
        invoice_data["invoice"]["subtotal"] = subtotal_match.group(1).strip()

    if tax_match:
        invoice_data["invoice"]["tax"] = tax_match.group(2).strip()

    if total_match:
        invoice_data["invoice"]["grand_total"] = total_match.group(2).strip()

    if payment_terms_match:
        invoice_data["invoice"]["payment_terms"] = payment_terms_match.group(1).strip()

    # Parse line items
    for line in text.splitlines():
        line = line.strip()

        item_match = re.match(
            patterns.ITEM,
            line,
        )

        if item_match:
            item = empty_item()

            item["description"] = item_match.group(1).strip()
            item["quantity"] = item_match.group(2).strip()
            item["unit_price"] = item_match.group(3).strip()

            if item_match.group(4):
                item["line_total"] = item_match.group(4).strip()

            invoice_data["items"].append(item)

    return invoice_data


if __name__ == "__main__":
    sample_text = """
    Vendor: ABC Supplies Ltd.
    Invoice No: INV-2025-0091
    Date: 29-09-2025
    Item            Qty   Price   Total
    Steel Rod       20    50.00   1000.00
    Cement Bags     50    10.00   500.00
    Subtotal: 1500.00
    Tax: 75.00
    Grand Total: 1575.00
    Payment Terms: Net 30 days
    """

    parsed = parse_invoice_text(sample_text)
    print(json.dumps(parsed, indent=2))