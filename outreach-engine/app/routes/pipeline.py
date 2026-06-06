from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Company, Contact, Outreach, PipelineRun, PipelineActivity

from app.schemas import (
    ConfirmSendRequest,
    ConfirmSendResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    StageProgress,
    EmailPreview,
)
from app.services.ocean_service import OceanClient
from app.services.prospeo_service import ProspeoClient
from app.services.eazyreach_service import EazyreachClient
from app.services.brevo_service import BrevoClient
from app.services.email_generator import generate_outreach_email
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("pipeline")


def _get_or_create_company(db: Session, domain: str, company_name: str | None = None) -> Company:
    company = db.query(Company).filter(Company.domain == domain).one_or_none()
    if company is None:
        company = Company(domain=domain, company_name=company_name)
        db.add(company)
        db.commit()
        db.refresh(company)
    elif company_name and not company.company_name:
        company.company_name = company_name
        db.commit()
        db.refresh(company)
    return company


def _get_or_create_contact(db: Session, company: Company, dm: dict[str, Any]) -> Contact:
    name = dm.get("name") or "Unknown"
    designation = dm.get("designation")
    linkedin_url = dm.get("linkedin_url")

    contact = (
        db.query(Contact)
        .filter(Contact.company_id == company.id, Contact.name == name)
        .order_by(Contact.id.asc())
        .first()
    )
    if contact is None:
        contact = Contact(
            company_id=company.id,
            name=name,
            designation=designation,
            linkedin_url=linkedin_url,
            email=None,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    updated = False
    if designation and not contact.designation:
        contact.designation = designation
        updated = True
    if linkedin_url and not contact.linkedin_url:
        contact.linkedin_url = linkedin_url
        updated = True
    if updated:
        db.commit()
        db.refresh(contact)
    return contact


def _upsert_outreach_draft(db: Session, contact_id: int, subject: str, body: str) -> bool:
    existing = (
        db.query(Outreach)
        .filter(Outreach.contact_id == contact_id, Outreach.status == "draft")
        .order_by(Outreach.id.desc())
        .first()
    )
    if existing is None:
        db.add(
            Outreach(
                contact_id=contact_id,
                subject=subject,
                body=body,
                status="draft",
                sent_at=None,
            )
        )
        return True

    existing.subject = subject
    existing.body = body
    return False


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/api/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(payload: PipelineRunRequest) -> PipelineRunResponse:
    domain = payload.domain.strip().lower()
    if not domain or "." not in domain:
        raise HTTPException(status_code=400, detail="Invalid domain")

    with SessionLocal() as db:
        run = PipelineRun(domain=domain, status="running", companies_found=0, contacts_found=0, emails_resolved=0, emails_ready=0)
        db.add(run)
        db.commit()
        db.refresh(run)

    from app.agents.pipeline_agents import (
        CompanyDiscoveryAgent,
        ContactDiscoveryAgent,
        EmailResolutionAgent,
        OutreachGenerationAgent,
    )

    company_agent = CompanyDiscoveryAgent()
    contact_agent = ContactDiscoveryAgent()
    email_agent = EmailResolutionAgent()
    outreach_agent = OutreachGenerationAgent()

    from app.background import run_in_thread

    def _activity(db: Session, stage: str, message: str, progress: int = 0, total: int | None = None) -> None:
        db.add(
            PipelineActivity(
                run_id=run.id,
                stage=stage,
                message=message,
                progress=progress,
                total=total,
            )
        )
        db.commit()

    def _sync_run_counters(
        db: Session,
        *,
        companies_found: int,
        contacts_found: int,
        emails_resolved: int,
        emails_ready: int,
    ) -> None:
        run_db = db.query(PipelineRun).filter(PipelineRun.id == run.id).one()
        run_db.companies_found = companies_found
        run_db.contacts_found = contacts_found
        run_db.emails_resolved = emails_resolved
        run_db.emails_ready = emails_ready
        db.commit()

    def _work() -> None:
        companies_found = 0
        contacts_found = 0
        emails_resolved = 0
        emails_ready = 0
        run_contact_ids: list[int] = []

        with SessionLocal() as db:
            try:
                _activity(db, "analyzing_domain", "Analyzing company domain", progress=5)
                lookalikes = company_agent.discover(domain)

                _activity(
                    db,
                    "finding_similar_companies",
                    "Finding similar companies",
                    progress=15,
                    total=len(lookalikes) or None,
                )

                for i, c in enumerate(lookalikes, start=1):
                    similar_domain = (c.get("domain") or "").strip().lower()
                    if not similar_domain:
                        continue

                    companies_found += 1
                    _sync_run_counters(
                        db,
                        companies_found=companies_found,
                        contacts_found=contacts_found,
                        emails_resolved=emails_resolved,
                        emails_ready=emails_ready,
                    )
                    _get_or_create_company(db, similar_domain, company_name=c.get("name"))
                    _activity(
                        db,
                        "finding_decision_makers",
                        f"Finding decision makers ({i}/{len(lookalikes)})",
                        progress=20 + int(i * 60 / max(len(lookalikes), 1)),
                        total=len(lookalikes),
                    )

                    company_name = c.get("name")
                    contacts = contact_agent.discover_for_company(similar_domain, company_name=company_name)
                    for dm in contacts:
                        company = _get_or_create_company(db, similar_domain, company_name=company_name)
                        contact = _get_or_create_contact(db, company, dm)
                        if contact.id not in run_contact_ids:
                            run_contact_ids.append(contact.id)

                        contacts_found += 1
                        _sync_run_counters(
                            db,
                            companies_found=companies_found,
                            contacts_found=contacts_found,
                            emails_resolved=emails_resolved,
                            emails_ready=emails_ready,
                        )
                        _activity(
                            db,
                            "resolving_verified_emails",
                            f"Resolving email ({contacts_found} contacts)",
                            progress=70,
                        )

                        resolved_email, _email_status = email_agent.resolve_for_contact(dm, company_domain=similar_domain)
                        if resolved_email:
                            contact.email = resolved_email
                            db.commit()
                            db.refresh(contact)
                            emails_resolved += 1
                            _sync_run_counters(
                                db,
                                companies_found=companies_found,
                                contacts_found=contacts_found,
                                emails_resolved=emails_resolved,
                                emails_ready=emails_ready,
                            )

                _activity(db, "generating_outreach", "Generating personalized outreach", progress=90)

                for contact_id in run_contact_ids:
                    contact = db.query(Contact).filter(Contact.id == contact_id).one_or_none()
                    if contact is None or not contact.email:
                        continue

                    company = db.query(Company).filter(Company.id == contact.company_id).one()
                    subject, body = outreach_agent.generate(
                        company_name=company.company_name or company.domain,
                        contact_name=contact.name,
                    )
                    _upsert_outreach_draft(db, contact.id, subject, body)

                db.commit()

                emails_ready = (
                    db.query(Outreach)
                    .filter(Outreach.contact_id.in_(run_contact_ids), Outreach.status == "draft")
                    .count()
                )
                _sync_run_counters(
                    db,
                    companies_found=companies_found,
                    contacts_found=contacts_found,
                    emails_resolved=emails_resolved,
                    emails_ready=emails_ready,
                )

                run_db = db.query(PipelineRun).filter(PipelineRun.id == run.id).one()
                run_db.companies_found = companies_found
                run_db.contacts_found = contacts_found
                run_db.emails_resolved = emails_resolved
                run_db.emails_ready = emails_ready
                run_db.status = "completed"
                run_db.completed_at = datetime.utcnow()
                db.commit()

            except Exception as e:
                logger.exception("pipeline_work_failed")
                _activity(db, "failed", f"Pipeline failed: {e}", progress=100)
                run_db = db.query(PipelineRun).filter(PipelineRun.id == run.id).one_or_none()
                if run_db is not None:
                    run_db.companies_found = companies_found
                    run_db.contacts_found = contacts_found
                    run_db.emails_resolved = emails_resolved
                    run_db.emails_ready = emails_ready
                    run_db.status = "failed"
                    run_db.completed_at = datetime.utcnow()
                    db.commit()

    run_in_thread(_work)

    return PipelineRunResponse(
        run_id=run.id,
        domain=domain,
        companies_found=0,
        contacts_found=0,
        emails_resolved=0,
        emails_ready=0,
    )




@router.post("/api/pipeline/confirm-send", response_model=ConfirmSendResponse)
def confirm_send(payload: ConfirmSendRequest) -> ConfirmSendResponse:
    domain = payload.domain.strip().lower()
    if not payload.send:
        return ConfirmSendResponse(domain=domain, sent=0, skipped=0, previews=[])

    with SessionLocal() as db:
        base_company = db.query(Company).filter(Company.domain == domain).one_or_none()
        if base_company is None:
            raise HTTPException(status_code=404, detail="Domain run not found")

        brevo = BrevoClient()

        drafts = db.query(Outreach).filter(Outreach.status == "draft").all()

        sent = 0
        skipped = 0
        previews: list[EmailPreview] = []

        for out in drafts:
            contact = out.contact
            if not contact or not contact.email:
                out.status = "missing_email"
                db.commit()
                skipped += 1
                continue

            # Add preview (so UI can show what was sent)
            previews.append(
                EmailPreview(
                    contact_id=contact.id,
                    to_email=contact.email,
                    subject=out.subject,
                    body=out.body,
                )
            )

            ok = brevo.send_email(to_email=contact.email, subject=out.subject, html_body=out.body)
            if ok:
                out.status = "sent"
                out.sent_at = datetime.utcnow()
                db.commit()
                sent += 1
            else:
                out.status = "failed"
                db.commit()
                skipped += 1

        return ConfirmSendResponse(domain=domain, sent=sent, skipped=skipped, previews=previews[:10])

