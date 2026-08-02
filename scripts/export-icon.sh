#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

uv run --with pillow python - <<'PY'
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("assets/icons")
OUT.mkdir(parents=True, exist_ok=True)
ORANGE = (234, 88, 12, 255)  # #EA580C
WHITE = (255, 255, 255, 255)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = int(size * 0.055)
    draw.ellipse((margin, margin, size - 1 - margin, size - 1 - margin), fill=ORANGE)
    # Prefer a bold TrueType; fall back to default bitmap font.
    font = None
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ):
        p = Path(name)
        if p.is_file():
            font = ImageFont.truetype(str(p), size=max(10, int(size * 0.38)))
            break
    if font is None:
        font = ImageFont.load_default()
    text = "SN"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=WHITE)
    return img


base = render(256)
base.save(OUT / "sn-manager.png", format="PNG")
# Pillow ICO: pass sizes= on a single image to embed multiple resolutions.
base.save(
    OUT / "sn-manager.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
)
print(f"Wrote {OUT / 'sn-manager.png'} and {OUT / 'sn-manager.ico'}")
PY
