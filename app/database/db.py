"""Database engine + session management."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.database.models import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """Thread-safe SQLAlchemy engine/session factory singleton."""

    _instance: Optional["Database"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "Database":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        url = settings.database_url
        # Ensure SQLite parent directory exists.
        if url.startswith("sqlite:///"):
            db_path = settings.project_root / url.replace("sqlite:///", "")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{db_path}"
            logger.debug("Database file: {p}", p=str(db_path))

        self._engine: Engine = create_engine(
            url,
            echo=settings.database_echo,
            future=True,
            connect_args=(
                {"check_same_thread": False} if url.startswith("sqlite") else {}
            ),
            pool_pre_ping=True,
        )

        @event.listens_for(self._engine, "connect")
        def _enable_sqlite_pragmas(dbapi_connection, _):  # noqa: ANN001
            if url.startswith("sqlite"):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )

    # ---------------- Public API ----------------
    @property
    def engine(self) -> Engine:
        return self._engine

    def create_all(self) -> None:
        logger.info("Creating database schema (if not exists)…")
        Base.metadata.create_all(self._engine)
        self._auto_migrate()

    def _auto_migrate(self) -> None:
        """Add columns introduced after the DB was first created (SQLite only).

        Compares the live ``jobs`` table to the ORM model and issues
        ``ALTER TABLE ... ADD COLUMN`` for any missing column.
        """
        try:
            inspector = inspect(self._engine)
            if "jobs" not in inspector.get_table_names():
                return
            existing = {col["name"] for col in inspector.get_columns("jobs")}
            wanted: dict[str, str] = {
                "status": "VARCHAR(32) NOT NULL DEFAULT 'new'",
                "notes": "TEXT",
                "follow_up_date": "DATETIME",
                "scrape_run_id": "INTEGER",
                "sponsorship": "BOOLEAN NOT NULL DEFAULT 0",
            }
            missing = [c for c in wanted if c not in existing]
            if not missing:
                return
            with self._engine.begin() as conn:
                for name in missing:
                    ddl = wanted[name]
                    conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}"))
                    logger.info("Auto-migrated: added jobs.{n}", n=name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Auto-migration failed (non-fatal): {e}", e=str(exc))

    def drop_all(self) -> None:  # pragma: no cover - destructive
        logger.warning("Dropping all database tables.")
        Base.metadata.drop_all(self._engine)

    def session(self) -> Session:
        return self._SessionLocal()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide a transactional scope around a series of operations."""
        s = self._SessionLocal()
        try:
            yield s
            s.commit()
        except Exception as exc:
            s.rollback()
            logger.error("DB transaction rolled back: {e}", e=str(exc))
            raise DatabaseError(str(exc), cause=exc) from exc
        finally:
            s.close()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
_db_instance: Optional[Database] = None


def init_database() -> Database:
    """Initialize and return the Database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.create_all()
    return _db_instance


def get_session() -> Session:
    """Return a new session (caller is responsible for closing it)."""
    return init_database().session()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Convenience context-manager wrapper."""
    with init_database().session_scope() as s:
        yield s
