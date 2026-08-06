def empty_invoice():
    """Structured invoice matching the fields the verify form reads/writes.

    Keys mirror core/views.py `_collect_invoice_data` and the templates so a
    parsed draft pre-fills the form directly. Category selects (tax, tax_group,
    wht) are left blank on purpose -- they are human-chosen, not parsed.
    """
    return {
        "invoice": {
            "vendor": "",
            "cost_center": "",
            "currency": "",

            "subtotal": "",
            "tax": "",
            "tax_group": "",
            "wht": "",
            "grand_total": "",
        },

        "items": [],
        "payment_terms": [],
    }


def empty_item():
    return {
        "item_name": "",
        "description": "",
        "quantity": "",
        "unit_price": "",
        "discount": "",
        "line_total": "",
    }
