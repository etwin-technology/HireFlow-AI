"""FastAPI app exposing programmatic access to JobHunter Pro."""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.constants import JOB_SOURCES
from app.database.db import init_database
from app.database.repositories import (
    ExportRepository,
    JobRepository,
    ScrapeRunRepository,
)
from app.services.analytics_service import AnalyticsService
from app.services.export_service import ExportService
from app.services.scraping_service import ScrapingService
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ScrapeRequest(BaseModel):
    keyword: str = Field(default="developer", min_length=1, max_length=120)
    country: Optional[str] = None
    city: Optional[str] = None
    remote_only: bool = False
    sources: Optional[list[str]] = None
    max_pages: Optional[int] = Field(default=None, ge=1, le=50)


class ScrapeResponse(BaseModel):
    accepted: bool
    message: str


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    location: str
    country: Optional[str] = None
    remote: bool = False
    salary: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    source: str
    url: str
    posted_date: Optional[str] = None
    scraped_at: Optional[str] = None


class ExportResponse(BaseModel):
    path: str
    rows: int
    format: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Build the FastAPI application."""
    init_database()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="HTTP API for JobHunter Pro — scrape, query, export.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    job_repo = JobRepository()
    run_repo = ScrapeRunRepository()
    export_repo = ExportRepository()
    analytics = AnalyticsService(job_repo, run_repo)
    export_service = ExportService(job_repo, export_repo)

    # NOTE: a single ScrapingService instance is shared so the API mirrors
    # the GUI behavior (only one scrape at a time).
    scraper_lock = threading.Lock()
    scraper = ScrapingService(job_repo=job_repo, run_repo=run_repo)

    # --------------------- Routes ---------------------
    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "endpoints": ["/jobs", "/stats", "/scrape", "/export", "/sources"],
        }

    @app.get("/sources", tags=["meta"])
    def list_sources() -> dict:
        return {"sources": JOB_SOURCES}

    @app.get("/jobs", response_model=list[JobOut], tags=["jobs"])
    def list_jobs(
        keyword: Optional[str] = None,
        country: Optional[str] = None,
        source: Optional[str] = None,
        remote_only: bool = False,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict]:
        jobs = job_repo.list_jobs(
            keyword=keyword,
            country=country,
            source=source,
            remote_only=remote_only,
            limit=limit,
            offset=offset,
        )
        return [j.to_dict() for j in jobs]

    @app.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
    def get_job(job_id: int) -> dict:
        job = job_repo.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.to_dict()

    @app.get("/stats", tags=["analytics"])
    def stats() -> dict:
        return {
            "summary": analytics.summary(),
            "per_source": analytics.jobs_per_source(),
            "per_country": analytics.jobs_per_country(),
            "remote_vs_onsite": analytics.remote_vs_onsite(),
            "top_companies": analytics.top_companies(),
            "jobs_over_time": analytics.jobs_over_time(),
        }

    @app.post("/scrape", response_model=ScrapeResponse, tags=["scrape"])
    def trigger_scrape(req: ScrapeRequest) -> ScrapeResponse:
        if not scraper_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="A scrape is already running")
        try:
            scraper.start(
                keyword=req.keyword,
                sources=req.sources or JOB_SOURCES,
                country=req.country,
                city=req.city,
                remote_only=req.remote_only,
                max_pages=req.max_pages,
                trigger="api",
            )
            return ScrapeResponse(accepted=True, message="Scrape started")
        finally:
            scraper_lock.release()

    @app.post("/scrape/cancel", response_model=ScrapeResponse, tags=["scrape"])
    def cancel_scrape() -> ScrapeResponse:
        scraper.cancel()
        return ScrapeResponse(accepted=True, message="Cancellation requested")

    @app.get("/scrape/status", tags=["scrape"])
    def scrape_status() -> dict:
        return {"running": scraper.is_running}

    @app.get("/export", response_model=ExportResponse, tags=["export"])
    def export_endpoint(
        fmt: str = Query(default="xlsx"),
        keyword: Optional[str] = None,
        country: Optional[str] = None,
        source: Optional[str] = None,
        remote_only: bool = False,
    ) -> dict:
        try:
            path = export_service.export(
                fmt=fmt,
                filters={
                    "keyword": keyword,
                    "country": country,
                    "source": source,
                    "remote_only": remote_only,
                },
            )
            rows = job_repo.count()
            return {"path": str(path), "rows": rows, "format": fmt}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run_api() -> None:
    """Run the API with uvicorn (blocking)."""
    app = create_app()
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


def run_api_threaded() -> threading.Thread:
    """Start the API on a background daemon thread (non-blocking)."""
    thread = threading.Thread(target=run_api, name="JobHunterAPI", daemon=True)
    thread.start()
    return thread


# Allow ``uvicorn app.api.main:app`` direct invocation.
app = create_app()
