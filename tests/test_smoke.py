"""Smoke tests for core building blocks (no network, no GUI)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Make the project root importable when running ``python tests/test_smoke.py``.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///data/test_jobhunter.db")


class CoreImportsTest(unittest.TestCase):
    def test_imports(self) -> None:
        from app.core.config import settings  # noqa: F401
        from app.core.constants import JOB_SOURCES, COUNTRIES  # noqa: F401
        from app.core.exceptions import JobHunterError  # noqa: F401
        from app.utils.helpers import slugify, parse_salary, parse_posted_date
        from app.utils.validators import is_valid_url, sanitize_keyword
        from app.scrapers import SCRAPER_REGISTRY

        self.assertTrue(len(JOB_SOURCES) == 8)
        self.assertTrue(len(SCRAPER_REGISTRY) == 8)
        self.assertEqual(slugify("Senior Python Dev / Remote"), "senior-python-dev-remote")
        self.assertTrue(is_valid_url("https://example.com/jobs"))
        self.assertFalse(is_valid_url("not a url"))
        self.assertEqual(sanitize_keyword("Python <script>"), "Python script")
        self.assertIsNotNone(parse_posted_date("2 days ago"))
        self.assertEqual(parse_salary("60,000 USD")[-3:], "USD")


class DatabaseTest(unittest.TestCase):
    def test_create_schema(self) -> None:
        from app.database.db import init_database
        from app.database.repositories import JobRepository

        init_database()
        # Counts should not raise even if empty.
        self.assertGreaterEqual(JobRepository().count(), 0)


class DedupTest(unittest.TestCase):
    def test_hash_stable(self) -> None:
        from app.services.deduplication_service import DeduplicationService

        h1 = DeduplicationService.compute_hash(
            "Senior Python Engineer",
            "ACME Inc",
            "https://acme.com/jobs/12?utm_source=x",
        )
        h2 = DeduplicationService.compute_hash(
            " senior python engineer ",
            "Acme Inc",
            "HTTPS://ACME.COM/jobs/12",
        )
        self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
