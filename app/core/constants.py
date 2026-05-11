"""Application-wide constants and reference data."""

from __future__ import annotations

from typing import Final


# ---------------------------------------------------------------------------
# Supported job sources
# ---------------------------------------------------------------------------
JOB_SOURCES: Final[list[str]] = [
    "LinkedIn",
    "Indeed",
    "RemoteOK",
    "Rekrute",
    "Emploi.ma",
    "WelcomeToTheJungle",
    "Arbeitnow",
    "TheMuse",
    # Newly added — extended Middle East + remote coverage
    "Bayt",
    "WeWorkRemotely",
    "Jobicy",
]


# ---------------------------------------------------------------------------
# Country selector data: name -> ISO code (used in API queries)
# ---------------------------------------------------------------------------
COUNTRIES: Final[dict[str, str]] = {
    "Morocco": "MA",
    "France": "FR",
    "Spain": "ES",
    "Germany": "DE",
    "UAE": "AE",
    "Saudi Arabia": "SA",
    "Qatar": "QA",
    "Canada": "CA",
    "USA": "US",
    "UK": "GB",
    "Remote": "RE",
}


# ---------------------------------------------------------------------------
# Preset filter shortcuts
# ---------------------------------------------------------------------------
PRESET_FILTERS: Final[dict[str, dict]] = {
    "Python Developer": {
        "keyword": "Python Developer",
        "remote": False,
    },
    "Full Stack Developer": {
        "keyword": "Full Stack Developer",
        "remote": False,
    },
    "Remote Jobs": {
        "keyword": "developer",
        "remote": True,
        "country": "Remote",
    },
    "AI Engineer": {
        "keyword": "AI Engineer",
        "remote": False,
    },
    "Data Scientist": {
        "keyword": "Data Scientist",
        "remote": False,
    },
    "DevOps Engineer": {
        "keyword": "DevOps Engineer",
        "remote": False,
    },
    "Morocco Jobs": {
        "keyword": "developer",
        "country": "Morocco",
    },
    "Europe Jobs": {
        "keyword": "developer",
        "country": "France",
    },
}


# ---------------------------------------------------------------------------
# Employment types
# ---------------------------------------------------------------------------
EMPLOYMENT_TYPES: Final[list[str]] = [
    "Full-time",
    "Part-time",
    "Contract",
    "Internship",
    "Temporary",
    "Freelance",
]


# ---------------------------------------------------------------------------
# Experience levels
# ---------------------------------------------------------------------------
EXPERIENCE_LEVELS: Final[list[str]] = [
    "Internship",
    "Entry level",
    "Associate",
    "Mid-Senior",
    "Senior",
    "Director",
    "Executive",
]


# ---------------------------------------------------------------------------
# Date posted filter options (used by GUI / API where applicable)
# ---------------------------------------------------------------------------
DATE_POSTED_OPTIONS: Final[dict[str, str]] = {
    "Any time": "any",
    "Past 24 hours": "1d",
    "Past 3 days": "3d",
    "Past week": "1w",
    "Past month": "1m",
}


# ---------------------------------------------------------------------------
# Browser fingerprint pools
# ---------------------------------------------------------------------------
BROWSER_LOCALES: Final[list[str]] = [
    "en-US",
    "en-GB",
    "fr-FR",
    "de-DE",
    "es-ES",
    "ar-MA",
]

BROWSER_TIMEZONES: Final[list[str]] = [
    "Europe/Paris",
    "Europe/London",
    "Africa/Casablanca",
    "America/New_York",
    "America/Los_Angeles",
    "Asia/Dubai",
]

BROWSER_VIEWPORTS: Final[list[tuple[int, int]]] = [
    (1920, 1080),
    (1680, 1050),
    (1536, 864),
    (1440, 900),
    (1366, 768),
]


# ---------------------------------------------------------------------------
# Fallback user-agents (used if fake-useragent is unavailable)
# ---------------------------------------------------------------------------
FALLBACK_USER_AGENTS: Final[list[str]] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 "
    "Firefox/130.0",
]


# ---------------------------------------------------------------------------
# GUI section titles (used by the sidebar)
# ---------------------------------------------------------------------------
GUI_PAGES: Final[list[str]] = [
    "Dashboard",
    "Jobs",
    "Follow-ups",
    "Exports",
    "Logs",
    "Analytics",
    "Settings",
    "About",
]


# ---------------------------------------------------------------------------
# Table column metadata (used by JobsTable)
# ---------------------------------------------------------------------------
JOB_TABLE_COLUMNS: Final[list[tuple[str, str, int]]] = [
    # (attribute, display name, width)
    ("status", "Status", 110),
    ("title", "Title", 240),
    ("company", "Company", 170),
    ("location", "Location", 150),
    ("source", "Source", 100),
    ("sponsorship", "Visa", 60),
    ("salary", "Salary", 110),
    ("posted_date", "Posted", 100),
    ("follow_up_date", "Follow-up", 100),
]


# ---------------------------------------------------------------------------
# Application / follow-up status values
# ---------------------------------------------------------------------------
class JobStatus:
    NEW: Final[str] = "new"
    BOOKMARKED: Final[str] = "bookmarked"
    APPLIED: Final[str] = "applied"
    INTERVIEW: Final[str] = "interview"
    OFFER: Final[str] = "offer"
    REJECTED: Final[str] = "rejected"


JOB_STATUSES: Final[list[str]] = [
    JobStatus.NEW,
    JobStatus.BOOKMARKED,
    JobStatus.APPLIED,
    JobStatus.INTERVIEW,
    JobStatus.OFFER,
    JobStatus.REJECTED,
]

#: Statuses considered "active follow-ups" (everything except NEW/REJECTED).
FOLLOW_UP_STATUSES: Final[list[str]] = [
    JobStatus.BOOKMARKED,
    JobStatus.APPLIED,
    JobStatus.INTERVIEW,
    JobStatus.OFFER,
]

#: Pretty labels and small glyph icons per status (used in the GUI).
STATUS_LABELS: Final[dict[str, str]] = {
    JobStatus.NEW: "● New",
    JobStatus.BOOKMARKED: "★ Bookmarked",
    JobStatus.APPLIED: "✉ Applied",
    JobStatus.INTERVIEW: "☎ Interview",
    JobStatus.OFFER: "✓ Offer",
    JobStatus.REJECTED: "✗ Rejected",
}


# ---------------------------------------------------------------------------
# Status / event topic strings (used across GUI <-> services queue)
# ---------------------------------------------------------------------------
class EventTopic:
    SCRAPE_STARTED: Final[str] = "scrape.started"
    SCRAPE_PROGRESS: Final[str] = "scrape.progress"
    SCRAPE_PAGE: Final[str] = "scrape.page"
    SCRAPE_FOUND: Final[str] = "scrape.found"
    SCRAPE_ERROR: Final[str] = "scrape.error"
    SCRAPE_COMPLETED: Final[str] = "scrape.completed"
    EXPORT_STARTED: Final[str] = "export.started"
    EXPORT_COMPLETED: Final[str] = "export.completed"
    LOG_LINE: Final[str] = "log.line"
    NOTIFY: Final[str] = "notify"
