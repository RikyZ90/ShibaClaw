"""Generate Windows ICO and PNG icons from the source WebP logo.

Usage::

    python scripts/generate_icons.py

Requires Pillow (``pip install pillow`` or ``pip install -e '.[windows-native]'``).
Outputs:

* ``assets/shibaclaw.ico`` — multi-resolution Windows icon for PyInstaller
* ``assets/shibaclaw_16.png``  — 16 × 16 for pystray / small contexts
* ``assets/shibaclaw_32.png``  — 32 × 32
* ``assets/shibaclaw_64.png``  — 64 × 64
* ``assets/shibaclaw_128.png`` — 128 × 128
* ``assets/shibaclaw_256.png`` — 256 × 256
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
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_path = ASSETS / "shibaclaw.ico"
    img.save(
        ico_path,
        format="ICO",
        sizes=ico_sizes,
    )

    generated = Image.open(ico_path)
    generated_sizes = set(generated.info.get("sizes", set()))
    missing_sizes = sorted(set(ico_sizes) - generated_sizes)
    if missing_sizes:
        print(
            f"Generated ICO is missing expected sizes: {missing_sizes}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  wrote {ico_path.relative_to(ROOT)}")
    print("Icons generated successfully.")


if __name__ == "__main__":
    main()
