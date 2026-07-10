"""Generate the static Open Graph preview image (1200x630) for SEO/link previews.

Run manually with `py -3 scripts/generate_og_image.py` whenever the brand palette changes.
Not part of the app's runtime; the output PNG is committed to src/na_planner/static/.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BG = "#F2EEE6"
NAVY = "#1A2733"
ACCENT = "#1E3A5F"
MUTED = "#5B6672"

FONTS_DIR = Path("C:/Windows/Fonts")


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS_DIR / name), size)


def main() -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    margin = 90

    # Top accent bar
    draw.rectangle([0, 0, WIDTH, 10], fill=ACCENT)

    # Eyebrow label
    eyebrow_font = load_font("arialbd.ttf", 24)
    draw.text((margin, 110), "NORTH AMERICAN UNIVERSITY", font=eyebrow_font, fill=ACCENT)

    # Title
    title_font = load_font("georgiab.ttf", 76)
    draw.text((margin, 165), "NA Course", font=title_font, fill=NAVY)
    draw.text((margin, 255), "Planner", font=title_font, fill=NAVY)

    # Subtitle
    sub_font = load_font("arial.ttf", 32)
    draw.text(
        (margin, 400),
        "Audit your transcript. Plan next term.",
        font=sub_font,
        fill=MUTED,
    )
    draw.text(
        (margin, 445),
        "Get a roadmap to graduation.",
        font=sub_font,
        fill=MUTED,
    )

    # Bottom URL chip
    url_font = load_font("arialbd.ttf", 26)
    draw.text((margin, HEIGHT - 90), "course-planner.dev", font=url_font, fill=ACCENT)

    repo_root = Path(__file__).resolve().parent.parent
    out_path = repo_root / "src" / "na_planner" / "static" / "og-image.png"
    img.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
