from django.contrib import admin
from .models import InvoiceRecord


@admin.register(InvoiceRecord)
class InvoiceRecordAdmin(admin.ModelAdmin):

    list_display = (
        "vendor_name",
        "verification_status",
        "created_at",
    )

    list_filter = (
        "verified",
        "created_at",
    )

    search_fields = (
        "parsed_data",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(description="Vendor")
    def vendor_name(self, obj):
        return obj.parsed_data.get(
            "invoice",
            {}
        ).get(
            "vendor",
            "Unknown"
        )

    @admin.display(description="Status")
    def verification_status(self, obj):
        return "Verified" if obj.verified else "Pending"