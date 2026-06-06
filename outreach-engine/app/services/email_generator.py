from __future__ import annotations


def generate_outreach_email(company_name: str, name: str) -> tuple[str, str]:
    subject = f"Helping {company_name} improve outreach"

    body = f"""Hi {name},\n\nI came across {company_name} and noticed your growth in the software industry.\n\nWe help businesses automate lead generation and outreach workflows.\n\nI would love to connect and explore possible collaboration.\n\nRegards,\nAnkita"""

    # Basic HTML wrapping
    html_body = "<pre style=\"font-family:inherit;white-space:pre-wrap\">" + body + "</pre>"

    return subject, html_body

