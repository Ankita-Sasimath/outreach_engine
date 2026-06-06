from __future__ import annotations

import os

import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.utils.logger import get_logger

logger = get_logger("brevo")


class BrevoClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("BREVO_API_KEY", "")
        self.base_url = os.getenv("BREVO_BASE_URL", "https://api.brevo.com/v3")
        self.from_email = os.getenv("BREVO_FROM_EMAIL", "")
        self.from_name = os.getenv("BREVO_FROM_NAME", "Outreach Engine")
        self.timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        if not self.api_key:
            logger.warning("BREVO_API_KEY not set. Skipping send.")
            return False
        if not self.from_email:
            logger.warning("BREVO_FROM_EMAIL not set. Skipping send.")
            return False

        url = f"{self.base_url}/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        payload = {
            "sender": {"email": self.from_email, "name": self.from_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    logger.error("Brevo send failed: %s %s", resp.status_code, resp.text)
                    return False
                return True
        except Exception as e:
            logger.exception("Brevo send error: %s", e)
            return False

