"""
Opal - Every-Feature Verification Suite
Plain English: Runs EVERY action in the Opal catalog against real sample files,
opens EVERY dialog and modal surface headless, exercises the whole
cross-platform layer, and drives the command line - then writes a markdown
report saying exactly what passed, what failed and why.

Nothing is mocked: the same code paths the shipping product uses, the same
real AI models, the same real FFmpeg, the same real PDF engine.
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
import time
import datetime
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from opal_studio.engine import OpalEngine
from opal_studio.config import ConfigManager, CONFIG_FILE

SANDBOX = ROOT / "test_sandbox" / "every_feature"
# Files that are handed to Explorer / Notepad / PowerShell must NOT live inside
# the sandbox: a process whose working directory is inside a folder makes that
# folder undeletable on Windows, which would break the next run's cleanup.
PROBE_DIR = Path(tempfile.gettempdir()) / "opal_every_feature_probe"
REPORT_PATH = ROOT / "tests" / "EVERY_FEATURE_REPORT.md"

PASS, FAIL, SKIPPED = [], [], []
RESULTS = []          # every check, in order: dict(name, area, ok, detail, kind)
OUTPUTS = {}          # action id -> output path produced by the engine
AREA = {"kind": ""}   # current area label, set as we walk through the suite


# ---------------------------------------------------------------------------
# Reporting helpers (same shape as tests/test_engine_extended.py)
# ---------------------------------------------------------------------------

def check(name, ok, detail="", kind=""):
    """Prints one PASS/FAIL line and records it for the markdown report."""
    ok = bool(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)
    RESULTS.append({
        "name": name,
        "area": AREA.get("kind", ""),
        "ok": ok,
        "detail": "" if ok else str(detail),
        "kind": "" if ok else (kind or "product"),
    })


def skip(name, reason=""):
    """Records a check this environment cannot make, without failing it.

    A build machine with no clipboard tool and no terminal emulator is not a
    defect in the app, so the check is reported as skipped rather than
    failed.
    """
    print(f"[SKIP] {name} {('- ' + str(reason)) if reason else ''}")
    SKIPPED.append(name)
    RESULTS.append({
        "name": name,
        "area": AREA.get("kind", ""),
        "ok": True,
        "detail": str(reason),
        "kind": "environment",
    })


def section(title):
    AREA["kind"] = title
    print(f"\n--- {title} ---")


def pump(app, ms=200):
    """Lets Qt breathe so widgets actually lay out and paint."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


# ---------------------------------------------------------------------------
# Output validation: a file only counts as "working" if it really opens
# ---------------------------------------------------------------------------

def _validate_file(path: Path, expect: str):
    """Returns (ok, detail) after really reading the produced file."""
    try:
        if expect == "image":
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                im.load()
                return True, f"{im.format} {im.width}x{im.height}"
        if expect == "pdf":
            import fitz
            doc = fitz.open(str(path))
            try:
                pages = len(doc)
                if pages < 1:
                    return False, "PDF has no pages"
                return True, f"{pages} page(s)"
            finally:
                doc.close()
        if expect == "docx":
            if not zipfile.is_zipfile(path):
                return False, "not a zip container"
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if "word/document.xml" not in names:
                return False, "word/document.xml missing"
            return True, f"{len(names)} parts"
        if expect == "pptx":
            if not zipfile.is_zipfile(path):
                return False, "not a zip container"
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if not any(n.startswith("ppt/") for n in names):
                return False, "no ppt/ parts"
            return True, f"{len(names)} parts"
        if expect == "xlsx":
            if not zipfile.is_zipfile(path):
                return False, "not a zip container"
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if "xl/workbook.xml" not in names:
                return False, "xl/workbook.xml missing"
            return True, f"{len(names)} parts"
        if expect == "epub":
            if not zipfile.is_zipfile(path):
                return False, "not a zip container"
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if "mimetype" not in names:
                return False, "mimetype missing"
            return True, f"{len(names)} parts"
        if expect == "zip":
            if not zipfile.is_zipfile(path):
                return False, "not a zip container"
            with zipfile.ZipFile(path) as z:
                if z.testzip() is not None:
                    return False, "corrupt member inside archive"
                return True, f"{len(z.namelist())} member(s)"
        if expect == "text":
            data = path.read_text(encoding="utf-8", errors="replace")
            if not data.strip():
                return False, "text file is empty"
            return True, f"{len(data)} chars"
        if expect == "media":
            ff = OpalEngine.get_ffmpeg_bin()
            if not ff:
                return False, "FFmpeg is not installed, cannot verify the media file"
            proc = subprocess.run([ff, "-v", "error", "-i", str(path), "-f", "null", "-"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  creationflags=subprocess.CREATE_NO_WINDOW
                                  if sys.platform == "win32" else 0)
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", "ignore").strip()[-200:]
                return False, f"FFmpeg could not decode the file: {err}"
            return True, f"{path.stat().st_size // 1024} KB, decodes cleanly"
        if expect == "folder":
            files = [f for f in path.rglob("*") if f.is_file()]
            if not files:
                return False, "folder has no files"
            return True, f"{len(files)} file(s)"
        # "any" - try every reader until one works
        try:
            with Image.open(path) as im:
                im.verify()
            return True, "image"
        except Exception:
            pass
        try:
            import fitz
            doc = fitz.open(str(path))
            try:
                return True, f"{len(doc)} page(s)"
            finally:
                doc.close()
        except Exception:
            pass
        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as z:
                    return True, f"{len(z.namelist())} member(s)"
        except Exception:
            pass
        if path.suffix.lower() in (".txt", ".md", ".html", ".htm", ".vtt", ".srt",
                                   ".json", ".csv", ".xml", ".log"):
            try:
                data = path.read_text(encoding="utf-8", errors="replace")
                if data.strip():
                    return True, f"{len(data)} chars"
            except Exception:
                pass
            return False, "text file is empty"
        media_ok, media_detail = _validate_file(path, "media")
        if media_ok:
            return True, media_detail
        return False, "could not be opened by any reader"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _guess_expect(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".ico"):
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext == ".pptx":
        return "pptx"
    if ext == ".xlsx":
        return "xlsx"
    if ext == ".epub":
        return "epub"
    if ext == ".zip":
        return "zip"
    if ext in (".txt", ".md", ".html", ".htm", ".vtt", ".srt", ".json", ".csv"):
        return "text"
    if ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv",
               ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aiff", ".wma", ".aac"):
        return "media"
    return "any"


def validate_output(output_path, expect: str):
    """Checks the produced path really exists, is non-empty and really opens."""
    if not output_path:
        return False, "no output_path was returned"
    p = Path(output_path)
    if not p.exists():
        return False, f"output_path does not exist: {output_path}"
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.is_file()]
        if not files:
            return False, f"output folder is empty: {p}"
        for f in files:
            ok, detail = _validate_file(f, _guess_expect(f))
            if not ok:
                return False, f"invalid file inside output folder ({f.name}): {detail}"
        return True, f"{len(files)} file(s) in {p.name}"
    if p.stat().st_size == 0:
        return False, f"output file is 0 bytes: {p.name}"
    return _validate_file(p, expect)


# ---------------------------------------------------------------------------
# Sample files
# ---------------------------------------------------------------------------

def make_portrait(path: Path):
    """A believable portrait: head, shoulders, plain background."""
    img = Image.new("RGB", (600, 800), (208, 214, 226))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 600, 520], fill=(196, 204, 218))
    d.ellipse([140, 520, 460, 860], fill=(62, 78, 128))      # shoulders
    d.ellipse([195, 140, 405, 420], fill=(226, 186, 158))    # face
    d.ellipse([228, 245, 262, 275], fill=(40, 36, 34))       # eyes
    d.ellipse([338, 245, 372, 275], fill=(40, 36, 34))
    d.arc([250, 300, 350, 350], 0, 180, fill=(150, 90, 80), width=6)
    d.rectangle([270, 195, 330, 230], fill=(48, 40, 38))     # hair
    img.save(path, quality=94)


def make_photo(path: Path):
    img = Image.new("RGB", (640, 480), (30, 120, 200))
    d = ImageDraw.Draw(img)
    d.ellipse([180, 120, 460, 400], fill=(255, 200, 40))
    d.rectangle([60, 400, 580, 450], fill=(240, 240, 245))
    d.text((70, 30), "Opal Test Photo", fill=(255, 255, 255))
    img.save(path, quality=92)


def make_big_pdf(path: Path):
    """A PDF well over 1 MB so the WhatsApp shrinker has real work to do."""
    import fitz
    noise = Image.frombytes("RGB", (900, 900), os.urandom(900 * 900 * 3))
    noise_path = path.parent / "_noise.png"
    noise.save(noise_path)
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(0, 0, 595, 842), filename=str(noise_path))
    doc.save(str(path))
    doc.close()
    noise_path.unlink(missing_ok=True)


def make_certificate(path: Path):
    """A throwaway self-signed PKCS#12 certificate for the DSC signing test."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Opal Test Signer")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))
    blob = pkcs12.serialize_key_and_certificates(
        b"opal-test", key, cert, None, serialization.NoEncryption())
    path.write_bytes(blob)


def setup():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)
    # A leftover file can survive the cleanup (Explorer or a terminal may still
    # hold it), so make sure the folder really is empty before we start.
    if SANDBOX.exists():
        for leftover in SANDBOX.rglob("*"):
            try:
                if leftover.is_file():
                    leftover.unlink()
            except OSError:
                pass
    SANDBOX.mkdir(parents=True, exist_ok=True)

    make_photo(SANDBOX / "photo.jpg")
    make_portrait(SANDBOX / "portrait.jpg")
    # The Real-ESRGAN model needs a few hundred MB of RAM per tensor, so the
    # catalogue run uses a small image; a full-size photo is checked separately.
    Image.new("RGB", (128, 128), (200, 120, 60)).save(SANDBOX / "tiny.png")

    (SANDBOX / "notes.txt").write_text(
        "Opal every-feature test.\n\nLine two with unicode: peaches \u2764 oranges \u2764.\n" * 8,
        encoding="utf-8")
    (SANDBOX / "readme.md").write_text(
        "# Opal\n\n## Features\n\n- **Zero-click** conversion\n- Local *AI* tools\n\n"
        "```python\nprint('hi')\n```\n\n| Tool | Speed |\n| --- | --- |\n| Convert | fast |\n",
        encoding="utf-8")
    (SANDBOX / "subs.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello there\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\nSecond line here\n", encoding="utf-8")
    (SANDBOX / "data.csv").write_text(
        "name,price,qty\nApple,1.5,10\nPear,2.5,5\nPlum,3.0,7\n", encoding="utf-8")
    (SANDBOX / "data.json").write_text(
        '[{"tool":"convert","speed":"fast"},{"tool":"compress","speed":"medium"}]', encoding="utf-8")

    import docx
    d1 = docx.Document()
    d1.add_heading("Opal Report", 0)
    d1.add_paragraph("This document powers the every-feature test.")
    d1.save(str(SANDBOX / "report.docx"))

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fruit", "Count"])
    ws.append(["Apple", 10])
    ws.append(["Pear", 5])
    wb.save(str(SANDBOX / "sheet.xlsx"))

    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Opal Deck"
    prs.save(str(SANDBOX / "deck.pptx"))

    import fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Contract page {i + 1} for testing", fontsize=16)
        page.insert_text((72, 140), "The quick brown fox jumps over the lazy dog.", fontsize=11)
    doc.save(str(SANDBOX / "contract.pdf"))
    doc.close()

    doc2 = fitz.open()
    for i in range(2):
        page = doc2.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Second contract page {i + 1}", fontsize=16)
    doc2.save(str(SANDBOX / "contract2.pdf"))
    doc2.close()

    scan_img = SANDBOX / "_scan.png"
    scan_pil = Image.new("RGB", (1000, 1400), (250, 250, 248))
    scan_draw = ImageDraw.Draw(scan_pil)
    scan_draw.text((90, 140), "OPAL SCANNED DOCUMENT", fill=(20, 20, 30))
    scan_draw.text((90, 220), "Invoice number 4821", fill=(20, 20, 30))
    scan_draw.text((90, 290), "Total payable 2500 rupees", fill=(20, 20, 30))
    scan_pil.save(scan_img)
    scan_doc = fitz.open()
    page = scan_doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(40, 40, 555, 800), filename=str(scan_img))
    scan_doc.save(str(SANDBOX / "scan.pdf"))
    scan_doc.close()
    scan_img.unlink(missing_ok=True)

    make_big_pdf(SANDBOX / "big.pdf")
    make_certificate(SANDBOX / "cert.p12")

    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier("opal-every-feature")
    book.set_title("Test Novel")
    book.set_language("en")
    c1 = epub.EpubHtml(title="Ch 1", file_name="c1.xhtml", lang="en")
    c1.content = "<h1>Chapter One</h1><p>It was a bright cold day.</p>"
    c2 = epub.EpubHtml(title="Ch 2", file_name="c2.xhtml", lang="en")
    c2.content = "<h1>Chapter Two</h1><p>The clocks were striking thirteen.</p>"
    book.add_item(c1)
    book.add_item(c2)
    book.toc = [c1, c2]
    book.spine = ["nav", c1, c2]
    book.add_item(epub.EpubNav())
    epub.write_epub(str(SANDBOX / "novel.epub"), book, {})

    # A font to inspect. Every platform ships a different one, so the first
    # one that exists is used.
    font_src = None
    for candidate in (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ):
        if not candidate.exists():
            continue
        try:
            # copy2 keeps the file's metadata, which the system fonts on macOS
            # do not allow to be copied. copyfile does not.
            shutil.copyfile(candidate, SANDBOX / "arial.ttf")
            font_src = candidate
            break
        except OSError:
            continue

    with zipfile.ZipFile(SANDBOX / "bundle.zip", "w") as z:
        z.write(SANDBOX / "photo.jpg", "photo.jpg")
        z.write(SANDBOX / "notes.txt", "notes.txt")

    ff = OpalEngine.get_ffmpeg_bin()
    if ff:
        flags = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=3",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(SANDBOX / "clip.mp4")], **flags)
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
                        "-c:a", "pcm_s16le", str(SANDBOX / "tone.wav")], **flags)
    (SANDBOX / "clip.srt").write_text(
        "1\n00:00:00,500 --> 00:00:02,000\nBurned subtitle line\n", encoding="utf-8")

    print(f"Sandbox ready at {SANDBOX}")


# ---------------------------------------------------------------------------
# Environment probes: are the optional engines present at all?
# ---------------------------------------------------------------------------

def probe_environment():
    """Returns {concern: reason} for every optional dependency that is missing."""
    blockers = {}
    if not OpalEngine.get_ffmpeg_bin():
        blockers["media"] = "FFmpeg is not installed on this machine"
    try:
        from opal_studio import dsc_sign
        if not dsc_sign.available():
            blockers["dsc"] = "pyHanko (the PDF signing engine) is not installed"
    except Exception as e:
        blockers["dsc"] = f"the signing engine could not be imported: {e}"
    try:
        from opal_studio.engines import EngineManager
        if EngineManager.ocr_available() is False:
            blockers["ocr"] = "the RapidOCR engine is not available"
        cfg = ConfigManager.load_config()
        up_model = cfg.get("upscale_model", "realesrgan-x4plus")
        if not EngineManager.esrgan_cached(up_model):
            blockers["upscale"] = (f"the {up_model} Real-ESRGAN model is not cached, "
                                   "so it has to be downloaded from the network first")
    except Exception as e:
        blockers["engine"] = f"the AI engine manager could not be queried: {e}"
    return blockers


# ---------------------------------------------------------------------------
# SECTION 1 - every catalog action, for real
# ---------------------------------------------------------------------------

# action id -> (input file, options, expected output type)
CATALOG_RUNS = [
    ("remove_bg",        "portrait.jpg", {"bg_model": "u2netp"}, "image"),
    ("aadhaar_photo",    "portrait.jpg", {}, "image"),
    ("print_4x6",        "photo.jpg",    {}, "image"),
    ("photo_whatsapp",   "photo.jpg",    {}, "image"),
    ("pdf_whatsapp",     "big.pdf",      {}, "pdf"),
    ("pdf_a4",           "contract.pdf", {}, "pdf"),
    ("add_border",       "photo.jpg",    {}, "image"),
    ("bg_cutout_blur",   "portrait.jpg", {"bg_model": "u2netp"}, "image"),
    ("upscale_2x",       "tiny.png",     {}, "image"),
    ("enhance_auto",     "photo.jpg",    {}, "image"),
    ("compress_image",   "photo.jpg",    {}, "image"),
    ("social_portrait",  "photo.jpg",    {}, "image"),
    ("color_palette",    "photo.jpg",    {}, "text"),
    ("exif_report",      "photo.jpg",    {}, "text"),
    ("watermark_image",  "photo.jpg",    {"watermark_text": "OPAL"}, "image"),
    ("qr_code",          "notes.txt",    {}, "image"),
    ("pdf",              "readme.md",    {}, "pdf"),
    ("pptx",             "contract.pdf", {}, "pptx"),
    ("docx",             "contract.pdf", {}, "docx"),
    ("epub",             "contract.pdf", {}, "epub"),
    ("pdf_dsc_sign",     "contract.pdf", {"pfx_path": str(SANDBOX / "cert.p12"),
                                          "password": "", "page": 0}, "pdf"),
    ("pdf_pagenum",      "contract.pdf", {}, "pdf"),
    ("pdf_watermark",    "contract.pdf", {"watermark_text": "OPAL"}, "pdf"),
    ("pdf_ocr",          "scan.pdf",     {}, "pdf"),
    ("split_pdf",        "contract.pdf", {}, "folder"),
    ("epub_txt",         "novel.epub",   {}, "text"),
    ("md_html",          "readme.md",    {}, "text"),
    ("srt_vtt",          "subs.srt",     {}, "text"),
    ("csv_xlsx",         "data.csv",     {}, "xlsx"),
    ("font_report",      "arial.ttf",    {}, "text"),
    ("video_thumbnails", "clip.mp4",     {}, "image"),
    ("video_frames",     "clip.mp4",     {"frames_per_second": "all"}, "folder"),
    ("burn_subtitles",   "clip.mp4",     {}, "media"),
    ("hash_file",        "photo.jpg",    {}, "text"),
    ("quick_zip",        "notes.txt",    {}, "zip"),
]

# Actions that are driven by FFmpeg.
MEDIA_ACTIONS = ("video_thumbnails", "video_frames", "burn_subtitles", "compress_media",
                 "video_720p", "mute_video", "trim_30s", "video_speed", "video_rotate",
                 "audio_normalize", "audio_speed")

# Actions the product exposes but the catalog does not list.
EXTRA_RUNS = [
    ("join_photos", "portrait.jpg", {"second": str(SANDBOX / "photo.jpg")}, "image"),
    ("compress_media", "clip.mp4", {}, "media"),
    ("video_720p", "clip.mp4", {}, "media"),
    ("mute_video", "clip.mp4", {}, "media"),
    ("trim_30s", "clip.mp4", {}, "media"),
    ("video_speed", "clip.mp4", {"speed": 2.0}, "media"),
    ("audio_normalize", "tone.wav", {}, "media"),
    ("audio_speed", "tone.wav", {"speed": 1.5}, "media"),
    ("video_rotate", "clip.mp4", {"degrees": 90}, "media"),
]


def free_ram_gb():
    """Free RAM right now - several AI actions are memory hungry."""
    try:
        import psutil
        return psutil.virtual_memory().available / 1e9
    except Exception:
        return float("nan")


MEMORY_ERRORS = ("bad allocation", "openblas error", "memory allocation",
                 "out of memory", "cannot allocate", "not enough memory",
                 "paging file is too small")


def looks_like_memory_failure(text: str) -> bool:
    """True when an error is the machine running out of RAM, not a code fault."""
    low = (text or "").lower()
    return any(marker in low for marker in MEMORY_ERRORS)


_FFMPEG_PROBE = {}


def ffmpeg_healthy():
    """Runs FFmpeg on a trivial clip once, to tell 'broken FFmpeg' from
    'this particular conversion failed'. Cached for the whole run."""
    if "ok" in _FFMPEG_PROBE:
        return _FFMPEG_PROBE["ok"], _FFMPEG_PROBE["detail"]
    ff = OpalEngine.get_ffmpeg_bin()
    if not ff:
        _FFMPEG_PROBE.update(ok=False, detail="FFmpeg is not installed")
        return False, _FFMPEG_PROBE["detail"]
    probe_dir = SANDBOX / "_ffprobe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    target = probe_dir / "probe.mp4"
    try:
        proc = subprocess.run(
            [ff, "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=5:duration=1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "ignore").strip()[-200:]
            detail = f"FFmpeg failed on a trivial test clip: {err}"
            _FFMPEG_PROBE.update(ok=False, detail=detail)
            return False, detail
        _FFMPEG_PROBE.update(ok=True, detail="FFmpeg encodes a test clip correctly")
        return True, _FFMPEG_PROBE["detail"]
    except Exception as e:
        detail = f"FFmpeg could not be run: {type(e).__name__}: {e}"
        _FFMPEG_PROBE.update(ok=False, detail=detail)
        return False, detail
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def env_kind_for(action_id, blockers):
    """Maps a failed action to an environment reason when a dependency is missing."""
    if action_id in ("video_thumbnails", "video_frames", "burn_subtitles") and "media" in blockers:
        return "env", blockers["media"]
    if action_id == "pdf_ocr" and "ocr" in blockers:
        return "env", blockers["ocr"]
    if action_id == "pdf_dsc_sign" and "dsc" in blockers:
        return "env", blockers["dsc"]
    if action_id == "upscale_2x" and "upscale" in blockers:
        return "env", blockers["upscale"]
    return "product", ""


def run_catalog(app):
    section("CATALOG - every action run for real")
    catalog = OpalEngine.get_catalog()
    print(f"Catalog advertises {len(catalog)} actions")
    check("catalog is not empty", bool(catalog), f"{len(catalog)} entries")

    catalog_ids = [c["id"] for c in catalog]
    covered = {r[0] for r in CATALOG_RUNS} | {"merge_pdf"}
    missing = [i for i in catalog_ids if i not in covered]
    check("every catalog id has a test fixture", not missing,
          f"missing: {missing}" if missing else "all covered")
    extra = sorted(covered - set(catalog_ids))
    check("no test runs an action the catalog does not advertise",
          all(e in ("merge_pdf",) for e in extra), f"extra ids: {extra}")

    blockers = probe_environment()
    for name, reason in blockers.items():
        print(f"      (environment note: {name}: {reason})")

    for action_id, src_name, options, expect in CATALOG_RUNS:
        src = SANDBOX / src_name
        if not src.exists():
            # A fixture this machine could not provide is not a defect.
            skip(f"catalog action '{action_id}'", f"fixture missing: {src_name}")
            continue
        try:
            res = OpalEngine.execute_single(str(src), action_id, options)
        except Exception as e:
            check(f"catalog action '{action_id}'", False,
                  f"{type(e).__name__}: {e}", "product")
            continue
        if not res.success:
            kind, reason = env_kind_for(action_id, blockers)
            detail = res.message
            if kind == "product" and looks_like_memory_failure(res.message):
                kind = "env"
                detail = (f"{res.message} | only {free_ram_gb():.1f} GB of RAM was free "
                          f"when the model ran")
            elif kind == "product" and action_id in MEDIA_ACTIONS:
                healthy, why = ffmpeg_healthy()
                if not healthy:
                    kind = "env"
                    detail = f"{res.message} | {why}"
            check(f"catalog action '{action_id}'", False, detail, kind)
            continue
        ok, detail = validate_output(res.output_path, expect)
        OUTPUTS[action_id] = res.output_path
        check(f"catalog action '{action_id}'", ok,
              detail if ok else f"{detail} | message={res.message}")

    # merge_pdf needs more than one file, so it runs through the batch API.
    batch = OpalEngine.execute_batch([str(SANDBOX / "contract.pdf"),
                                       str(SANDBOX / "contract2.pdf")], "merge_pdf")
    ok = batch.succeeded == 2 and bool(batch.outputs)
    detail = batch.message
    if ok:
        vok, vdetail = validate_output(batch.outputs[0], "pdf")
        ok, detail = vok, vdetail if vok else f"{vdetail} | message={batch.message}"
    check("catalog action 'merge_pdf'", ok, detail)

    for action_id, src_name, options, expect in EXTRA_RUNS:
        src = SANDBOX / src_name
        res = OpalEngine.execute_single(str(src), action_id, options)
        if not res.success:
            kind = "product"
            detail = res.message
            if looks_like_memory_failure(res.message):
                kind = "env"
                detail = (f"{res.message} | only {free_ram_gb():.1f} GB of RAM was free")
            elif action_id in MEDIA_ACTIONS:
                healthy, why = ffmpeg_healthy()
                if not healthy:
                    kind = "env"
                    detail = f"{res.message} | {why}"
            check(f"extra action '{action_id}'", False, detail, kind)
            continue
        ok, detail = validate_output(res.output_path, expect)
        check(f"extra action '{action_id}'", ok,
              detail if ok else f"{detail} | message={res.message}")

    # The AI cut-out must really use the cached ONNX model, not a stand-in.
    try:
        from opal_studio.engines import EngineManager
        used = EngineManager.cutout_model_used("u2netp")
        check("AI cut-out model resolves to the cached u2netp.onnx",
              Path(used).name.lower().startswith("u2netp"), used)
    except Exception as e:
        check("AI cut-out model resolves to the cached u2netp.onnx", False,
              f"{type(e).__name__}: {e}", "env")

    nobg = OUTPUTS.get("remove_bg")
    if nobg and Path(nobg).exists():
        with Image.open(nobg) as im:
            rgba = im.convert("RGBA")
            alpha = rgba.getchannel("A")
            extrema = alpha.getextrema()
            samples = list(alpha.getdata())[::37]
            transparent = sum(1 for v in samples if v < 30)
        check("remove_bg produced real transparency (AI matting ran)",
              extrema[0] < 30 and transparent > 0, f"alpha range {extrema}")
    else:
        check("remove_bg produced real transparency (AI matting ran)", False,
              f"no transparent cut-out was produced ({nobg})", "product")

    # The AI upscaler must not leave a broken model behind in the cache.
    try:
        from opal_studio.engines import ESRGAN_MODELS, EngineManager, _pinned_request
        cfg = ConfigManager.load_config()
        up_model = cfg.get("upscale_model", "realesrgan-x4plus")
        cached = EngineManager.esrgan_path(up_model)
        if cached.exists():
            head = cached.read_bytes()[:512].lstrip().lower()
            looks_like_html = head.startswith(b"<") or b"<!doctype html" in head
            check("AI Upscale cache holds a real ONNX model, not an HTML error page",
                  not looks_like_html,
                  f"{cached.name} begins with {head[:24]!r} ({cached.stat().st_size} bytes)")
        else:
            # No model on disk. If the network is down that is the reason, and
            # it is not a defect in the app.
            reachable = False
            try:
                resp, close = _pinned_request(ESRGAN_MODELS[up_model][2])
                try:
                    reachable = (getattr(resp, "status", None) or resp.getcode()) == 200
                finally:
                    close()
            except Exception:
                reachable = False
            if not reachable:
                skip("AI Upscale cache holds a real ONNX model, not an HTML error page",
                     "no network, so no model could be fetched")
            else:
                check("AI Upscale cache holds a real ONNX model, not an HTML error page", False,
                      f"{cached} is absent - the downloader never produced a usable model "
                      f"(the shipped URL answers HTTP 404, so the copy it stores is deleted again)",
                      "product")

    except Exception as e:
        check("AI Upscale cache holds a real ONNX model, not an HTML error page", False,
              f"{type(e).__name__}: {e}", "product")

    # The product deletes a damaged model and asks the user to try again.
    # Prove whether that self-heal ever converges, and whether the model can
    # cope with a full-size photo.
    try:
        big = OpalEngine.execute_single(str(SANDBOX / "photo.jpg"), "upscale_2x", {})
        detail = big.message if big.success else \
            f"{big.message} | {free_ram_gb():.1f} GB of RAM was free"
        check("AI Upscale handles a full-size (640x480) photo", big.success, detail,
              "env" if looks_like_memory_failure(big.message) else "product")
    except Exception as e:
        check("AI Upscale handles a full-size (640x480) photo", False,
              f"{type(e).__name__}: {e}", "product")

    # The AI cut-out model must survive a failed run. A low-memory error is
    # not corruption, and the model file must not be thrown away because of it.
    try:
        from opal_studio.engines import EngineManager
        cut_path = EngineManager.cutout_model_path("u2netp")
        if not cut_path.exists():
            check("the AI cut-out model is still on disk after the run", False,
                  f"{cut_path.name} was deleted from the model cache", "product")
        else:
            check("the AI cut-out model is still on disk after the run", True,
                  f"{cut_path.name} ({cut_path.stat().st_size} bytes)")
            try:
                import onnxruntime
                so = onnxruntime.SessionOptions()
                so.enable_cpu_mem_arena = False
                so.intra_op_num_threads = 1
                sess = onnxruntime.InferenceSession(str(cut_path), sess_options=so,
                                                    providers=["CPUExecutionProvider"])
                check("the cached AI cut-out model loads in ONNX Runtime", True,
                      f"input {sess.get_inputs()[0].shape}")
            except Exception as e:
                check("the cached AI cut-out model loads in ONNX Runtime", False,
                      f"{type(e).__name__}: {e} | {free_ram_gb():.1f} GB of RAM was free",
                      "env")
    except Exception as e:
        check("the AI cut-out model is still on disk after the run", False,
              f"{type(e).__name__}: {e}", "product")

    # Evidence for the AI Upscale failure: are the URLs the product ships
    # actually reachable? The check uses the product's own downloader, so it
    # goes through the same allow-list, the same address pinning and the same
    # refusal of anything that is not a model as the app itself.
    try:
        from opal_studio.engines import ESRGAN_MODELS, _pinned_request

        for mid, meta in ESRGAN_MODELS.items():
            url = meta[2]
            unreachable = False
            try:
                resp, close = _pinned_request(url)
                try:
                    status = getattr(resp, "status", None) or resp.getcode()
                finally:
                    close()
            except Exception as e:
                # A machine that cannot reach the network at all is not a
                # broken address, so it is reported as skipped.
                unreachable = True
                status = f"error: {type(e).__name__}: {e}"
            if unreachable:
                skip(f"AI Upscale model URL for '{mid}' is reachable", str(status))
            else:
                check(f"AI Upscale model URL for '{mid}' is reachable",
                      status == 200, f"HTTP {status} for {url}")
    except Exception as e:
        check("AI Upscale model URL for 'realesrgan-x4plus' is reachable", False,
              f"{type(e).__name__}: {e}", "product")

    # The DSC signature must really be embedded in the signed PDF.
    signed = OUTPUTS.get("pdf_dsc_sign")
    if signed and Path(signed).exists():
        try:
            from opal_studio import dsc_sign
            info = dsc_sign.verify_signature(signed)
            check("pdf_dsc_sign embedded a real cryptographic signature",
                  info.get("signed") is True and info.get("count", 0) >= 1,
                  f"{info.get('count')} signature field(s)")
        except Exception as e:
            check("pdf_dsc_sign embedded a real cryptographic signature", False,
                  f"{type(e).__name__}: {e}", "product")

    # OCR must leave a searchable text layer behind.
    ocr = OUTPUTS.get("pdf_ocr")
    if ocr and Path(ocr).exists():
        try:
            import fitz
            doc = fitz.open(ocr)
            try:
                text = "".join(page.get_text() for page in doc)
            finally:
                doc.close()
            check("pdf_ocr left a searchable text layer on the scan",
                  len(text.strip()) > 0, f"{len(text.strip())} characters of OCR text")
            if not text.strip():
                # The page could not be read. Ask the OCR engine directly so
                # the swallowed error becomes visible.
                try:
                    from opal_studio.engines import EngineManager
                    engine = EngineManager.rapidocr_engine()
                    src = fitz.open(str(SANDBOX / "scan.pdf"))
                    try:
                        pix = src[0].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72),
                                                alpha=False)
                        payload = pix.tobytes("png")
                    finally:
                        src.close()
                    found, _ = engine(payload)
                    check("pdf_ocr left a searchable text layer on the scan", False,
                          f"the OCR engine read {len(found)} line(s) from the page image, "
                          f"but the PDF ended up with no text layer", "product")
                except Exception as e:
                    check("pdf_ocr left a searchable text layer on the scan", False,
                          f"the OCR engine itself failed: {type(e).__name__}: {e} "
                          f"| {free_ram_gb():.1f} GB of RAM was free", "env")
        except Exception as e:
            check("pdf_ocr left a searchable text layer on the scan", False,
                  f"{type(e).__name__}: {e}", "product")


# ---------------------------------------------------------------------------
# SECTION 2 - every module in the package imports cleanly
# ---------------------------------------------------------------------------

def test_module_imports(app):
    section("MODULES - every opal_studio module imports cleanly")
    import importlib
    pkg = ROOT / "opal_studio"
    modules = sorted(p.stem for p in pkg.glob("*.py")
                     if p.stem not in ("__init__", "__main__"))
    bad = []
    for name in modules:
        try:
            importlib.import_module(f"opal_studio.{name}")
            check(f"module opal_studio.{name} imports", True, "")
        except Exception as e:
            bad.append(f"{name}: {type(e).__name__}: {e}")
            check(f"module opal_studio.{name} imports", False,
                  f"{type(e).__name__}: {e}", "product")
    check("every opal_studio module imports without error", not bad,
          "; ".join(bad) if bad else f"{len(modules)} modules")


# ---------------------------------------------------------------------------
# SECTION 3 - every dialog and modal surface
# ---------------------------------------------------------------------------

def test_dialogs(app):
    from PySide6.QtWidgets import QApplication, QLineEdit

    section("DIALOGS - every modal surface opens")

    # --- SettingsDialog (recently crashed on open) ---
    from opal_studio.settings_dialog import SettingsDialog
    cfg_before = ConfigManager.load_config()
    cfg_raw = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else None
    try:
        dlg = SettingsDialog()
        dlg.show()
        pump(app, 150)
        check("SettingsDialog opens without crashing", True, "shown")
        check("SettingsDialog is visible", dlg.isVisible())
        check("SettingsDialog shows the AI model pickers",
              dlg.cmb_bg_model.count() > 0 and dlg.cmb_upscale_model.count() > 0,
              f"{dlg.cmb_bg_model.count()} cut-out / {dlg.cmb_upscale_model.count()} upscale models")
        check("SettingsDialog buttons are wired",
              all(b is not None for b in (dlg.btn_save, dlg.btn_cancel,
                                          dlg.btn_install_shell, dlg.btn_remove_shell)))
        # Exercise the Save path for real.
        dlg.chk_keep_dates.setChecked(True)
        dlg.rad_source.setChecked(True)
        dlg.btn_save.click()
        pump(app, 150)
        check("SettingsDialog 'Save Preferences' button works",
              dlg.result() == 1 or dlg.isHidden(), f"result={dlg.result()}")
        saved = ConfigManager.load_config()
        check("SettingsDialog save persisted the preferences",
              saved.get("keep_original_dates") is True and "bg_model" in saved,
              f"bg_model={saved.get('bg_model')}")
    except Exception as e:
        check("SettingsDialog opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")
    finally:
        if cfg_raw is not None:
            try:
                CONFIG_FILE.write_text(cfg_raw, encoding="utf-8")
            except Exception:
                pass

    # --- HistoryDialog ---
    try:
        from opal_studio.history_dialog import HistoryDialog
        ConfigManager.add_history_entry("photo.jpg", "photo_webp.webp", "webp",
                                        str(SANDBOX / "photo.jpg"), 1024)
        hist = HistoryDialog()
        hist.show()
        pump(app, 150)
        check("HistoryDialog opens without crashing", True, "shown")
        check("HistoryDialog is visible", hist.isVisible())
        check("HistoryDialog lists recorded runs", hist.table.rowCount() >= 1,
              f"{hist.table.rowCount()} row(s)")
    except Exception as e:
        check("HistoryDialog opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- SignatureDialog: draw / type / image tabs ---
    try:
        from opal_studio.viewer_pdf import SignatureDialog
        sig = SignatureDialog()
        sig.show()
        pump(app, 120)
        check("SignatureDialog opens without crashing", True, "shown")
        check("SignatureDialog is visible", sig.isVisible())
        check("SignatureDialog has draw / type / image tabs", sig.tabs.count() == 3,
              f"{sig.tabs.count()} tabs")
        # Type tab
        sig.tabs.setCurrentIndex(1)
        sig.name_edit.setText("Ramesh Kumar")
        typed = sig._typed_signature()
        check("SignatureDialog type tab renders a signature", typed is not None,
              f"{len(typed)} bytes" if typed else "no PNG")
        # Draw tab: paint on the canvas and read the ink bounds back
        sig.tabs.setCurrentIndex(0)
        from PySide6.QtGui import QPainter, QPen, QColor
        from PySide6.QtCore import Qt
        p = QPainter(sig.canvas_img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(0, 0, 0), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(60, 120, 320, 60)
        p.drawLine(320, 60, 300, 140)
        p.end()
        rect = sig._content_rect()
        check("SignatureDialog draw tab captures strokes",
              not rect.isNull(), f"ink rect {rect}")
        # Image tab
        sig.tabs.setCurrentIndex(2)
        sig.signature_image_path = str(SANDBOX / "photo.jpg")
        from PySide6.QtGui import QImage, QPixmap
        sig.image_preview.setPixmap(QPixmap.fromImage(QImage(SANDBOX / "photo.jpg").scaled(200, 80)))
        sig._apply()
        pump(app, 100)
        check("SignatureDialog image tab produces a signature PNG",
              sig.signature_png is not None,
              f"{len(sig.signature_png)} bytes" if sig.signature_png else "none")
    except Exception as e:
        check("SignatureDialog opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- PdfStudio ---
    try:
        from opal_studio.viewer_pdf import PdfStudio
        studio = PdfStudio(str(SANDBOX / "contract.pdf"))
        studio.show()
        pump(app, 400)
        check("PdfStudio opens without crashing", True, "shown")
        check("PdfStudio is visible", studio.isVisible())
        check("PdfStudio loaded the document", studio.doc is not None,
              f"{len(studio.doc) if studio.doc else 0} page(s)")
        check("PdfStudio built a page view per page",
              len(studio.views) == len(studio.doc) if studio.doc else False,
              f"{len(studio.views)} view(s)")
        check("PdfStudio built page thumbnails", studio.thumb_list.count() >= 1,
              f"{studio.thumb_list.count()} thumbnail(s)")
    except Exception as e:
        check("PdfStudio opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- _range_dialog (a modal helper) ---
    try:
        from opal_studio.viewer_pdf import _range_dialog
        state = {}

        def _fill():
            w = QApplication.activeModalWidget()
            if w is None:
                return
            state["title"] = w.windowTitle()
            edit = w.findChild(QLineEdit)
            if edit is not None:
                edit.setText("1-2")
            w.accept()

        from PySide6.QtCore import QTimer
        QTimer.singleShot(400, _fill)
        spec, accepted = _range_dialog(None, "Extract Page Range", 3)
        check("_range_dialog opens and returns the typed range",
              accepted is True and spec == "1-2",
              f"title={state.get('title')!r} spec={spec!r} accepted={accepted}")
    except Exception as e:
        check("_range_dialog opens and returns the typed range", False,
              f"{type(e).__name__}: {e}", "product")

    # --- ImageLab ---
    try:
        from opal_studio.viewer_image import ImageLab
        lab = ImageLab(str(SANDBOX / "photo.jpg"))
        lab.show()
        pump(app, 300)
        check("ImageLab opens without crashing", True, "shown")
        check("ImageLab is visible", lab.isVisible())
        check("ImageLab loaded the picture", lab.current_image is not None,
              f"{lab.current_image.width()}x{lab.current_image.height()}"
              if lab.current_image else "no image")
        lab.set_tool("palette")
        lab._run_palette()
        pump(app, 120)
        check("ImageLab palette tool produces swatches", lab.palette_lay.count() == 6,
              f"{lab.palette_lay.count()} swatch(es)")
    except Exception as e:
        check("ImageLab opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- DocStudio ---
    try:
        from opal_studio.viewer_doc import DocStudio
        doc = DocStudio(str(SANDBOX / "notes.txt"))
        doc.show()
        pump(app, 200)
        check("DocStudio opens without crashing", True, "shown")
        check("DocStudio is visible", doc.isVisible())
        check("DocStudio rendered the text", "Opal" in doc.text_view.toPlainText(),
              doc.text_stats.text())
    except Exception as e:
        check("DocStudio opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- MediaStudio ---
    try:
        from opal_studio.viewer_media import MediaStudio
        if (SANDBOX / "clip.mp4").exists():
            media = MediaStudio(str(SANDBOX / "clip.mp4"))
            media.show()
            pump(app, 400)
            check("MediaStudio opens without crashing", True, "shown")
            check("MediaStudio is visible", media.isVisible())
            check("MediaStudio read the media duration", media.duration > 0.5,
                  f"{media.duration}s")
        else:
            check("MediaStudio opens without crashing", False,
                  "fixture clip.mp4 is missing (no FFmpeg)", "env")
    except Exception as e:
        check("MediaStudio opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- Dashboard ---
    try:
        from opal_studio.dashboard import OpalDashboard
        dash = OpalDashboard()
        dash.show()
        pump(app, 200)
        check("OpalDashboard opens without crashing", True, "shown")
        check("OpalDashboard is visible", dash.isVisible())
    except Exception as e:
        check("OpalDashboard opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- FloatStudio + HomeTab ---
    try:
        from opal_studio.float_viewer import FloatStudio, HomeTab
        studio = FloatStudio()
        studio.show()
        pump(app, 250)
        check("FloatStudio opens without crashing", True, "shown")
        check("FloatStudio is visible", studio.isVisible())
        check("FloatStudio starts on the Home tab", studio.tabs.count() == 1,
              f"{studio.tabs.count()} tab(s)")
        opened = studio.open_file(str(SANDBOX / "photo.jpg"))
        pump(app, 250)
        check("FloatStudio opens a file in a new tab",
              opened and studio.tabs.count() == 2, f"{studio.tabs.count()} tab(s)")
        home = HomeTab()
        home.show()
        pump(app, 150)
        check("FloatStudio HomeTab opens without crashing", True, "shown")
        check("FloatStudio HomeTab is visible", home.isVisible())
    except Exception as e:
        check("FloatStudio opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- RadialMenuWidget in all three modes ---
    try:
        from opal_studio.radial_widget import RadialMenuWidget
        from PySide6.QtCore import QPoint
        wheel = RadialMenuWidget()
        wheel.show_for_files([str(SANDBOX / "photo.jpg")], QPoint(200, 200),
                              initial_mode="convert")
        pump(app, 200)
        check("RadialMenuWidget opens without crashing", True, "shown")
        check("RadialMenuWidget is visible", wheel.isVisible())
        convert_ids = [o["id"] for o in wheel.options]
        check("RadialMenuWidget 'convert' mode lists conversions", len(convert_ids) > 3,
              f"{len(convert_ids)} option(s)")
        wheel.set_mode("tools")
        pump(app, 120)
        tool_ids = [o["id"] for o in wheel.options]
        check("RadialMenuWidget 'tools' mode lists tools",
              "remove_bg" in tool_ids, f"{len(tool_ids)} option(s)")
        wheel.set_mode("actions")
        pump(app, 120)
        action_ids = [o["id"] for o in wheel.options]
        check("RadialMenuWidget 'actions' mode lists actions",
              "float" in action_ids and "hash_file" in action_ids,
              f"{len(action_ids)} option(s)")
        wheel.close()
    except Exception as e:
        check("RadialMenuWidget opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- Toast ---
    try:
        from opal_studio.toast import OpalToast
        toast = OpalToast()
        toast.show_message("Conversion Complete", "Saved new file.",
                            str(SANDBOX / "photo.jpg"))
        pump(app, 150)
        check("OpalToast opens without crashing", True, "shown")
        check("OpalToast is visible", toast.isVisible())
        check("OpalToast shows the action buttons",
              toast.btn_open.isVisible() and toast.btn_folder.isVisible())
        toast.close()
    except Exception as e:
        check("OpalToast opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")

    # --- Tray ---
    try:
        from opal_studio.tray import OpalTray
        tray = OpalTray()
        pump(app, 100)
        check("OpalTray opens without crashing", True, "created")
        check("OpalTray has a context menu", tray.contextMenu() is not None,
              f"{len(tray.contextMenu().actions())} menu item(s)")
    except Exception as e:
        check("OpalTray opens without crashing", False,
              f"{type(e).__name__}: {e}", "product")


# ---------------------------------------------------------------------------
# SECTION 4 - the cross-platform layer
# ---------------------------------------------------------------------------

def snapshot_registry():
    """Saves the registry entries the platform layer may touch, so we can put
    the user's machine back exactly as we found it."""
    saved = {}
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            try:
                saved["run"] = winreg.QueryValueEx(key, "Opal")[0]
            except FileNotFoundError:
                saved["run"] = None
    except Exception:
        saved["run"] = "unavailable"
    return saved


def restore_registry(saved):
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if saved.get("run") is None:
                try:
                    winreg.DeleteValue(key, "Opal")
                except FileNotFoundError:
                    pass
            elif isinstance(saved.get("run"), str):
                winreg.SetValueEx(key, "Opal", 0, winreg.REG_SZ, saved["run"])
    except Exception:
        pass


def test_platform_compat():
    section("CROSS-PLATFORM LAYER")
    from opal_studio import platform_compat as pc

    saved = snapshot_registry()

    # platform_name / supported flags
    name = pc.platform_name()
    check("platform_name() returns the OS name", name in ("Windows", "macOS", "Linux"),
          name)
    check("startup_supported() returns a bool", isinstance(pc.startup_supported(), bool),
          f"startup_supported={pc.startup_supported()}")
    check("context_menu_supported() returns a bool",
          isinstance(pc.context_menu_supported(), bool),
          f"context_menu_supported={pc.context_menu_supported()}")

    # portable_root / user_data_dir / is_portable
    root = pc.portable_root()
    check("portable_root() returns a path or None",
          root is None or Path(root).is_dir(), str(root))
    udd = pc.user_data_dir()
    check("user_data_dir() returns an existing folder",
          isinstance(udd, Path) and udd.is_dir(), str(udd))
    check("is_portable() agrees with portable_root()",
          pc.is_portable() == (root is not None), f"is_portable={pc.is_portable()}")

    # clipboard
    # A build machine with no clipboard tool and no display is not a defect in
    # the app, so the check is skipped rather than failed.
    clipboard_tool = (pc.IS_WINDOWS or pc.IS_MAC
                      or any(shutil.which(c) for c in ("wl-copy", "xclip", "xsel")))
    if clipboard_tool:
        try:
            ok = pc.copy_text_to_clipboard("Opal clipboard probe 12345")
            check("copy_text_to_clipboard() works", ok is True, f"returned {ok}")
        except Exception as e:
            check("copy_text_to_clipboard() works", False,
                  f"{type(e).__name__}: {e}", "product")
    else:
        skip("copy_text_to_clipboard() works", "no clipboard tool on this machine")

    # trash a throwaway file
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    throwaway = PROBE_DIR / "throwaway_trash_probe.txt"
    throwaway.write_text("delete me", encoding="utf-8")
    try:
        ok = pc.send_to_trash(str(throwaway))
        check("send_to_trash() removes the file", ok is True and not throwaway.exists(),
              f"returned {ok}, file still there={throwaway.exists()}")
    except Exception as e:
        check("send_to_trash() removes the file", False,
              f"{type(e).__name__}: {e}", "product")

    # start-up entry
    try:
        ok_on = pc.set_startup_entry(True)
        check("set_startup_entry(True) registers the app", ok_on is True, f"returned {ok_on}")
        ok_off = pc.set_startup_entry(False)
        check("set_startup_entry(False) removes the app", ok_off is True, f"returned {ok_off}")
    except Exception as e:
        check("set_startup_entry(True) registers the app", False,
              f"{type(e).__name__}: {e}", "product")

    # file-manager integration
    try:
        ok = pc.install_context_menu()
        check("install_context_menu() registers the entry", ok is True, f"returned {ok}")
        ok = pc.uninstall_context_menu()
        check("uninstall_context_menu() removes the entry", ok is True, f"returned {ok}")
    except Exception as e:
        check("install_context_menu() registers the entry", False,
              f"{type(e).__name__}: {e}", "product")

    # reveal / open / terminal - these really touch the desktop
    probe_file = PROBE_DIR / "probe.txt"
    probe_file.write_text("Opal platform probe", encoding="utf-8")
    try:
        ok = pc.reveal_in_file_manager(str(probe_file))
        check("reveal_in_file_manager() opens Explorer on the file", ok is True,
              f"returned {ok}")
    except Exception as e:
        check("reveal_in_file_manager() opens Explorer on the file", False,
              f"{type(e).__name__}: {e}", "product")

    try:
        ok = pc.open_with_default(str(probe_file))
        check("open_with_default() opens the file with its default app", ok is True,
              f"returned {ok}")
    except Exception as e:
        check("open_with_default() opens the file with its default app", False,
              f"{type(e).__name__}: {e}", "product")

    terminal_tool = (pc.IS_WINDOWS or pc.IS_MAC
                     or any(shutil.which(c) for c in
                            ("x-terminal-emulator", "gnome-terminal", "konsole",
                             "xfce4-terminal", "xterm")))
    if terminal_tool:
        try:
            ok = pc.open_terminal(str(PROBE_DIR))
            check("open_terminal() opens a terminal in the folder", ok is True,
                  f"returned {ok}")
        except Exception as e:
            check("open_terminal() opens a terminal in the folder", False,
                  f"{type(e).__name__}: {e}", "product")
    else:
        skip("open_terminal() opens a terminal in the folder",
             "no terminal emulator on this machine")

    restore_registry(saved)


# ---------------------------------------------------------------------------
# SECTION 5 - the command line
# ---------------------------------------------------------------------------

def run_cli(args, timeout=900):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "opal_studio" / "cli.py")] + args,
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0 and proc.stderr.strip():
        print(f"      (cli stderr) {proc.stderr.strip()[-800:]}")
    return proc


def test_cli():
    section("COMMAND LINE")
    cli = str(ROOT / "opal_studio" / "cli.py")

    try:
        proc = run_cli(["--catalog"])
        catalog = OpalEngine.get_catalog()
        missing = [c["id"] for c in catalog if c["id"] not in proc.stdout]
        check("CLI --catalog exits 0", proc.returncode == 0, f"code={proc.returncode}")
        check("CLI --catalog prints the whole catalog",
              "Opal can do" in proc.stdout and not missing,
              f"missing ids: {missing}" if missing else f"{len(catalog)} ids listed")
    except Exception as e:
        check("CLI --catalog exits 0", False, f"{type(e).__name__}: {e}", "product")

    try:
        proc = run_cli(["--list-formats"])
        wanted = ("Images:", "Video  :", "Audio  :", "Docs   :", "PDF    :",
                  "Fonts  :", "Archive:")
        missing = [w for w in wanted if w not in proc.stdout]
        check("CLI --list-formats exits 0", proc.returncode == 0, f"code={proc.returncode}")
        check("CLI --list-formats prints every format group", not missing,
              f"missing: {missing}" if missing else "all groups present")
    except Exception as e:
        check("CLI --list-formats exits 0", False, f"{type(e).__name__}: {e}", "product")

    try:
        proc = run_cli(["--info", str(SANDBOX / "contract.pdf")])
        check("CLI --info exits 0", proc.returncode == 0, f"code={proc.returncode}")
        try:
            payload = json.loads(proc.stdout)
            check("CLI --info prints machine-readable JSON about the file",
                  payload.get("category") == "pdf" and payload.get("pages", 0) >= 1,
                  f"category={payload.get('category')} pages={payload.get('pages')}")
        except json.JSONDecodeError as e:
            check("CLI --info prints machine-readable JSON about the file", False,
                  f"{type(e).__name__}: {e} | stdout began with {proc.stdout[:120]!r}",
                  "product")
    except Exception as e:
        check("CLI --info exits 0", False, f"{type(e).__name__}: {e}", "product")

    out_dir = SANDBOX / "cli_out"
    try:
        proc = run_cli(["--convert", str(SANDBOX / "photo.jpg"), "--to", "webp",
                        "--out", str(out_dir)])
        produced = list(out_dir.glob("*.webp")) if out_dir.exists() else []
        check("CLI --convert exits 0", proc.returncode == 0,
              f"code={proc.returncode} out={proc.stdout.strip()[-120:]}")
        check("CLI --convert really produced a file",
              "1 succeeded, 0 failed" in proc.stdout and bool(produced),
              f"{len(produced)} webp file(s)")
        if produced:
            ok, detail = _validate_file(produced[0], "image")
            check("CLI --convert output is a valid WebP", ok, detail)
    except Exception as e:
        check("CLI --convert exits 0", False, f"{type(e).__name__}: {e}", "product")

    try:
        proc = run_cli(["--tool", str(SANDBOX / "portrait.jpg"), "--to", "remove_bg",
                        "--options", '{"bg_model": "u2netp"}'])
        noise = f"{proc.stdout}\n{proc.stderr}"
        kind = "env" if looks_like_memory_failure(noise) else "product"
        check("CLI --tool exits 0", proc.returncode == 0,
              f"code={proc.returncode} out={proc.stdout.strip()[-160:]} "
              f"err={proc.stderr.strip()[-200:]}", kind)
        check("CLI --tool really ran the AI cut-out",
              "1 succeeded, 0 failed" in proc.stdout and "FAIL" not in proc.stdout,
              proc.stdout.strip()[-160:], kind)
    except Exception as e:
        check("CLI --tool exits 0", False, f"{type(e).__name__}: {e}", "product")

    # put the user's own output preference back the way we found it
    try:
        ConfigManager.save_config(ConfigManager.load_config())
        cfg = ConfigManager.load_config()
        cfg["output_mode"] = "same_as_source"
        cfg["custom_output_dir"] = ""
        ConfigManager.save_config(cfg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# SECTION 6 - the markdown report
# ---------------------------------------------------------------------------

def environment_facts():
    """A short, factual list of what was actually available on this machine."""
    facts = {}
    ff = OpalEngine.get_ffmpeg_bin()
    facts["FFmpeg"] = ff if ff else "NOT FOUND"
    try:
        import onnxruntime
        facts["onnxruntime"] = onnxruntime.__version__
    except Exception as e:
        facts["onnxruntime"] = f"not available ({e})"
    try:
        from opal_studio.engines import EngineManager
        from opal_studio.config import ConfigManager as _cm
        cfg = _cm.load_config()
        model = cfg.get("upscale_model", "realesrgan-x4plus")
        cut = EngineManager.local_cutout_model()
        facts["AI cut-out model (u2netp)"] = f"cached at {cut}" if cut else "NOT cached"
        up_path = EngineManager.esrgan_path(model)
        if up_path.exists():
            head = up_path.read_bytes()[:64].lstrip().lower()
            if head.startswith(b"<"):
                facts[f"AI upscale model ({model})"] = (
                    f"file present but CORRUPT - {up_path.name} is an HTML page "
                    f"({up_path.stat().st_size} bytes)")
            else:
                facts[f"AI upscale model ({model})"] = f"cached at {up_path}"
        else:
            facts[f"AI upscale model ({model})"] = "NOT cached - must be downloaded"
    except Exception as e:
        facts["AI models"] = f"could not be queried ({e})"
    try:
        from opal_studio import dsc_sign
        facts["PDF signing (pyHanko)"] = "installed" if dsc_sign.available() else "NOT installed"
    except Exception as e:
        facts["PDF signing (pyHanko)"] = f"not available ({e})"
    try:
        from opal_studio.engines import EngineManager
        facts["OCR (RapidOCR)"] = "available" if EngineManager.ocr_available() else "NOT available"
    except Exception as e:
        facts["OCR (RapidOCR)"] = f"not available ({e})"
    facts["Network"] = "reachable" if _network_ok() else "NOT reachable"
    try:
        import psutil
        vm = psutil.virtual_memory()
        facts["Free RAM during the run"] = (f"{vm.available / 1e9:.1f} GB free of "
                                           f"{vm.total / 1e9:.1f} GB")
    except Exception:
        pass
    return facts


def _network_ok():
    try:
        import urllib.request
        with urllib.request.urlopen("https://github.com", timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def write_report():
    failures = [r for r in RESULTS if not r["ok"]]
    product = [r for r in failures if r["kind"] == "product"]
    env = [r for r in failures if r["kind"] == "env"]
    harness = [r for r in failures if r["kind"] == "harness"]

    lines = []
    lines.append("# Opal - Every-Feature Verification Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Suite: `tests/test_every_feature.py`")
    lines.append(f"- Result: **{len(PASS)} passed, {len(FAIL)} failed** "
                 f"({len(RESULTS)} checks in total)")
    lines.append("")
    lines.append("The suite runs every action in `OpalEngine.get_catalog()` against real "
                 "sample files, opens every dialog and modal surface headless, exercises "
                 "every public function in `opal_studio/platform_compat.py` and drives "
                 "the CLI. Output files are re-opened with the matching reader "
                 "(PIL / PyMuPDF / zipfile) so a \"successful\" conversion that produced "
                 "a broken file counts as a failure.")
    lines.append("")
    lines.append("### Areas covered")
    lines.append("")
    lines.append("| Area | Checks |")
    lines.append("|------|--------|")
    seen = {}
    for r in RESULTS:
        seen.setdefault(r["area"], [0, 0])
        seen[r["area"]][0] += 1
        if not r["ok"]:
            seen[r["area"]][1] += 1
    for area, (total, bad) in seen.items():
        lines.append(f"| {area} | {total} ({total - bad} passed, {bad} failed) |")
    lines.append("")
    lines.append("### Engines available on this machine")
    lines.append("")
    lines.append("| Engine | State |")
    lines.append("|--------|-------|")
    for name, state in environment_facts().items():
        lines.append(f"| {name} | {state} |")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- The suite touches the real desktop on purpose: "
                 "`reveal_in_file_manager()`, `open_with_default()` and `open_terminal()` "
                 "really open Explorer, the default app and a PowerShell window, and "
                 "`send_to_trash()` really uses the Recycle Bin.")
    lines.append("- The user's own `config.json` and the `HKCU\\...\\Run` startup entry are "
                 "snapshotted before the run and written back afterwards, and the outputs are "
                 "forced next to the sample files so the run never depends on a saved "
                 "preference.")
    lines.append("- Every AI action runs the real model. `u2netp.onnx` is cached locally and "
                 "the cut-out is proven by the transparency of the produced PNG; the "
                 "Real-ESRGAN model is downloaded on first use and verified by the product's "
                 "own checksum check.")
    lines.append("- The memory numbers in the table matter: the Real-ESRGAN model needs a "
                 "large contiguous allocation, so on a busy machine its failures are "
                 "allocator errors, not logic errors. Those checks are reported as "
                 "environment problems, with the free RAM at the time of the run.")
    lines.append("")

    lines.append("## Full results")
    lines.append("")
    lines.append("| # | Area | Feature | Result | Detail |")
    lines.append("|---|------|---------|--------|--------|")
    for i, r in enumerate(RESULTS, 1):
        detail = r["detail"].replace("|", "\\|").replace("\n", " ")
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(f"| {i} | {r['area']} | {r['name']} | "
                     f"{'PASS' if r['ok'] else 'FAIL'} | {detail} |")
    lines.append("")

    lines.append("## Failures")
    lines.append("")
    if not failures:
        lines.append("No failures: every feature checked works end to end.")
        lines.append("")
    else:
        causes = []
        for r in failures:
            c = guess_cause(r)
            if c not in causes:
                causes.append(c)
        lines.append(f"{len(failures)} failed check(s) fall into "
                     f"{len(causes)} distinct root cause(s):")
        lines.append("")
        for c in causes:
            lines.append(f"- {c}")
        lines.append("")
        lines.append("### (a) Real product bugs")
        lines.append("")
        if product:
            lines.append("| Feature | Exact error | Most likely cause | How to reproduce |")
            lines.append("|---------|-------------|-------------------|-----------------|")
            for r in product:
                lines.append(f"| {r['name']} | `{r['detail']}` | {guess_cause(r)} | "
                             f"{repro_steps(r)} |")
        else:
            lines.append("None.")
        lines.append("")

        lines.append("### (b) Environment problems")
        lines.append("")
        lines.append("Not product defects - a required optional dependency is missing "
                     "or unreachable in this sandbox.")
        lines.append("")
        if env:
            lines.append("| Feature | Exact error | Missing dependency |")
            lines.append("|---------|-------------|--------------------|")
            for r in env:
                lines.append(f"| {r['name']} | `{r['detail']}` | {guess_cause(r)} |")
        else:
            lines.append("None.")
        lines.append("")

        lines.append("### (c) Test-harness problems")
        lines.append("")
        lines.append("Problems with the test itself, not with the product.")
        lines.append("")
        if harness:
            lines.append("| Feature | Exact error | Harness issue |")
            lines.append("|---------|-------------|---------------|")
            for r in harness:
                lines.append(f"| {r['name']} | `{r['detail']}` | {guess_cause(r)} |")
        else:
            lines.append("None.")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return len(product), len(env), len(harness)


def repro_steps(r):
    """A one-line reproduction command for a failed check."""
    low = (r["detail"] + " " + r["name"]).lower()
    if ("invalid_protobuf" in low or "html error page" in low or "http 404" in low
            or "damaged" in low):
        return ("`python opal_studio/cli.py --tool <image.jpg> --to upscale_2x` - or use the "
                "AI Upscale button in the Image Lab. Delete "
                "`%APPDATA%\\Opal\\models\\realesrgan-x4plus.onnx` first to see the download "
                "step itself.")
    if "jsondecodeerror" in low:
        return "`python opal_studio/cli.py --info <file.pdf> | python -c \"import json,sys; json.load(sys.stdin)\"`"
    return "See the exact error in the table above."


def guess_cause(r):
    """A short, evidence-based cause for a failed check."""
    d = r["detail"]
    low = d.lower()
    name_low = r["name"].lower()
    if r["kind"] == "env":
        if looks_like_memory_failure(d):
            tail = d.split("|")[-1].strip() if "|" in d else ""
            return ("The machine ran out of free RAM while the AI model was running - "
                    "this is an allocator failure, not a code fault. " + tail).strip()
        return d.split("|")[0].strip() if "|" in d else d
    if r["kind"] == "harness":
        return "The test fixture was missing or the harness could not drive the widget."
    if ("invalid_protobuf" in low or "html error page" in low or "http 404" in low
            or "damaged" in low or "html" in name_low or "upscale" in name_low
            or "upscales" in low):
        return ("`opal_studio/engines.py` ships a Real-ESRGAN model URL that answers HTTP 404, "
                "and `_pinned_request()` never checks the HTTP status, so the GitHub 404 HTML "
                "page is written to the model cache as `realesrgan-x4plus.onnx`. ONNX Runtime "
                "then fails with INVALID_PROTOBUF. `EngineManager.ensure_esrgan()` returns any "
                "existing file, so the broken model stays cached and the feature never "
                "self-heals.")
    if "jsondecodeerror" in low and "fitz" in low:
        return ("`opal_studio/cli.py` imports the engine at module load, and PyMuPDF prints "
                "its `fitz` deprecation notice to STDOUT on import. `--info` therefore prints "
                "that warning before the JSON, so stdout is not machine-readable (the same "
                "warning also prefixes `--catalog` and `--list-formats`).")
    if "not supported" in low:
        return ("The action id is never routed inside `OpalEngine._execute_single_inner` / "
                "`_route_extended`, so the engine answers 'not supported'.")
    if "no certificate" in low:
        return "The DSC signing action needs a .pfx/.p12 certificate passed in the options."
    if "module not found" in low or "no module named" in low:
        return "An optional third-party dependency for this action is not installed."
    if "not available" in low:
        return "A required engine (FFmpeg / OCR / signing) is not available on this machine."
    return ("The product returned this error for a valid input - needs a code fix in "
            "`opal_studio/`.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def release_ai_sessions():
    """Frees the AI sessions this process loaded, so that the command line
    run (which has to load the very same model again) has room to do it."""
    try:
        from opal_studio.engines import EngineManager
        EngineManager._rembg_sessions.clear()
        EngineManager._esrgan_sessions.clear()
        EngineManager._rapidocr_engine = None
        import gc
        gc.collect()
        return True
    except Exception:
        return False


def main():
    # The suite must be hermetic: remember the user's own preferences, force
    # the outputs next to the sample files, and put everything back at the end.
    cfg_snapshot = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else None
    try:
        cfg = ConfigManager.load_config()
        cfg["output_mode"] = "same_as_source"
        cfg["custom_output_dir"] = ""
        ConfigManager.save_config(cfg)
    except Exception as e:
        print(f"(could not pin the output directory: {e})")

    try:
        setup()
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        run_catalog(app)
        test_module_imports(app)
        test_dialogs(app)
        test_platform_compat()
        release_ai_sessions()
        test_cli()

        n_product, n_env, n_harness = write_report()
    finally:
        if cfg_snapshot is not None:
            try:
                CONFIG_FILE.write_text(cfg_snapshot, encoding="utf-8")
            except Exception:
                pass

    print("\n" + "=" * 68)
    print(f"EVERY-FEATURE RESULT: {len(PASS)} passed, {len(FAIL)} failed, "
          f"{len(SKIPPED)} skipped")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    if SKIPPED:
        print("SKIPPED:", ", ".join(SKIPPED))
    print(f"Breakdown -> product bugs: {n_product}, environment: {n_env}, harness: {n_harness}")
    print(f"Report written to {REPORT_PATH}")
    print("=" * 68)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    _code = main()
    # This suite opens real windows and leaves them for Qt to tear down when
    # the interpreter exits, which crashes on macOS and Windows alike. The
    # app's own quit path is exercised by the smoke test, so the process is
    # ended here, once the results are in.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
