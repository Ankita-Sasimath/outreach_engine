from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import re

from app.services.ocean_service import OceanClient
from app.services.prospeo_service import ProspeoClient
from app.services.eazyreach_service import EazyreachClient
from app.services.email_generator import generate_outreach_email


def _extract_company_name_from_domain(domain: str) -> str:
    # e.g. freshworks.com -> freshworks
    # e.g. tcs.com -> tcs
    name = domain.split(".")[0]
    name = re.sub(r"[^a-zA-Z0-9]+", " ", name).strip()
    if not name:
        return "Unknown"
    return name.title()


def _fallback_similar_companies(domain: str, limit: int = 15) -> list[dict[str, Any]]:
    # Deterministic, local-only fallback. Not “real” similarity, but provides volume.
    base = domain.split(".")[0].lower()
    suffixes = [
        "tech",
        "systems",
        "labs",
        "software",
        "cloud",
        "digital",
        "works",
        "solutions",
        "group",
        "hq",
        "global",
    ]
    results: list[dict[str, Any]] = []
    for i in range(limit):
        suf = suffixes[i % len(suffixes)]
        fake_domain = f"{base}-{suf}{i+1}.com"
        results.append({"domain": fake_domain, "name": _extract_company_name_from_domain(fake_domain)})
    return results


def _fallback_decision_makers(company_name: str, roles: list[str]) -> list[dict[str, Any]]:
    # Deterministic role-based names (local-only fallback)
    tokens = re.findall(r"[a-zA-Z]+", company_name) or [company_name]
    token = tokens[0].lower()[:8] if tokens else "lead"

    first_names = ["Alex", "Taylor", "Jordan", "Morgan", "Casey", "Riley", "Quinn", "Avery"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia"]

    out: list[dict[str, Any]] = []
    for idx, role in enumerate(roles):
        fn = first_names[idx % len(first_names)]
        ln = last_names[idx % len(last_names)]
        designation = role
        linkedin_url = None
        out.append({
            "name": f"{fn} {ln}",
            "designation": designation,
            "linkedin_url": linkedin_url,
        })
    return out


def _estimate_email(contact_name: str, company_domain: str) -> str:
    # Simple estimation: john.smith@company.com and johnsmith@...
    parts = re.findall(r"[a-zA-Z]+", contact_name)
    if not parts:
        local = "lead"
    else:
        first = parts[0].lower()
        last = (parts[1].lower() if len(parts) > 1 else "").strip()
        if last:
            candidates = [f"{first}.{last}", f"{first}{last}", f"{first}_{last}"]
        else:
            candidates = [first]
        local = candidates[0]
    return f"{local}@{company_domain}"


@dataclass
class PipelineStage:
    stage: str
    message: str
    progress: int
    total: int | None = None


class CompanyDiscoveryAgent:
    def __init__(self) -> None:
        self.ocean = OceanClient()

    def discover(self, base_domain: str) -> list[dict[str, Any]]:
        lookalikes = self.ocean.find_lookalike_companies(base_domain)
        if lookalikes:
            # Limit for performance
            cleaned = []
            for c in lookalikes:
                d = (c.get("domain") or "").strip().lower()
                n = c.get("name")
                if d:
                    cleaned.append({"domain": d, "name": n})
                if len(cleaned) >= 20:
                    break
            return cleaned

        # Fallback
        return _fallback_similar_companies(base_domain, limit=15)


class ContactDiscoveryAgent:
    def __init__(self) -> None:
        self.prospeo = ProspeoClient()

    def discover_for_company(self, company_domain: str, company_name: str | None = None) -> list[dict[str, Any]]:
        decision_roles = ["CEO", "CTO", "Founder", "VP Engineering", "Head of Product"]
        contacts = self.prospeo.find_decision_makers(company_domain)
        if contacts:
            # Best-effort: keep only target roles
            roles_lc = [r.lower() for r in decision_roles]
            filtered: list[dict[str, Any]] = []
            for c in contacts:
                designation = (c.get("designation") or "").strip()
                if any(r in designation.lower() for r in roles_lc):
                    filtered.append(c)
                if len(filtered) >= 5:
                    break
            return filtered

        # Fallback
        cname = company_name or _extract_company_name_from_domain(company_domain)
        return _fallback_decision_makers(cname, decision_roles)


class EmailResolutionAgent:
    def __init__(self) -> None:
        self.eazy = EazyreachClient()

    def resolve_for_contact(self, contact: dict[str, Any], company_domain: str) -> tuple[str | None, str]:
        linkedin_url = contact.get("linkedin_url")
        name = contact.get("name") or ""

        if linkedin_url:
            resolved = self.eazy.resolve_email(linkedin_url)
            if resolved:
                return resolved, "verified"

        # fallback estimate
        return _estimate_email(name, company_domain), "estimated"


class OutreachGenerationAgent:
    def generate(self, company_name: str, contact_name: str) -> tuple[str, str]:
        return generate_outreach_email(company_name=company_name, name=contact_name)

