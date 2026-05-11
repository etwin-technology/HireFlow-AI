"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------
class Job(Base):
    """A single scraped job posting."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    salary: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    experience_level: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)

    posted_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    # ----- Visa / relocation sponsorship -----
    sponsorship: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # ----- Application / follow-up tracking -----
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="new", index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    scrape_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    __table_args__ = (
        UniqueConstraint("hash_id", name="uq_jobs_hash_id"),
        Index("ix_jobs_company", "company"),
        Index("ix_jobs_title", "title"),
        Index("ix_jobs_country", "country"),
        Index("ix_jobs_source_scraped", "source", "scraped_at"),
    )

    # ----- Serialization helpers -----
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hash_id": self.hash_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "country": self.country,
            "remote": self.remote,
            "salary": self.salary,
            "job_type": self.job_type,
            "experience_level": self.experience_level,
            "description": self.description,
            "source": self.source,
            "url": self.url,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "sponsorship": self.sponsorship,
            "status": self.status,
            "notes": self.notes,
            "follow_up_date": (
                self.follow_up_date.isoformat() if self.follow_up_date else None
            ),
            "scrape_run_id": self.scrape_run_id,
        }

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Job id={self.id} title={self.title!r} source={self.source}>"


# ---------------------------------------------------------------------------
# ScrapeRun (scraping session metadata)
# ---------------------------------------------------------------------------
class ScrapeRun(Base):
    """A single scraping operation kicked off by the user or scheduler."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    remote_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sources: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "country": self.country,
            "city": self.city,
            "remote_only": self.remote_only,
            "sources": self.sources,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_found": self.total_found,
            "new_jobs": self.new_jobs,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "status": self.status,
            "trigger": self.trigger,
        }


# ---------------------------------------------------------------------------
# ExportRecord (audit log of exports)
# ---------------------------------------------------------------------------
class ExportRecord(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "format": self.format,
            "rows": self.rows,
            "filters": self.filters,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
