"""Repository layer — encapsulates all DB queries used by the service layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseError, DuplicateJobError
from app.database.db import init_database
from app.database.models import ExportRecord, Job, ScrapeRun
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ===========================================================================
# JobRepository
# ===========================================================================
class JobRepository:
    """All DB operations on the ``jobs`` table."""

    def __init__(self, session: Optional[Session] = None) -> None:
        self._session = session
        self._owns_session = session is None

    def _open(self) -> Session:
        return self._session if self._session is not None else init_database().session()

    def _close(self, session: Session) -> None:
        if self._owns_session:
            session.close()

    # ---------------- Inserts ----------------
    def add(self, job: Job) -> Job:
        session = self._open()
        try:
            session.add(job)
            if self._owns_session:
                session.commit()
                session.refresh(job)
            return job
        except IntegrityError as exc:
            session.rollback()
            raise DuplicateJobError(f"Duplicate job hash: {job.hash_id}", cause=exc) from exc
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def bulk_add(self, jobs: Iterable[Job]) -> tuple[int, int]:
        """Insert ``jobs`` skipping duplicates. Returns ``(inserted, duplicates)``."""
        inserted, duplicates = 0, 0
        session = self._open()
        try:
            for job in jobs:
                exists = session.execute(
                    select(Job.id).where(Job.hash_id == job.hash_id)
                ).scalar_one_or_none()
                if exists is not None:
                    duplicates += 1
                    continue
                session.add(job)
                try:
                    session.flush()
                    inserted += 1
                except IntegrityError:
                    session.rollback()
                    duplicates += 1
                    continue
            if self._owns_session:
                session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)
        return inserted, duplicates

    # ---------------- Queries ----------------
    def get_by_hash(self, hash_id: str) -> Optional[Job]:
        session = self._open()
        try:
            return session.execute(
                select(Job).where(Job.hash_id == hash_id)
            ).scalar_one_or_none()
        finally:
            self._close(session)

    def get_by_id(self, job_id: int) -> Optional[Job]:
        session = self._open()
        try:
            return session.get(Job, job_id)
        finally:
            self._close(session)

    def exists(self, hash_id: str) -> bool:
        session = self._open()
        try:
            return (
                session.execute(
                    select(func.count()).select_from(Job).where(Job.hash_id == hash_id)
                ).scalar_one()
                > 0
            )
        finally:
            self._close(session)

    def list_jobs(
        self,
        *,
        keyword: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        source: Optional[str] = None,
        remote_only: bool = False,
        date_from: Optional[datetime] = None,
        employment_type: Optional[str] = None,
        experience_level: Optional[str] = None,
        status: Optional[str] = None,
        statuses: Optional[list[str]] = None,
        scrape_run_id: Optional[int] = None,
        has_follow_up: bool = False,
        sponsorship_only: bool = False,
        limit: int = 1000,
        offset: int = 0,
        order_by: str = "scraped_at",
        descending: bool = True,
    ) -> list[Job]:
        session = self._open()
        try:
            stmt = select(Job)
            conditions = []
            if keyword:
                like = f"%{keyword.lower()}%"
                conditions.append(
                    or_(
                        func.lower(Job.title).like(like),
                        func.lower(Job.company).like(like),
                        func.lower(Job.description).like(like),
                    )
                )
            if country:
                conditions.append(Job.country == country)
            if city:
                conditions.append(Job.location.ilike(f"%{city}%"))
            if source:
                conditions.append(Job.source == source)
            if remote_only:
                conditions.append(Job.remote.is_(True))
            if date_from:
                conditions.append(Job.scraped_at >= date_from)
            if employment_type:
                conditions.append(Job.job_type == employment_type)
            if experience_level:
                conditions.append(Job.experience_level == experience_level)
            if status:
                conditions.append(Job.status == status)
            if statuses:
                conditions.append(Job.status.in_(statuses))
            if scrape_run_id is not None:
                conditions.append(Job.scrape_run_id == scrape_run_id)
            if has_follow_up:
                conditions.append(Job.follow_up_date.isnot(None))
            if sponsorship_only:
                conditions.append(Job.sponsorship.is_(True))
            if conditions:
                stmt = stmt.where(and_(*conditions))

            order_col = getattr(Job, order_by, Job.scraped_at)
            stmt = stmt.order_by(desc(order_col) if descending else order_col)
            stmt = stmt.limit(limit).offset(offset)
            return list(session.execute(stmt).scalars().all())
        finally:
            self._close(session)

    def count(self) -> int:
        session = self._open()
        try:
            return session.execute(select(func.count()).select_from(Job)).scalar_one()
        finally:
            self._close(session)

    def count_filtered(
        self,
        *,
        keyword: Optional[str] = None,
        country: Optional[str] = None,
        source: Optional[str] = None,
        remote_only: bool = False,
        status: Optional[str] = None,
        statuses: Optional[list[str]] = None,
        scrape_run_id: Optional[int] = None,
        sponsorship_only: bool = False,
    ) -> int:
        """Count rows that would be returned by ``list_jobs`` with the same filters."""
        session = self._open()
        try:
            stmt = select(func.count()).select_from(Job)
            conditions = []
            if keyword:
                like = f"%{keyword.lower()}%"
                conditions.append(
                    or_(
                        func.lower(Job.title).like(like),
                        func.lower(Job.company).like(like),
                        func.lower(Job.description).like(like),
                    )
                )
            if country:
                conditions.append(Job.country == country)
            if source:
                conditions.append(Job.source == source)
            if remote_only:
                conditions.append(Job.remote.is_(True))
            if status:
                conditions.append(Job.status == status)
            if statuses:
                conditions.append(Job.status.in_(statuses))
            if scrape_run_id is not None:
                conditions.append(Job.scrape_run_id == scrape_run_id)
            if sponsorship_only:
                conditions.append(Job.sponsorship.is_(True))
            if conditions:
                stmt = stmt.where(and_(*conditions))
            return session.execute(stmt).scalar_one()
        finally:
            self._close(session)

    def last_run_id(self) -> Optional[int]:
        """Return the most recent ``scrape_run_id`` actually attached to jobs."""
        session = self._open()
        try:
            return session.execute(
                select(func.max(Job.scrape_run_id))
            ).scalar_one_or_none()
        finally:
            self._close(session)

    def count_since(self, since: datetime) -> int:
        session = self._open()
        try:
            return session.execute(
                select(func.count()).select_from(Job).where(Job.scraped_at >= since)
            ).scalar_one()
        finally:
            self._close(session)

    # ---------------- Aggregations (analytics) ----------------
    def count_by_source(self) -> dict[str, int]:
        session = self._open()
        try:
            rows = session.execute(
                select(Job.source, func.count(Job.id)).group_by(Job.source)
            ).all()
            return {row[0]: row[1] for row in rows}
        finally:
            self._close(session)

    def count_by_country(self) -> dict[str, int]:
        session = self._open()
        try:
            rows = session.execute(
                select(Job.country, func.count(Job.id))
                .where(Job.country.isnot(None))
                .group_by(Job.country)
            ).all()
            return {row[0]: row[1] for row in rows}
        finally:
            self._close(session)

    def top_companies(self, limit: int = 10) -> list[tuple[str, int]]:
        session = self._open()
        try:
            rows = session.execute(
                select(Job.company, func.count(Job.id))
                .where(Job.company != "")
                .group_by(Job.company)
                .order_by(desc(func.count(Job.id)))
                .limit(limit)
            ).all()
            return [(r[0], r[1]) for r in rows]
        finally:
            self._close(session)

    def remote_vs_onsite(self) -> dict[str, int]:
        session = self._open()
        try:
            remote = session.execute(
                select(func.count()).select_from(Job).where(Job.remote.is_(True))
            ).scalar_one()
            onsite = session.execute(
                select(func.count()).select_from(Job).where(Job.remote.is_(False))
            ).scalar_one()
            return {"Remote": remote, "On-site": onsite}
        finally:
            self._close(session)

    def jobs_over_time(self, days: int = 14) -> list[tuple[str, int]]:
        """Return [(YYYY-MM-DD, count), ...] for the last ``days`` days."""
        session = self._open()
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            rows = session.execute(
                select(
                    func.strftime("%Y-%m-%d", Job.scraped_at),
                    func.count(Job.id),
                )
                .where(Job.scraped_at >= since)
                .group_by(func.strftime("%Y-%m-%d", Job.scraped_at))
                .order_by(func.strftime("%Y-%m-%d", Job.scraped_at))
            ).all()
            return [(r[0], r[1]) for r in rows]
        finally:
            self._close(session)

    # ---------------- Mutations: status / notes / follow-up ----------------
    def update_status(self, job_id: int, status: str) -> bool:
        return self._patch(job_id, {"status": status})

    def update_status_many(self, job_ids: list[int], status: str) -> int:
        if not job_ids:
            return 0
        session = self._open()
        try:
            updated = (
                session.query(Job)
                .filter(Job.id.in_(job_ids))
                .update({"status": status}, synchronize_session=False)
            )
            if self._owns_session:
                session.commit()
            return updated
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def update_notes(self, job_id: int, notes: Optional[str]) -> bool:
        return self._patch(job_id, {"notes": notes})

    def set_follow_up(self, job_id: int, when: Optional[datetime]) -> bool:
        return self._patch(job_id, {"follow_up_date": when})

    def _patch(self, job_id: int, fields: dict[str, Any]) -> bool:
        session = self._open()
        try:
            obj = session.get(Job, job_id)
            if obj is None:
                return False
            for key, value in fields.items():
                setattr(obj, key, value)
            if self._owns_session:
                session.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    # ---------------- Deletes ----------------
    def delete_many(self, job_ids: list[int]) -> int:
        if not job_ids:
            return 0
        session = self._open()
        try:
            deleted = (
                session.query(Job)
                .filter(Job.id.in_(job_ids))
                .delete(synchronize_session=False)
            )
            if self._owns_session:
                session.commit()
            return deleted
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def delete_by_id(self, job_id: int) -> bool:
        session = self._open()
        try:
            obj = session.get(Job, job_id)
            if obj is None:
                return False
            session.delete(obj)
            if self._owns_session:
                session.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def clear_all(self) -> int:
        session = self._open()
        try:
            count = session.execute(select(func.count()).select_from(Job)).scalar_one()
            session.query(Job).delete()
            if self._owns_session:
                session.commit()
            return count
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)


# ===========================================================================
# ScrapeRunRepository
# ===========================================================================
class ScrapeRunRepository:
    def __init__(self, session: Optional[Session] = None) -> None:
        self._session = session
        self._owns_session = session is None

    def _open(self) -> Session:
        return self._session if self._session is not None else init_database().session()

    def _close(self, session: Session) -> None:
        if self._owns_session:
            session.close()

    def create(
        self,
        keyword: Optional[str],
        country: Optional[str],
        city: Optional[str],
        remote_only: bool,
        sources: list[str],
        trigger: str = "manual",
    ) -> ScrapeRun:
        run = ScrapeRun(
            keyword=keyword,
            country=country,
            city=city,
            remote_only=remote_only,
            sources=",".join(sources) if sources else None,
            trigger=trigger,
            status="running",
        )
        session = self._open()
        try:
            session.add(run)
            if self._owns_session:
                session.commit()
                session.refresh(run)
            return run
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def finish(
        self,
        run_id: int,
        *,
        total_found: int,
        new_jobs: int,
        duplicates: int,
        errors: int,
        status: str = "completed",
    ) -> None:
        session = self._open()
        try:
            run = session.get(ScrapeRun, run_id)
            if run is None:
                return
            run.total_found = total_found
            run.new_jobs = new_jobs
            run.duplicates = duplicates
            run.errors = errors
            run.status = status
            run.finished_at = datetime.now(timezone.utc)
            if self._owns_session:
                session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def recent(self, limit: int = 20) -> list[ScrapeRun]:
        session = self._open()
        try:
            stmt = select(ScrapeRun).order_by(desc(ScrapeRun.started_at)).limit(limit)
            return list(session.execute(stmt).scalars().all())
        finally:
            self._close(session)

    def last_completed(self) -> Optional[ScrapeRun]:
        session = self._open()
        try:
            stmt = (
                select(ScrapeRun)
                .where(ScrapeRun.status == "completed")
                .order_by(desc(ScrapeRun.finished_at))
                .limit(1)
            )
            return session.execute(stmt).scalar_one_or_none()
        finally:
            self._close(session)


# ===========================================================================
# ExportRepository
# ===========================================================================
class ExportRepository:
    def __init__(self, session: Optional[Session] = None) -> None:
        self._session = session
        self._owns_session = session is None

    def _open(self) -> Session:
        return self._session if self._session is not None else init_database().session()

    def _close(self, session: Session) -> None:
        if self._owns_session:
            session.close()

    def record(
        self,
        *,
        file_path: str,
        fmt: str,
        rows: int,
        filters: Optional[dict[str, Any]] = None,
    ) -> ExportRecord:
        import json

        rec = ExportRecord(
            file_path=file_path,
            format=fmt,
            rows=rows,
            filters=json.dumps(filters or {}, ensure_ascii=False),
        )
        session = self._open()
        try:
            session.add(rec)
            if self._owns_session:
                session.commit()
                session.refresh(rec)
            return rec
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            self._close(session)

    def recent(self, limit: int = 50) -> list[ExportRecord]:
        session = self._open()
        try:
            stmt = select(ExportRecord).order_by(desc(ExportRecord.created_at)).limit(limit)
            return list(session.execute(stmt).scalars().all())
        finally:
            self._close(session)

    def count(self) -> int:
        session = self._open()
        try:
            return session.execute(
                select(func.count()).select_from(ExportRecord)
            ).scalar_one()
        finally:
            self._close(session)
