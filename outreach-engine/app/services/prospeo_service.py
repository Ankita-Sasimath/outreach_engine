from __future__ import annotations

from typing import Any

import os
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.utils.logger import get_logger

logger = get_logger("prospeo")


class ProspeoClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("PROSPEO_API_KEY", "")
        self.timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
        self.base_url = os.getenv("PROSPEO_BASE_URL", "https://api.prospeo.io")

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def find_decision_makers(self, domain: str) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning("PROSPEO_API_KEY not set. Returning empty result.")
            return []

        # NOTE: Provider-specific endpoint may differ.
        url = f"{self.base_url}/contacts/find"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"domain": domain}
        roles = ["CEO", "CTO", "Founder", "VP Engineering", "Head of Product"]

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.exception("Prospeo API failed: %s", e)
            return []

        candidates = data.get("contacts") or data.get("results") or data.get("data") or []
        normalized: list[dict[str, Any]] = []
        for c in candidates:
            designation = (c.get("designation") or c.get("title") or "").strip()
            if designation and not any(r.lower() in designation.lower() for r in roles):
                continue
            normalized.append(
                {
                    "name": c.get("name") or c.get("full_name"),
                    "designation": designation,
                    "linkedin_url": c.get("linkedin_url") or c.get("linkedin") or c.get("profile_url"),
                }
            )
        return normalized

