import re

# Invoice field patterns
#
# These run against OCR'd text from scanned invoices, so they are deliberately
# tolerant: optional punctuation, flexible whitespace, and amounts that may use
# "," or "." as separators. Parsing is best-effort pre-fill -- the human
# verifies every value on the form.

VENDOR = r"Vendor\s*[:\-]?\s*(.+)"

# Currency by ISO code or symbol anywhere in the text.
CURRENCY_CODE = r"\b(NGN|USD|GBP|EUR)\b"
CURRENCY_SYMBOLS = {
    "₦": "NGN",
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
}

# Lines that look like contact info rather than a priced line item. Used to
# reject phone/tel rows the ITEM regex would otherwise capture as items.
ITEM_REJECT = re.compile(r"\b(tel|phone|fax|line|email|address)\b", re.IGNORECASE)

# A run of 7+ digits with no decimal point -- almost always a phone number,
# not a quantity or price.
PHONE_LIKE = re.compile(r"\d{7,}")

SUBTOTAL = r"Sub\s*total\s*[:\-]?\s*([\d,]+(?:\.\d{2})?)"

# "Total" / "Grand Total" / "Amount Due" followed by an amount. Group 2 = amount.
# \b before Total avoids matching the "total" inside "Subtotal".
TOTAL = r"\b(Grand\s*Total|Amount\s*Due|Total)\s*[:\-]?\s*([\d,]+(?:\.\d{2})?)"

# A line item: description, quantity, unit price, optional line total.
# Quantity may carry a unit suffix ("5,000tons") so we capture digits loosely.
ITEM = (
    r"(.+?)\s+([\d,]+)\s*[a-zA-Z]*\s+([\d,]+(?:\.\d{2})?)"
    r"(?:\s+[₦N$£€]?\s*([\d,]+(?:\.\d{2})?))?"
)
