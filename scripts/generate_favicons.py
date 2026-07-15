"""Generate the favicon set from the site's brand mark (navy rounded box + serif "N",
matching the app-bar logo in index.html: #1E3A5F box, #F2EEE6 letter).

Run manually with `py -3 scripts/generate_favicons.py` whenever the brand mark changes.
Not part of the app's runtime; the outputs are committed to src/na_planner/static/:
  - favicon.ico          (16 + 32 + 48 px, transparent rounded corners)
  - apple-touch-icon.png (180 px, full-bleed opaque — iOS rounds it itself)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = "#1E3A5F"
CREAM = "#F2EEE6"
FONTS_DIR = Path("C:/Windows/Fonts")

# Header mark proportions (34px box, 9px radius, 18px letter) scaled up.
RADIUS_RATIO = 9 / 34
# Slightly larger letter than the header's 18/34 so it stays legible at 16px.
LETTER_RATIO = 0.62


def draw_mark(size: int, rounded: bool = True) -> Image.Image:
    """The brand mark at `size` px. Rendered 4x and downsampled for smooth edges."""
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(s * RADIUS_RATIO) if rounded else 0
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=NAVY)
    font = ImageFont.truetype(str(FONTS_DIR / "georgiab.ttf"), int(s * LETTER_RATIO))
    left, top, right, bottom = draw.textbbox((0, 0), "N", font=font)
    x = (s - (right - left)) / 2 - left
    y = (s - (bottom - top)) / 2 - top
    draw.text((x, y), "N", font=font, fill=CREAM)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "src" / "na_planner" / "static"

    ico_sizes = [16, 32, 48]
    images = [draw_mark(sz) for sz in ico_sizes]
    ico_path = out_dir / "favicon.ico"
    images[-1].save(ico_path, format="ICO",
                    sizes=[(sz, sz) for sz in ico_sizes],
                    append_images=images[:-1])
    print(f"Wrote {ico_path}")

    # iOS applies its own corner mask, so the touch icon is a full-bleed square.
    apple = draw_mark(180, rounded=False).convert("RGB")
    apple_path = out_dir / "apple-touch-icon.png"
    apple.save(apple_path)
    print(f"Wrote {apple_path}")


if __name__ == "__main__":
    main()
