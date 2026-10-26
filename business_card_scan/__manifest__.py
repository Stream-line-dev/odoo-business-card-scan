# -*- coding: utf-8 -*-
{
    "name": "Business Card Scanner",
    "version": "19.0.1.0.0",
    "category": "Sales/CRM",
    "summary": "Take a photo of a business card and create a CRM lead, no IAP credits",
    "description": """
Business Card Scanner
==========================
- Take a photo on mobile or upload images from your computer
- OCR runs in the browser (Tesseract.js): no IAP credits, nothing to install on the server
- Automatic detection: name, company, job position, email, phones, website, address
- Review screen before creating the lead
- Duplicate detection (existing contact and lead by email)
- Card photo attached to the lead
    """,
    "author": "Stream lean industry 4.0",
    "license": "LGPL-3",
    "depends": ["crm"],
    "data": [
        "security/ir.model.access.csv",
        "views/business_card_scan_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "business_card_scan/static/src/**/*",
        ],
    },
    "installable": True,
    "application": True,
    "sequence": 26,
}
