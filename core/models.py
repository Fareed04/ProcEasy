from django.db import models


class InvoiceRecord(models.Model):
    pdf_file = models.FileField(upload_to="dataset/pdfs/")
    extracted_text = models.TextField()

    parsed_data = models.JSONField()

    verified = models.BooleanField(default=False)
    
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        invoice_number = self.parsed_data.get("invoice", {}).get("invoice_number", "Unknown")
        return invoice_number