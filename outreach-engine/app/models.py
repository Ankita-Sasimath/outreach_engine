from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(255))
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="contacts")
    outreach: Mapped[list["Outreach"]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # simple high-level counters (kept in sync by pipeline)
    companies_found: Mapped[int] = mapped_column(Integer, default=0)
    contacts_found: Mapped[int] = mapped_column(Integer, default=0)
    emails_resolved: Mapped[int] = mapped_column(Integer, default=0)
    emails_ready: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(64), default="running", index=True)


class PipelineActivity(Base):
    __tablename__ = "pipeline_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[str] = mapped_column(String(512))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Outreach(Base):
    __tablename__ = "outreach"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)

    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contact: Mapped[Contact] = relationship(back_populates="outreach")


