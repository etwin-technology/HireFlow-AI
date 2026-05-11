"""File and folder management utilities (exports, logs, settings)."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.utils.helpers import slugify
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    """Centralized helpers for filesystem operations the app performs."""

    # ---------------- Path helpers ----------------
    @staticmethod
    def ensure_dir(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def timestamped_filename(prefix: str, extension: str) -> str:
        """Return ``<prefix>_<YYYYmmdd_HHMMSS>.<ext>``."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prefix = slugify(prefix) or "jobs"
        ext = extension.lstrip(".")
        return f"{safe_prefix}_{ts}.{ext}"

    @staticmethod
    def export_path(prefix: str, extension: str) -> Path:
        FileManager.ensure_dir(settings.export_path)
        return settings.export_path / FileManager.timestamped_filename(
            prefix, extension
        )

    # ---------------- JSON helpers ----------------
    @staticmethod
    def read_json(path: Path, default: Optional[Any] = None) -> Any:
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning(
                "read_json failed for {p}: {e}", p=str(path), e=str(exc)
            )
            return default

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        FileManager.ensure_dir(path.parent)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
        tmp.replace(path)

    # ---------------- Open helpers ----------------
    @staticmethod
    def open_in_explorer(path: Path) -> bool:
        """Open ``path`` (folder or file) in the OS file explorer."""
        try:
            target = str(path.resolve())
            system = platform.system()
            if system == "Windows":
                if path.is_dir():
                    os.startfile(target)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["explorer", "/select,", target])
                return True
            if system == "Darwin":
                subprocess.Popen(["open", target])
                return True
            subprocess.Popen(["xdg-open", target])
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("open_in_explorer failed: {e}", e=str(exc))
            return False

    @staticmethod
    def open_url(url: str) -> bool:
        """Open ``url`` in the default browser."""
        try:
            import webbrowser

            return webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("open_url failed: {e}", e=str(exc))
            return False

    @staticmethod
    def list_exports(limit: int = 50) -> list[Path]:
        """Return the most-recent files in the exports directory."""
        FileManager.ensure_dir(settings.export_path)
        files = [p for p in settings.export_path.iterdir() if p.is_file()]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:limit]

    @staticmethod
    def file_size_human(path: Path) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return "?"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    # ---------------- Logs ----------------
    @staticmethod
    def read_log_tail(lines: int = 500) -> str:
        log_file = settings.log_path / settings.log_file
        if not log_file.exists():
            return ""
        try:
            with log_file.open("r", encoding="utf-8", errors="ignore") as fh:
                buf = fh.readlines()[-lines:]
            return "".join(buf)
        except OSError as exc:
            logger.warning("read_log_tail failed: {e}", e=str(exc))
            return ""

    @staticmethod
    def clear_logs() -> bool:
        log_file = settings.log_path / settings.log_file
        try:
            if log_file.exists():
                log_file.unlink()
            return True
        except OSError as exc:
            logger.warning("clear_logs failed: {e}", e=str(exc))
            return False

    # ---------------- Python info ----------------
    @staticmethod
    def python_executable() -> str:
        return sys.executable
