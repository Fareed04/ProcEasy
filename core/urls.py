from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.pdf_upload, name="pdf_upload"),
    path("verify/<int:pk>/", views.verify_invoice, name="verify_invoice"),
]
