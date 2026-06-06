from __future__ import annotations

from typing import Any

import os
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from app.utils.logger import get_logger

logger = get_logger("ocean")


class OceanClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OCEAN_API_KEY", "")
        self.timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
        self.max_retries = int(os.getenv("HTTP_MAX_RETRIES", "3"))
        self.base_url = os.getenv("OCEAN_BASE_URL", "https://api.ocean.io")

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=False,
    )
    def find_lookalike_companies(self, domain: str) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning("OCEAN_API_KEY not set. Returning empty result.")
            return []

        # NOTE: Provider-specific endpoint may differ.
        url = f"{self.base_url}/companies/lookalikes"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"domain": domain}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.exception("Ocean API failed: %s", e)
            return []

        # Normalize shape.
        companies = data.get("companies") or data.get("results") or data.get("data") or []
        normalized: list[dict[str, Any]] = []
        for c in companies:
            normalized.append(
                {
                    "domain": c.get("domain") or c.get("website") or c.get("company_domain"),
                    "name": c.get("name") or c.get("company_name"),
                }
            )
        return normalized

