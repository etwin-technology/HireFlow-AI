"""Persist user-modifiable settings to disk and apply them at runtime.

Pydantic-settings loads defaults from environment / .env at startup. On top
of that, we layer a small JSON file (``data/user_settings.json``) that the
GUI's Settings panel writes to. The next time the app starts, those values
are reapplied so the user's preferences survive restarts.

Only a curated whitelist of fields is persisted — sensitive things like
``SECRET_KEY`` are never written here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Whitelist of pydantic-settings attributes that can be persisted and live-applied.
PERSISTED_FIELDS: tuple[str, ...] = (
    # Scraping
    "scraper_headless",
    "scraper_max_pages",
    "scraper_retry_count",
    "scraper_min_delay",
    "scraper_max_delay",
    "scraper_concurrent_limit",
    "scraper_user_agent_rotate",
    # Export
    "export_dir",
    "export_default_format",
    "export_auto_open",
    # Scheduler
    "scheduler_enabled",
    "scheduler_interval_minutes",
    "scheduler_daily_time",
    "scheduler_run_on_startup",
    # Notifications
    "notifications_enabled",
    "notify_on_complete",
    "notify_on_error",
    # GUI
    "gui_theme",
    "gui_color_theme",
    "gui_scaling",
)


class SettingsService:
    """Load / save the user-settings JSON overlay and apply it live."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._path: Path = file_path or (settings.data_path / "user_settings.json")

    # ---------------- Persistence ----------------
    @property
    def file_path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return {}
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read user settings: {e}", e=str(exc))
            return {}

    def save(self, values: dict[str, Any]) -> None:
        sanitized = {k: v for k, v in values.items() if k in PERSISTED_FIELDS}
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(sanitized, fh, indent=2, ensure_ascii=False, default=str)
            tmp.replace(self._path)
            logger.info("Persisted {n} user settings to {p}",
                        n=len(sanitized), p=self._path.name)
        except OSError as exc:
            logger.error("Failed to save user settings: {e}", e=str(exc))

    # ---------------- Apply ----------------
    def apply(self, values: dict[str, Any]) -> dict[str, Any]:
        """Apply ``values`` to the live ``settings`` object.

        Returns the (potentially coerced) values that were applied — useful
        for callers that want to feed them back into the GUI.
        """
        applied: dict[str, Any] = {}
        for key, raw in values.items():
            if key not in PERSISTED_FIELDS:
                continue
            if not hasattr(settings, key):
                continue
            current = getattr(settings, key)
            coerced = self._coerce(raw, type(current) if current is not None else None)
            try:
                setattr(settings, key, coerced)
                applied[key] = coerced
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not apply setting {k}={v}: {e}",
                               k=key, v=raw, e=str(exc))
        return applied

    def load_and_apply(self) -> dict[str, Any]:
        return self.apply(self.load())

    @staticmethod
    def _coerce(value: Any, target_type: Optional[type]) -> Any:
        if target_type is None or isinstance(value, target_type):
            return value
        try:
            if target_type is bool:
                if isinstance(value, str):
                    return value.strip().lower() in {"1", "true", "yes", "on"}
                return bool(value)
            if target_type is int:
                return int(value)
            if target_type is float:
                return float(value)
            if target_type is str:
                return str(value)
        except (TypeError, ValueError):
            pass
        return value
