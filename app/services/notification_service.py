"""Cross-platform notification service.

Tries OS-level notifications (plyer) first; falls back to a Tk message box.
"""

from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


try:  # pragma: no cover - optional dependency
    from plyer import notification as _plyer

    _PLYER_OK = True
except Exception:  # noqa: BLE001
    _plyer = None
    _PLYER_OK = False


class NotificationService:
    """Send user-visible notifications."""

    def __init__(self, app_name: Optional[str] = None) -> None:
        self._app_name = app_name or settings.app_name

    def notify(
        self,
        title: str,
        message: str,
        *,
        kind: str = "info",
    ) -> None:
        if not settings.notifications_enabled:
            return
        if kind == "success" and not settings.notify_on_complete:
            return
        if kind == "error" and not settings.notify_on_error:
            return

        sent = False
        if _PLYER_OK and _plyer is not None:
            try:
                _plyer.notify(
                    title=title,
                    message=message[:240],
                    app_name=self._app_name,
                    timeout=6,
                )
                sent = True
            except Exception as exc:  # noqa: BLE001
                logger.debug("Plyer notify failed: {e}", e=str(exc))

        if not sent:
            self._fallback_message_box(title, message, kind)

        logger.debug("Notification | {k} | {t}: {m}", k=kind, t=title, m=message)

    # ---------------- Convenience wrappers ----------------
    def info(self, title: str, message: str) -> None:
        self.notify(title, message, kind="info")

    def success(self, title: str, message: str) -> None:
        self.notify(title, message, kind="success")

    def error(self, title: str, message: str) -> None:
        self.notify(title, message, kind="error")

    # ---------------- Internals ----------------
    @staticmethod
    def _fallback_message_box(title: str, message: str, kind: str) -> None:
        try:
            import tkinter as tk
            from tkinter import messagebox

            # Use a transient root so we don't crash if no main loop exists.
            root = tk.Tk()
            root.withdraw()
            try:
                if kind == "error":
                    messagebox.showerror(title, message)
                elif kind == "success":
                    messagebox.showinfo(title, message)
                else:
                    messagebox.showinfo(title, message)
            finally:
                try:
                    root.destroy()
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            # Last-ditch: just log it.
            logger.info("Notification ({k}) {t}: {m} (fallback failed: {e})",
                        k=kind, t=title, m=message, e=str(exc))
