"""Generate Windows ICO and PNG icons from the source WebP logo.

Usage::

    python scripts/generate_icons.py

Requires Pillow (``pip install pillow`` or ``pip install -e '.[windows-native]'``).
Outputs:

* ``assets/shibaclaw.ico`` — multi-resolution Windows icon for PyInstaller
* ``assets/shibaclaw_16.png``  — 16 × 16 for pystray / small contexts
* ``assets/shibaclaw_32.png``  — 32 × 32
* ``assets/shibaclaw_64.png``  — 64 × 64
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "assets" / "shibaclaw_logo.webp"
ASSETS = ROOT / "assets"


def main() -> None:
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required: pip install pillow", file=sys.stderr)
        sys.exit(1)

    if not SRC.exists():
        print(f"Source image not found: {SRC}", file=sys.stderr)
        sys.exit(1)

    img = Image.open(SRC).convert("RGBA")

    # ------------------------------------------------------------------
    # PNG variants
    # ------------------------------------------------------------------
    for size in (16, 32, 64, 128, 256):
        out = ASSETS / f"shibaclaw_{size}.png"
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(out, format="PNG")
        print(f"  wrote {out.relative_to(ROOT)}")

    # ------------------------------------------------------------------
    # Multi-resolution ICO (Windows standard sizes)
    # ------------------------------------------------------------------
    ico_sizes = [16, 32, 48, 64, 128, 256]
    ico_images = [img.resize((s, s), Image.LANCZOS) for s in ico_sizes]
    ico_path = ASSETS / "shibaclaw.ico"
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_images[1:],
    )
    print(f"  wrote {ico_path.relative_to(ROOT)}")
    print("Icons generated successfully.")


if __name__ == "__main__":
    main()
