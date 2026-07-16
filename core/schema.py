def empty_invoice():
    return {
        "invoice": {
            "vendor": "",
            "invoice_number": "",
            "invoice_date": "",
            "currency": "",

            "subtotal": "",
            "tax": "",
            "grand_total": "",

            "payment_terms": "",

            "purchase_order_reference": "",
            "delivery_note_reference": ""
        },

        "items": []
    }


def empty_item():
    return {
        "description": "",
        "quantity": "",
        "unit": "",
        "unit_price": "",
        "discount": "",
        "tax": "",
        "line_total": ""
    }