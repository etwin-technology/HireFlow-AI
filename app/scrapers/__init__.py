"""Scrapers package — one module per job board."""

from typing import Type

from app.scrapers.base_scraper import BaseScraper, ScrapeQuery, JobRecord
from app.scrapers.linkedin_scraper import LinkedInScraper
from app.scrapers.indeed_scraper import IndeedScraper
from app.scrapers.remoteok_scraper import RemoteOKScraper
from app.scrapers.rekrute_scraper import RekruteScraper
from app.scrapers.emploi_scraper import EmploiScraper
from app.scrapers.muse_scraper import MuseScraper
from app.scrapers.arbeitnow_scraper import ArbeitnowScraper
from app.scrapers.jungle_scraper import JungleScraper
from app.scrapers.bayt_scraper import BaytScraper
from app.scrapers.wwr_scraper import WeWorkRemotelyScraper
from app.scrapers.jobicy_scraper import JobicyScraper


SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "LinkedIn": LinkedInScraper,
    "Indeed": IndeedScraper,
    "RemoteOK": RemoteOKScraper,
    "Rekrute": RekruteScraper,
    "Emploi.ma": EmploiScraper,
    "TheMuse": MuseScraper,
    "Arbeitnow": ArbeitnowScraper,
    "WelcomeToTheJungle": JungleScraper,
    "Bayt": BaytScraper,
    "WeWorkRemotely": WeWorkRemotelyScraper,
    "Jobicy": JobicyScraper,
}


def get_scraper(name: str) -> Type[BaseScraper]:
    """Return the scraper class for ``name``."""
    if name not in SCRAPER_REGISTRY:
        raise KeyError(f"Unknown scraper: {name}")
    return SCRAPER_REGISTRY[name]


__all__ = [
    "BaseScraper",
    "ScrapeQuery",
    "JobRecord",
    "LinkedInScraper",
    "IndeedScraper",
    "RemoteOKScraper",
    "RekruteScraper",
    "EmploiScraper",
    "MuseScraper",
    "ArbeitnowScraper",
    "JungleScraper",
    "BaytScraper",
    "WeWorkRemotelyScraper",
    "JobicyScraper",
    "SCRAPER_REGISTRY",
    "get_scraper",
]
