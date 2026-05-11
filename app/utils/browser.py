"""Playwright browser orchestration with stealth + anti-bot features.

This module exposes a single ``BrowserManager`` class that:
- launches a Chromium instance with anti-detection flags,
- rotates user-agents / locales / timezones / viewports,
- applies the ``playwright-stealth`` patches,
- supports proxies via configuration,
- exposes context-manager and explicit lifecycle methods.

A scraper typically uses the ``new_page()`` helper to get a fresh, masked page.
"""

from __future__ import annotations

import random
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.core.config import settings
from app.core.constants import (
    BROWSER_LOCALES,
    BROWSER_TIMEZONES,
    BROWSER_VIEWPORTS,
    FALLBACK_USER_AGENTS,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Lazy/optional imports for fake-useragent + stealth (graceful fallback).
try:  # pragma: no cover - optional dependency
    from fake_useragent import UserAgent

    _UA_INSTANCE = UserAgent(browsers=["chrome", "firefox", "edge"])
except Exception:  # noqa: BLE001
    _UA_INSTANCE = None

try:  # pragma: no cover - optional dependency
    from playwright_stealth import stealth_async

    _STEALTH_AVAILABLE = True
except Exception:  # noqa: BLE001
    _STEALTH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Anti-bot init script injected into every page
# ---------------------------------------------------------------------------
_ANTI_DETECT_SCRIPT = r"""
// Mask webdriver flag
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Make plugins array look populated
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// Languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// Chrome runtime stub
window.chrome = window.chrome || { runtime: {} };

// Permissions API: report "denied" for notifications
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
}
"""


def pick_user_agent() -> str:
    """Return a random user-agent (fake-useragent if available)."""
    if _UA_INSTANCE is not None:
        try:
            return _UA_INSTANCE.random
        except Exception:  # noqa: BLE001
            pass
    return random.choice(FALLBACK_USER_AGENTS)


class BrowserManager:
    """High-level Playwright lifecycle helper for scrapers."""

    def __init__(
        self,
        *,
        headless: Optional[bool] = None,
        timeout_ms: Optional[int] = None,
    ) -> None:
        self.headless = settings.scraper_headless if headless is None else headless
        self.timeout_ms = (
            (timeout_ms if timeout_ms is not None else settings.scraper_timeout) * 1000
        )
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    # ---------------- Lifecycle ----------------
    async def start(self) -> None:
        if self._browser is not None:
            return
        logger.debug("Starting Playwright | headless={h}", h=self.headless)
        self._playwright = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--disable-gpu",
            "--window-size=1920,1080",
        ]
        launch_kwargs: dict = {"headless": self.headless, "args": launch_args}
        if proxy := settings.proxy_config:
            launch_kwargs["proxy"] = proxy
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self) -> None:
        try:
            if self._context is not None:
                await self._context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = None
        self._browser = None
        self._playwright = None

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    # ---------------- Page factory ----------------
    async def new_context(self) -> BrowserContext:
        """Return a fresh context with randomized fingerprint."""
        if self._browser is None:
            await self.start()
        assert self._browser is not None

        viewport = random.choice(BROWSER_VIEWPORTS)
        self._context = await self._browser.new_context(
            user_agent=pick_user_agent(),
            locale=random.choice(BROWSER_LOCALES),
            timezone_id=random.choice(BROWSER_TIMEZONES),
            viewport={"width": viewport[0], "height": viewport[1]},
            device_scale_factor=1.0,
            is_mobile=False,
            has_touch=False,
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        await self._context.add_init_script(_ANTI_DETECT_SCRIPT)
        self._context.set_default_timeout(self.timeout_ms)
        self._context.set_default_navigation_timeout(self.timeout_ms)
        return self._context

    async def new_page(self) -> Page:
        ctx = await self.new_context()
        page = await ctx.new_page()
        if _STEALTH_AVAILABLE:
            try:
                await stealth_async(page)
            except Exception as exc:  # noqa: BLE001
                logger.debug("stealth_async failed: {e}", e=exc)
        return page

    # ---------------- Page helpers ----------------
    @staticmethod
    async def smooth_scroll(
        page: Page, *, steps: int = 6, delay_ms: int = 350
    ) -> None:
        """Scroll to the bottom of ``page`` in human-like increments."""
        await page.evaluate(
            """async (params) => {
                const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                const total = document.body.scrollHeight;
                const step = total / params.steps;
                for (let i = 1; i <= params.steps; i++) {
                    window.scrollTo({top: step * i, behavior: 'smooth'});
                    await sleep(params.delay_ms);
                }
            }""",
            {"steps": steps, "delay_ms": delay_ms},
        )
