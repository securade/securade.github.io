#!/usr/bin/env python3
"""Generate the 1200x630 Open Graph / Twitter social card for Securade.ai.

Writes /assets/images/og-default.png. Uses the brand teal palette, the existing
logo PNG, and inline drawing primitives (PIL). No external assets needed beyond
the logo and Inter from the system fallback (Helvetica/Arial if Inter absent).
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "images" / "og-default.png"
LOGO = ROOT / "assets" / "images" / "logo" / "logo.png"

W, H = 1200, 630

# Brand palette
INK = (11, 18, 32)
INK_MUTED = (160, 174, 192)
BRAND_400 = (92, 191, 191)
BRAND_600 = (42, 133, 133)
BRAND_900 = (14, 50, 50)
ACCENT_GRID = (92, 191, 191, 28)


def find_font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for n in names:
        candidates.insert(0, n)
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_grid(img: Image.Image) -> None:
    """Subtle teal grid overlay, in the spirit of the SVG illustrations."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    step = 60
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=ACCENT_GRID, width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=ACCENT_GRID, width=1)
    img.alpha_composite(overlay)


def draw_glow(img: Image.Image, cx: int, cy: int, r: int, color: tuple[int, int, int, int]) -> None:
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=80))
    img.alpha_composite(glow)


def draw_camera_node(img: Image.Image, x: int, y: int, size: int = 1) -> None:
    """Small CCTV-camera glyph for decorative purposes."""
    s = size
    d = ImageDraw.Draw(img)
    # body
    d.rounded_rectangle([x, y, x + 80 * s, y + 50 * s], radius=8, fill=(255, 255, 255, 255))
    # lens
    d.ellipse([x + 9 * s, y + 12 * s, x + 35 * s, y + 38 * s], fill=INK)
    d.ellipse([x + 15 * s, y + 18 * s, x + 29 * s, y + 32 * s], fill=BRAND_400)
    d.ellipse([x + 18 * s, y + 21 * s, x + 22 * s, y + 25 * s], fill=(255, 255, 255, 200))
    # label bars
    d.rounded_rectangle([x + 44 * s, y + 14 * s, x + 68 * s, y + 18 * s], radius=2, fill=(11, 18, 32, 120))
    d.rounded_rectangle([x + 44 * s, y + 22 * s, x + 62 * s, y + 26 * s], radius=2, fill=(11, 18, 32, 80))
    # status LED
    d.ellipse([x + 65 * s, y + 38 * s, x + 71 * s, y + 44 * s], fill=(34, 197, 94))


def main():
    base = Image.new("RGBA", (W, H), (250, 250, 247, 255))  # surface-2
    # Dark gradient panel on right
    right = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(right)
    for i, x in enumerate(range(620, W)):
        alpha = int(220 * (i / (W - 620)))
        rd.line([(x, 0), (x, H)], fill=(15, 23, 34, min(255, alpha + 30)))
    base.alpha_composite(right)

    # Soft teal glow
    draw_glow(base, 980, 200, 240, (92, 191, 191, 110))
    draw_glow(base, 220, 540, 200, (42, 133, 133, 70))

    # Grid overlay
    draw_grid(base)

    d = ImageDraw.Draw(base)

    # Logo top-left
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        # Logo is 1024x332 — resize to 240 wide
        logo_w = 240
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        base.alpha_composite(logo, (72, 70))

    # Headline
    h1_font = find_font(["Inter-Bold", "InterTight-ExtraBold"], 76)
    h2_font = find_font(["Inter-Medium"], 32)
    h3_font = find_font(["Inter-SemiBold"], 22)

    # Eyebrow
    d.rounded_rectangle([72, 200, 72 + 220, 200 + 38], radius=19, fill=(92, 191, 191, 50))
    d.text((72 + 14, 200 + 8), "SAFETY, POWERED BY AI", fill=BRAND_600, font=find_font(["Inter-Bold"], 16))

    # H1 (multi-line)
    h1_lines = ["Generative AI", "video analytics", "for workplace safety."]
    y = 260
    for i, line in enumerate(h1_lines):
        # Middle line in teal accent
        color = BRAND_600 if i == 1 else INK
        d.text((72, y), line, fill=color, font=h1_font)
        y += 84

    # Award row bottom
    award_y = 540
    d.text((72, award_y), "Recognised by IEEE Tech4Good · AI for Public Good · WSH Award 2023",
           fill=INK_MUTED, font=h3_font)

    # Right-hand visual: camera nodes connected to a central HUB card
    cx = 920
    cy = 320

    # Lines
    nodes = [(cx - 130, cy - 160), (cx + 100, cy - 170), (cx - 150, cy + 70), (cx + 120, cy + 80)]
    for nx, ny in nodes:
        d.line([(nx + 40, ny + 25), (cx, cy)], fill=(92, 191, 191, 180), width=2)

    # Cameras (small)
    for nx, ny in nodes:
        draw_camera_node(base, nx, ny, size=1)

    # Central HUB card
    card_w, card_h = 220, 140
    cx0, cy0 = cx - card_w // 2, cy - card_h // 2
    # Shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([cx0, cy0 + 14, cx0 + card_w, cy0 + card_h + 14], radius=16, fill=(0, 0, 0, 80))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))
    base.alpha_composite(shadow)

    d.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + card_h], radius=16, fill=(15, 23, 34, 255))
    d.rounded_rectangle([cx0, cy0, cx0 + card_w, cy0 + card_h], radius=16, outline=(92, 191, 191, 140), width=2)

    # HUB badge
    d.rounded_rectangle([cx0 + 14, cy0 + 14, cx0 + 14 + 56, cy0 + 14 + 26], radius=13, fill=(92, 191, 191, 60))
    d.text((cx0 + 14 + 13, cy0 + 14 + 4), "HUB", fill=BRAND_400, font=find_font(["Inter-Bold"], 14))

    # Detection rows
    row_font = find_font(["Inter-Medium"], 13)
    rows = [
        ((34, 197, 94), "hard hat detected", "98%"),
        ((34, 197, 94), "high-vis vest ok", "96%"),
        ((245, 158, 11), "person near forklift", "82%"),
    ]
    ry = cy0 + 56
    for (col, label, conf) in rows:
        d.ellipse([cx0 + 18, ry, cx0 + 26, ry + 8], fill=col)
        d.text((cx0 + 36, ry - 4), label, fill=(224, 230, 237), font=row_font)
        d.text((cx0 + card_w - 50, ry - 4), conf, fill=(160, 174, 192), font=row_font)
        ry += 24

    # Save
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)}  ({W}x{H})")


if __name__ == "__main__":
    main()
