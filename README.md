# ProcEasy

ProcEasy is a Django-based procurement automation platform designed to reduce the time and effort required to process procurement documents.

The project begins by extracting structured information from purchase invoices and is being developed toward an intelligent procurement assistant capable of:

- Extracting data from PDF invoices
- Parsing key procurement fields
- Building a verified invoice dataset
- Training document understanding models
- Automatically populating ERP procurement forms through a browser extension

## Current Features

- PDF upload
- Text extraction
- OCR fallback for scanned invoices
- Initial rule-based invoice parser

## Planned Features

- Human verification interface
- Dataset collection platform
- Machine learning model training
- Chrome extension for ERP autofill
- Procurement workflow automation

## Tech Stack

- Python
- Django
- PyPDF2
- pdfplumber
- Tesseract OCR
- Poppler
