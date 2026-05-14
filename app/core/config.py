"""Centralized application configuration via pydantic-settings.

All runtime configuration is read from environment variables (or a .env file
in the project root). Defaults are production-safe.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application-wide settings."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Application ----------
    app_name: str = Field(default="HireFlow AI", alias="APP_NAME")
    app_vendor: str = Field(default="Etwin Technology", alias="APP_VENDOR")
    app_version: str = Field(default="1.1.4", alias="APP_VERSION")
    app_env: Literal["development", "production", "test"] = Field(
        default="production", alias="APP_ENV"
    )
    debug: bool = Field(default=False, alias="DEBUG")

    # ---------- Database ----------
    database_url: str = Field(
        default="sqlite:///data/jobhunter.db", alias="DATABASE_URL"
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # ---------- Scraping ----------
    scraper_headless: bool = Field(default=True, alias="SCRAPER_HEADLESS")
    scraper_max_pages: int = Field(default=5, alias="SCRAPER_MAX_PAGES")
    scraper_retry_count: int = Field(default=3, alias="SCRAPER_RETRY_COUNT")
    scraper_timeout: int = Field(default=30, alias="SCRAPER_TIMEOUT")
    scraper_min_delay: float = Field(default=1.5, alias="SCRAPER_MIN_DELAY")
    scraper_max_delay: float = Field(default=4.0, alias="SCRAPER_MAX_DELAY")
    scraper_concurrent_limit: int = Field(
        default=3, alias="SCRAPER_CONCURRENT_LIMIT"
    )
    scraper_user_agent_rotate: bool = Field(
        default=True, alias="SCRAPER_USER_AGENT_ROTATE"
    )

    # ---------- Proxy ----------
    proxy_enabled: bool = Field(default=False, alias="PROXY_ENABLED")
    proxy_url: Optional[str] = Field(default=None, alias="PROXY_URL")
    proxy_username: Optional[str] = Field(default=None, alias="PROXY_USERNAME")
    proxy_password: Optional[str] = Field(default=None, alias="PROXY_PASSWORD")

    # ---------- Export ----------
    export_dir: str = Field(default="exports", alias="EXPORT_DIR")
    export_default_format: Literal["xlsx", "csv", "json"] = Field(
        default="xlsx", alias="EXPORT_DEFAULT_FORMAT"
    )
    export_auto_open: bool = Field(default=False, alias="EXPORT_AUTO_OPEN")

    # ---------- Scheduler ----------
    scheduler_enabled: bool = Field(default=False, alias="SCHEDULER_ENABLED")
    scheduler_interval_minutes: int = Field(
        default=120, alias="SCHEDULER_INTERVAL_MINUTES"
    )
    scheduler_daily_time: str = Field(default="08:00", alias="SCHEDULER_DAILY_TIME")
    scheduler_run_on_startup: bool = Field(
        default=False, alias="SCHEDULER_RUN_ON_STARTUP"
    )

    # ---------- Logging ----------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    log_file: str = Field(default="app.log", alias="LOG_FILE")
    log_rotation: str = Field(default="10 MB", alias="LOG_ROTATION")
    log_retention: str = Field(default="14 days", alias="LOG_RETENTION")

    # ---------- API ----------
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8765, alias="API_PORT")
    api_enabled: bool = Field(default=False, alias="API_ENABLED")

    # ---------- Security ----------
    secret_key: str = Field(
        default="change-me-to-a-long-random-string", alias="SECRET_KEY"
    )
    encryption_salt: str = Field(
        default="jobhunter-default-salt", alias="ENCRYPTION_SALT"
    )

    # ---------- Notifications ----------
    notifications_enabled: bool = Field(default=True, alias="NOTIFICATIONS_ENABLED")
    notify_on_complete: bool = Field(default=True, alias="NOTIFY_ON_COMPLETE")
    notify_on_error: bool = Field(default=True, alias="NOTIFY_ON_ERROR")

    # ---------- GUI ----------
    gui_theme: Literal["dark", "light", "system"] = Field(
        default="dark", alias="GUI_THEME"
    )
    gui_color_theme: str = Field(default="blue", alias="GUI_COLOR_THEME")
    gui_scaling: float = Field(default=1.0, alias="GUI_SCALING")

    # ---------- Derived paths ----------
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def export_path(self) -> Path:
        candidate = Path(self.export_dir)
        path = candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def log_path(self) -> Path:
        path = PROJECT_ROOT / self.log_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data_path(self) -> Path:
        path = PROJECT_ROOT / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def screenshots_path(self) -> Path:
        path = PROJECT_ROOT / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def proxy_config(self) -> Optional[dict]:
        if not self.proxy_enabled or not self.proxy_url:
            return None
        cfg: dict = {"server": self.proxy_url}
        if self.proxy_username:
            cfg["username"] = self.proxy_username
        if self.proxy_password:
            cfg["password"] = self.proxy_password
        return cfg

    @field_validator("scraper_max_delay")
    @classmethod
    def _validate_delay(cls, v: float, info) -> float:
        min_delay = info.data.get("scraper_min_delay", 1.0)
        if v < min_delay:
            return min_delay + 1.0
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()


settings: Settings = get_settings()
