from django.urls import path
from . import views

urlpatterns = [
    path("", views.pdf_upload, name="pdf_upload"),
    path("verify/", views.verify_draft, name="verify_draft"),
    path("verify/<int:pk>/", views.verify_invoice, name="verify_invoice"),
]
