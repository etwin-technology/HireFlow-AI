"""Miscellaneous helper functions: text cleaning, parsing, timing utilities."""

from __future__ import annotations

import random
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

from dateutil import parser as date_parser

from app.core.config import settings


_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-zA-Z0-9-]+")
_SALARY_RE = re.compile(
    r"(\d{1,3}(?:[,.\s]?\d{3})*(?:\.\d+)?)\s*(?:k|K)?\s*"
    r"(USD|EUR|GBP|MAD|AED|SAR|QAR|CAD|\$|€|£|DH|د\.?م)?",
    re.UNICODE,
)


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------
def random_delay(
    min_seconds: Optional[float] = None,
    max_seconds: Optional[float] = None,
) -> None:
    """Sleep for a random duration between ``min_seconds`` and ``max_seconds``.

    Defaults come from settings (scraper_min_delay / scraper_max_delay).
    """
    lo = min_seconds if min_seconds is not None else settings.scraper_min_delay
    hi = max_seconds if max_seconds is not None else settings.scraper_max_delay
    if hi < lo:
        hi = lo + 0.5
    time.sleep(random.uniform(lo, hi))


def now_iso() -> str:
    """Return the current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def safe_text(value: Optional[str], default: str = "") -> str:
    """Return a whitespace-collapsed, never-None string."""
    if value is None:
        return default
    cleaned = _WHITESPACE_RE.sub(" ", str(value)).strip()
    return cleaned or default


def truncate(text: str, max_length: int = 200, suffix: str = "…") -> str:
    """Truncate ``text`` to ``max_length`` characters."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def slugify(text: str) -> str:
    """Return an ASCII filesystem-safe slug of ``text``."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.strip().lower().replace(" ", "-")
    ascii_only = _NON_WORD_RE.sub("", ascii_only)
    ascii_only = re.sub(r"-+", "-", ascii_only).strip("-")
    return ascii_only or "untitled"


# ---------------------------------------------------------------------------
# Salary parser
# ---------------------------------------------------------------------------
def parse_salary(raw: Optional[str]) -> Optional[str]:
    """Normalize a raw salary string to a compact display form.

    Returns ``None`` if no number was found.
    """
    if not raw:
        return None
    text = safe_text(raw)
    match = _SALARY_RE.search(text)
    if not match:
        return None
    amount, currency = match.group(1), match.group(2)
    amount = amount.replace(" ", "").replace(",", ".")
    return f"{amount} {currency}".strip() if currency else amount


# ---------------------------------------------------------------------------
# Date parser
# ---------------------------------------------------------------------------
_RELATIVE_DATE_RE = re.compile(
    r"(\d+)\s*(minute|hour|day|week|month|year)s?\s*ago",
    re.IGNORECASE,
)


def parse_posted_date(raw: Optional[str]) -> Optional[datetime]:
    """Best-effort conversion of a ``posted_date`` string to a datetime.

    Handles:
    - relative strings ("3 hours ago", "Posted 2 days ago")
    - absolute strings ("2025-09-12", "Sep 12, 2025")
    - epoch timestamps (numeric strings)
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None

    # Numeric epoch
    if text.isdigit():
        try:
            value = int(text)
            if value > 10**12:  # likely milliseconds
                value //= 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError):
            pass

    # Relative phrasing
    match = _RELATIVE_DATE_RE.search(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        delta_map = {
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": timedelta(days=amount * 30),
            "year": timedelta(days=amount * 365),
        }
        return datetime.now(timezone.utc) - delta_map[unit]

    if "today" in text.lower() or "just posted" in text.lower():
        return datetime.now(timezone.utc)
    if "yesterday" in text.lower():
        return datetime.now(timezone.utc) - timedelta(days=1)

    # Fallback: dateutil
    try:
        dt = date_parser.parse(text, fuzzy=True, default=datetime.now(timezone.utc))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, OverflowError, date_parser.ParserError):
        return None


# ---------------------------------------------------------------------------
# Small utility helpers
# ---------------------------------------------------------------------------
def chunked(seq, size: int):
    """Yield successive ``size``-sized chunks from ``seq``."""
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def humanize_count(n: int) -> str:
    """Return a human-readable representation of ``n`` (e.g. 12_345 -> 12.3K)."""
    if n is None:
        return "0"
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}K"
    return f"{n / 1_000_000:.1f}M"
