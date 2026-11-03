"""Artifact validation for the Opal test-suite.

`ConversionResult.success` only says the engine did not raise.  It does not
say a usable file came out.  These helpers open the produced file with the
matching reader - PIL for images, PyMuPDF for PDFs, zipfile for Office files,
the `wave` module for audio - so a conversion that writes a broken or empty
file is caught instead of being counted as a pass.
"""
from __future__ import annotations

import csv
import json
import sys
import wave
import zipfile
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
TEXT_SUFFIXES = {".txt", ".md", ".srt", ".vtt", ".html", ".htm", ".log", ".rtf", ".csv"}
MEDIA_SUFFIXES = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"}


def _image(path: Path) -> tuple[bool, str]:
    from PIL import Image
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
            return True, f"{im.format} {im.width}x{im.height}"
    except Exception as exc:
        return False, f"not a readable image: {type(exc).__name__}: {exc}"


def _pdf(path: Path) -> tuple[bool, str]:
    try:
        import fitz
    except Exception as exc:
        return False, f"PyMuPDF is unavailable: {exc}"
    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return False, f"not a readable PDF: {type(exc).__name__}: {exc}"
    try:
        pages = len(doc)
        if pages < 1:
            return False, "PDF has no pages"
        return True, f"{pages} page(s)"
    finally:
        doc.close()


def _zip_part(path: Path, prefix: str, exact: str | None = None) -> tuple[bool, str]:
    try:
        if not zipfile.is_zipfile(path):
            return False, "not a zip container"
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            broken = z.testzip()
    except Exception as exc:
        return False, f"unreadable zip: {type(exc).__name__}: {exc}"
    if broken is not None:
        return False, f"corrupt member inside the archive: {broken}"
    if exact is not None and exact not in names:
        return False, f"{exact} missing from the archive"
    if exact is None and not any(n.startswith(prefix) for n in names):
        return False, f"no {prefix} parts in the archive"
    return True, f"{len(names)} part(s)"


def _epub(path: Path) -> tuple[bool, str]:
    try:
        if not zipfile.is_zipfile(path):
            return False, "not a zip container"
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            mimetype = z.read("mimetype").decode("ascii", "replace") if "mimetype" in names else ""
    except Exception as exc:
        return False, f"unreadable epub: {type(exc).__name__}: {exc}"
    if mimetype.strip() != "application/epub+zip":
        return False, f"mimetype says {mimetype!r}, not application/epub+zip"
    return True, f"{len(names)} part(s)"


def _json(path: Path) -> tuple[bool, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"not valid JSON: {type(exc).__name__}: {exc}"
    return True, f"{type(data).__name__} with {len(data) if hasattr(data, '__len__') else 1} item(s)"


def _csv(path: Path) -> tuple[bool, str]:
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
    except Exception as exc:
        return False, f"not readable as CSV: {type(exc).__name__}: {exc}"
    if len(rows) < 2:
        return False, f"CSV has {len(rows)} row(s), expected a header and at least one record"
    return True, f"{len(rows) - 1} data row(s)"


def _text(path: Path) -> tuple[bool, str]:
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "not UTF-8 text"
    except Exception as exc:
        return False, f"unreadable: {type(exc).__name__}: {exc}"
    if not body.strip():
        return False, "the file is empty"
    return True, f"{len(body)} characters"


def _font(path: Path) -> tuple[bool, str]:
    try:
        from fontTools.ttLib import TTFont
    except Exception as exc:
        return False, f"fontTools is unavailable: {exc}"
    try:
        font = TTFont(str(path), lazy=True)
        tables = list(font.keys())
        font.close()
    except Exception as exc:
        return False, f"not a readable font: {type(exc).__name__}: {exc}"
    return True, f"{len(tables)} table(s)"


def _wav(path: Path) -> tuple[bool, str]:
    try:
        with wave.open(str(path), "rb") as fh:
            frames = fh.getnframes()
            rate = fh.getframerate()
    except Exception as exc:
        return False, f"not a readable WAV: {type(exc).__name__}: {exc}"
    if frames <= 0:
        return False, "the WAV has no audio frames"
    return True, f"{frames} frames at {rate} Hz"


def _video(path: Path) -> tuple[bool, str]:
    try:
        head = path.read_bytes()[:64]
    except Exception as exc:
        return False, f"unreadable: {type(exc).__name__}: {exc}"
    if b"ftyp" in head:
        return True, f"{path.stat().st_size} bytes with an ISO-BMFF container header"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return True, f"{path.stat().st_size} bytes with a Matroska/WebM container header"
    if head[:4] == b"RIFF":
        return True, f"{path.stat().st_size} bytes with a RIFF container header"
    return False, "no known video container header - not a real video file"


def _archive(path: Path) -> tuple[bool, str]:
    try:
        if not zipfile.is_zipfile(path):
            return False, "not a zip container"
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            broken = z.testzip()
    except Exception as exc:
        return False, f"unreadable zip: {type(exc).__name__}: {exc}"
    if broken is not None:
        return False, f"corrupt member inside the archive: {broken}"
    if not names:
        return False, "the archive is empty"
    return True, f"{len(names)} member(s)"


def validate_file(path: Path) -> tuple[bool, str]:
    """Open one produced file and say whether it is genuinely usable."""
    path = Path(path)
    if not path.exists():
        return False, "the file does not exist"
    if path.is_dir():
        return False, "expected a file, found a folder"
    if path.stat().st_size == 0:
        return False, "the file is empty (0 bytes)"

    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return _image(path)
    if suffix == ".pdf":
        return _pdf(path)
    if suffix == ".docx":
        return _zip_part(path, "word/", exact="word/document.xml")
    if suffix == ".xlsx":
        return _zip_part(path, "xl/", exact="xl/workbook.xml")
    if suffix == ".pptx":
        return _zip_part(path, "ppt/")
    if suffix == ".epub":
        return _epub(path)
    if suffix == ".zip":
        return _archive(path)
    if suffix == ".json":
        return _json(path)
    if suffix == ".csv":
        return _csv(path)
    if suffix in (".ttf", ".otf", ".ttc"):
        return _font(path)
    if suffix == ".wav":
        return _wav(path)
    if suffix in MEDIA_SUFFIXES:
        return _video(path)
    if suffix in TEXT_SUFFIXES:
        return _text(path)
    # Unknown suffix: the file must at least hold something.
    return True, f"{path.stat().st_size} bytes"


def validate_path(path: str | Path) -> tuple[bool, str]:
    """Validate a produced artifact, whether it is a file or a folder of files."""
    if not path:
        return False, "the engine reported no output path"
    p = Path(path)
    if not p.exists():
        return False, f"nothing was written to {p}"
    if not p.is_dir():
        return validate_file(p)

    children = [c for c in sorted(p.rglob("*")) if c.is_file()]
    if not children:
        return False, f"the folder {p.name} is empty"
    real = [c for c in children if c.stat().st_size > 0]
    if not real:
        return False, f"every file inside {p.name} is empty"
    broken = []
    for child in real:
        ok, detail = validate_file(child)
        if not ok:
            broken.append(f"{child.name}: {detail}")
    if broken:
        return False, f"{len(broken)} of {len(real)} file(s) are not usable - " + "; ".join(broken[:3])
    return True, f"{len(real)} file(s) in {p.name}"
