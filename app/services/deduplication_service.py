"""Hash-based deduplication service.

A job is considered "duplicate" when the SHA-256 hash of:
    title || company || canonical_url
already exists in the database.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from app.core.security import stable_hash
from app.database.repositories import JobRepository


_URL_QUERY_STRIP = re.compile(r"\?.*$")


def canonical_url(url: str) -> str:
    """Return a deduplication-stable form of ``url`` (no query, no fragment)."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip().lower())
        if not parsed.scheme:
            return _URL_QUERY_STRIP.sub("", url.strip().lower())
        cleaned = parsed._replace(query="", fragment="")
        return urlunparse(cleaned).rstrip("/")
    except (ValueError, AttributeError):
        return _URL_QUERY_STRIP.sub("", url.strip().lower())


class DeduplicationService:
    """Compute hashes + check existence against the DB."""

    def __init__(self, repo: JobRepository | None = None) -> None:
        self._repo = repo or JobRepository()

    @staticmethod
    def compute_hash(title: str, company: str, url: str) -> str:
        return stable_hash(title or "", company or "", canonical_url(url or ""))

    def is_duplicate(self, title: str, company: str, url: str) -> bool:
        return self._repo.exists(self.compute_hash(title, company, url))

    def filter_new(self, records: list) -> tuple[list, int]:
        """Split records into ``(new_records, duplicates_count)``.

        Records may be ``JobRecord`` dataclasses or plain dicts; both are
        supported. The hash is added/recomputed on each item.
        """
        seen_hashes: set[str] = set()
        new_records: list = []
        dup_count = 0

        for rec in records:
            title = getattr(rec, "title", None) or rec.get("title", "")  # type: ignore[union-attr]
            company = getattr(rec, "company", None) or rec.get("company", "")  # type: ignore[union-attr]
            url = getattr(rec, "url", None) or rec.get("url", "")  # type: ignore[union-attr]
            h = self.compute_hash(title, company, url)

            if h in seen_hashes:
                dup_count += 1
                continue
            seen_hashes.add(h)

            if self._repo.exists(h):
                dup_count += 1
                continue
            new_records.append((h, rec))

        return new_records, dup_count
