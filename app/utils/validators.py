"""Input validators."""

from __future__ import annotations

import re
from urllib.parse import urlparse


_KEYWORD_RE = re.compile(r"[^\w\s\+\#\.\-/&]", re.UNICODE)
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def is_valid_url(url: str) -> bool:
    """Return True if ``url`` is a syntactically valid http(s) URL."""
    if not url or not isinstance(url, str):
        return False
    if not _URL_RE.match(url):
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in {"http", "https"} and parsed.netloc)
    except (ValueError, TypeError):
        return False


def is_valid_keyword(keyword: str) -> bool:
    """Return True if ``keyword`` is non-empty and printable."""
    if not keyword or not isinstance(keyword, str):
        return False
    cleaned = keyword.strip()
    return 1 <= len(cleaned) <= 120


def sanitize_keyword(keyword: str) -> str:
    """Remove unsafe characters from a keyword search."""
    if not keyword:
        return ""
    cleaned = _KEYWORD_RE.sub(" ", keyword).strip()
    return re.sub(r"\s+", " ", cleaned)


def is_valid_country_name(name: str, allowed: set[str]) -> bool:
    return bool(name) and name in allowed


def is_valid_source(source: str, allowed: set[str]) -> bool:
    return bool(source) and source in allowed
