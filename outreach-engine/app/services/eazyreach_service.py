from __future__ import annotations

from typing import Any

import os
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.utils.logger import get_logger

logger = get_logger("eazyreach")


class EazyreachClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("EAZYREACH_API_KEY", "")
        self.timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
        self.base_url = os.getenv("EAZYREACH_BASE_URL", "https://eazyreach.com")

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def resolve_email(self, linkedin_url: str) -> str | None:
        if not self.api_key:
            logger.warning("EAZYREACH_API_KEY not set. Returning empty result.")
            return None

        # NOTE: Provider-specific endpoint may differ.
        url = f"{self.base_url}/api/email/resolve"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"linkedin_url": linkedin_url}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data: Any = resp.json()
        except Exception as e:
            logger.exception("Eazyreach API failed: %s", e)
            return None

        email = data.get("email") or data.get("work_email") or data.get("result") or None
        if not email:
            return None

        email = str(email).strip()
        if "@" not in email:
            return None
        return email

