"""Generate the Toma Timer tomato icon at multiple sizes.

Outputs PNGs to assets/icons/hicolor/<size>/apps/toma-timer.png plus a
512px master at assets/icons/toma-timer.png.

Run:  python assets/generate_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZES = [16, 22, 32, 48, 64, 128, 256, 512]
OUT_DIR = Path(__file__).resolve().parent / "icons"


def draw_tomato(size: int) -> Image.Image:
    """Draw a clean tomato icon at the given pixel size."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Geometry as fractions of the canvas
    body = [0.14 * s, 0.24 * s, 0.86 * s, 0.92 * s]        # main fruit
    leaf_y = 0.10 * s
    stem_cx, stem_top = 0.50 * s, 0.04 * s

    # Soft drop shadow under the fruit (subtle, skipped at tiny sizes)
    if s >= 48:
        shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse([body[0] + 2, body[1] + 3, body[2] + 2, body[3] + 3], fill=(0, 0, 0, 70))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=s * 0.02))
        img = Image.alpha_composite(img, shadow)
        d = ImageDraw.Draw(img)

    # Fruit body — red with slight gradient feel via two stacked ellipses
    d.ellipse(body, fill=(225, 60, 48, 255))
    # Darker lower rim
    rim = [body[0], body[1] + s * 0.45, body[2], body[3]]
    d.ellipse(rim, fill=(200, 45, 38, 255))
    # Re-overlay top to keep the highlight area bright
    d.ellipse([body[0], body[1], body[2], body[1] + s * 0.62], fill=(225, 60, 48, 255))

    # Glossy highlight (top-left)
    if s >= 32:
        hl = [0.24 * s, 0.34 * s, 0.46 * s, 0.52 * s]
        d.ellipse(hl, fill=(255, 165, 140, 180))
        # small bright spot
        d.ellipse([0.30 * s, 0.38 * s, 0.38 * s, 0.46 * s], fill=(255, 220, 200, 220))

    # Calyx (green leafy top) — five small leaves around the stem
    green = (58, 165, 74, 255)
    dark_green = (40, 130, 55, 255)
    import math
    n_leaves = 5
    leaf_len = 0.16 * s
    leaf_w = 0.07 * s
    cx, cy = stem_cx, leaf_y + 0.02 * s
    for i in range(n_leaves):
        ang = -math.pi / 2 + (i - (n_leaves - 1) / 2) * (math.pi / 5.5)
        ex = cx + math.cos(ang) * leaf_len
        ey = cy + math.sin(ang) * leaf_len
        # leaf as a rotated ellipse approximation: draw small ellipse at tip
        d.ellipse(
            [ex - leaf_w, ey - leaf_w * 0.6, ex + leaf_w, ey + leaf_w * 0.6],
            fill=green,
        )
    # central calyx blob
    d.ellipse([cx - 0.09 * s, cy - 0.04 * s, cx + 0.09 * s, cy + 0.06 * s], fill=dark_green)

    # Stem
    stem_w = max(2, 0.035 * s)
    d.rectangle(
        [cx - stem_w, stem_top, cx + stem_w, cy + 0.03 * s],
        fill=dark_green,
    )

    return img


def main() -> None:
    master = draw_tomato(512)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master.save(OUT_DIR / "toma-timer.png")
    for sz in SIZES:
        sub = OUT_DIR / "hicolor" / f"{sz}x{sz}" / "apps"
        sub.mkdir(parents=True, exist_ok=True)
        draw_tomato(sz).save(sub / "toma-timer.png")
    print(f"Generated {len(SIZES)} sizes + 512px master in {OUT_DIR}")


if __name__ == "__main__":
    main()
