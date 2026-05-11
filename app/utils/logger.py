"""Loguru-based application logger.

A single setup function configures sinks (console + rotating file) the first
time it is called. ``get_logger(name)`` returns a bound logger you can use as
a drop-in for the stdlib logger.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from app.core.config import settings


_INITIALIZED: bool = False


def setup_logging(
    level: Optional[str] = None,
    *,
    log_file: Optional[Path] = None,
    extra_sink: Optional[Callable[[str], Any]] = None,
) -> None:
    """Configure loguru sinks once.

    Args:
        level: minimum log level (default = settings.log_level).
        log_file: override the default log file location.
        extra_sink: optional callable that receives formatted log lines —
            used by the GUI to stream live logs into a panel.
    """
    global _INITIALIZED

    target_level = (level or settings.log_level).upper()
    target_file = log_file or (settings.log_path / settings.log_file)

    # Wipe defaults so re-configuration is idempotent
    logger.remove()

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
        "| <level>{level: <8}</level> "
        "| <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
        "- <level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        level=target_level,
        format=console_format,
        colorize=True,
        backtrace=True,
        diagnose=settings.debug,
        enqueue=False,
    )

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} - {message}"
    )
    logger.add(
        str(target_file),
        level=target_level,
        format=file_format,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        backtrace=True,
        diagnose=settings.debug,
        enqueue=True,
        encoding="utf-8",
    )

    if extra_sink is not None:
        logger.add(
            extra_sink,
            level=target_level,
            format="{time:HH:mm:ss} | {level: <7} | {message}",
            enqueue=True,
        )

    _INITIALIZED = True
    logger.debug(
        "Logger initialized | level={lvl} | file={path}",
        lvl=target_level,
        path=str(target_file),
    )


def get_logger(name: Optional[str] = None):
    """Return a configured logger bound to ``name``."""
    if not _INITIALIZED:
        setup_logging()
    if name is None:
        return logger
    return logger.bind(name=name)
