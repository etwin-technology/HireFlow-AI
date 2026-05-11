"""Application entry-point.

Supports three modes:
    python -m app.main            # GUI (default)
    python -m app.main --api      # FastAPI only
    python -m app.main --headless # CLI-style headless scrape demo
"""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from app.core.config import settings
from app.database.db import init_database
from app.utils.logger import get_logger, setup_logging

logger = get_logger("main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jobhunter", description=settings.app_name)
    parser.add_argument("--api", action="store_true", help="Run FastAPI server only.")
    parser.add_argument(
        "--with-api",
        action="store_true",
        help="Run GUI and start the API in the background.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run a headless scrape (for CI / debugging).",
    )
    parser.add_argument(
        "--keyword", type=str, default="developer", help="Keyword for headless run."
    )
    parser.add_argument(
        "--country", type=str, default=None, help="Country for headless run."
    )
    parser.add_argument(
        "--source",
        type=str,
        action="append",
        default=None,
        help="Restrict to a specific source (repeatable).",
    )
    return parser.parse_args(argv)


def run_gui(start_api: bool = False) -> NoReturn:
    from app.gui.main_window import MainWindow

    if start_api:
        from app.api.main import run_api_threaded

        run_api_threaded()
        logger.info(
            "API listening on http://{h}:{p}",
            h=settings.api_host,
            p=settings.api_port,
        )

    app = MainWindow()
    try:
        app.mainloop()
    finally:
        logger.info("GUI exited.")
    sys.exit(0)


def run_api_only() -> NoReturn:
    from app.api.main import run_api

    logger.info(
        "Starting API on http://{h}:{p}",
        h=settings.api_host,
        p=settings.api_port,
    )
    run_api()
    sys.exit(0)


def run_headless(args: argparse.Namespace) -> NoReturn:
    """Run a synchronous-ish headless scrape using the existing service."""
    import time

    from app.core.constants import JOB_SOURCES
    from app.services.scraping_service import ScrapingService

    sources = args.source or list(JOB_SOURCES)
    logger.info(
        "Headless scrape | keyword={k} | country={c} | sources={s}",
        k=args.keyword,
        c=args.country,
        s=sources,
    )

    service = ScrapingService()
    service.start(
        keyword=args.keyword,
        country=args.country,
        sources=sources,
        trigger="cli",
    )
    while service.is_running:
        try:
            event = service.event_queue.get(timeout=0.5)
        except Exception:  # noqa: BLE001
            event = None
        if event:
            topic = event.get("topic", "")
            if topic == "scrape.completed":
                logger.info(
                    "Done | new={n} | dup={d} | err={e}",
                    n=event.get("new_jobs"),
                    d=event.get("duplicates"),
                    e=event.get("errors"),
                )
        time.sleep(0.05)
    logger.info("Headless run finished.")
    sys.exit(0)


def main(argv: list[str] | None = None) -> NoReturn:
    setup_logging()
    init_database()
    args = parse_args(argv)

    if args.api:
        run_api_only()
    if args.headless:
        run_headless(args)
    run_gui(start_api=args.with_api)


if __name__ == "__main__":  # pragma: no cover
    main()
