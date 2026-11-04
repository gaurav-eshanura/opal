"""
Opal - Full product screen capture
Plain English: Renders every user-facing screen of the app offscreen, each one
in a real "in use" state (files loaded, tools selected, dialogs open, menus
shown), and saves PNGs so we can audit every pixel of the product.
Usage:  python tools/capture_all_screens.py [out_dir]
"""

import os
import sys
import time
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
sys.path.insert(0, str(ROOT / "tools"))

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("TEMP", r"C:\Temp")) / "opal_screens_all"
OUT.mkdir(parents=True, exist_ok=True)

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTabWidget
from PySide6.QtCore import QPoint, QPointF, QRectF, QEvent, Qt
from PySide6.QtGui import QMouseEvent

import capture_screenshots as cs  # reuse pump() and make_samples()

pump = cs.pump
WORK = cs.WORK


def grab(widget, name, app, settle=450):
    if (OUT / f"{name}.png").exists():
        print(f"  skip {name}.png (already captured)")
        return OUT / f"{name}.png"
    widget.show()
    pump(app, settle)
    pix = widget.grab()
    path = OUT / f"{name}.png"
    pix.save(str(path))
    print(f"  saved {name}.png  ({pix.width()}x{pix.height()})")
    widget.hide()
    return path


def make_doc_samples():
    """Text/markdown/csv/json/archive/ebook/font/video samples for the viewers."""
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "notes.txt").write_text("Government of India\n\nNotice line one\nnotice line two\n"
                                     "notice line three\n" * 10, encoding="utf-8")
    (WORK / "readme.md").write_text("# Service Notice\n\nSome *markdown* text with rules.\n\n"
                                    "- one\n- two\n", encoding="utf-8")
    (WORK / "data.csv").write_text("item,qty,price\nPen,12,25\nBook,4,499\nBag,2,1299\n", encoding="utf-8")
    (WORK / "data.json").write_text('{"tool": "convert", "nested": {"x": 1}, "list": [1, 2, 3]}',
                                    encoding="utf-8")
    import zipfile
    with zipfile.ZipFile(WORK / "bundle.zip", "w") as z:
        z.writestr("hello.txt", "inside the archive")
        z.writestr("sub/folder.txt", "nested file")
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier("x")
    book.set_title("Tiny Book")
    book.set_language("en")
    ch = epub.EpubHtml(title="Only Chapter", file_name="c1.xhtml", lang="en")
    ch.content = "<h1>Chapter</h1><p>Once upon a time there was a notice.</p>"
    book.add_item(ch)
    book.toc = [ch]
    book.spine = ["nav", ch]
    book.add_item(epub.EpubNav())
    epub.write_epub(str(WORK / "book.epub"), book, {})
    font_src = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    if font_src.exists():
        import shutil
        shutil.copy2(font_src, WORK / "arial.ttf")
    clip = WORK / "clip.mp4"
    if not clip.exists():
        from opal_studio.engine import OpalEngine
        ff = OpalEngine.get_ffmpeg_bin()
        if ff:
            import subprocess
            subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=2",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            str(clip)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    return {p.stem: p for p in WORK.iterdir()}


FAKE_HISTORY = [
    {"source_name": "passport_scan.jpg", "target_name": "passport_scan.png",
     "action": "convert", "output_path": "", "saved_bytes": 184320, "timestamp": time.time() - 3600},
    {"source_name": "agreement.pdf", "target_name": "agreement_signed.pdf",
     "action": "sign", "output_path": "", "saved_bytes": 402112, "timestamp": time.time() - 86400},
    {"source_name": "receipt.jpg", "target_name": "receipt_upscaled.jpg",
     "action": "upscale", "output_path": "", "saved_bytes": 1240096, "timestamp": time.time() - 172800},
]


def main():
    app = QApplication(sys.argv)
    from opal_studio.theme import build_stylesheet
    app.setStyleSheet(build_stylesheet())

    photo, pdf = cs.make_samples()
    docs = make_doc_samples()
    # Recent files list points at real files so the home tab shows entries.
    for i, entry in enumerate(FAKE_HISTORY):
        entry["output_path"] = str(photo if i % 2 == 0 else pdf)

    # Keep the real history.json untouched - patch the reader in this process only.
    from opal_studio.config import ConfigManager
    ConfigManager.load_history = classmethod(lambda cls: [dict(e) for e in FAKE_HISTORY])

    print("Capturing every screen...")

    # --- 1. Dashboard, empty and working ---
    from opal_studio.dashboard import OpalDashboard
    dash = OpalDashboard()
    dash.resize(1080, 720)
    grab(dash, "01-dashboard", app)
    dash.set_queue_status(True, 3)
    pump(app, 250)
    grab(dash, "02-dashboard-working", app, settle=250)
    dash.set_queue_status(False, 0)

    # --- 2. Tray menu ---
    from opal_studio.tray import OpalTray
    tray = OpalTray()
    menu = tray.contextMenu()
    menu.popup(QPoint(80, 60))
    pump(app, 350)
    pix = menu.grab()
    pix.save(str(OUT / "03-tray-menu.png"))
    print(f"  saved 03-tray-menu.png  ({pix.width()}x{pix.height()})")
    menu.close()

    # --- 3. Settings & History dialogs ---
    from opal_studio.settings_dialog import SettingsDialog
    grab(SettingsDialog(), "04-settings", app)
    from opal_studio.history_dialog import HistoryDialog
    grab(HistoryDialog(), "05-history", app)

    # --- 4. Toast ---
    from opal_studio.toast import OpalToast
    toast = OpalToast()
    toast.show_message("Conversion Complete", f"Saved {Path(photo).name} next to the original.",
                       str(photo))
    pump(app, 350)
    pix = toast.grab()
    pix.save(str(OUT / "06-toast.png"))
    print(f"  saved 06-toast.png  ({pix.width()}x{pix.height()})")
    toast.hide()

    # --- 5. Drop orb, idle and drag-over ---
    from opal_studio.drop_orb import DropOrbWidget
    orb = DropOrbWidget()
    grab(orb, "07-drop-orb", app, settle=250)
    orb.is_drag_over = True
    orb.update()
    grab(orb, "07b-drop-orb-dragover", app, settle=250)

    # --- 6. Radial wheel: tools page 1, More page 2, convert, actions ---
    from opal_studio.radial_widget import RadialMenuWidget
    wheel = RadialMenuWidget()
    wheel.show_for_files([str(photo)], QPoint(0, 0), initial_mode="tools")
    pump(app, 400)
    wheel.hovered_index = 0
    wheel.update()
    grab(wheel, "08-wheel-tools", app, settle=250)
    more_idx = next((i for i, o in enumerate(wheel.options) if o["id"] == wheel.MORE_ID), None)
    if more_idx is not None:
        wheel.hovered_index = more_idx
        wheel._trigger_current()
        pump(app, 300)
        wheel.hovered_index = 0
        wheel.update()
        grab(wheel, "09-wheel-tools-more", app, settle=250)

    wheel2 = RadialMenuWidget()
    wheel2.show_for_files([str(photo)], QPoint(0, 0), initial_mode="convert")
    pump(app, 400)
    wheel2.hovered_index = 1
    wheel2.update()
    grab(wheel2, "10-wheel-convert", app, settle=250)

    wheel3 = RadialMenuWidget()
    wheel3.show_for_files([str(photo)], QPoint(0, 0), initial_mode="actions")
    pump(app, 400)
    wheel3.hovered_index = 2
    wheel3.update()
    grab(wheel3, "11-wheel-actions", app, settle=250)

    # --- 7. Floating Studio: home grid, then file tabs chrome ---
    from opal_studio.float_viewer import FloatStudio
    studio = FloatStudio()
    studio.resize(1180, 780)
    pump(app, 500)
    grab(studio, "12-float-home", app)
    studio.open_file(str(photo))
    studio.open_file(str(docs["notes"]))
    pump(app, 500)
    studio.tabs.setCurrentIndex(1)
    pump(app, 300)
    grab(studio, "13-float-tabs", app)

    # --- 8. Image Lab states ---
    from opal_studio.viewer_image import ImageLab
    lab = ImageLab(str(photo))
    lab.resize(1180, 780)
    grab(lab, "14-image-lab-default", app, settle=600)

    lab.set_tool("crop")
    pump(app, 250)
    target = lab.canvas.image_rect()
    lab.canvas.crop_fixed_ratio = 1.0
    lab.canvas.crop_rect = QRectF(target.x() + 40, target.y() + 40,
                                  target.width() - 100, target.height() - 100)
    lab.canvas.update()
    pump(app, 200)
    grab(lab, "15-image-crop", app, settle=250)
    lab.canvas.crop_rect = None

    lab.set_tool("rotate")
    pump(app, 250)
    grab(lab, "16-image-rotate", app, settle=250)

    lab.set_tool("exif")
    pump(app, 300)
    grab(lab, "17-image-exif", app, settle=250)

    lab.set_tool("signature")
    pump(app, 300)
    grab(lab, "18-image-signature", app, settle=250)

    # Signature pad dialog, Type tab with a typed name
    from opal_studio.viewer_pdf import SignatureDialog
    sig = SignatureDialog(lab)
    sig.resize(520, 460)
    sig.name_edit.setText("Ramesh Kumar")
    sig.tabs.setCurrentIndex(1)
    pump(app, 250)
    grab(sig, "19-signature-dialog-type", app, settle=250)

    # --- 9. PDF Studio states ---
    from opal_studio.viewer_pdf import PdfStudio
    pdf_studio = PdfStudio(str(pdf))
    pdf_studio.resize(1180, 800)
    pump(app, 700)
    grab(pdf_studio, "20-pdf-main", app, settle=400)

    # Annotate: highlight tool selected + a real highlight dragged on page 1
    pdf_studio.set_tool("highlight")
    pump(app, 250)
    try:
        view = pdf_studio.views[0]

        def mev(t, x, y):
            return QMouseEvent(t, QPointF(x, y), QPointF(x, y),
                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        view.mousePressEvent(mev(QEvent.MouseButtonPress, 120, 300))
        view.mouseMoveEvent(mev(QEvent.MouseMove, 300, 360))
        view.mouseReleaseEvent(mev(QEvent.MouseButtonRelease, 300, 360))
        pump(app, 300)
    except Exception as e:
        print(f"  (annotation drag skipped: {e})")
    pdf_studio.refresh_comments()
    pump(app, 200)
    grab(pdf_studio, "21-pdf-annotate", app, settle=250)

    # Search with live matches
    pdf_studio.search_input.setText("Service")
    pump(app, 600)
    grab(pdf_studio, "22-pdf-search", app, settle=300)

    side = next((t for t in pdf_studio.findChildren(QTabWidget) if t.count() == 3), None)
    if side is not None:
        side.setCurrentIndex(1)
        pump(app, 250)
        grab(pdf_studio, "23-pdf-comments", app, settle=250)
        side.setCurrentIndex(2)
        pump(app, 250)
        grab(pdf_studio, "24-pdf-inspector", app, settle=250)

    # Modal dialogs: show, grab, dismiss (patched exec - never blocks)
    real_exec = QDialog.exec

    def fake_exec(self):
        self.show()
        pump(app, 400)
        pix = self.grab()
        name = "dlg-" + (self.windowTitle() or "dialog").lower().replace(" ", "-")
        pix.save(str(OUT / f"{name}.png"))
        print(f"  saved {name}.png  ({pix.width()}x{pix.height()})")
        self.hide()
        return QDialog.Rejected

    QDialog.exec = fake_exec
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    try:
        pdf_studio._open_dsc()  # "Sign with a DSC" choice dialog
        pdf_studio._confirm_certificate({
            "subject": "CN=GAURAV GUPTA, SERIALNUMBER=..., O=PERSONAL, C=IN",
            "issuer": "CN=Personal DSC Class 3, O=Capricorn CA, C=IN",
            "serial": "0x5F3A91C2",
            "valid_from": "2026-10-30 09:00:00+05:30",
            "valid_to": "2027-10-30 23:59:59+05:30",
            "sha256_fingerprint": "1bc2645747d21dea50916053eacaa11371c21e5ced61ddaa3fa5401788ccbed3",
        })
        pdf_studio._watermark_dialog()
    finally:
        QDialog.exec = real_exec

    # --- 10. Document viewer, one per format ---
    from opal_studio.viewer_doc import DocStudio
    doc_txt = DocStudio(str(docs["notes"]))
    doc_txt.resize(1080, 640)
    pump(app, 300)
    doc_txt.find_edit.setText("line two")
    pump(app, 250)
    grab(doc_txt, "28-doc-text-find", app, settle=250)

    csv_path = WORK / "data.csv"
    json_path = WORK / "data.json"
    for name, path in [("29-doc-markdown", WORK / "readme.md"),
                       ("30-doc-csv", csv_path),
                       ("31-doc-json", json_path),
                       ("32-doc-archive", WORK / "bundle.zip"),
                       ("33-doc-epub", WORK / "book.epub")]:
        d = DocStudio(str(path))
        d.resize(1080, 640)
        pump(app, 400)
        grab(d, name, app, settle=300)

    font_path = WORK / "arial.ttf"
    if font_path.exists():
        f = DocStudio(str(font_path))
        f.resize(1080, 640)
        pump(app, 400)
        grab(f, "34-doc-font", app, settle=300)

    # --- 11. Media studio ---
    clip = WORK / "clip.mp4"
    if clip.exists():
        from opal_studio.viewer_media import MediaStudio
        media = MediaStudio(str(clip))
        media.resize(1080, 640)
        pump(app, 900)
        media._on_position(500)
        pump(app, 300)
        grab(media, "35-media-studio", app, settle=300)
    else:
        print("  (media sample missing - ffmpeg not found, skipped 35)")

    print(f"Done. {len(list(OUT.glob('*.png')))} screens in {OUT}")


if __name__ == "__main__":
    main()
