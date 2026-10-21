"""
Opal - icon generator
Plain English: draws the Opal app icon at every size Windows and the web
need, and writes the .ico the app installs itself with. The drawing itself
lives in opal_studio/brand.py so the mark can never drift from the app.

Usage:  python generate_icon.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from opal_studio.brand import app_icon_pixmap, opal_pixmap, wordmark_pixmap  # noqa: E402

APP_ICON = ROOT / "opal_studio" / "app.ico"
BRAND_DIR = ROOT / "website" / "assets" / "brand"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def main():
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    APP_ICON.parent.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        app_icon_pixmap(size).save(str(BRAND_DIR / f"icon-{size}.png"))
        opal_pixmap(size).save(str(BRAND_DIR / f"mark-{size}.png"))
    print(f"Wrote {len(SIZES)} icon sizes and {len(SIZES)} mark sizes to {BRAND_DIR}")

    # The Windows icon: several sizes inside one .ico.
    from PIL import Image

    Image.open(str(BRAND_DIR / "icon-256.png")).convert("RGBA").save(
        str(APP_ICON), format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Wrote {APP_ICON}")

    # The wordmark, as a PNG for the site header.
    wordmark_pixmap(96).save(str(BRAND_DIR / "wordmark.png"))
    print(f"Wrote {BRAND_DIR / 'wordmark.png'}")


if __name__ == "__main__":
    print("Generating the Opal icon set...")
    main()
    print("Done.")
