"""
Opal - Product screenshot capture
Plain English: Renders the real app windows offscreen and saves PNGs for the
website and the README, so the marketing always shows the actual product.
Usage:  python tools/capture_screenshots.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Qt's offscreen plugin does not look in the Windows font folder on its own,
# so every label would render as an empty box. Point it at the real fonts.
if sys.platform.startswith("win") and "QT_QPA_FONTDIR" not in os.environ:
    _fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    if _fonts.is_dir():
        os.environ["QT_QPA_FONTDIR"] = str(_fonts)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QTimer

OUT = ROOT / "website" / "assets" / "screenshots"
WORK = ROOT / "test_sandbox" / "shots"


def pump(app, ms=400):
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def make_samples():
    WORK.mkdir(parents=True, exist_ok=True)
    bazaar_src = ROOT / "website" / "assets" / "screenshots" / "brand" / "jaisalmer_bazaar.jpg"

    import shutil
    photo_path = WORK / "jaisalmer_bazaar.jpg"
    if bazaar_src.exists():
        shutil.copy2(bazaar_src, photo_path)
        shutil.copy2(bazaar_src, WORK / "portrait.jpg")

    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((64, 90), "Service Agreement", fontsize=22, fontname="hebo")
    page.insert_text((64, 120), "Between the Service Provider and the Citizen", fontsize=11)
    page.insert_text((64, 170), "1. Scope of work", fontsize=13, fontname="hebo")
    page.insert_text((64, 190), "The provider shall complete the requested service and deliver the",
                     fontsize=10.5)
    page.insert_text((64, 205), "output on the same day. All processing happens on this computer.",
                     fontsize=10.5)
    page.insert_text((64, 250), "2. Fees and receipts", fontsize=13, fontname="hebo")
    for i in range(12):
        page.insert_text((64, 275 + i * 16), f"{i + 1}.  Clause {i + 1} describing the agreed terms "
                                            f"and obligations of both parties.", fontsize=10.5)
    page.draw_rect(fitz.Rect(64, 560, 300, 620), color=(0.85, 0.45, 0.05), width=1.2)
    page.insert_text((80, 585), "Signature of the applicant", fontsize=9, color=(0.4, 0.4, 0.45))
    page.draw_line(fitz.Point(70, 640), fitz.Point(280, 640), color=(0.6, 0.6, 0.65), width=0.8)
    page.insert_text((70, 632), "Customer signature", fontsize=8.5, color=(0.45, 0.45, 0.5))
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((64, 90), "Schedule of charges", fontsize=18, fontname="hebo")
    for i in range(16):
        page2.insert_text((64, 130 + i * 22), f"Service {i + 1:<3}  ..............  "
                                              f"Rs. {50 + i * 25}", fontsize=11)
    doc.save(str(WORK / "agreement.pdf"))
    doc.close()
    return photo_path, WORK / "agreement.pdf"


def capture(widget, name, app, settle=500):
    widget.resize(widget.size() if widget.width() > 200 else widget.size())
    widget.show()
    pump(app, settle)
    pix = widget.grab()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    pix.save(str(path))
    print(f"  saved {path.name}  ({pix.width()}x{pix.height()})")
    widget.hide()
    return path


def main():
    app = QApplication(sys.argv)
    from opal_studio.theme import build_stylesheet
    app.setStyleSheet(build_stylesheet())
    photo, pdf = make_samples()

    print("Capturing product screenshots...")

    from opal_studio.dashboard import OpalDashboard
    dashboard = OpalDashboard()
    dashboard.resize(1080, 720)
    capture(dashboard, "01-dashboard", app)

    from opal_studio.float_viewer import FloatStudio
    studio = FloatStudio()
    studio.resize(1180, 780)
    studio.open_file(str(photo))
    pump(app, 500)
    capture(studio, "02-image-lab", app, settle=700)

    from opal_studio.viewer_pdf import PdfStudio
    pdf_studio = PdfStudio(str(pdf))
    pdf_studio.resize(1180, 800)
    pdf_studio.show()
    pump(app, 700)
    capture(pdf_studio, "03-pdf-studio", app, settle=600)

    from opal_studio.radial_widget import RadialMenuWidget
    wheel = RadialMenuWidget()
    wheel.show_for_files([str(photo)], QPoint(0, 0), initial_mode="tools")
    pump(app, 400)
    wheel.hovered_index = 0
    wheel.update()
    capture(wheel, "04-wheel-tools", app, settle=300)

    wheel2 = RadialMenuWidget()
    wheel2.show_for_files([str(photo)], QPoint(0, 0), initial_mode="convert")
    pump(app, 400)
    wheel2.hovered_index = 1
    wheel2.update()
    capture(wheel2, "04b-wheel-convert", app, settle=300)

    from opal_studio.viewer_doc import DocStudio
    notes = WORK / "notice.txt"
    notes.write_text("Government of India\n\nThis document is issued for public use.\n",
                     encoding="utf-8")
    doc_view = DocStudio(str(notes))
    doc_view.resize(1000, 620)
    capture(doc_view, "05-document-viewer", app)

    print("Done.")


if __name__ == "__main__":
    main()
