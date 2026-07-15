# parser.py
import re
import json

def parse_invoice_text(text: str) -> dict:
    """
    Parse invoice text and return structured data.
    Uses regex + simple rules.
    """

    invoice_data = {
        "vendor": None,
        "invoice_number": None,
        "date": None,
        "items": [],
        "subtotal": None,
        "tax": None,
        "total": None,  # renamed from grand_total for consistency
        "payment_terms": None,
    }

    # Regex patterns
    vendor_match = re.search(r"Vendor\s*[:\-]?\s*(.+)", text, re.IGNORECASE)

    invoice_number_match = re.search(
        r"(?:Invoice\s*(?:No\.?|Number)?\s*[:\-]?\s*|INV[-\s]*)\s*([\w\-\/]+)",
        text,
        re.IGNORECASE,
    )

    date_match = re.search(
        r"(?:Invoice\s*Date|Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})",
        text,
        re.IGNORECASE,
    )

    subtotal_match = re.search(r"Subtotal\s*[:\-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    tax_match = re.search(r"(Tax|VAT)\s*[:\-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    total_match = re.search(r"(Total|Grand\s*Total|Amount\s*Due)\s*[:\-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    payment_terms_match = re.search(r"(Net\s*\d+\s*days|Due\s*on\s*receipt)", text, re.IGNORECASE)

    # Assign values
    if vendor_match:
        invoice_data["vendor"] = vendor_match.group(1).strip()
    else:
        # fallback: first non-empty line
        first_line = next((l for l in text.splitlines() if l.strip()), None)
        invoice_data["vendor"] = first_line.strip() if first_line else None

    if invoice_number_match:
        invoice_data["invoice_number"] = invoice_number_match.group(1).strip()

    if date_match:
        invoice_data["date"] = date_match.group(1).strip()

    if subtotal_match:
        invoice_data["subtotal"] = subtotal_match.group(1).strip()

    if tax_match:
        invoice_data["tax"] = tax_match.group(2).strip()

    if total_match:
        invoice_data["total"] = total_match.group(2).strip()

    if payment_terms_match:
        invoice_data["payment_terms"] = payment_terms_match.group(1).strip()

    # Item parsing
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        # Match: description | quantity | price | optional total
        item_match = re.match(
            r"(.+?)\s+(\d+)\s+([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?",
            line
        )
        if item_match:
            invoice_data["items"].append({
                "description": item_match.group(1).strip(),
                "quantity": int(item_match.group(2)),
                "price": item_match.group(3),
                "total": item_match.group(4) if item_match.group(4) else None,
            })

    return invoice_data


if __name__ == "__main__":
    # quick test
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




# # parser.py
# import re
# import json

# def parse_invoice_text(text: str) -> dict:
#     """
#     Parse invoice text and return structured data.
#     Uses regex + simple rules.
#     """

#     invoice_data = {
#         "vendor": None,
#         "invoice_number": None,
#         "date": None,
#         "items": [],
#         "subtotal": None,
#         "tax": None,
#         "grand_total": None,
#         "payment_terms": None,
#     }

#     # Regex patterns
#     vendor_match = re.search(r"Vendor\s*[:\-]?\s*(.+)", text, re.IGNORECASE)

#     # Improved invoice number regex (fixes "OICE" issue)
#     invoice_number_match = re.search(
#         r"(?:Invoice\s*(?:No\.?|Number)?\s*[:\-]?\s*|INV[-\s]*)\s*([\w\-\/]+)",
#         text,
#         re.IGNORECASE,
#     )

#     date_match = re.search(r"Date\s*[:\-]?\s*(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})", text, re.IGNORECASE)
#     subtotal_match = re.search(r"Subtotal\s*[:\-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
#     tax_match = re.search(r"(Tax|VAT)\s*[:\-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
#     total_match = re.search(r"(Total|Grand\s*Total)\s*[:\-]?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
#     payment_terms_match = re.search(r"(Net\s*\d+\s*days|Due\s*on\s*receipt)", text, re.IGNORECASE)

#     # Assign values
#     if vendor_match:
#         invoice_data["vendor"] = vendor_match.group(1).strip()

#     if invoice_number_match:
#         invoice_data["invoice_number"] = invoice_number_match.group(1).strip()

#     if date_match:
#         invoice_data["date"] = date_match.group(1).strip()

#     if subtotal_match:
#         invoice_data["subtotal"] = subtotal_match.group(1).strip()

#     if tax_match:
#         invoice_data["tax"] = tax_match.group(2).strip()

#     if total_match:
#         invoice_data["grand_total"] = total_match.group(2).strip()

#     if payment_terms_match:
#         invoice_data["payment_terms"] = payment_terms_match.group(1).strip()

#     # Item parsing - more flexible
#     lines = text.splitlines()
#     for line in lines:
#         line = line.strip()
#         # Match: description | quantity | price | optional total
#         item_match = re.match(
#             r"(.+?)\s+(\d+)\s+([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?",
#             line
#         )
#         if item_match:
#             invoice_data["items"].append({
#                 "name": item_match.group(1).strip(),
#                 "quantity": int(item_match.group(2)),
#                 "unit_price": item_match.group(3),
#                 "total": item_match.group(4) if item_match.group(4) else None,
#             })

#     return invoice_data


# if __name__ == "__main__":
#     # quick test
#     sample_text = """
#     Vendor: ABC Supplies Ltd.
#     Invoice No: INV-2025-0091
#     Date: 29-09-2025
#     Item            Qty   Price   Total
#     Steel Rod       20    50.00   1000.00
#     Cement Bags     50    10.00   500.00
#     Subtotal: 1500.00
#     Tax: 75.00
#     Grand Total: 1575.00
#     Payment Terms: Net 30 days
#     """

#     parsed = parse_invoice_text(sample_text)
#     print(json.dumps(parsed, indent=2))
