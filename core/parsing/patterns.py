# Invoice field patterns

VENDOR = r"Vendor\s*[:\-]?\s*(.+)"

INVOICE_NUMBER = (
    r"(?:Invoice\s*(?:No\.?|Number)?\s*[:\-]?\s*|INV[-\s]*)\s*([\w\-\/]+)"
)

DATE = (
    r"(?:Invoice\s*Date|Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})"
)

SUBTOTAL = r"Subtotal\s*[:\-]?\s*([\d,]+\.\d{2})"

TAX = r"(Tax|VAT)\s*[:\-]?\s*([\d,]+\.\d{2})"

TOTAL = (
    r"(Total|Grand\s*Total|Amount\s*Due)\s*[:\-]?\s*([\d,]+\.\d{2})"
)

PAYMENT_TERMS = r"(Net\s*\d+\s*days|Due\s*on\s*receipt)"

ITEM = (
    r"(.+?)\s+(\d+)\s+([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?"
)