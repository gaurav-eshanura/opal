"""Real sample files for the Opal test-suite.

The old suite printed PASS/FAIL and exited 0 whatever happened, so a broken
feature still looked green.  This module supplies the raw material for a suite
that can actually fail: one real file in every format Opal handles, built on
the machine that runs the test.

Nothing here is a stub.  Every file is a genuine document that the matching
reader can open.
"""
from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Every sample the suite knows about, in the order they are built.
SAMPLE_NAMES = [
    "photo.jpg", "portrait.jpg", "tiny.png", "alpha.png", "pic.webp",
    "contract.pdf", "contract2.pdf", "scan.pdf", "big.pdf",
    "notes.txt", "readme.md", "page.html", "app.log", "rich.rtf",
    "data.csv", "data.json", "subs.srt", "subs.vtt",
    "report.docx", "sheet.xlsx", "deck.pptx", "novel.epub",
    "arial.ttf", "bundle.zip", "cert.p12",
    "clip.mp4", "clip.srt", "tone.wav",
]


class Samples:
    """The sample files on disk, and why any of them could not be built."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.files: dict[str, Path] = {}
        self.missing: dict[str, str] = {}

    def path(self, name: str) -> Path:
        return self.folder / name

    def has(self, name: str) -> bool:
        return name in self.files

    def reason(self, name: str) -> str:
        return self.missing.get(name, "")

    def __contains__(self, name: str) -> bool:
        return name in self.files


def _ffmpeg() -> str | None:
    """The ffmpeg binary Opal itself would use, if this machine has one."""
    try:
        from opal_studio.engine import OpalEngine
        return OpalEngine.get_ffmpeg_bin()
    except Exception:
        return None


def _run_ffmpeg(binary: str, arguments: list[str]) -> bool:
    """Run ffmpeg with an argument list.  Never through a shell, so nothing
    from the arguments can be read as a command."""
    options = {"shell": False, "capture_output": True}
    if sys.platform == "win32":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run([binary, *arguments], **options)
    except Exception:
        return False
    return proc.returncode == 0


def _make_photo(path: Path) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 480), (30, 120, 200))
    d = ImageDraw.Draw(img)
    d.ellipse((180, 120, 460, 400), fill=(255, 200, 40))
    d.rectangle((60, 400, 580, 450), fill=(240, 240, 245))
    d.text((70, 30), "Opal Test Photo", fill=(255, 255, 255))
    img.save(path, quality=92)


def _make_portrait(path: Path) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 800), (208, 214, 226))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 600, 520), fill=(196, 204, 218))
    d.ellipse((140, 520, 460, 860), fill=(62, 78, 128))
    d.ellipse((195, 140, 405, 420), fill=(226, 186, 158))
    d.ellipse((228, 245, 262, 275), fill=(40, 36, 34))
    d.ellipse((338, 245, 372, 275), fill=(40, 36, 34))
    d.arc((250, 300, 350, 350), 0, 180, fill=(150, 90, 80), width=6)
    d.rectangle((270, 195, 330, 230), fill=(48, 40, 38))
    img.save(path, quality=94)


def _make_pdf(path: Path, pages: int, text: str) -> None:
    import fitz
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"{text} page {i + 1}", fontsize=16)
        page.insert_text((72, 140), "The quick brown fox jumps over the lazy dog.", fontsize=11)
    doc.save(str(path))
    doc.close()


def _make_scan_pdf(path: Path) -> None:
    """A PDF that holds only a picture of text, so OCR has real work to do."""
    import fitz
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1000, 1400), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.text((90, 140), "OPAL SCANNED DOCUMENT", fill=(20, 20, 30))
    d.text((90, 220), "Invoice number 4821", fill=(20, 20, 30))
    d.text((90, 290), "Total payable 2500 rupees", fill=(20, 20, 30))
    tmp = path.parent / "_scan.png"
    img.save(tmp)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(40, 40, 555, 800), filename=str(tmp))
    doc.save(str(path))
    doc.close()
    tmp.unlink(missing_ok=True)


def _make_big_pdf(path: Path) -> None:
    """A PDF well over 1 MB, so the WhatsApp shrinker has something to do."""
    import fitz
    from PIL import Image
    noise = Image.frombytes("RGB", (900, 900), os.urandom(900 * 900 * 3))
    tmp = path.parent / "_noise.png"
    noise.save(tmp)
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(0, 0, 595, 842), filename=str(tmp))
    doc.save(str(path))
    doc.close()
    tmp.unlink(missing_ok=True)


def _make_certificate(path: Path) -> None:
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
    path.write_bytes(pkcs12.serialize_key_and_certificates(
        b"opal-test", key, cert, None, serialization.NoEncryption()))


def _make_epub(path: Path) -> None:
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier("opal-samples")
    book.set_title("Test Novel")
    book.set_language("en")
    c1 = epub.EpubHtml(title="Ch 1", file_name="c1.xhtml", lang="en")
    c1.content = "<h1>Chapter One</h1><p>It was a bright cold day.</p>"
    c2 = epub.EpubHtml(title="Ch 2", file_name="c2.xhtml", lang="en")
    c2.content = "<h1>Chapter Two</h1><p>The clocks were striking thirteen.</p>"
    book.add_item(c1)
    book.add_item(c2)
    book.toc = (c1, c2)
    book.spine = ["nav", c1, c2]
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book, {})


def _make_font(dest: Path) -> str:
    """Copy a system font. Returns the reason when there is none to copy."""
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            shutil.copyfile(candidate, dest)
            return ""
        except OSError as exc:
            return f"could not copy {candidate}: {exc}"
    return "no system font found on this machine"


def build_samples(folder: Path) -> Samples:
    """Build every sample inside `folder`.  A sample that cannot be built on
    this machine is recorded as missing, with the reason - never faked."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    s = Samples(folder)

    def note(name: str, reason: str) -> None:
        s.missing[name] = reason

    def done(name: str) -> None:
        s.files[name] = folder / name

    # --- images ---
    _make_photo(folder / "photo.jpg")
    done("photo.jpg")
    _make_portrait(folder / "portrait.jpg")
    done("portrait.jpg")

    from PIL import Image, ImageDraw
    Image.new("RGB", (128, 128), (200, 120, 60)).save(folder / "tiny.png")
    done("tiny.png")

    alpha = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
    ImageDraw.Draw(alpha).ellipse((50, 30, 150, 130), fill=(220, 60, 40, 255))
    alpha.save(folder / "alpha.png")
    done("alpha.png")

    Image.open(folder / "photo.jpg").save(folder / "pic.webp")
    done("pic.webp")

    # --- pdf ---
    _make_pdf(folder / "contract.pdf", 3, "Contract")
    done("contract.pdf")
    _make_pdf(folder / "contract2.pdf", 2, "Second contract")
    done("contract2.pdf")
    _make_scan_pdf(folder / "scan.pdf")
    done("scan.pdf")
    _make_big_pdf(folder / "big.pdf")
    done("big.pdf")

    # --- text-ish ---
    (folder / "notes.txt").write_text(
        "Opal sample text.\n\nLine two with unicode: peaches \u2764 oranges \u2764.\n" * 8,
        encoding="utf-8")
    done("notes.txt")
    (folder / "readme.md").write_text(
        "# Opal\n\n## Features\n\n- **Zero-click** conversion\n- Local *AI* tools\n\n"
        "```python\nprint('hi')\n```\n\n| Tool | Speed |\n| --- | --- |\n| Convert | fast |\n",
        encoding="utf-8")
    done("readme.md")
    (folder / "page.html").write_text(
        "<html><body><h1>Title</h1><p>Hello</p></body></html>", encoding="utf-8")
    done("page.html")
    (folder / "app.log").write_text(
        "2026-01-01 INFO started\n2026-01-01 ERROR failed\n", encoding="utf-8")
    done("app.log")
    (folder / "rich.rtf").write_text(
        r"{\rtf1\ansi Hello RTF.\par}", encoding="utf-8")
    done("rich.rtf")
    (folder / "data.csv").write_text(
        "name,price,qty\nApple,1.5,10\nPear,2.5,5\nPlum,3.0,7\n", encoding="utf-8")
    done("data.csv")
    (folder / "data.json").write_text(
        '[{"tool":"convert","speed":"fast"},{"tool":"compress","speed":"medium"}]',
        encoding="utf-8")
    done("data.json")
    (folder / "subs.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello there\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\nSecond line here\n", encoding="utf-8")
    done("subs.srt")
    (folder / "subs.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello there\n", encoding="utf-8")
    done("subs.vtt")

    # A subtitle that matches the video, so the burn tool has something to do.
    (folder / "clip.srt").write_text(
        "1\n00:00:00,500 --> 00:00:01,500\nOpal burns subtitles\n\n"
        "2\n00:00:02,000 --> 00:00:02,900\nRight into the picture\n", encoding="utf-8")
    done("clip.srt")

    # --- office ---
    import docx
    d1 = docx.Document()
    d1.add_heading("Opal Report", 0)
    d1.add_paragraph("This document powers the test-suite.")
    d1.save(str(folder / "report.docx"))
    done("report.docx")

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fruit", "Count"])
    ws.append(["Apple", 10])
    ws.append(["Pear", 5])
    wb.save(str(folder / "sheet.xlsx"))
    done("sheet.xlsx")

    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Opal Deck"
    prs.save(str(folder / "deck.pptx"))
    done("deck.pptx")

    _make_epub(folder / "novel.epub")
    done("novel.epub")

    # --- font ---
    reason = _make_font(folder / "arial.ttf")
    if reason:
        note("arial.ttf", reason)
    else:
        done("arial.ttf")

    # --- archive ---
    with zipfile.ZipFile(folder / "bundle.zip", "w") as z:
        z.write(str(folder / "photo.jpg"), "photo.jpg")
        z.write(str(folder / "notes.txt"), "notes.txt")
    done("bundle.zip")

    # --- certificate ---
    try:
        _make_certificate(folder / "cert.p12")
        done("cert.p12")
    except Exception as exc:
        note("cert.p12", f"{type(exc).__name__}: {exc}")

    # --- media ---
    ff = _ffmpeg()
    if not ff or not os.path.exists(ff):
        why = "no ffmpeg binary on this machine"
        note("clip.mp4", why)
        note("tone.wav", why)
    else:
        if _run_ffmpeg(ff, ["-y", "-f", "lavfi", "-i",
                             "testsrc=size=320x240:rate=15:duration=3",
                             "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                             "-shortest", str(folder / "clip.mp4")]):
            done("clip.mp4")
        else:
            note("clip.mp4", "ffmpeg could not encode the test clip")
        if _run_ffmpeg(ff, ["-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                             str(folder / "tone.wav")]):
            done("tone.wav")
        else:
            note("tone.wav", "ffmpeg could not encode the test tone")

    return s


_SHARED: Samples | None = None


def shared_samples() -> Samples:
    """The sample set for this process, built once and reused.

    Collection and the test body need the same files, so they are built at
    import time and cached rather than rebuilt per fixture.
    """
    global _SHARED
    if _SHARED is None:
        import atexit
        import tempfile
        folder = Path(tempfile.mkdtemp(prefix="opal_samples_"))
        atexit.register(shutil.rmtree, folder, True)
        _SHARED = build_samples(folder)
    return _SHARED


if __name__ == "__main__":
    import tempfile
    out = Path(tempfile.mkdtemp(prefix="opal_samples_"))
    samples = build_samples(out)
    print(f"folder: {out}\n")
    for name in SAMPLE_NAMES:
        if name in samples:
            print(f"  OK     {name:16s} {samples.path(name).stat().st_size:>10d} bytes")
        else:
            print(f"  ABSENT {name:16s} {samples.reason(name)}")
    print(f"\n{len(samples.files)}/{len(SAMPLE_NAMES)} samples built")
