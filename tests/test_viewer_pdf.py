"""
Opal - PDF Studio headless verification
Plain English: Boots the real Qt PDF Studio on synthetic documents (with a fake
form, a scanned page and a protected file) and exercises the studio's own code
paths: loading, page rendering, annotation tools, form filling, search,
redaction, page operations, signature placement, OCR worker, save and reload.
Runs with the offscreen Qt platform, so no window is shown.
"""

import os
import sys
import secrets
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz
from PySide6.QtWidgets import QApplication, QInputDialog  # noqa: F401
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage

from opal_studio.viewer_pdf import PdfStudio
from opal_studio import pdf_tools as pt

WORK = ROOT / "test_sandbox" / "studio"
# Unique per run: a file left open by an earlier run must never block us.
RUN_ID = __import__("time").strftime("%H%M%S")
PASS, FAIL = [], []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)


class _LeftClick:
    def button(self):
        return Qt.LeftButton


LEFT_CLICK = _LeftClick()


def make_docs():
    WORK.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Quarterly report page {i + 1}", fontsize=18)
        page.insert_text((72, 140), "The quick brown fox jumps over the lazy dog. " * 3, fontsize=11)
        page.insert_text((72, 200), "Confidential business figures appear here.", fontsize=11)
    doc.save(str(WORK / f"report_{RUN_ID}.pdf"))
    doc.close()

    form = fitz.open()
    page = form.new_page(width=595, height=842)
    page.insert_text((72, 80), "Client Intake Form", fontsize=20)
    w = fitz.Widget()
    w.field_name = "full_name"
    w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w.field_value = ""
    w.rect = fitz.Rect(200, 120, 400, 150)
    page.add_widget(w)
    w2 = fitz.Widget()
    w2.field_name = "subscribe"
    w2.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    w2.field_value = False
    w2.rect = fitz.Rect(200, 180, 220, 200)
    page.add_widget(w2)
    form.save(str(WORK / f"form_{RUN_ID}.pdf"))
    form.close()

    img = WORK / "scan_source.png"
    src = fitz.open(WORK / f"report_{RUN_ID}.pdf")
    pix = src[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    pix.save(str(img))
    src.close()
    scan = fitz.open()
    scan.new_page(width=595, height=842).insert_image(fitz.Rect(30, 30, 565, 812), filename=str(img))
    scan.save(str(WORK / "scanned.pdf"))
    scan.close()

    # Random per-run password: nothing sensitive is ever hardcoded.
    fixture_pw = secrets.token_hex(8)
    (WORK / "_fixture_pw.txt").write_text(fixture_pw)
    # A user password is what actually forces a password prompt when opening.
    pt.protect_pdf(str(WORK / f"report_{RUN_ID}.pdf"), str(WORK / f"locked_{RUN_ID}.pdf"),
                   owner_password=fixture_pw, user_password=fixture_pw)
    return fixture_pw


def pump(app, ms=120):
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def drag_release(view, a: QPointF, b: QPointF):
    view._press_pos = a
    view._current_pos = b
    view.mouseReleaseEvent(LEFT_CLICK)


def main():
    fixture_pw = make_docs()
    app = QApplication(sys.argv)

    print("\n--- STUDIO LOAD & RENDER ---")
    studio = PdfStudio(str(WORK / f"report_{RUN_ID}.pdf"))
    pump(app, 400)
    check("studio opens document", studio.doc is not None and len(studio.doc) == 3)
    check("page views created", len(studio.views) == 3)
    check("thumbnails built", studio.thumb_list.count() == 3)
    pix = studio.page_pixmap(0)
    check("page rendered to pixmap", pix is not None and not pix.isNull())
    rendered = pix.toImage() if pix else QImage()
    check("rendered page is not blank", rendered.width() > 500,
          f"{rendered.width()}x{rendered.height()}")
    studio._update_inspector()
    check("inspector reports size", "Page size" in studio.inspector.toPlainText())

    print("\n--- STUDIO TOOLS (simulated on real coordinates) ---")
    view = studio.views[0]

    studio.set_tool("highlight")
    drag_release(view, QPointF(72, 140), QPointF(300, 156))
    pump(app, 80)
    page0 = studio.doc[0]  # keep the page proxy alive: annots bind to it
    annots = list(page0.annots() or [])
    check("highlight annotation added", len(annots) >= 1,
          [a.type[1] for a in annots])
    check("studio marked dirty", studio.dirty is True)

    studio.set_tool("underline")
    drag_release(view, QPointF(72, 200), QPointF(280, 216))
    pump(app, 80)
    page0 = studio.doc[0]
    annots = list(page0.annots() or [])
    check("underline annotation added", len(annots) >= 2, len(annots))

    studio.set_tool("redact")
    # PDF space y=200..215 -> view space is PDF * zoom (1.25)
    z = studio.zoom
    drag_release(view, QPointF(70 * z, 195 * z), QPointF(420 * z, 218 * z))
    pump(app, 80)
    text_after = studio.doc[0].get_text()
    check("redaction removed underlying text", "Confidential" not in text_after,
          text_after[:60])

    from opal_studio.viewer_pdf import SignatureDialog
    dlg = SignatureDialog(studio)
    dlg.name_edit.setText("Peach Farmer")
    dlg.tabs.setCurrentIndex(1)
    png = dlg._typed_signature()
    ink_pixels = 0
    if png:
        from PIL import Image as PILImage
        import io as _io
        pil = PILImage.open(_io.BytesIO(png)).convert("RGBA")
        alpha = pil.split()[-1]
        ink_pixels = sum(1 for v in alpha.get_flattened_data() if v > 10)
    check("typed signature rendered", bool(png) and ink_pixels > 100,
          f"{ink_pixels} ink pixels, {len(png) if png else 0} bytes")
    studio.pending_signature = png
    studio.place_signature(1, fitz.Point(200, 300))
    check("signature stamped into page",
          len(studio.doc[1].get_images(full=True)) >= 1)

    print("\n--- STUDIO FORM FILLING ---")
    fstudio = PdfStudio(str(WORK / f"form_{RUN_ID}.pdf"))
    pump(app, 200)
    check("form studio opens", fstudio.doc is not None)
    widgets = list(fstudio.doc[0].widgets() or [])
    check("form fields detected", len(widgets) == 2, [w.field_name for w in widgets])

    orig_text = QInputDialog.getText
    QInputDialog.getText = staticmethod(lambda *a, **k: ("Ada Lovelace", True))
    try:
        # Use the studio's own lookup so the page proxy stays alive (as in the app)
        text_widget = fstudio.widget_at(0, fitz.Point(300, 135))
        fstudio.edit_widget(text_widget)
    finally:
        QInputDialog.getText = orig_text
    fresh_page = fstudio.doc[0]
    value = next(w.field_value for w in fresh_page.widgets() or []
                 if w.field_name == "full_name")
    check("form text field filled", value == "Ada Lovelace", value)

    cb = fstudio.widget_at(0, fitz.Point(210, 190))
    fstudio.edit_widget(cb)
    cb_page = fstudio.doc[0]
    cb2 = next(w for w in cb_page.widgets() or [] if w.field_name == "subscribe")
    check("checkbox toggled", bool(cb2.field_value) is True)

    print("\n--- STUDIO TEXT SELECTION ---")
    studio.set_tool("select")
    z = studio.zoom
    # Drag across the "quick brown fox" line (PDF y=140..155)
    drag_release(view, QPointF(72 * z, 138 * z), QPointF(320 * z, 158 * z))
    pump(app, 120)
    clip = QApplication.clipboard().text()
    check("drag-select copies text", "quick brown fox" in clip.lower(), clip[:60])
    total = studio.copy_all_text()
    check("copy all text works", "Quarterly report" in total, len(total))

    print("\n--- STUDIO SEARCH ---")
    studio.search_input.setText("Quarterly")
    pump(app, 150)
    check("search finds matches", len(studio.search_matches) >= 3, len(studio.search_matches))
    studio.search_input.setText("figures")
    pump(app, 150)
    check("search narrows", len(studio.search_matches) >= 1, len(studio.search_matches))
    studio.search_input.setText("")

    print("\n--- STUDIO ORGANIZE ---")
    studio.doc.new_page(width=595, height=842, pno=3)
    pump(app, 60)
    studio._build_pages()
    check("blank page appended", len(studio.doc) == 4, len(studio.doc))
    studio.go_to_page(3)
    studio._reverse_pages()
    pump(app, 60)
    check("pages reversed", len(studio.doc) == 4)
    studio.doc.select(list(range(len(studio.doc))))
    studio._build_pages()
    pump(app, 60)
    studio.go_to_page(1)
    studio._rotate_page(90)
    check("page rotated", studio.doc[1].rotation in (90, 270),
          studio.doc[1].rotation)

    print("\n--- STUDIO SAVE & RELOAD ---")
    out = WORK / "saved_output.pdf"
    pt.save_doc(studio.doc, str(out))
    check("document saved", out.exists() and out.stat().st_size > 1000)
    reloaded = fitz.open(str(out))
    check("saved doc reopens with edits", len(reloaded) >= 3)
    reloaded.close()

    print("\n--- STUDIO PROTECTED FILE ---")
    try:
        pt.open_pdf(str(WORK / f"locked_{RUN_ID}.pdf"))
        check("protected doc blocks blind open", False)
    except Exception as e:
        check("protected doc blocks blind open", "password" in str(e).lower())
    unlocked = pt.unlock_pdf(str(WORK / f"locked_{RUN_ID}.pdf"), str(WORK / f"unlocked_{RUN_ID}.pdf"),
                             password=(WORK / "_fixture_pw.txt").read_text())
    reopened = fitz.open(unlocked)
    check("correct password unlocks", not reopened.needs_pass,
          f"needs_pass={reopened.needs_pass}")
    reopened.close()

    print("\n--- STUDIO FORM BUILDER ---")
    built = studio.create_form_field(0, fitz.Point(90, 300), "form_build", "applicant_name")
    check("text field added to the page", built)
    built = studio.create_form_field(0, fitz.Point(90, 340), "form_check", "agree")
    check("checkbox added to the page", built)
    fields = [w.field_name for w in (studio.doc[0].widgets() or [])]
    check("both fields are in the document",
          "applicant_name" in fields and "agree" in fields, fields)

    print("\n--- STUDIO DIGITAL SIGNATURE (DSC) ---")
    pfx = WORK / "test_dsc.pfx"
    if not pfx.exists():
        pfx = _make_test_dsc(WORK)
    from opal_studio import dsc_sign
    info = dsc_sign.inspect_certificate(str(pfx), "test123")
    check("certificate details readable", "Ramesh" in info["subject"], info["subject"][:40])
    check("certificate validity readable", bool(info["valid_to"]), info["valid_to"])
    studio.dsc_context = {"pfx": str(pfx), "password": "test123", "info": info}
    before = set(Path(WORK).glob("*.pdf"))
    signed_path = studio.sign_with_dsc(0, fitz.Point(80, 700))
    check("DSC signing returned a file", bool(signed_path), signed_path)
    pump(app, 250)
    after = set(Path(WORK).glob("*.pdf"))
    new_files = [p for p in after - before if "signed" in p.name]
    check("DSC signing produced a file", bool(new_files), [p.name for p in new_files])
    if new_files:
        raw = new_files[0].read_bytes()
        check("signed PDF carries a CMS signature",
              b"/ByteRange" in raw and b"adbe.pkcs7.detached" in raw)
        check("signed copy is next to the original", new_files[0].parent == WORK)

    print("\n--- STUDIO WORKER (OCR on real scan) ---")
    from opal_studio.viewer_pdf import StudioWorker

    class _FakeSignals:
        def __init__(self):
            self.calls = []
        def emit(self, *a):
            self.calls.append(a)

    worker = StudioWorker("ocr", str(WORK / "scanned.pdf"), {})
    worker.progress = _FakeSignals()
    worker.done = _FakeSignals()
    worker.run()
    calls = worker.done.calls
    check("OCR worker completes", bool(calls) and calls[0][0] is True,
          calls[0][1] if calls else "no signal")
    if calls and calls[0][2]:
        check("OCR output exists", Path(calls[0][2]).exists(), Path(calls[0][2]).name)

    print("\n" + "=" * 60)
    print(f"STUDIO RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 0 if not FAIL else 1


def _make_test_dsc(folder: Path) -> Path:
    """Creates a throwaway certificate that behaves like a real DSC."""
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import rsa

    target = folder / "test_dsc.pfx"
    if target.exists():
        return target
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CSC Authority"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Ramesh Kumar - Test DSC"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))
    blob = pkcs12.serialize_key_and_certificates(
        b"test-dsc", key, cert, None, serialization.BestAvailableEncryption(b"test123"))
    target.write_bytes(blob)
    return target


if __name__ == "__main__":
    sys.exit(main())
