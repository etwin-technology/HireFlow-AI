"""WeWorkRemotely scraper using their RSS feeds.

We aggregate across a few category feeds (programming, devops, data, etc.)
to maximize coverage without scraping HTML pages.
"""

from __future__ import annotations

from typing import AsyncIterator

from bs4 import BeautifulSoup

from app.core.constants import EventTopic
from app.scrapers.base_scraper import BaseScraper, JobRecord, ScrapeQuery


class WeWorkRemotelyScraper(BaseScraper):
    SOURCE_NAME: str = "WeWorkRemotely"

    FEEDS: list[tuple[str, str]] = [
        ("Programming", "https://weworkremotely.com/categories/remote-programming-jobs.rss"),
        ("DevOps", "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"),
        ("Full-Stack", "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"),
        ("Front-End", "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss"),
        ("Back-End", "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss"),
        ("Design", "https://weworkremotely.com/categories/remote-design-jobs.rss"),
        ("Product", "https://weworkremotely.com/categories/remote-product-jobs.rss"),
    ]

    async def run(self, query: ScrapeQuery) -> AsyncIterator[JobRecord]:
        await self.emit(EventTopic.SCRAPE_STARTED, query=query.keyword)
        keyword = query.keyword.lower().strip()
        total = 0
        seen_urls: set[str] = set()

        for page, (category, feed_url) in enumerate(self.FEEDS, start=1):
            if self.cancelled:
                break
            if page > query.max_pages * 2:  # one "page" per feed
                break

            try:
                response = await self.fetch(feed_url)
                items = self._parse_rss(response.text)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "WWR feed {c} failed: {e}", c=category, e=str(exc)
                )
                await self.emit(EventTopic.SCRAPE_ERROR, error=str(exc), page=page)
                continue

            await self.emit(EventTopic.SCRAPE_PAGE, page=page, total=len(items))

            for entry in items:
                if self.cancelled:
                    break
                title_full = entry["title"]
                # WWR titles look like:  "Company Name: Senior Backend Engineer"
                if ":" in title_full:
                    company, _, title_part = title_full.partition(":")
                    company = company.strip()
                    title = title_part.strip()
                else:
                    company = ""
                    title = title_full.strip()

                description = entry["description"]
                haystack = f"{title} {company} {description}".lower()
                if keyword and keyword not in haystack:
                    continue

                url = entry["link"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                record = JobRecord(
                    title=title,
                    company=company,
                    location="Remote",
                    country="Remote",
                    remote=True,
                    salary=None,
                    job_type=None,
                    experience_level=None,
                    description=description,
                    source=self.SOURCE_NAME,
                    url=url,
                    posted_date=self.parse_date(entry["pub_date"]),
                    sponsorship=self.detect_sponsorship(title, description),
                )

                total += 1
                await self.emit(
                    EventTopic.SCRAPE_FOUND, count=total, title=record.title
                )
                yield record

            await self._throttle()

        await self.emit(EventTopic.SCRAPE_COMPLETED, count=total)

    @staticmethod
    def _parse_rss(xml: str) -> list[dict]:
        soup = BeautifulSoup(xml, "lxml-xml")
        items = []
        for node in soup.find_all("item"):
            title_n = node.find("title")
            link_n = node.find("link")
            desc_n = node.find("description")
            pub_n = node.find("pubDate")
            if title_n is None or link_n is None:
                continue
            description = ""
            if desc_n is not None:
                # Strip HTML from the description body.
                description = BeautifulSoup(desc_n.text, "lxml").get_text(
                    " ", strip=True
                )
            items.append(
                {
                    "title": (title_n.text or "").strip(),
                    "link": (link_n.text or "").strip(),
                    "description": description,
                    "pub_date": (pub_n.text or "").strip() if pub_n else "",
                }
            )
        return items
