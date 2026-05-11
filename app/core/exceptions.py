"""Custom exception hierarchy for JobHunter Pro."""

from __future__ import annotations


class JobHunterError(Exception):
    """Base exception for the JobHunter Pro application."""

    def __init__(self, message: str = "", *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:
        if self.cause is not None:
            return f"{self.message} (caused by {type(self.cause).__name__}: {self.cause})"
        return self.message or self.__class__.__name__


class ConfigError(JobHunterError):
    """Configuration is missing or invalid."""


class ScraperError(JobHunterError):
    """A scraper failed irrecoverably."""


class ScraperTimeoutError(ScraperError):
    """A scraper timed out while loading a page."""


class RateLimitError(ScraperError):
    """A source is rate-limiting our requests."""


class CaptchaError(ScraperError):
    """A captcha/anti-bot challenge was detected."""


class DatabaseError(JobHunterError):
    """A database operation failed."""


class DuplicateJobError(DatabaseError):
    """Attempted to insert an already-existing job."""


class ExportError(JobHunterError):
    """An export operation failed."""


class SchedulerError(JobHunterError):
    """The scheduler subsystem failed."""


class ValidationError(JobHunterError):
    """Input failed validation."""
