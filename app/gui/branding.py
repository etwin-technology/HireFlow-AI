"""Centralized logo / branding asset loading.

Works in both development (running from source) and packaged builds
(PyInstaller `_MEIPASS`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image

from app.utils.logger import get_logger

logger = get_logger(__name__)


def assets_dir() -> Path:
    """Return the directory containing logo files (works in PyInstaller too)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app" / "gui" / "assets"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "assets"


def logo_path(size: int = 256) -> Optional[Path]:
    """Return the path to the closest available logo PNG."""
    options = (size, 256, 128, 64, 32, 512)
    for candidate in options:
        name = "logo.png" if candidate == 512 else f"logo_{candidate}.png"
        path = assets_dir() / name
        if path.exists():
            return path
    return None


def icon_path() -> Optional[Path]:
    """Return the Windows .ico path used for window/taskbar icons."""
    path = assets_dir() / "icon.ico"
    return path if path.exists() else None


def load_ctk_image(size_px: int) -> Optional[ctk.CTkImage]:
    """Return a HiDPI-aware CTkImage of the logo at ``size_px`` (square).

    Returns ``None`` if the logo file can't be found.
    """
    path = logo_path(size_px)
    if path is None:
        logger.debug("No logo asset found in {d}", d=assets_dir())
        return None
    try:
        pil_img = Image.open(path).convert("RGBA")
        return ctk.CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=(size_px, size_px),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load logo {p}: {e}", p=str(path), e=str(exc))
        return None


def set_window_icon(window) -> None:
    """Apply the multi-resolution ICO to ``window`` (Tk root or Toplevel)."""
    ico = icon_path()
    if ico is None:
        return
    try:
        window.iconbitmap(default=str(ico))
    except Exception as exc:  # noqa: BLE001
        # On some platforms iconbitmap fails — fall back to wm_iconphoto.
        try:
            png = logo_path(64)
            if png is not None:
                import tkinter as tk

                window.iconphoto(True, tk.PhotoImage(file=str(png)))
        except Exception as exc2:  # noqa: BLE001
            logger.debug(
                "Could not set window icon: {e1} / {e2}",
                e1=str(exc), e2=str(exc2),
            )
