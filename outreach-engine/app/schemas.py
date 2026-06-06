from datetime import datetime

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    domain: str = Field(..., examples=["zoho.com"])


class StageProgress(BaseModel):
    stage: str
    message: str
    progress: int = 0
    total: int | None = None


class PipelineRunResponse(BaseModel):
    run_id: int
    domain: str
    companies_found: int
    contacts_found: int
    emails_resolved: int
    emails_ready: int


class PipelineActivityEvent(BaseModel):
    stage: str
    message: str
    progress: int = 0
    total: int | None = None


class PipelineRunSnapshot(BaseModel):
    run_id: int
    domain: str
    status: str
    companies_found: int
    contacts_found: int
    emails_resolved: int
    emails_ready: int
    latest_activity: list[PipelineActivityEvent] = []



class ConfirmSendRequest(BaseModel):
    domain: str
    send: bool = True


class EmailPreview(BaseModel):
    contact_id: int
    to_email: str
    subject: str
    body: str


class ConfirmSendResponse(BaseModel):
    domain: str
    sent: int
    skipped: int
    previews: list[EmailPreview] = []

