"""Generate HireFlow AI's logo set programmatically.

Produces, under ``app/gui/assets/``:
  - logo.png        512×512, full-resolution master
  - logo_256.png    256×256
  - logo_128.png    128×128
  - logo_64.png     64×64
  - logo_32.png     32×32
  - icon.ico        Windows multi-resolution icon (16/24/32/48/64/128/256)
  - icon.iconset/   macOS iconset folder (10 PNGs at Apple's required sizes)

The design is a rounded-square tile with a blue→cyan vertical gradient,
overlaid with a stylized "H" monogram and a small rising-arrow accent on
the right pillar (symbolizing the "Flow" half of HireFlow). A tiny "AI"
mark sits in the lower-right corner.

The .iconset folder is consumed by ``iconutil -c icns icon.iconset`` on
macOS to produce ``icon.icns`` (PyInstaller's BUNDLE step needs the
.icns; we generate the .iconset on all platforms because the PNGs are
portable, and the workflow runs iconutil on the macOS runner).

Run from the project root:
    python tools/generate_logo.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# -----------------------------------------------------------------------------
# Brand colors
# -----------------------------------------------------------------------------
GRADIENT_TOP: Tuple[int, int, int] = (31, 111, 235)      # primary blue (#1F6FEB)
GRADIENT_BOT: Tuple[int, int, int] = (91, 192, 248)      # cyan accent (#5BC0F8)
GLYPH_COLOR: Tuple[int, int, int, int] = (255, 255, 255, 255)
ACCENT_COLOR: Tuple[int, int, int, int] = (255, 220, 70, 255)  # warm spark


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "app" / "gui" / "assets"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def make_gradient(size: int) -> Image.Image:
    """Vertical gradient from GRADIENT_TOP → GRADIENT_BOT."""
    img = Image.new("RGB", (size, size), GRADIENT_TOP)
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        color = (
            _lerp(GRADIENT_TOP[0], GRADIENT_BOT[0], t),
            _lerp(GRADIENT_TOP[1], GRADIENT_BOT[1], t),
            _lerp(GRADIENT_TOP[2], GRADIENT_BOT[2], t),
        )
        for x in range(size):
            px[x, y] = color
    return img


def round_corners(img: Image.Image, radius_ratio: float = 0.22) -> Image.Image:
    """Apply a rounded-square alpha mask."""
    size = img.size[0]
    radius = int(size * radius_ratio)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius, fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def soft_shadow(img: Image.Image, blur: int = 12, offset: int = 4) -> Image.Image:
    """Composite the tile over a transparent canvas with a soft drop shadow."""
    pad = blur * 2 + offset
    size = img.size[0]
    canvas = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    shadow_mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(shadow_mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), int(size * 0.22), fill=int(255 * 0.40)
    )
    shadow_layer.paste(
        Image.new("RGBA", img.size, (0, 0, 0, 120)),
        (pad, pad + offset),
        shadow_mask,
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
    canvas = Image.alpha_composite(canvas, shadow_layer)
    canvas.alpha_composite(img, (pad, pad))
    return canvas


def draw_monogram(canvas: Image.Image) -> None:
    """Draw a stylized 'H' with a rising-arrow flourish on the right bar."""
    size = canvas.size[0]
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Geometry of the H
    left_x   = int(size * 0.28)
    right_x  = int(size * 0.72)
    bar_w    = int(size * 0.105)
    top_y    = int(size * 0.26)
    bot_y    = int(size * 0.74)
    mid_y    = int(size * 0.50)
    cross_h  = int(size * 0.085)

    # Left pillar — full height
    draw.rounded_rectangle(
        (left_x - bar_w // 2, top_y, left_x + bar_w // 2, bot_y),
        radius=bar_w // 2, fill=GLYPH_COLOR,
    )

    # Right pillar — full height
    draw.rounded_rectangle(
        (right_x - bar_w // 2, top_y, right_x + bar_w // 2, bot_y),
        radius=bar_w // 2, fill=GLYPH_COLOR,
    )

    # Crossbar (slightly thicker)
    draw.rounded_rectangle(
        (left_x, mid_y - cross_h // 2, right_x, mid_y + cross_h // 2),
        radius=cross_h // 2, fill=GLYPH_COLOR,
    )

    # Rising spark on the right pillar's upper tip (the "flow" accent)
    spark_r = int(size * 0.055)
    spark_cx = right_x
    spark_cy = top_y - int(size * 0.035)
    draw.ellipse(
        (spark_cx - spark_r, spark_cy - spark_r,
         spark_cx + spark_r, spark_cy + spark_r),
        fill=ACCENT_COLOR,
    )
    # Outer glow halo for the spark
    halo_r = int(spark_r * 1.7)
    halo = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse(
        (spark_cx - halo_r, spark_cy - halo_r,
         spark_cx + halo_r, spark_cy + halo_r),
        fill=(255, 220, 70, 80),
    )
    halo = halo.filter(ImageFilter.GaussianBlur(size * 0.012))
    canvas.alpha_composite(halo)


def draw_ai_badge(canvas: Image.Image) -> None:
    """Draw a prominent 'AI' badge in the lower-right corner."""
    size = canvas.size[0]
    draw = ImageDraw.Draw(canvas, "RGBA")
    badge_w = int(size * 0.28)
    badge_h = int(size * 0.115)
    pad_x = int(size * 0.06)
    pad_y = int(size * 0.07)
    x0 = size - badge_w - pad_x
    y0 = size - badge_h - pad_y
    # Solid white pill (more visible than translucent)
    draw.rounded_rectangle(
        (x0, y0, x0 + badge_w, y0 + badge_h),
        radius=badge_h // 2,
        fill=(255, 255, 255, 230),
    )
    text = "AI"
    font = _load_bold_font(int(badge_h * 0.62))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    # Center text in the badge — compensate for font ascent (bbox[1]).
    tx = x0 + (badge_w - tw) // 2 - bbox[0]
    ty = y0 + (badge_h - th) // 2 - bbox[1]
    draw.text((tx, ty), text, fill=GRADIENT_TOP, font=font)


def _load_bold_font(size_px: int) -> ImageFont.FreeTypeFont:
    """Try several known bold fonts before falling back to Pillow's default."""
    import os

    win_fonts = os.environ.get("WINDIR", "C:/Windows") + "/Fonts"
    candidates = [
        f"{win_fonts}/segoeuib.ttf",
        f"{win_fonts}/seguibl.ttf",
        f"{win_fonts}/arialbd.ttf",
        "segoeuib.ttf",
        "arialbd.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size_px)
        except OSError:
            continue
    return ImageFont.load_default()


# -----------------------------------------------------------------------------
# Build pipeline
# -----------------------------------------------------------------------------
def build_master(size: int = 512) -> Image.Image:
    gradient = make_gradient(size)
    tile = round_corners(gradient.convert("RGBA"))
    draw_monogram(tile)
    draw_ai_badge(tile)
    return tile


def generate() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    master = build_master(512)

    # Master + sized PNGs
    for px in (512, 256, 128, 64, 32):
        out = ASSETS_DIR / (f"logo_{px}.png" if px != 512 else "logo.png")
        master.resize((px, px), Image.LANCZOS).save(out, "PNG", optimize=True)
        print(f"  wrote {out.relative_to(PROJECT_ROOT)}")

    # Multi-resolution Windows icon
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                  (128, 128), (256, 256)]
    icon_path = ASSETS_DIR / "icon.ico"
    master.save(icon_path, format="ICO", sizes=icon_sizes)
    print(f"  wrote {icon_path.relative_to(PROJECT_ROOT)} (7 resolutions)")

    # macOS .iconset folder — Apple expects these exact filenames + sizes.
    # The CI workflow runs ``iconutil -c icns icon.iconset`` to bake it
    # into the icon.icns that PyInstaller's BUNDLE step references.
    iconset_dir = ASSETS_DIR / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)
    iconset_spec = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    # Up-scale once to 1024 so the @2x renders cleanly; everything else
    # is a Lanczos downscale from that master.
    iconset_master = master.resize((1024, 1024), Image.LANCZOS)
    for fname, px in iconset_spec:
        iconset_master.resize((px, px), Image.LANCZOS).save(
            iconset_dir / fname, "PNG", optimize=True
        )
    print(f"  wrote {iconset_dir.relative_to(PROJECT_ROOT)}/ ({len(iconset_spec)} PNGs)")

    print("Done.")


if __name__ == "__main__":
    generate()
