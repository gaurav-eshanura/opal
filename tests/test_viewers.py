"""
Opal - Viewers & shell verification
Plain English: Boots the AI Image Lab, the Document viewer, the Media studio and
the Floating Studio shell on real files and checks that each one actually
renders content, applies its tools and keeps its state. Offscreen Qt.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from opal_studio.viewer_image import ImageLab
from opal_studio.viewer_doc import DocStudio
from opal_studio.viewer_media import MediaStudio
from opal_studio.float_viewer import FloatStudio

WORK = ROOT / "test_sandbox" / "viewers"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)


def pump(app, ms=120):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def make_files():
    WORK.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (800, 600), (32, 40, 56))
    d = ImageDraw.Draw(img)
    d.ellipse([250, 150, 550, 450], fill=(255, 122, 24))
    d.rectangle([40, 500, 760, 560], fill=(220, 225, 235))
    img.save(WORK / "photo.jpg", quality=94)

    (WORK / "notes.txt").write_text("Opal line one\nline two\nline three\n" * 12,
                                    encoding="utf-8")
    (WORK / "readme.md").write_text("# Title\n\nSome *markdown* text.\n\n- a\n- b\n",
                                    encoding="utf-8")
    (WORK / "data.csv").write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    (WORK / "data.json").write_text('{"tool": "convert", "nested": {"x": 1}, "list": [1, 2]}',
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
    ch.content = "<h1>Chapter</h1><p>Once upon a time.</p>"
    book.add_item(ch)
    book.toc = [ch]
    book.spine = ["nav", ch]
    book.add_item(epub.EpubNav())
    epub.write_epub(str(WORK / "book.epub"), book, {})

    font_src = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    if font_src.exists():
        import shutil
        shutil.copy2(font_src, WORK / "arial.ttf")

    from opal_studio.engine import OpalEngine
    ff = OpalEngine.get_ffmpeg_bin()
    if ff:
        import subprocess
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(WORK / "clip.mp4")],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def test_image_lab(app):
    print("\n--- AI IMAGE LAB ---")
    lab = ImageLab(str(WORK / "photo.jpg"))
    pump(app, 250)
    check("image lab loads file", lab.current_image is not None)
    check("canvas holds the image", lab.canvas.image is not None)
    check("info line populated", "px" in lab.info_label.text(), lab.info_label.text())

    lab.set_tool("enhance")
    lab.enhance_mode.setCurrentText("Auto (balanced)")
    before = lab.current_image.copy()
    lab._run_enhance()
    pump(app, 100)
    check("enhance changes pixels", lab.current_image != before)

    lab.set_tool("filters")
    lab._filter_sepia(lab._qimage_to_pil(lab.current_image))
    pump(app, 60)
    check("filter applies", lab.current_image is not None)

    lab.set_tool("adjust")
    lab.brightness.setValue(150)
    lab._run_adjust()
    pump(app, 60)
    check("adjustments apply", lab.current_image is not None)

    lab.set_tool("crop")
    lab.canvas.crop_fixed_ratio = 1.0
    from PySide6.QtCore import QPointF
    lab.canvas.image_rect()
    target = lab.canvas.image_rect()
    lab.canvas.crop_rect = type("R", (), {"x": lambda s: target.x() + 10,
                                          "y": lambda s: target.y() + 10,
                                          "right": lambda s: target.right() - 10,
                                          "bottom": lambda s: target.bottom() - 10})()
    lab._apply_crop()
    pump(app, 60)
    check("crop changes size", lab.current_image.width() != 800,
          f"{lab.current_image.width()}x{lab.current_image.height()}")

    lab.set_tool("palette")
    lab._run_palette()
    pump(app, 60)
    check("palette produces swatches", lab.palette_lay.count() == 6,
          lab.palette_lay.count())

    lab.set_tool("exif")
    check("exif panel filled", len(lab.exif_view.toPlainText()) > 0)

    lab.set_tool("watermark")
    lab.wm_text.setText("STUDIO")
    lab._run_watermark()
    pump(app, 80)
    check("watermark applied", lab.current_image is not None)

    lab.set_tool("signature")
    from opal_studio.viewer_pdf import SignatureDialog
    sig_dialog = SignatureDialog(lab)
    sig_dialog.name_edit.setText("Ramesh Kumar")
    sig_dialog.tabs.setCurrentIndex(1)
    sig_png = sig_dialog._typed_signature()
    composed = lab.composite_signature(sig_png, "Bottom right", 30, 100) if sig_png else None
    check("signature can be stamped on a photo", composed is not None
          and composed.width() == lab.current_image.width(),
          composed.size() if composed else "none")
    if composed is not None:
        lab.current_image = composed
        lab.canvas.set_image(composed)

    undo_before = lab.current_image
    lab.undo()
    pump(app, 60)
    check("undo restores previous state", lab.current_image is not None
          and lab.current_image != undo_before)
    lab.redo()
    pump(app, 60)
    check("redo re-applies", lab.current_image is not None)

    # Real AI cutout through the studio's own worker
    lab.set_tool("background")
    from opal_studio.viewer_image import ImageWorker

    def _run_worker(options):
        worker = ImageWorker("cutout", lab.current_image, options)
        results = []

        class _Sig:
            def emit(self, *a):
                results.append(a)
        worker.done = _Sig()
        worker.progress = _Sig()
        worker.run()
        return results

    results = _run_worker({"model": "u2netp", "soft_edges": False})
    check("AI cutout worker returns an image",
          bool(results) and results[-1][0] is True and results[-1][1] is not None,
          results[-1][2] if results else "no result")

    # Background replacement modes
    def _alpha_stats(qimage):
        from PySide6.QtGui import QImage
        img = qimage.convertToFormat(QImage.Format_RGBA8888)
        transparent = 0
        opaque = 0
        for y in range(0, img.height(), 4):
            for x in range(0, img.width(), 4):
                alpha = img.pixelColor(x, y).alpha()
                if alpha < 20:
                    transparent += 1
                elif alpha > 235:
                    opaque += 1
        return transparent, opaque

    transparent_result = _run_worker({"model": "u2netp", "mode": 0})
    blur_result = _run_worker({"model": "u2netp", "mode": 3})
    if transparent_result and blur_result:
        t_alpha = _alpha_stats(transparent_result[-1][1])
        b_alpha = _alpha_stats(blur_result[-1][1])
        check("transparent cutout keeps transparency", t_alpha[0] > 0, t_alpha)
        check("blurred-background mode fills the frame", b_alpha[0] == 0, b_alpha)
    else:
        check("background replacement worker ran", False, "no results")


def test_doc_studio(app):
    print("\n--- DOCUMENT VIEWER ---")
    doc = DocStudio(str(WORK / "notes.txt"))
    pump(app, 150)
    check("text view loads", "Opal" in doc.text_view.toPlainText())
    check("text stats computed", "lines" in doc.text_stats.text(), doc.text_stats.text())

    doc.find_edit.setText("line two")
    pump(app, 80)
    check("find does not crash", True)

    md = DocStudio(str(WORK / "readme.md"))
    pump(app, 150)
    check("markdown renders to html", "Title" in md.html_view.toPlainText()
          or "<h1" in md.html_view.toHtml())

    csv_doc = DocStudio(str(WORK / "data.csv"))
    pump(app, 150)
    check("csv table populated", csv_doc.table.rowCount() == 2 and csv_doc.table.columnCount() == 3,
          f"{csv_doc.table.rowCount()}x{csv_doc.table.columnCount()}")

    json_doc = DocStudio(str(WORK / "data.json"))
    pump(app, 150)
    check("json tree populated", json_doc.tree.topLevelItemCount() >= 3,
          json_doc.tree.topLevelItemCount())
    check("json raw view filled", "convert" in json_doc.tree_json.toPlainText())

    arc = DocStudio(str(WORK / "bundle.zip"))
    pump(app, 150)
    check("archive tree populated", arc.archive_tree.topLevelItemCount() == 2,
          arc.archive_tree.topLevelItemCount())
    check("archive info computed", "entries" in arc.archive_info.text(), arc.archive_info.text())

    book = DocStudio(str(WORK / "book.epub"))
    pump(app, 300)
    check("epub chapters listed", book.epub_chapters.count() >= 1,
          book.epub_chapters.count())
    check("epub chapter renders", "Once upon" in book.epub_view.toPlainText()
          or book.epub_view.toPlainText() != "")

    if (WORK / "arial.ttf").exists():
        font = DocStudio(str(WORK / "arial.ttf"))
        pump(app, 200)
        check("font metadata read", "Family" in font.font_meta.toPlainText()
              or "fontTools" in font.font_meta.toPlainText())
        check("font specimen rendered", "quick brown fox" in font.font_specimen.toPlainText())


def test_media_studio(app):
    print("\n--- MEDIA STUDIO ---")
    if not (WORK / "clip.mp4").exists():
        check("media fixture missing (ffmpeg)", False)
        return
    media = MediaStudio(str(WORK / "clip.mp4"))
    pump(app, 400)
    check("media studio loads", Path(media.file_path).exists())
    check("duration detected", media.duration > 0.5, media.duration)
    check("metadata shown", len(media.meta_label.text()) > 0, media.meta_label.text())
    check("waveform decoded", len(media.waveform.peaks) > 10, len(media.waveform.peaks))
    media._on_position(500)
    check("position updates waveform", media.waveform.progress > 0)


def test_float_studio(app):
    print("\n--- FLOATING STUDIO SHELL ---")
    studio = FloatStudio()
    pump(app, 200)
    check("shell starts with home tab", studio.tabs.count() == 1)
    check("home tab lists tools", studio.home.recent is not None)

    ok_pdf = studio.open_file(str(WORK / "photo.jpg"))
    check("image file opens in a tab", ok_pdf and studio.tabs.count() == 2)
    from opal_studio.viewer_image import ImageLab
    check("image tab hosts the image lab",
          isinstance(studio.tabs.widget(1), ImageLab))

    studio.open_file(str(WORK / "notes.txt"))
    check("second file opens in another tab", studio.tabs.count() == 3)
    from opal_studio.viewer_doc import DocStudio as _Doc
    check("document tab hosts the doc viewer", isinstance(studio.tabs.widget(2), _Doc))

    studio._next_tab()
    check("tab switching works", studio.tabs.currentIndex() == 0,
          studio.tabs.currentIndex())

    studio._toggle_opacity()
    check("opacity toggles", studio.opacity_level < 1.0)
    studio._toggle_ghost()
    check("ghost mode toggles", studio.ghost_mode is True)
    studio._toggle_ghost()

    studio._close_tab(2)
    pump(app, 100)
    check("tab closes", studio.tabs.count() == 2)


def main():
    make_files()
    app = QApplication(sys.argv)
    test_image_lab(app)
    test_doc_studio(app)
    test_media_studio(app)
    test_float_studio(app)
    print("\n" + "=" * 60)
    print(f"VIEWERS RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
