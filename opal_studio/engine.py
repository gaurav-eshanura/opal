"""
Opal - Production Conversion & Tools Engine
Plain English: This engine converts single files or batches of files completely on your local computer.
It handles corrupted files, unicode filenames, and protected folders safely without crashing.
"""

import os
import re
import sys
import csv
import io
import time
import json
import html as _html_mod
import hashlib
import shutil
import zipfile
import tarfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageOps, ImageFilter, UnidentifiedImageError

from opal_studio.safepath import safe_path

# FFmpeg path is resolved directly from bundled directory or system PATH

try:
    import pypdf
except Exception:
    pypdf = None

try:
    from send2trash import send2trash
except Exception:
    send2trash = None

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import docx
except Exception:
    docx = None

from opal_studio.config import ConfigManager


def _partial_sibling(dst: Path) -> Path:
    """
    Temp file beside dst used for crash-safe writes.
    The name is built only from dst's final component; any traversal segment is
    rejected and the resolved path must stay inside dst's own directory.
    """
    name = dst.name + ".tan_partial"
    if ".." in Path(name).parts or "/" in name or "\\" in name:
        raise ValueError(f"Unsafe temp file name derived from {dst.name!r}")
    base = dst.parent.resolve()
    candidate = (dst.parent / name).resolve()
    if candidate.parent != base:
        raise ValueError("Temp file escaped the output directory")
    return candidate


def _html_escape(text: str) -> str:
    return _html_mod.escape(text or "")


def _srt_to_vtt(text: str) -> str:
    body = "\n".join(ln.lstrip("\ufeff") for ln in text.splitlines())
    return "WEBVTT\n\n" + body.replace(",", ".", 0) + "\n"


def _vtt_to_srt(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.strip().upper().startswith("WEBVTT")]
    return "\n".join(lines) + "\n"


def _emu_to_pt(emu, page_dim: float, slide_dim) -> float:
    if emu is None or not slide_dim:
        return 8.0
    try:
        return max(0.0, float(emu) / float(slide_dim) * page_dim)
    except (TypeError, ValueError):
        return 8.0


def _apply_vignette(img):
    """Soft dark corner shading, keeping the alpha channel intact."""
    from PIL import ImageDraw
    ratio = max(img.size) / 800.0
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    w, h = img.size
    grad = 380
    d.rounded_rectangle([-int(w * 0.25), -int(h * 0.28), int(w * 1.25), int(h * 1.28)],
                        radius=int(min(w, h) * 0.55), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.09))
    dark = Image.new(img.mode, img.size, tuple([12, 12, 18] + ([255] if "A" in img.mode else [])))
    out = Image.composite(img.convert(img.mode), dark.convert(img.mode), mask)
    return out


def _text_to_pdf_fit(text: str, dest: str, title: str = "") -> None:
    """Typesets plain text into a clean PDF with word wrapping and proper pagination."""
    import fitz
    font_path = _system_font_path()
    # Indian scripts (Devanagari, Tamil, Telugu, Bengali, Kannada, Malayalam,
    # Gujarati, Gurmukhi, Arabic, ...) are not in Segoe UI, so pick a font that
    # actually has the glyphs - otherwise the PDF comes out with blank boxes.
    if _needs_unicode_font(text):
        font_path = _unicode_font_path() or font_path
    doc = fitz.open()
    measure_font = None
    if font_path:
        try:
            measure_font = fitz.Font(fontfile=font_path)
        except Exception:
            measure_font = None
    font_kw = {"fontname": "F0", "fontfile": font_path} if font_path else {"fontname": "helv"}

    def _width(ln: str) -> float:
        if measure_font is not None:
            try:
                return measure_font.text_length(ln, fontsize=11)
            except Exception:
                pass
        return fitz.get_text_length(ln, fontname="helv", fontsize=11)

    page = None
    cursor_y = 66.0

    def new_page_() -> None:
        nonlocal page, cursor_y
        page = doc.new_page(width=595, height=842)
        cursor_y = 66.0

    for para in text.split("\n"):
        words = para.split()
        line = ""
        lines_out: List[str] = []
        for w in words:
            candidate = (line + " " + w).strip()
            if _width(candidate) > 495 and line:
                lines_out.append(line)
                line = w
            else:
                line = candidate
        if line:
            lines_out.append(line)
        for ln in lines_out:
            if page is None or cursor_y > 790:
                new_page_()
                if title and page.number == 0:
                    page.insert_text((50, 46), title, fontsize=8,
                                     color=_c((140, 140, 150)), **font_kw)
            page.insert_text((50, cursor_y), ln, fontsize=11,
                             color=_c((22, 23, 34)), **font_kw)
            cursor_y += 15
    if page is None:  # empty text still yields one titled page
        new_page_()
        if title:
            page.insert_text((50, 46), title, fontsize=8,
                             color=_c((140, 140, 150)), **font_kw)
    doc.save(dest, deflate=True)
    doc.close()


def _system_font_path() -> Optional[str]:
    for name in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        cand = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
        if cand.exists():
            return str(cand)
    return None


# Scripts that need a dedicated font on Windows.
_INDIC_RANGES = (
    (0x0900, 0x097F),   # Devanagari (Hindi, Marathi, Nepali, Sanskrit)
    (0x0980, 0x09FF),   # Bengali
    (0x0A00, 0x0A7F),   # Gurmukhi (Punjabi)
    (0x0A80, 0x0AFF),   # Gujarati
    (0x0B00, 0x0B7F),   # Oriya
    (0x0B80, 0x0BFF),   # Tamil
    (0x0C00, 0x0C7F),   # Telugu
    (0x0C80, 0x0CFF),   # Kannada
    (0x0D00, 0x0D7F),   # Malayalam
    (0x0D80, 0x0DFF),   # Sinhala
    (0x0E00, 0x0E7F),   # Thai
    (0x0600, 0x06FF),   # Arabic
    (0x0E00, 0x0E7F),   # Lao / Khmer ranges nearby
    (0x1000, 0x109F),   # Myanmar
    (0x0370, 0x03FF),   # Greek
    (0x0400, 0x04FF),   # Cyrillic
    (0x0590, 0x05FF),   # Hebrew
)


def _needs_unicode_font(text: str) -> bool:
    """True when the text contains glyphs that the default Latin font cannot draw."""
    for ch in text:
        code = ord(ch)
        if code < 0x0100:
            continue
        if code in (0x00A0,):
            continue
        for low, high in _INDIC_RANGES:
            if low <= code <= high:
                return True
        if 0x2000 <= code <= 0x206F:      # general punctuation
            continue
        if 0x20B9 in (code,) or 0x20BA in (code,):
            return True
        if code >= 0x2500:                 # box drawing, symbols, emoji
            return True
    return False


def _parse_subtitle_cues(path: Path) -> List[Tuple[float, float, str]]:
    """Reads the cues out of an SRT or WebVTT file.

    Returns a list of (start seconds, end seconds, text).
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    stamp = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
        r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")

    cues: List[Tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        match = None
        for index, line in enumerate(lines):
            match = stamp.search(line)
            if match:
                text_lines = lines[index + 1:]
                break
        if not match:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()

        def _seconds(h, m, s, ms):
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0

        start = _seconds(h1, m1, s1, ms1)
        end = _seconds(h2, m2, s2, ms2)
        text = "\n".join(text_lines).strip()
        if text:
            cues.append((start, end, text))
    return cues


def _render_subtitle_png(path: Path, text: str, width: int, height: int) -> None:
    """Draws one subtitle cue onto a transparent picture the size of the frame."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (max(2, width), max(2, height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    font = None
    font_path = _unicode_font_path()
    if font_path:
        try:
            font = ImageFont.truetype(font_path, max(18, int(height * 0.055)))
        except Exception:
            font = None
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    try:
        left, top, right, bottom = draw.textbbox((0, 0), "Ag", font=font)
        line_height = max(20, (bottom - top) + max(6, int(height * 0.012)))
    except Exception:
        line_height = max(20, int(height * 0.06))

    # Wrap the text so it fits the frame.
    max_width = int(width * 0.92)
    lines: List[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            try:
                w = draw.textlength(candidate, font=font)
            except Exception:
                w = len(candidate) * (line_height // 2)
            if w <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)

    block_height = line_height * len(lines)
    y = height - int(height * 0.06) - block_height
    bar_top = max(0, y - int(line_height * 0.25))
    draw.rectangle([0, bar_top, width, height], fill=(0, 0, 0, 170))

    for line in lines:
        try:
            w = draw.textlength(line, font=font)
        except Exception:
            w = len(line) * (line_height // 2)
        x = max(0, (width - w) / 2)
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    image.save(path, "PNG")


def _unicode_font_path() -> Optional[str]:
    """Finds a font that covers Indian and other non-Latin scripts.

    The font has to exist on the machine the app is running on, and each
    platform names its Indic font differently. Without this, Hindi text turns
    into a row of dots on a machine that has no Nirmala UI.
    """
    import sys

    if sys.platform.startswith("win"):
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        preferred = ["Nirmala.ttc", "Nirmala.ttf", "Kokila.ttf", "Mangal.ttf",
                     "Sanskrit2003.ttf", "Vrinda.ttf", "IskoolaPota.ttf",
                     "Ebrima.ttf", "arialuni.ttf"]
    elif sys.platform == "darwin":
        fonts_dir = Path("/System/Library/Fonts")
        preferred = ["DevanagariSangamMN.ttc", "Kohinoor.ttc",
                     "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
                     "/System/Library/Fonts/Supplemental/Kohinoor Devanagari.ttc",
                     "/Library/Fonts/Arial Unicode.ttf"]
    else:
        fonts_dir = Path("/usr/share/fonts")
        preferred = [
            "truetype/noto/NotoSansDevanagari-Regular.ttf",
            "truetype/lohit-devanagari/Lohit-Devanagari.ttf",
            "truetype/noto/NotoSansDevanagari[wdth,wght].ttf",
            "opentype/noto/NotoSansDevanagari-Regular.ttf",
            "truetype/dejavu/DejaVuSans.ttf",
        ]

    for name in preferred:
        cand = Path(name) if os.path.isabs(name) else fonts_dir / name
        if cand.exists():
            return str(cand)

    # Last resort: look through the system font folders for anything that
    # mentions Devanagari in its name.
    for root in (fonts_dir, Path("/usr/share/fonts"), Path("/Library/Fonts"),
                 Path.home() / ".fonts", Path.home() / ".local/share/fonts"):
        if not root.exists():
            continue
        try:
            for found in sorted(root.rglob("*")):
                if found.is_file() and "devanagari" in found.name.lower():
                    return str(found)
        except OSError:
            continue
    return None


def _c(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """PyMuPDF wants colors as 0-1 floats."""
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


class ConversionResult:
    def __init__(self, success: bool, output_path: Optional[str] = None, message: str = "", saved_bytes: int = 0):
        self.success = success
        self.output_path = output_path
        self.message = message
        self.saved_bytes = saved_bytes


class BatchConversionResult:
    def __init__(self, total: int, succeeded: int, failed: int, outputs: List[str], saved_bytes: int, message: str):
        self.total = total
        self.succeeded = succeeded
        self.failed = failed
        self.outputs = outputs
        self.saved_bytes = saved_bytes
        self.message = message


class OpalEngine:
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".ico", ".gif", ".avif", ".svg", ".heic", ".heif"}
    AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aiff", ".wma", ".aac"}
    VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv"}
    PDF_EXTS = {".pdf"}
    DOC_EXTS = {".txt", ".md", ".json", ".csv", ".docx", ".html", ".epub", ".srt", ".vtt",
                ".xlsx", ".xls", ".pptx", ".ppt", ".rtf", ".log"}
    FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
    ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".tgz"}

    @classmethod
    def get_file_category(cls, file_paths: List[str]) -> str:
        """Determines category for a single file or a batch of files."""
        if not file_paths:
            return "generic"
        categories = set()
        for fp in file_paths:
            ext = Path(fp).suffix.lower()
            if ext in cls.IMAGE_EXTS:
                categories.add("image")
            elif ext in cls.AUDIO_EXTS:
                categories.add("audio")
            elif ext in cls.VIDEO_EXTS:
                categories.add("video")
            elif ext in cls.PDF_EXTS:
                categories.add("pdf")
            elif ext in cls.FONT_EXTS:
                categories.add("font")
            elif ext in cls.DOC_EXTS:
                categories.add("document")
            elif ext in cls.ARCHIVE_EXTS:
                categories.add("archive")
            else:
                categories.add("generic")

        if len(categories) == 1:
            return categories.pop()
        return "mixed"

    @classmethod
    def get_options_for_file(cls, file_path: str, mode: str) -> List[Dict[str, str]]:
        return cls.get_options_for_files([file_path], mode)

    @classmethod
    def execute(cls, file_path: str, action_id: str) -> ConversionResult:
        return cls.execute_single(file_path, action_id)

    @classmethod
    def get_options_for_files(cls, file_paths: List[str], mode: str) -> List[Dict[str, str]]:
        if not file_paths:
            return []
        category = cls.get_file_category(file_paths)
        is_batch = len(file_paths) > 1

        if mode == "convert":
            return cls._get_conversion_options(category, is_batch, file_paths)
        elif mode == "tools":
            return cls._get_tools_options(category, is_batch, file_paths)
        else:
            return cls._get_action_options(file_paths)

    @classmethod
    def _get_conversion_options(cls, category: str, is_batch: bool, file_paths: List[str] = None) -> List[Dict[str, str]]:
        if category == "image":
            return [
                {"id": "webp", "label": "WebP", "desc": "Modern efficient web image"},
                {"id": "png", "label": "PNG", "desc": "Clean transparent image"},
                {"id": "jpg", "label": "JPG", "desc": "Standard universal photo"},
                {"id": "wa_sticker", "label": "WA Sticker", "desc": "512x512 transparent WebP sticker"},
                {"id": "pdf", "label": "PDF", "desc": "Export as PDF page" if not is_batch else "Combine into single PDF"},
                {"id": "ico", "label": "ICO", "desc": "Application icon (multi-size)"},
            ]
        elif category == "audio":
            return [
                {"id": "mp3", "label": "MP3", "desc": "Universal audio standard (320k)"},
                {"id": "wav", "label": "WAV", "desc": "Uncompressed studio quality"},
                {"id": "m4a", "label": "M4A", "desc": "Apple AAC high fidelity audio"},
                {"id": "flac", "label": "FLAC", "desc": "Lossless audio master"},
                {"id": "ogg", "label": "OGG", "desc": "Lightweight open audio container"},
            ]
        elif category == "video":
            return [
                {"id": "mp4", "label": "MP4", "desc": "Universal H.264 video"},
                {"id": "gif", "label": "GIF", "desc": "Animated shareable clip"},
                {"id": "webm", "label": "WebM", "desc": "High efficiency web video"},
                {"id": "mp3", "label": "MP3 Audio", "desc": "Extract sound track"},
                {"id": "mkv", "label": "MKV", "desc": "High quality video container"},
            ]
        elif category == "pdf":
            opts = [
                {"id": "docx", "label": "Word (DOCX)", "desc": "Convert PDF into editable Word document"},
                {"id": "pptx", "label": "PowerPoint", "desc": "Each page becomes an editable slide image"},
                {"id": "png_pages", "label": "PNG Pages", "desc": "Extract all pages as crisp 300 DPI images"},
                {"id": "extract_text", "label": "Extract Text", "desc": "Save clean readable text file"},
                {"id": "html", "label": "HTML", "desc": "Export text-structured web page"},
                {"id": "epub", "label": "EPUB", "desc": "Rebuild as an e-book file"},
                {"id": "split_pdf", "label": "Split Pages", "desc": "Save every page as individual PDF"},
            ]
            if is_batch:
                opts.insert(0, {"id": "merge_pdf", "label": "Merge PDFs", "desc": "Combine all selected PDFs into one document"})
            return opts
        elif category == "font":
            return [
                {"id": "font_report", "label": "Font Report", "desc": "Full family, style, licensing report"},
                {"id": "png_preview", "label": "Preview PNG", "desc": "Render specimen sheet as PNG"},
            ]
        elif category == "document":
            opts = [
                {"id": "pdf", "label": "PDF", "desc": "Export as high quality PDF document"},
                {"id": "extract_text", "label": "Extract Text", "desc": "Strip formatting to clean text file"},
            ]
            exts = {Path(fp).suffix.lower() for fp in (file_paths or [])}
            if ".json" in exts:
                opts.append({"id": "format_json", "label": "Format JSON", "desc": "Prettify and indent JSON"})
                opts.append({"id": "csv", "label": "CSV", "desc": "Flatten JSON records to CSV table"})
            if ".csv" in exts:
                opts.append({"id": "xlsx", "label": "XLSX", "desc": "Build a formatted Excel workbook"})
                opts.append({"id": "json", "label": "JSON", "desc": "Convert CSV rows to JSON records"})
            if any(e in (".xlsx", ".xls") for e in exts):
                opts.append({"id": "csv", "label": "CSV Table", "desc": "Export spreadsheet sheet as CSV"})
            if ".epub" in exts:
                opts += [
                    {"id": "extract_text", "label": "EPUB → TXT", "desc": "Extract readable book text"},
                    {"id": "html", "label": "EPUB → HTML", "desc": "Convert book chapters to HTML"},
                ]
            if any(e in (".srt", ".vtt") for e in exts):
                opts += [
                    {"id": "vtt", "label": "VTT / SRT", "desc": "Convert subtitle format"},
                    {"id": "extract_text", "label": "Dialogue TXT", "desc": "Extract spoken lines only"},
                ]
            if ".md" in exts:
                opts += [
                    {"id": "html", "label": "HTML", "desc": "Render markdown to styled web page"},
                    {"id": "docx", "label": "DOCX", "desc": "Convert markdown to Word"},
                ]
            if ".pptx" in exts or ".ppt" in exts:
                opts += [
                    {"id": "pdf", "label": "PPT → PDF", "desc": "Render slides to PDF pages"},
                    {"id": "extract_text", "label": "Slides → TXT", "desc": "Extract speaker text"},
                ]
            return opts
        elif category == "archive":
            return [
                {"id": "extract_archive", "label": "Extract", "desc": "Unpack archive contents here"},
            ]

        # Mixed / Generic
        return [
            {"id": "zip_bundle", "label": "ZIP Archive", "desc": "Compress files into single ZIP"},
        ]

    @classmethod
    def _get_tools_options(cls, category: str, is_batch: bool,
                           file_paths: Optional[List[str]] = None) -> List[Dict[str, str]]:
        if category == "image":
            return [
                {"id": "remove_bg", "label": "Remove BG", "desc": "AI removes the background - transparent PNG"},
                {"id": "face_blur", "label": "Blur Faces", "desc": "Detect faces and blur them for privacy"},
                {"id": "remove_object", "label": "Remove Object", "desc": "Erase an unwanted object from a photo"},
                {"id": "beautify", "label": "Beautify", "desc": "One-tap portrait fix for old photos"},
                {"id": "meme", "label": "Meme", "desc": "Add a caption above and below the photo"},
                {"id": "image_ocr", "label": "OCR Photo", "desc": "Read the text in a photo into a PDF"},
                {"id": "aadhaar_photo", "label": "ID Photo", "desc": "Aadhaar/passport size 413x599 px"},
                {"id": "white_bg_photo", "label": "White BG Photo", "desc": "Cut-out on a clean white background"},
                {"id": "stamp_photo", "label": "Stamp Photo", "desc": "50x40 mm photo for forms"},
                {"id": "print_4x6", "label": "Print 4R", "desc": "4R photo paper (4x6 in, 300 DPI)"},
                {"id": "print_6x4", "label": "Print 6R", "desc": "6R photo paper (6x4 in, 300 DPI)"},
                {"id": "print_5x7", "label": "Print 5R", "desc": "5R photo paper (5x7 in, 300 DPI)"},
                {"id": "photo_whatsapp", "label": "WhatsApp", "desc": "Small, sharp photo ready to share"},
                {"id": "bg_cutout_blur", "label": "BG → Blur", "desc": "AI cutout over blurred original"},
                {"id": "upscale_2x", "label": "Upscale 2x", "desc": "Real-ESRGAN AI detail restoration"},
                {"id": "upscale_4x", "label": "Upscale 4x", "desc": "Real-ESRGAN 4x (best for old photos)"},
                {"id": "enhance_auto", "label": "Auto-Enhance", "desc": "Instant contrast, color and clarity fix"},
                {"id": "compress_image", "label": "Compress", "desc": "Shrink file size without losing visible clarity"},
                {"id": "fit_25mb", "label": "Fit 25MB", "desc": "Target under 25MB Discord limit"},
                {"id": "fit_10mb", "label": "Fit 10MB", "desc": "Target under 10MB email limit"},
                {"id": "add_border", "label": "Add Border", "desc": "White border for printing photos"},
                {"id": "social_portrait", "label": "Post 4:5", "desc": "Fit 1080x1350 portrait post (blurred fill)"},
                {"id": "social_banner", "label": "Banner", "desc": "Fit 1584x396 channel banner (blurred fill)"},
                {"id": "crop_9_16", "label": "Shorts 9:16", "desc": "Crop to 9:16 vertical ratio"},
                {"id": "crop_square", "label": "Crop Square", "desc": "Center-crop to 1:1 ratio"},
                {"id": "watermark_image", "label": "Watermark", "desc": "Stamp diagonal text watermark"},
                {"id": "strip_metadata", "label": "Strip EXIF", "desc": "Remove private GPS, camera and device data"},
                {"id": "exif_report", "label": "EXIF Report", "desc": "Show hidden camera, GPS and device data"},
                {"id": "color_palette", "label": "Palette", "desc": "Extract dominant colors from image"},
            ]
            if is_batch:
                opts.insert(0, {"id": "contact_sheet", "label": "Contact Sheet",
                                "desc": f"Combine {len(file_paths)} images into one grid"})
        elif category in ("video", "audio"):
            return [
                {"id": "compress_media", "label": "Compress", "desc": "Reduce file size for messaging & sharing"},
                {"id": "fit_25mb", "label": "Fit 25MB", "desc": "Target under 25MB Discord limit"},
                {"id": "fit_10mb", "label": "Fit 10MB", "desc": "Target under 10MB email limit"},
                {"id": "crop_9_16", "label": "Shorts 9:16", "desc": "Crop video to 1080x1920 vertical format"},
                {"id": "trim_30s", "label": "Trim 30s", "desc": "Keep first 30 seconds"},
                {"id": "video_720p", "label": "Make 720p", "desc": "Resize to 720p H.264"},
                {"id": "video_frames", "label": "All Frames", "desc": "Export every frame as images"},
                {"id": "video_thumbnails", "label": "Thumb Grid", "desc": "9-frame contact sheet image"},
                {"id": "mute_video", "label": "Mute Audio", "desc": "Strip sound track completely"},
                {"id": "burn_subtitles", "label": "Burn Subs", "desc": "Permanently embed matching .srt subtitles"},
            ]
        elif category == "pdf":
            opts = [
                {"id": "pdf_whatsapp", "label": "WhatsApp PDF", "desc": "Shrink under 1 MB to send on WhatsApp"},
                {"id": "pdf_a4", "label": "Fit A4", "desc": "Fit every page onto A4 paper"},
                {"id": "repair_pdf", "label": "Repair PDF", "desc": "Rebuild a broken or damaged PDF"},
                {"id": "autocrop_pdf", "label": "Trim Margins", "desc": "Cut the white scanner margins away"},
                {"id": "grayscale_pdf", "label": "B&W PDF", "desc": "Photocopy-style black and white PDF"},
                {"id": "pdf_summary", "label": "Summarise", "desc": "Key points extracted offline"},
                {"id": "pdf_remove_blank", "label": "Remove Blank Pages", "desc": "Drop the empty pages a scanner leaves behind"},
                {"id": "compress_pdf", "label": "Compress PDF", "desc": "Optimize images and stream sizes"},
                {"id": "rotate_90", "label": "Rotate 90°", "desc": "Rotate pages clockwise"},
                {"id": "pdf_watermark", "label": "Watermark", "desc": "Stamp diagonal text watermark"},
                {"id": "pdf_pagenum", "label": "Page Numbers", "desc": "Add footer page numbers"},
                {"id": "pdf_flatten", "label": "Flatten", "desc": "Lock annotations & signatures in place"},
                {"id": "pdf_ocr", "label": "Make Searchable", "desc": "OCR scan pages with offline AI"},
                {"id": "pdf_metadata_clean", "label": "Clean Metadata", "desc": "Erase author, location, hidden data"},
                {"id": "split_pdf", "label": "Split Pages", "desc": "Save every page as individual PDF"},
            ]
            if is_batch:
                opts.insert(0, {"id": "merge_pdf", "label": "Merge PDFs", "desc": "Combine all selected PDFs into one document"})
            return opts
        return [
            {"id": "quick_zip", "label": "Quick ZIP", "desc": "Compress into standard ZIP file"},
            {"id": "hash_file", "label": "Checksums", "desc": "MD5 / SHA1 / SHA256 to clipboard & file"},
        ]

    @classmethod
    def _get_action_options(cls, file_paths: List[str]) -> List[Dict[str, str]]:
        is_batch = len(file_paths) > 1
        return [
            {"id": "float", "label": "Float", "desc": "Pin floating studio on top of your screen"},
            {"id": "open_with", "label": "Open", "desc": "Open with its default app"},
            {"id": "copy_path", "label": "Copy Path" if not is_batch else "Copy Paths", "desc": "Copy exact path(s) to clipboard"},
            {"id": "copy_file", "label": "Copy", "desc": "Copy to Downloads for pasting elsewhere"},
            {"id": "show_explorer", "label": "Show in Folder", "desc": "Reveal in File Explorer"},
            {"id": "open_terminal", "label": "PowerShell", "desc": "Open PowerShell in this folder"},
            {"id": "duplicate", "label": "Duplicate", "desc": "Create safe backup copies"},
            {"id": "hash_file", "label": "Checksums", "desc": "MD5 / SHA1 / SHA256 sums"},
            {"id": "trash", "label": "Recycle Bin", "desc": "Safely send to Windows Recycle Bin"},
        ]

    # --- EXECUTION & BATCH ORCHESTRATION ---

    @classmethod
    def execute_batch(cls, file_paths: List[str], action_id: str,
                      options: Optional[Dict[str, Any]] = None) -> BatchConversionResult:
        options = options or {}
        if not file_paths:
            return BatchConversionResult(0, 0, 0, [], 0, "No files specified.")

        # Special case: multi-image contact sheet
        if action_id == "contact_sheet" and len(file_paths) > 1:
            res = cls._contact_sheet(file_paths, options)
            return BatchConversionResult(
                len(file_paths), len(file_paths) if res.success else 0,
                0 if res.success else len(file_paths),
                [res.output_path] if res.output_path else [], res.saved_bytes, res.message)

        # Special case: multi-image to single PDF
        if action_id == "pdf" and len(file_paths) > 1 and cls.get_file_category(file_paths) == "image":
            res = cls._combine_images_to_pdf(file_paths)
            return BatchConversionResult(
                len(file_paths),
                len(file_paths) if res.success else 0,
                0 if res.success else len(file_paths),
                [res.output_path] if res.output_path else [],
                res.saved_bytes,
                res.message
            )

        # Special case: ZIP bundle
        if action_id == "zip_bundle":
            res = cls._bundle_to_zip(file_paths)
            return BatchConversionResult(
                len(file_paths),
                len(file_paths) if res.success else 0,
                0 if res.success else len(file_paths),
                [res.output_path] if res.output_path else [],
                res.saved_bytes,
                res.message
            )

        # Special case: Multi-PDF Merge
        if action_id == "merge_pdf" and len(file_paths) > 1:
            res = cls._merge_pdfs(file_paths)
            return BatchConversionResult(
                len(file_paths),
                len(file_paths) if res.success else 0,
                0 if res.success else len(file_paths),
                [res.output_path] if res.output_path else [],
                res.saved_bytes,
                res.message
            )

        succeeded = 0
        failed = 0
        outputs = []
        total_saved = 0

        for fp in file_paths:
            single_res = cls.execute_single(fp, action_id, options)
            if single_res.success:
                succeeded += 1
                if single_res.output_path:
                    outputs.append(single_res.output_path)
                total_saved += single_res.saved_bytes
                # Log to history
                ConfigManager.add_history_entry(
                    Path(fp).name,
                    Path(single_res.output_path).name if single_res.output_path else "action",
                    action_id,
                    single_res.output_path or fp,
                    single_res.saved_bytes
                )
            else:
                failed += 1

        msg = f"Processed {succeeded} of {len(file_paths)} files successfully."
        if failed > 0:
            msg += f" ({failed} failed)"
        return BatchConversionResult(len(file_paths), succeeded, failed, outputs, total_saved, msg)

    @classmethod
    def execute_single(cls, file_path: str, action_id: str, options: Optional[Dict[str, Any]] = None) -> ConversionResult:
        result = cls._execute_single_inner(file_path, action_id, options or {})
        if result.success and result.output_path and result.output_path != str(Path(file_path)):
            # Honour "keep original dates" so converted files sort like their sources.
            try:
                cfg = ConfigManager.load_config()
                if cfg.get("keep_original_dates", True):
                    out = Path(result.output_path)
                    if out.is_file():
                        shutil.copystat(Path(file_path).resolve(), out)
            except Exception:
                pass
        return result

    @classmethod
    def _execute_single_inner(cls, file_path: str, action_id: str, options: Dict[str, Any]) -> ConversionResult:
        try:
            src = Path(file_path).resolve()
            if not src.exists():
                return ConversionResult(False, message="Source file does not exist.")

            cat = cls.get_file_category([str(src)])

            # Zero-byte check
            if src.stat().st_size == 0 and action_id not in ("trash", "copy_path", "show_explorer", "open_terminal"):
                return ConversionResult(False, message="File is empty (0 bytes).")

            # Route actions
            if action_id == "float":
                return cls._action_float(src)
            if action_id == "copy_path":
                return cls._action_copy_path(src)
            if action_id == "show_explorer":
                return cls._action_show_explorer(src)
            if action_id == "open_terminal":
                return cls._action_open_terminal(src)
            if action_id == "duplicate":
                return cls._action_duplicate(src)
            if action_id == "trash":
                return cls._action_trash(src)

            # Route target size compression
            if action_id == "fit_25mb":
                return cls._compress_to_target_size(src, 25.0)
            if action_id == "fit_10mb":
                return cls._compress_to_target_size(src, 10.0)

            # Route social and workflow presets
            if action_id == "wa_sticker":
                return cls._convert_wa_sticker(src)
            if action_id == "crop_9_16":
                return cls._crop_9_16(src)

            # Route image conversions
            if action_id in ("png", "jpg", "jpeg", "webp", "bmp", "tiff", "ico", "pdf") and cls.get_file_category([str(src)]) == "image":
                return cls._convert_image(src, action_id)

            # Route image tools
            if action_id == "remove_bg":
                return cls._remove_background(src, bg_mode="transparent", options=options)
            if action_id == "compress_image":
                return cls._compress_image(src)
            if action_id == "resize_50":
                return cls._resize_image(src, 0.5)
            if action_id == "crop_square":
                return cls._crop_square(src)
            if action_id == "crop_16_9":
                return cls._crop_16_9(src)
            if action_id == "invert":
                return cls._invert_image(src)
            if action_id == "strip_metadata":
                return cls._strip_image_metadata(src)
            if action_id == "grayscale":
                return cls._grayscale_image(src)

            # Route media conversions
            if action_id in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac", "aiff", "wma",
                             "mp4", "webm", "mkv", "gif", "avi", "mov"):
                return cls._convert_media(src, action_id)
            if action_id == "compress_media":
                return cls._compress_media(src)
            if action_id == "trim_30s":
                return cls._trim_media(src, 30)
            if action_id == "mute_video":
                return cls._mute_video(src)

            # Route PDF tools & conversions
            if action_id == "docx" and cat == "pdf":
                return cls._convert_pdf_to_docx(src)
            if action_id == "compress_pdf":
                return cls._pdf_compress(src)
            if action_id == "png_pages":
                return cls._pdf_extract_png_pages(src)
            if action_id == "extract_text":
                return cls._convert_document_to_text(src)
            if action_id == "split_pdf":
                return cls._pdf_split_pages(src)
            if action_id == "rotate_90":
                return cls._pdf_rotate(src, 90)

            # Route documents & spreadsheets
            if action_id == "pdf" and cat == "document":
                return cls._convert_document_to_pdf(src)
            if action_id == "csv":
                return cls._convert_excel_to_csv(src)
            if action_id == "extract_archive":
                return cls._extract_archive(src)
            if action_id == "format_json":
                return cls._format_json(src)
            if action_id == "quick_zip":
                return cls._bundle_to_zip([str(src)])

            # Extended toolkit routing
            extended = cls._route_extended(src, cat, action_id, options)
            if extended is not None:
                return extended

            return ConversionResult(False, message=f"Operation '{action_id}' not supported.")
        except Exception as e:
            return ConversionResult(False, message=f"Failed: {str(e)}")

    # ------------------------------------------------------------------
    # EXTENDED TOOLKIT ROUTER (handles everything added beyond v1.0)
    # ------------------------------------------------------------------

    @classmethod
    def _route_extended(cls, src: Path, cat: str, action_id: str,
                        options: Dict[str, Any]) -> Optional[ConversionResult]:
        if action_id == "open_with":
            return cls._action_open_with(src)
        if action_id == "copy_file":
            return cls._action_copy_file(src)
        if action_id == "hash_file":
            return cls._hash_files([str(src)])

        # --- image tools ---
        if action_id in ("remove_bg", "bg_cutout_blur", "bg_cutout_white", "bg_cutout_black"):
            bg_mode = "blur" if action_id == "bg_cutout_blur" else (
                "white" if action_id == "bg_cutout_white" else (
                "black" if action_id == "bg_cutout_black" else "transparent"))
            return cls._remove_background(src, bg_mode=bg_mode, options=options)
        if action_id in ("upscale_2x", "upscale_4x"):
            factor = 2 if action_id.endswith("2x") else 4
            return cls._upscale_image(src, factor, options)
        if action_id == "enhance_auto":
            return cls._enhance_image(src, "auto")
        if action_id == "enhance_vivid":
            return cls._enhance_image(src, "vivid")
        if action_id in ("filter_blur", "filter_pixelate", "filter_sepia", "filter_vignette"):
            return cls._image_filter(src, action_id)
        if action_id == "watermark_image":
            return cls._watermark_image(src, options)
        if action_id in ("social_portrait", "social_banner", "social_landscape"):
            return cls._social_fit(src, action_id)
        if action_id == "add_padding":
            return cls._add_padding(src, options)
        if action_id == "color_palette":
            return cls._color_palette(src)
        if action_id == "exif_report":
            return cls._exif_report(src)
        if action_id == "qr_code":
            return cls._qr_code(src, options)
        if action_id in ("rotate_left", "rotate_right", "flip_h", "flip_v"):
            return cls._rotate_flip_image(src, action_id)
        if action_id == "contact_sheet":
            return cls._contact_sheet([str(src)], options)

        # --- print-shop / everyday document sizes ---
        if action_id == "aadhaar_photo":
            return cls._resize_photo_spec(src, 413, 599, "aadhaar")
        if action_id == "passport_photo":
            return cls._resize_photo_spec(src, 413, 599, "passport")
        if action_id == "print_4x6":
            return cls._print_size(src, 4, 6, 300, "4R")
        if action_id == "print_5x7":
            return cls._print_size(src, 5, 7, 300, "5R")
        if action_id == "print_6x4":
            return cls._print_size(src, 6, 4, 300, "6R")
        if action_id == "print_8x10":
            return cls._print_size(src, 8, 10, 300, "8R")
        if action_id == "photo_whatsapp":
            return cls._whatsapp_image(src, options)
        if action_id == "pdf_whatsapp":
            return cls._pdf_target_size(src, float(options.get("target_mb", 1.0)))
        if action_id == "pdf_a4":
            return cls._pdf_to_a4(src)
        if action_id == "add_border":
            return cls._add_border(src, options)
        if action_id == "face_blur":
            return cls._face_blur(src, options)
        if action_id == "remove_object":
            return cls._remove_object(src, options)
        if action_id == "meme":
            return cls._meme(src, options)
        if action_id == "beautify":
            return cls._beautify(src, options)
        if action_id == "liquid_resize":
            return cls._liquid_resize(src, options)
        if action_id == "image_ocr":
            return cls._image_ocr(src, options)
        if action_id == "repair_pdf":
            return cls._repair_pdf(src, options)
        if action_id == "autocrop_pdf":
            return cls._autocrop_pdf(src, options)
        if action_id == "grayscale_pdf":
            return cls._grayscale_pdf(src, options)
        if action_id == "pdf_summary":
            return cls._pdf_summary(src, options)
        if action_id == "stamp_photo":
            return cls._stamp_photo(src, options)
        if action_id == "white_bg_photo":
            return cls._white_bg_photo(src, options)
        if action_id == "join_photos":
            return cls._join_photos(src, options)
        if action_id == "pdf_dsc_sign":
            return cls._pdf_dsc_sign(src, options)
        if action_id == "pdf_remove_blank":
            return cls._pdf_remove_blank_pages(src, options)
        if action_id == "favicon_set":
            return cls._favicon_set(src)
        if action_id == "optimize_web":
            return cls._optimize_web(src)

        # --- pdf tools that need the toolkit ---
        if action_id == "pdf_watermark":
            return cls._pdf_action(src, "watermark", options)
        if action_id == "pdf_pagenum":
            return cls._pdf_action(src, "pagenum", options)
        if action_id == "pdf_flatten":
            return cls._pdf_action(src, "flatten", options)
        if action_id == "pdf_metadata_clean":
            return cls._pdf_action(src, "meta_clean", options)
        if action_id == "pdf_ocr":
            return cls._pdf_action(src, "ocr", options)
        if action_id == "pdf_reverse":
            return cls._pdf_action(src, "reverse", options)

        # --- pdf conversions via toolkit ---
        if action_id == "pptx" and cat == "pdf":
            return cls._pdf_to_pptx(src, options)
        if action_id == "html" and cat == "pdf":
            return cls._pdf_to_html(src, options)
        if action_id == "epub" and cat == "pdf":
            return cls._pdf_to_epub(src, options)
        if action_id == "jpg" and cat == "pdf":
            return cls._pdf_pages_to_images(src, "jpg", options)

        # --- documents & ebooks ---
        if action_id == "epub_txt":
            return cls._epub_to_text(src)
        if action_id == "epub_html":
            return cls._epub_to_html(src)
        if action_id == "epub_pdf":
            return cls._epub_to_pdf(src)
        if action_id == "md_html":
            return cls._md_to_html(src)
        if action_id == "md_pdf":
            return cls._md_or_html_to_pdf(src)
        if action_id == "html_pdf":
            return cls._md_or_html_to_pdf(src)
        if action_id == "docx_pdf":
            return cls._docx_to_pdf(src)
        if action_id == "docx_html":
            return cls._docx_to_html(src)
        if action_id == "pptx_pdf":
            return cls._pptx_to_pdf(src)
        if action_id == "pptx_txt":
            return cls._pptx_to_text(src)
        if action_id == "xlsx_pdf":
            return cls._xlsx_to_pdf(src)
        if action_id == "xlsx_csv":
            return cls._xlsx_to_csv(src)
        if action_id == "csv_xlsx":
            return cls._csv_to_xlsx(src)
        if action_id == "csv_json":
            return cls._csv_to_json(src)
        if action_id == "json_csv":
            return cls._json_to_csv(src)
        if action_id == "srt_vtt":
            return cls._convert_subtitles(src, "vtt")
        if action_id == "vtt_srt":
            return cls._convert_subtitles(src, "srt")
        if action_id == "subs_txt":
            return cls._subtitles_to_text(src)
        if action_id == "subs_shift":
            return cls._subtitles_shift(src, options)
        if action_id == "font_report":
            return cls._font_report(src)
        if action_id == "png_preview" and cat == "font":
            return cls._font_preview_png(src)
        if action_id == "font_subset":
            return cls._font_report(src)  # placeholder safety

        # --- media extras ---
        if action_id == "video_720p":
            return cls._media_scale(src, 720)
        if action_id == "video_frames":
            return cls._extract_frames(src, options)
        if action_id == "video_thumbnails":
            return cls._video_thumbnail_grid(src, options)
        if action_id == "burn_subtitles":
            return cls._burn_subtitles(src)
        if action_id == "audio_normalize":
            return cls._audio_normalize(src)
        if action_id == "audio_speed":
            return cls._audio_speed(src, options)
        if action_id == "video_speed":
            return cls._video_speed(src, options)
        if action_id == "video_rotate":
            return cls._video_rotate(src, options)

        return None

    # --- OUTPUT DESTINATION RESOLVER ---

    @classmethod
    def _resolve_dest_path(cls, src: Path, suffix: str, ext: str) -> Path:
        """Determines destination directory based on user settings and ensures no collisions."""
        config = ConfigManager.load_config()
        mode = config.get("output_mode", "same_as_source")
        custom_dir = config.get("custom_output_dir", "")

        if mode == "downloads":
            target_dir = Path.home() / "Downloads"
        elif mode == "custom" and custom_dir and Path(custom_dir).exists():
            target_dir = Path(custom_dir)
        else:
            target_dir = src.parent

        target_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{src.stem}{suffix}{ext}"
        candidate = safe_path(target_dir, base_name)

        # Ensure no accidental overwriting
        counter = 1
        while candidate.exists():
            candidate = target_dir / f"{src.stem}{suffix} ({counter}){ext}"
            counter += 1

        return candidate

    # --- IMAGE IMPLEMENTATIONS ---

    @classmethod
    def _pil_save_atomic(cls, img, dst: Path, **save_kw) -> None:
        """Writes an image via a validated temp name, then swaps it in atomically."""
        tmp = _partial_sibling(dst)
        # The temp name hides the real extension, so infer the format explicitly.
        if "format" not in save_kw:
            ext_map = {".PNG": "PNG", ".JPG": "JPEG", ".JPEG": "JPEG", ".WEBP": "WEBP",
                       ".BMP": "BMP", ".GIF": "GIF", ".TIFF": "TIFF", ".TIF": "TIFF",
                       ".ICO": "ICO", ".AVIF": "AVIF", ".PDF": "PDF"}
            save_kw["format"] = ext_map.get(dst.suffix.upper(), "PNG")
        try:
            img.save(str(tmp), **save_kw)
            os.replace(str(tmp), str(dst))
        except Exception:
            try:
                os.remove(str(tmp))
            except OSError:
                pass
            raise

    @classmethod
    def _doc_save_atomic(cls, doc, dst: Path, **save_kw) -> None:
        """Same crash-safe write for a PyMuPDF document."""
        tmp = _partial_sibling(dst)
        try:
            doc.save(str(tmp), **save_kw)
            os.replace(str(tmp), str(dst))
        except Exception:
            try:
                os.remove(str(tmp))
            except OSError:
                pass
            raise

    @classmethod
    def _convert_image(cls, src: Path, target_ext: str) -> ConversionResult:
        try:
            with Image.open(src) as img:
                img.verify()
        except UnidentifiedImageError:
            return ConversionResult(False, message="Invalid or corrupted image file.")
        except Exception:
            pass  # Some valid formats fail verify() due to seeking, continue to save

        out_ext = ".jpg" if target_ext == "jpg" else f".{target_ext}"
        dst = cls._resolve_dest_path(src, f"_{target_ext}", out_ext)

        try:
            with Image.open(src) as img:
                # Convert color modes for formats that do not support alpha (JPG, BMP)
                if out_ext in (".jpg", ".jpeg", ".bmp") and img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    mask = img.split()[-1] if img.mode == "RGBA" else None
                    bg.paste(img, mask=mask)
                    cls._pil_save_atomic(bg, dst, quality=94, optimize=True)
                elif out_ext == ".ico":
                    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    cls._pil_save_atomic(img, dst, format="ICO", sizes=sizes)
                elif out_ext == ".pdf":
                    cls._pil_save_atomic(img.convert("RGB"), dst, format="PDF", resolution=150.0)
                elif out_ext == ".webp":
                    cls._pil_save_atomic(img, dst, format="WEBP", quality=90, method=6)
                else:
                    cls._pil_save_atomic(img, dst)

            saved = max(0, src.stat().st_size - dst.stat().st_size)
            return ConversionResult(True, str(dst), f"Converted to {target_ext.upper()}", saved_bytes=saved)
        except Exception as e:
            return ConversionResult(False, message=f"Image conversion failed: {str(e)}")

    @classmethod
    def _combine_images_to_pdf(cls, file_paths: List[str]) -> ConversionResult:
        try:
            first_src = Path(file_paths[0])
            dst = cls._resolve_dest_path(first_src, "_combined", ".pdf")

            images = []
            for fp in file_paths:
                with Image.open(fp) as img:
                    images.append(img.convert("RGB"))

            if not images:
                return ConversionResult(False, message="No valid images to combine.")

            cls._pil_save_atomic(images[0], dst, format="PDF", save_all=True,
                                 append_images=images[1:], resolution=150.0)
            return ConversionResult(True, str(dst), f"Combined {len(images)} images into single PDF.")
        except Exception as e:
            return ConversionResult(False, message=f"PDF generation error: {str(e)}")

    @classmethod
    def _compress_image(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_compressed", src.suffix)
        try:
            with Image.open(src) as img:
                if img.format in ("JPEG", "JPG"):
                    cls._pil_save_atomic(img, dst, quality=75, optimize=True)
                elif img.format == "PNG":
                    if img.mode in ("RGBA", "LA", "P"):
                        quantized = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
                    else:
                        quantized = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
                    cls._pil_save_atomic(quantized, dst, optimize=True)
                elif img.format == "WEBP":
                    cls._pil_save_atomic(img, dst, quality=78, method=6)
                else:
                    cls._pil_save_atomic(img, dst, optimize=True)

            saved = max(0, src.stat().st_size - dst.stat().st_size)
            return ConversionResult(True, str(dst), f"Compressed image ({saved // 1024} KB saved).", saved_bytes=saved)
        except Exception as e:
            return ConversionResult(False, message=f"Compression failed: {str(e)}")

    @classmethod
    def _resize_image(cls, src: Path, factor: float) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_scaled", src.suffix)
        try:
            with Image.open(src) as img:
                new_w = max(1, int(img.width * factor))
                new_h = max(1, int(img.height * factor))
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                resized.save(dst)
            return ConversionResult(True, str(dst), f"Resized to {new_w}x{new_h} px.")
        except Exception as e:
            return ConversionResult(False, message=f"Resize failed: {str(e)}")

    @classmethod
    def _crop_square(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_square", src.suffix)
        try:
            with Image.open(src) as img:
                min_dim = min(img.width, img.height)
                left = (img.width - min_dim) // 2
                top = (img.height - min_dim) // 2
                cropped = img.crop((left, top, left + min_dim, top + min_dim))
                cropped.save(dst)
            return ConversionResult(True, str(dst), f"Cropped to {min_dim}x{min_dim} square.")
        except Exception as e:
            return ConversionResult(False, message=f"Crop failed: {str(e)}")

    @classmethod
    def _strip_image_metadata(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_clean", src.suffix)
        try:
            with Image.open(src) as img:
                data = list(img.getdata())
                clean = Image.new(img.mode, img.size)
                clean.putdata(data)
                clean.save(dst)
            return ConversionResult(True, str(dst), "Removed camera, device, and GPS metadata.")
        except Exception as e:
            return ConversionResult(False, message=f"EXIF strip failed: {str(e)}")

    @classmethod
    def _grayscale_image(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_gray", src.suffix)
        try:
            with Image.open(src) as img:
                gray = ImageOps.grayscale(img)
                gray.save(dst)
            return ConversionResult(True, str(dst), "Converted to black & white.")
        except Exception as e:
            return ConversionResult(False, message=f"Grayscale failed: {str(e)}")

    # --- MEDIA IMPLEMENTATIONS ---

    @classmethod
    def get_ffmpeg_bin(cls) -> Optional[str]:
        """Resolves FFmpeg: next to the exe, in dist, in ffmpeg_backup, or on PATH."""
        try:
            from opal_studio.engines import EngineManager
            found = EngineManager.ffmpeg_bin()
            if found:
                return found
        except Exception:
            pass
        # 1. Next to the running executable (standalone bundle)
        cand1 = Path(sys.executable).parent / "ffmpeg.exe"
        if cand1.exists():
            return str(cand1)
        # 2. Bundled dist directory
        dist_root = Path(__file__).parent.parent / "dist"
        dist_cand = None
        for _name in ("Opal", "Opal-Full", "Opal"):
            _c = dist_root / _name / "ffmpeg.exe"
            if _c.exists():
                dist_cand = _c
                break
        if dist_cand.exists():
            return str(dist_cand)
        # 3. Development copy shipped with the project
        backup = Path(__file__).parent.parent / "ffmpeg_backup" / "ffmpeg.exe"
        if backup.exists():
            return str(backup)
        # 4. System PATH
        return shutil.which("ffmpeg")

    @classmethod
    def _convert_media(cls, src: Path, target_ext: str) -> ConversionResult:
        ffmpeg_bin = cls.get_ffmpeg_bin()
        if not ffmpeg_bin:
            return ConversionResult(False, message="Media encoder not available on system.")

        audio_targets = {"mp3", "wav", "m4a", "flac", "ogg", "aac", "opus", "aiff", "wma"}
        dst = cls._resolve_dest_path(src, f"_{target_ext}", f".{target_ext}")
        cmd = [ffmpeg_bin, "-y", "-i", str(src)]

        if target_ext == "mp3":
            cmd += ["-vn", "-acodec", "libmp3lame", "-q:a", "2", str(dst)]
        elif target_ext == "wav":
            cmd += ["-vn", "-acodec", "pcm_s16le", str(dst)]
        elif target_ext in ("m4a", "aac", "opus", "aiff", "wma", "flac", "ogg"):
            codec = {"m4a": "aac", "aac": "aac", "opus": "libopus",
                     "flac": "flac", "ogg": "libvorbis", "aiff": "pcm_s16le",
                     "wma": "wmav2"}[target_ext]
            cmd += ["-vn", "-acodec", codec, str(dst)]
        elif target_ext == "gif":
            cmd += ["-vf", "fps=12,scale=480:-1:flags=lanczos", str(dst)]
        elif target_ext == "mp4":
            cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dst)]
        elif target_ext == "webm":
            cmd += ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus", str(dst)]
        elif target_ext == "mkv":
            cmd += ["-c:v", "libx264", "-c:a", "aac", str(dst)]
        elif target_ext == "avi":
            cmd += ["-c:v", "mpeg4", "-c:a", "libmp3lame", str(dst)]
        elif target_ext == "mov":
            cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dst)]
        else:
            cmd += [str(dst)]

        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if p.returncode != 0 or not Path(dst).exists():
            return ConversionResult(False, message="Media conversion failed.")
        return ConversionResult(True, str(dst), f"Converted media to {target_ext.upper()}.")

    @classmethod
    def _compress_media(cls, src: Path) -> ConversionResult:
        ffmpeg_bin = cls.get_ffmpeg_bin()
        if not ffmpeg_bin:
            return ConversionResult(False, message="Media encoder not available.")
        dst = cls._resolve_dest_path(src, "_compressed", src.suffix)
        cat = cls.get_file_category([str(src)])
        if cat == "audio":
            cmd = [ffmpeg_bin, "-y", "-i", str(src), "-vn",
                   "-acodec", "libmp3lame", "-b:a", "128k", str(dst)]
        else:
            cmd = [ffmpeg_bin, "-y", "-i", str(src), "-vcodec", "libx264",
                   "-crf", "28", "-preset", "fast", "-acodec", "aac", str(dst)]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if p.returncode != 0 or not Path(dst).exists():
            return ConversionResult(False, message="Media compression failed.")
        saved = max(0, src.stat().st_size - dst.stat().st_size)
        return ConversionResult(True, str(dst), f"Compressed media ({saved // 1024} KB saved).", saved_bytes=saved)

    @classmethod
    def _trim_media(cls, src: Path, duration_seconds: int = 30) -> ConversionResult:
        ffmpeg_bin = cls.get_ffmpeg_bin()
        if not ffmpeg_bin:
            return ConversionResult(False, message="Media encoder not available.")
        dst = cls._resolve_dest_path(src, "_trimmed", src.suffix)
        cmd = [ffmpeg_bin, "-y", "-ss", "0", "-i", str(src), "-t", str(duration_seconds), "-c", "copy", str(dst)]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return ConversionResult(True, str(dst), f"Trimmed to first {duration_seconds} seconds.")

    @classmethod
    def _mute_video(cls, src: Path) -> ConversionResult:
        ffmpeg_bin = cls.get_ffmpeg_bin()
        if not ffmpeg_bin:
            return ConversionResult(False, message="Media encoder not available.")
        dst = cls._resolve_dest_path(src, "_muted", src.suffix)
        cmd = [ffmpeg_bin, "-y", "-i", str(src), "-c:v", "copy", "-an", str(dst)]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return ConversionResult(True, str(dst), "Soundtrack removed.")

    # --- PDF & ZIP IMPLEMENTATIONS ---

    @classmethod
    def _pdf_extract_text(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_text", ".txt")
        try:
            if fitz:
                doc = fitz.open(src)
                pages = [f"--- Page {i + 1} ---\n" + page.get_text() for i, page in enumerate(doc)]
                dst.write_text("\n\n".join(pages), encoding="utf-8")
                return ConversionResult(True, str(dst), f"Extracted {len(doc)} pages of text.")
            elif pypdf:
                reader = pypdf.PdfReader(str(src))
                pages = [f"--- Page {i + 1} ---\n" + (p.extract_text() or "") for i, p in enumerate(reader.pages)]
                dst.write_text("\n\n".join(pages), encoding="utf-8")
                return ConversionResult(True, str(dst), f"Extracted {len(reader.pages)} pages of text.")
            return ConversionResult(False, message="PDF engine not available.")
        except Exception as e:
            return ConversionResult(False, message=f"PDF extraction failed: {str(e)}")

    @classmethod
    def _pdf_split_pages(cls, src: Path) -> ConversionResult:
        if not pypdf:
            return ConversionResult(False, message="PDF engine not available.")
        try:
            reader = pypdf.PdfReader(str(src))
            out_folder = src.parent / f"{src.stem}_pages"
            out_folder.mkdir(parents=True, exist_ok=True)
            for i, p in enumerate(reader.pages):
                writer = pypdf.PdfWriter()
                writer.add_page(p)
                p_dst = safe_path(out_folder, f"page_{i + 1}.pdf")
                writer.write(str(p_dst))
            return ConversionResult(True, str(out_folder), f"Split into {len(reader.pages)} individual PDFs.")
        except Exception as e:
            return ConversionResult(False, message=f"PDF split failed: {str(e)}")

    @classmethod
    def _pdf_rotate(cls, src: Path, degrees: int = 90) -> ConversionResult:
        if not pypdf:
            return ConversionResult(False, message="PDF engine not available.")
        dst = cls._resolve_dest_path(src, "_rotated", ".pdf")
        try:
            reader = pypdf.PdfReader(str(src))
            writer = pypdf.PdfWriter()
            for p in reader.pages:
                p.rotate(degrees)
                writer.add_page(p)
            writer.write(str(dst))
            return ConversionResult(True, str(dst), f"Rotated pages by {degrees} degrees.")
        except Exception as e:
            return ConversionResult(False, message=f"Rotation failed: {str(e)}")

    @classmethod
    def _pdf_compress(cls, src: Path) -> ConversionResult:
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        dst = cls._resolve_dest_path(src, "_compressed", ".pdf")
        try:
            doc = fitz.open(src)
            try:
                cls._doc_save_atomic(doc, dst, garbage=4, deflate=True, clean=True)
            finally:
                doc.close()
            saved = max(0, src.stat().st_size - dst.stat().st_size)
            return ConversionResult(True, str(dst), f"Compressed PDF ({saved // 1024} KB saved).", saved_bytes=saved)
        except Exception as e:
            return ConversionResult(False, message=f"PDF compression failed: {str(e)}")

    @classmethod
    def _merge_pdfs(cls, file_paths: List[str]) -> ConversionResult:
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        first_src = Path(file_paths[0])
        dst = cls._resolve_dest_path(first_src, "_merged", ".pdf")
        try:
            merged_doc = fitz.open()
            try:
                total_pages = 0
                for fp in file_paths:
                    d = fitz.open(fp)
                    merged_doc.insert_pdf(d)
                    total_pages += len(d)
                    d.close()
                cls._doc_save_atomic(merged_doc, dst, garbage=4, deflate=True)
            finally:
                merged_doc.close()
            return ConversionResult(True, str(dst), f"Merged {len(file_paths)} PDFs ({total_pages} pages) into {dst.name}.")
        except Exception as e:
            return ConversionResult(False, message=f"PDF merge failed: {str(e)}")

    @classmethod
    def _convert_document_to_pdf(cls, src: Path) -> ConversionResult:
        ext = src.suffix.lower()
        dst = cls._resolve_dest_path(src, "", ".pdf")
        tmp = _partial_sibling(dst)

        # 1. Word Documents (.docx, .doc) via Word COM
        if ext in (".docx", ".doc"):
            try:
                import win32com.client
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                try:
                    doc = word.Documents.Open(str(src.resolve()))
                    doc.SaveAs(str(tmp.resolve()), FileFormat=17)
                    doc.Close()
                finally:
                    word.Quit()
                tmp.replace(dst)
                return ConversionResult(True, str(dst), "Exported Word document to PDF.")
            except Exception:
                pass

        # 2. Excel spreadsheets (.xlsx, .xls) via Excel COM
        if ext in (".xlsx", ".xls"):
            try:
                import win32com.client
                xl = win32com.client.Dispatch("Excel.Application")
                xl.Visible = False
                try:
                    wb = xl.Workbooks.Open(str(src.resolve()))
                    wb.ExportAsFixedFormat(0, str(tmp.resolve()))
                    wb.Close(False)
                finally:
                    xl.Quit()
                tmp.replace(dst)
                return ConversionResult(True, str(dst), "Exported Excel sheet to PDF.")
            except Exception:
                pass

        # 3. Text & Code files (.txt, .md, .csv, .json, .log, .dart, .py, .html) via PyMuPDF
        if ext in (".txt", ".md", ".csv", ".json", ".log", ".dart", ".py", ".html"):
            try:
                if not fitz:
                    return ConversionResult(False, message="PDF renderer unavailable.")
                content = src.read_text(encoding="utf-8", errors="replace")
                tmp = _partial_sibling(dst)
                _text_to_pdf_fit(content, str(tmp), title=src.name)
                os.replace(str(tmp), str(dst))
                return ConversionResult(True, str(dst), f"Exported document to PDF ({src.name}).")
            except Exception as e:
                return ConversionResult(False, message=f"PDF generation failed: {str(e)}")

        return ConversionResult(False, message=f"Cannot export {ext} to PDF.")

    @classmethod
    def _convert_pdf_to_docx(cls, src: Path) -> ConversionResult:
        if not fitz or not docx:
            return ConversionResult(False, message="Document converter unavailable.")
        dst = cls._resolve_dest_path(src, "", ".docx")
        tmp = _partial_sibling(dst)
        try:
            pdf_doc = fitz.open(src)
            word_doc = docx.Document()
            try:
                for page in pdf_doc:
                    text = page.get_text().strip()
                    if text:
                        word_doc.add_paragraph(text)
                page_count = len(pdf_doc)
            finally:
                pdf_doc.close()
            word_doc.save(str(tmp))
            tmp.replace(dst)
            return ConversionResult(True, str(dst), f"Converted PDF to Word DOCX ({page_count} pages).")
        except Exception as e:
            return ConversionResult(False, message=f"PDF to DOCX failed: {str(e)}")

    @classmethod
    def _convert_document_to_text(cls, src: Path) -> ConversionResult:
        ext = src.suffix.lower()
        if ext == ".pdf":
            return cls._pdf_extract_text(src)
        dst = cls._resolve_dest_path(src, "_text", ".txt")
        if ext in (".docx", ".doc"):
            if docx:
                try:
                    d = docx.Document(src)
                    text = "\n\n".join([p.text for p in d.paragraphs if p.text.strip()])
                    dst.write_text(text, encoding="utf-8")
                    return ConversionResult(True, str(dst), "Extracted text from Word document.")
                except Exception as e:
                    return ConversionResult(False, message=f"DOCX extraction failed: {str(e)}")
        if ext in (".txt", ".md", ".csv", ".json", ".log", ".dart", ".py", ".html"):
            content = src.read_text(encoding="utf-8", errors="replace")
            dst.write_text(content, encoding="utf-8")
            return ConversionResult(True, str(dst), "Saved clean text file.")
        return ConversionResult(False, message=f"Text extraction not supported for {ext}.")

    @classmethod
    def _convert_excel_to_csv(cls, src: Path) -> ConversionResult:
        try:
            import win32com.client
            dst = cls._resolve_dest_path(src, "", ".csv")
            tmp = _partial_sibling(dst)
            xl = win32com.client.Dispatch("Excel.Application")
            xl.Visible = False
            try:
                wb = xl.Workbooks.Open(str(src.resolve()))
                wb.SaveAs(str(tmp.resolve()), FileFormat=6)
                wb.Close(False)
            finally:
                xl.Quit()
            tmp.replace(dst)
            return ConversionResult(True, str(dst), "Converted Excel sheet to CSV.")
        except Exception as e:
            return ConversionResult(False, message=f"Excel to CSV failed: {str(e)}")

    @classmethod
    def _bundle_to_zip(cls, file_paths: List[str]) -> ConversionResult:
        try:
            first_src = Path(file_paths[0])
            dst = cls._resolve_dest_path(first_src, "_archive", ".zip")
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zipf:
                for fp in file_paths:
                    p = Path(fp)
                    if p.is_file():
                        zipf.write(p, arcname=p.name)
            return ConversionResult(True, str(dst), f"Compressed {len(file_paths)} files into ZIP archive.")
        except Exception as e:
            return ConversionResult(False, message=f"ZIP creation failed: {str(e)}")

    # --- ACTIONS ---

    @classmethod
    def _action_copy_path(cls, src: Path) -> ConversionResult:
        from opal_studio.platform_compat import copy_text_to_clipboard
        copy_text_to_clipboard(str(src))
        return ConversionResult(True, str(src), "File path copied to clipboard.")

    @classmethod
    def _action_show_explorer(cls, src: Path) -> ConversionResult:
        from opal_studio.platform_compat import reveal_in_file_manager
        reveal_in_file_manager(str(src))
        return ConversionResult(True, str(src), "Revealed in the file manager.")

    @classmethod
    def _action_open_terminal(cls, src: Path) -> ConversionResult:
        from opal_studio.platform_compat import open_terminal
        folder = src.parent if src.is_file() else src
        open_terminal(str(folder))
        return ConversionResult(True, str(src), "Opened a terminal in that folder.")

    @classmethod
    def _action_duplicate(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_copy", src.suffix)
        shutil.copy2(src, dst)
        return ConversionResult(True, str(dst), "Duplicated file.")

    @classmethod
    def _action_trash(cls, src: Path) -> ConversionResult:
        from opal_studio.platform_compat import send_to_trash
        if send_to_trash(str(src)):
            return ConversionResult(True, str(src), "Moved to the trash.")
        if send2trash:
            send2trash(str(src))
            return ConversionResult(True, str(src), "Moved to the trash.")
        return ConversionResult(False, message="Trash utility unavailable.")

    @classmethod
    def _action_float(cls, src: Path) -> ConversionResult:
        return ConversionResult(True, str(src), "Floating on top of screen.")

    @classmethod
    def _crop_16_9(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_16x9", src.suffix)
        try:
            with Image.open(src) as img:
                target_ratio = 16.0 / 9.0
                current_ratio = img.width / img.height
                if current_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    cropped = img.crop((left, 0, left + new_w, img.height))
                else:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    cropped = img.crop((0, top, img.width, top + new_h))
                cropped.save(dst)
            return ConversionResult(True, str(dst), "Cropped to 16:9 widescreen ratio.")
        except Exception as e:
            return ConversionResult(False, message=f"Crop 16:9 failed: {str(e)}")

    @classmethod
    def _invert_image(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_inverted", src.suffix)
        try:
            with Image.open(src) as img:
                if img.mode == "RGBA":
                    r, g, b, a = img.split()
                    rgb = Image.merge("RGB", (r, g, b))
                    inv = ImageOps.invert(rgb)
                    r2, g2, b2 = inv.split()
                    inverted = Image.merge("RGBA", (r2, g2, b2, a))
                else:
                    inverted = ImageOps.invert(img.convert("RGB"))
                inverted.save(dst)
            return ConversionResult(True, str(dst), "Inverted colors.")
        except Exception as e:
            return ConversionResult(False, message=f"Invert failed: {str(e)}")

    @classmethod
    def _pdf_extract_png_pages(cls, src: Path) -> ConversionResult:
        if fitz:
            try:
                doc = fitz.open(src)
                out_folder = src.parent / f"{src.stem}_300dpi_pages"
                out_folder.mkdir(parents=True, exist_ok=True)
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(matrix=mat)
                    pix.save(str(out_folder / f"page_{i + 1}.png"))
                return ConversionResult(True, str(out_folder), f"Extracted {len(doc)} pages at 300 DPI PNG.")
            except Exception as e:
                return ConversionResult(False, message=f"PDF render failed: {str(e)}")
        return cls._pdf_split_pages(src)

    @classmethod
    def _safe_extract(cls, archive: Path, out_folder: Path) -> int:
        """Extracts an archive, refusing to write outside the target folder.

        A crafted archive can name a member "../../something" or an absolute
        path, and an unguarded extraction would then write outside the folder
        the user chose. Every member is checked before anything is written.
        """
        import zipfile
        import tarfile

        target = out_folder.resolve()
        written = 0

        if archive.suffix.lower() == ".zip":
            with zipfile.ZipFile(archive, "r") as z:
                for member in z.infolist():
                    destination = safe_path(target, member.filename)
                    if member.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(z.read(member))
                    written += 1
            return written

        with tarfile.open(archive, "r:*") as t:
            for member in t.getmembers():
                destination = safe_path(target, member.name)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    # Devices, fifos and links have no place in an archive a
                    # user asked us to unpack.
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                extracted = t.extractfile(member)
                if extracted is None:
                    continue
                destination.write_bytes(extracted.read())
                written += 1
        return written

    @classmethod
    def _extract_archive(cls, src: Path) -> ConversionResult:
        out_folder = src.parent / f"{src.stem}_extracted"
        out_folder.mkdir(parents=True, exist_ok=True)
        try:
            ext = src.suffix.lower()
            if ext == ".zip" or ext in (".tar", ".tgz") or src.name.lower().endswith(".tar.gz"):
                written = cls._safe_extract(src, out_folder)
                return ConversionResult(True, str(out_folder), f"Extracted {written} files to {out_folder.name}")
            elif ext == ".gz":
                import gzip
                target = safe_path(out_folder, src.stem)
                with gzip.open(src, "rb") as g_in:
                    target.write_bytes(g_in.read())
                return ConversionResult(True, str(out_folder), f"Extracted archive to {out_folder.name}")
            else:
                return ConversionResult(False, message=f"Archive format {ext} is not supported yet.")
        except Exception as e:
            return ConversionResult(False, message=f"Archive extract failed: {str(e)}")

    @classmethod
    def _format_json(cls, src: Path) -> ConversionResult:
        import json
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            dst = cls._resolve_dest_path(src, "_formatted", ".json")
            dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return ConversionResult(True, str(dst), "Formatted JSON cleanly.")
        except Exception as e:
            return ConversionResult(False, message=f"JSON formatting failed: {str(e)}")

    @classmethod
    def _compress_to_target_size(cls, src: Path, target_mb: float) -> ConversionResult:
        target_bytes = int(target_mb * 1024 * 1024)
        original_size = src.stat().st_size
        if original_size <= target_bytes:
            return ConversionResult(True, str(src), f"Already under {int(target_mb)}MB ({original_size // 1024} KB).")

        cat = cls.get_file_category([str(src)])
        if cat == "image":
            import io
            dst = cls._resolve_dest_path(src, f"_{int(target_mb)}MB", ".jpg")
            try:
                with Image.open(src) as img:
                    rgb = img.convert("RGB")
                    low, high = 15, 88
                    best_q = 65
                    while low <= high:
                        mid = (low + high) // 2
                        buf = io.BytesIO()
                        rgb.save(buf, "JPEG", quality=mid, optimize=True)
                        if buf.tell() <= target_bytes:
                            best_q = mid
                            low = mid + 1
                        else:
                            high = mid - 1
                    cls._pil_save_atomic(rgb, dst, "JPEG", quality=best_q, optimize=True)
                saved = max(0, original_size - dst.stat().st_size)
                return ConversionResult(True, str(dst), f"Compressed under {int(target_mb)}MB ({dst.stat().st_size // 1024} KB).", saved_bytes=saved)
            except Exception as e:
                return ConversionResult(False, message=f"Target compression failed: {str(e)}")

        elif cat in ("video", "audio"):
            ffmpeg_bin = cls.get_ffmpeg_bin()
            if not ffmpeg_bin:
                return ConversionResult(False, message="Media encoder not available.")
            dst = cls._resolve_dest_path(src, f"_{int(target_mb)}MB", ".mp4" if cat == "video" else ".mp3")

            from opal_studio.engines import EngineManager
            duration = EngineManager.media_duration(src)
            if duration <= 0:
                duration = 10.0

            audio_bps = 128 * 1000
            total_bps = (target_bytes * 8) / max(1.0, duration)
            video_bps = max(150 * 1000, int(total_bps - audio_bps))

            if cat == "video":
                cmd = [
                    ffmpeg_bin, "-y", "-i", str(src),
                    "-c:v", "libx264", "-b:v", str(video_bps),
                    "-maxrate", str(int(video_bps * 1.2)), "-bufsize", str(int(video_bps * 2)),
                    "-c:a", "aac", "-b:a", "128k", "-preset", "fast", str(dst)
                ]
            else:
                cmd = [
                    ffmpeg_bin, "-y", "-i", str(src),
                    "-vn", "-c:a", "libmp3lame",
                    "-b:a", f"{min(320, int(total_bps // 1000))}k", str(dst)
                ]

            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if dst.exists():
                saved = max(0, original_size - dst.stat().st_size)
                return ConversionResult(True, str(dst), f"Compressed under {int(target_mb)}MB ({dst.stat().st_size // 1024} KB).", saved_bytes=saved)
            return ConversionResult(False, message="Media compression failed.")

        return cls.execute_single(str(src), "compress_image")

    @classmethod
    def _convert_wa_sticker(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_sticker", ".webp")
        try:
            with Image.open(src) as img:
                img_rgba = img.convert("RGBA")
                img_rgba.thumbnail((512, 512), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
                offset = ((512 - img_rgba.width) // 2, (512 - img_rgba.height) // 2)
                canvas.paste(img_rgba, offset)
                cls._pil_save_atomic(canvas, dst, format="WEBP", quality=85, method=6)
            return ConversionResult(True, str(dst), "Created 512x512 transparent WhatsApp Sticker.")
        except Exception as e:
            return ConversionResult(False, message=f"Sticker creation failed: {str(e)}")

    @classmethod
    def _crop_9_16(cls, src: Path) -> ConversionResult:
        cat = cls.get_file_category([str(src)])
        if cat == "video":
            ffmpeg_bin = cls.get_ffmpeg_bin()
            if not ffmpeg_bin:
                return ConversionResult(False, message="Media encoder not available.")
            dst = cls._resolve_dest_path(src, "_shorts_9x16", ".mp4")
            cmd = [
                ffmpeg_bin, "-y", "-i", str(src),
                "-vf", "crop=ih*(9/16):ih:(iw-ih*(9/16))/2:0,scale=1080:1920:flags=lanczos",
                "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", str(dst)
            ]
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if p.returncode == 0 and dst.exists():
                return ConversionResult(True, str(dst), "Cropped to 9:16 vertical Shorts/Reel video.")
            return ConversionResult(False, message="Video 9:16 crop failed.")
        else:
            dst = cls._resolve_dest_path(src, "_9x16", src.suffix)
            try:
                with Image.open(src) as img:
                    target_ratio = 9.0 / 16.0
                    current_ratio = img.width / img.height
                    if current_ratio > target_ratio:
                        new_w = int(img.height * target_ratio)
                        left = (img.width - new_w) // 2
                        cropped = img.crop((left, 0, left + new_w, img.height))
                    else:
                        new_h = int(img.width / target_ratio)
                        top = (img.height - new_h) // 2
                        cropped = img.crop((0, top, img.width, top + new_h))
                    cropped.save(dst)
                return ConversionResult(True, str(dst), "Cropped to 9:16 vertical format.")
            except Exception as e:
                return ConversionResult(False, message=f"Crop 9:16 failed: {str(e)}")

    # =========================================================================
    # EXTENDED TOOLKIT: ACTIONS, AI IMAGE LAB, PDF STUDIO, DOCUMENTS, MEDIA
    # =========================================================================

    # --- Small helpers ---

    @classmethod
    def _ffmpeg(cls) -> Optional[str]:
        return cls.get_ffmpeg_bin()

    @classmethod
    def _run_ffmpeg(cls, cmd: List[str], cwd: Optional[Path] = None) -> Optional[str]:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           cwd=str(cwd) if cwd else None,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        if p.returncode != 0:
            # The last few lines of ffmpeg's own complaint, which is where it
            # says what it could not open.
            return "\n".join(p.stderr.decode("utf-8", "ignore").strip().splitlines()[-3:])
        return None

    @classmethod
    def _set_clipboard(cls, text: str) -> None:
        from opal_studio.platform_compat import copy_text_to_clipboard
        copy_text_to_clipboard(text)

    # --- File actions ---

    @classmethod
    def _action_open_with(cls, src: Path) -> ConversionResult:
        from opal_studio.platform_compat import open_with_default
        try:
            if open_with_default(str(src)):
                return ConversionResult(True, str(src), f"Opened {src.name} in its default app.")
            return ConversionResult(False, message="No default application for this file type.")
        except Exception as e:
            return ConversionResult(False, message=f"Open failed: {e}")

    @classmethod
    def _action_copy_file(cls, src: Path) -> ConversionResult:
        try:
            target_dir = Path.home() / "Downloads"
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / src.name
            counter = 1
            stem, suffix = dst.stem, dst.suffix
            while dst.exists():
                dst = target_dir / f"{stem} ({counter}){suffix}"
                counter += 1
            shutil.copy2(src, dst)
            return ConversionResult(True, str(dst), f"Copied to Downloads as {dst.name}.")
        except Exception as e:
            return ConversionResult(False, message=f"Copy failed: {e}")

    @classmethod
    def _hash_files(cls, file_paths: List[str]) -> ConversionResult:
        lines = []
        for fp in file_paths:
            p = Path(fp)
            data = p.read_bytes()
            lines.append(f"File: {p.name} ({len(data) / 1024:.0f} KB)")
            lines.append(f"  MD5:    {hashlib.md5(data).hexdigest()}")
            lines.append(f"  SHA1:   {hashlib.sha1(data).hexdigest()}")
            lines.append(f"  SHA256: {hashlib.sha256(data).hexdigest()}")
            lines.append("")
        report = "\n".join(lines)
        first = Path(file_paths[0])
        dst = cls._resolve_dest_path(first, "_checksums", ".txt")
        dst.write_text(report, encoding="utf-8")
        cls._set_clipboard(report)
        return ConversionResult(True, str(dst), "Checksums copied to clipboard and saved.")

    # --- AI cutout (background removal) ---

    @classmethod
    def _remove_background(cls, src: Path, bg_mode: str = "transparent",
                          options: Optional[Dict[str, Any]] = None) -> ConversionResult:
        options = options or {}
        cfg = ConfigManager.load_config()
        model = options.get("bg_model", cfg.get("bg_model", "u2netp"))
        soft = options.get("bg_soft_edges", cfg.get("bg_soft_edges", False))
        try:
            from opal_studio.engines import EngineManager
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGBA")
                cutout = EngineManager.remove_background(base, model=model, soft_edges=soft)

            if bg_mode == "transparent":
                result = cutout
            elif bg_mode == "white":
                result = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
                result.alpha_composite(cutout)
            elif bg_mode == "black":
                result = Image.new("RGBA", cutout.size, (0, 0, 0, 255))
                result.alpha_composite(cutout)
            else:  # blurred original background
                background = base.filter(ImageFilter.GaussianBlur(18))
                result = background.copy()
                result.alpha_composite(cutout)

            suffix = "_nobg" if bg_mode == "transparent" else f"_nobg_{bg_mode}"
            dst = cls._resolve_dest_path(src, suffix, ".png")
            cls._pil_save_atomic(result.convert("RGBA"), dst, format="PNG")
            saved = max(0, src.stat().st_size - dst.stat().st_size)
            return ConversionResult(True, str(dst),
                                    f"Background removed ({EngineManager.cutout_model_used(model)}) -> {dst.name}",
                                    saved_bytes=saved)
        except Exception as e:
            return ConversionResult(False, message=f"Background removal failed: {str(e)}")

    @classmethod
    def _upscale_image(cls, src: Path, factor: int, options: Dict[str, Any]) -> ConversionResult:
        try:
            from opal_studio.engines import EngineManager
            cfg = ConfigManager.load_config()
            model = options.get("upscale_model", cfg.get("upscale_model", "realesrgan-x4plus"))
            with Image.open(src) as img:
                img.load()
                result = EngineManager.upscale(img, model_id=model)
            if factor != (4 if "x4" in model else 2):
                target = (img.width * factor, img.height * factor)
                result = result.resize(target, Image.Resampling.LANCZOS)
            dst = cls._resolve_dest_path(src, f"_{factor}x", src.suffix)
            cls._pil_save_atomic(result, dst)
            return ConversionResult(True, str(dst),
                                    f"AI-upscaled {factor}x to {result.width}x{result.height}.")
        except Exception as e:
            return ConversionResult(False, message=f"Upscale failed: {str(e)}")

    @classmethod
    def _enhance_image(cls, src: Path, preset: str) -> ConversionResult:
        from PIL import ImageEnhance
        dst = cls._resolve_dest_path(src, "_enhanced", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                out = img.convert("RGB")
                if preset == "auto":
                    out = ImageOps.autocontrast(out, cutoff=1)
                    out = ImageEnhance.Color(out).enhance(1.15)
                    out = ImageEnhance.Contrast(out).enhance(1.08)
                    out = ImageEnhance.Sharpness(out).enhance(1.35)
                else:  # vivid
                    out = ImageEnhance.Color(out).enhance(1.35)
                    out = ImageEnhance.Contrast(out).enhance(1.12)
                    out = ImageEnhance.Sharpness(out).enhance(1.25)
                cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst), f"Enhanced ({preset}).")
        except Exception as e:
            return ConversionResult(False, message=f"Enhance failed: {str(e)}")

    @classmethod
    def _image_filter(cls, src: Path, kind: str) -> ConversionResult:
        dst = cls._resolve_dest_path(src, f"_{kind}", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                if kind == "filter_blur":
                    out = img.filter(ImageFilter.GaussianBlur(4))
                elif kind == "filter_pixelate":
                    small = img.resize((max(1, img.width // 14), max(1, img.height // 14)),
                                       Image.Resampling.BILINEAR)
                    out = small.resize(img.size, Image.Resampling.NEAREST)
                elif kind == "filter_sepia":
                    out = ImageOps.colorize(img.convert("L"), black=(40, 20, 0), white=(255, 240, 210))
                elif kind == "filter_vignette":
                    out = _apply_vignette(img.convert("RGB"))
                else:
                    out = img
                cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst), f"Applied {kind.replace('filter_', '')} filter.")
        except Exception as e:
            return ConversionResult(False, message=f"Filter failed: {str(e)}")

    @classmethod
    def _watermark_image(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        text = options.get("watermark_text", "CONFIDENTIAL")
        opacity = float(options.get("watermark_opacity", 0.3))
        dst = cls._resolve_dest_path(src, "_watermarked", src.suffix)
        try:
            from opal_studio.pdf_tools import _watermark_pil
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGBA")
                tile = _watermark_pil(text, (1.0, 1.0, 1.0), 48, 30)
                tile.putalpha(tile.split()[-1].point(lambda v: int(v * opacity)))
                sheet = Image.new("RGBA", (max(512, tile.width), max(512, tile.height)), (0, 0, 0, 0))
                for y in range(0, sheet.height, tile.height + 90):
                    for x in range(0, sheet.width, tile.width + 140):
                        sheet.alpha_composite(tile, (x, y))
                out = base.copy()
                out.alpha_composite(sheet.resize(base.size))
                if dst.suffix.lower() in (".jpg", ".jpeg", ".bmp"):
                    out = out.convert("RGB")
                cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst), "Watermark stamped.")
        except Exception as e:
            return ConversionResult(False, message=f"Watermark failed: {str(e)}")

    @classmethod
    def _social_fit(cls, src: Path, preset: str) -> ConversionResult:
        targets = {
            "social_portrait": ((1080, 1350), "post_4x5"),
            "social_landscape": ((1600, 900), "banner_16x9"),
            "social_banner": ((1584, 396), "banner"),
        }
        (tw, th), suffix = targets[preset]
        dst = cls._resolve_dest_path(src, f"_{suffix}", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
                scale = max(tw / base.width, th / base.height)
                new_size = (max(tw, int(base.width * scale)), max(th, int(base.height * scale)))
                cover = base.resize(new_size, Image.Resampling.LANCZOS)
                left, top = (cover.width - tw) // 2, (cover.height - th) // 2
                cover = cover.crop((left, top, left + tw, top + th))
                cls._pil_save_atomic(cover, dst, quality=92)
            return ConversionResult(True, str(dst), f"Fitted to {tw}x{th} ({suffix}).")
        except Exception as e:
            return ConversionResult(False, message=f"Social fit failed: {str(e)}")

    @classmethod
    def _add_padding(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        pct = int(options.get("padding_pct", 10))
        color = options.get("padding_color", "#FFFFFF")
        dst = cls._resolve_dest_path(src, "_padded", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                pad_x = int(img.width * pct / 100)
                pad_y = int(img.height * pct / 100)
                new_size = (img.width + 2 * pad_x, img.height + 2 * pad_y)
                canvas = Image.new("RGBA", new_size, color)
                canvas.paste(img.convert("RGBA"), (pad_x, pad_y))
                cls._pil_save_atomic(canvas, dst)
            return ConversionResult(True, str(dst), f"Added {pct}% padding.")
        except Exception as e:
            return ConversionResult(False, message=f"Padding failed: {str(e)}")

    @classmethod
    def _color_palette(cls, src: Path) -> ConversionResult:
        try:
            from PIL import ImageDraw, ImageFont
            with Image.open(src) as img:
                img.load()
                small = img.convert("RGB").resize((150, 150))
                palette = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
            pal = palette.getpalette()
            colors = [tuple(pal[i * 3:i * 3 + 3]) for i in range(6)]
            hexes = [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in colors]
            dst = cls._resolve_dest_path(src, "_palette", ".png")
            sw = 96
            sheet = Image.new("RGB", (sw * len(colors), sw + 60), "#101118")
            d = ImageDraw.Draw(sheet)
            try:
                font = ImageFont.truetype(_system_font_path() or "arial.ttf", 14)
            except Exception:
                font = None
            for i, (c, hx) in enumerate(zip(colors, hexes)):
                d.rectangle([i * sw, 0, (i + 1) * sw, sw], fill=c)
                d.text((i * sw + 6, sw + 8), hx, fill=(230, 230, 240), font=font)
            cls._pil_save_atomic(sheet, dst)
            txt = cls._resolve_dest_path(src, "_palette", ".txt")
            txt.write_text("\n".join(hexes), encoding="utf-8")
            cls._set_clipboard("\n".join(hexes))
            return ConversionResult(True, str(txt), f"Palette: {', '.join(hexes)} (copied)")
        except Exception as e:
            return ConversionResult(False, message=f"Palette failed: {str(e)}")

    @classmethod
    def _exif_report(cls, src: Path) -> ConversionResult:
        try:
            from PIL import ExifTags
            lines = [f"EXIF report for {src.name}", ""]
            with Image.open(src) as img:
                lines.append(f"Format: {img.format} {img.size} {img.mode}")
                exif = img.getexif()
                if not exif:
                    lines.append("No EXIF data found.")
                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                    lines.append(f"{tag}: {value}")
                try:
                    gps = exif.get_ifd(0x8825)
                    if gps:
                        lines.append("")
                        lines.append("GPS location data (privacy!):")
                        for k, v in gps.items():
                            lines.append(f"  {ExifTags.GPSTAGS.get(k, k)}: {v}")
                except Exception:
                    pass
            dst = cls._resolve_dest_path(src, "_exif_report", ".txt")
            dst.write_text("\n".join(lines), encoding="utf-8")
            return ConversionResult(True, str(dst), "EXIF report saved.")
        except Exception as e:
            return ConversionResult(False, message=f"EXIF report failed: {str(e)}")

    @classmethod
    def _qr_code(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        try:
            import qrcode
            if src.suffix.lower() in (".txt", ".md", ".json", ".csv", ".url"):
                content = src.read_text(encoding="utf-8", errors="replace").strip()
            else:
                content = options.get("qr_text") or str(src)
            if not content:
                content = str(src)
            qr = qrcode.QRCode(border=2, box_size=12)
            qr.add_data(content[:3900])
            qr.make(fit=True)
            img = qr.make_image(fill_color="#101118", back_color="white").convert("RGB")
            dst = cls._resolve_dest_path(src, "_qr", ".png")
            cls._pil_save_atomic(img, dst)
            return ConversionResult(True, str(dst), f"QR code created ({min(len(content), 3900)} chars).")
        except Exception as e:
            return ConversionResult(False, message=f"QR creation failed: {str(e)}")

    @classmethod
    def _rotate_flip_image(cls, src: Path, action: str) -> ConversionResult:
        dst = cls._resolve_dest_path(src, f"_{action}", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                ops = {
                    "rotate_left": Image.Transpose.ROTATE_90,
                    "rotate_right": Image.Transpose.ROTATE_270,
                    "flip_h": Image.Transpose.FLIP_LEFT_RIGHT,
                    "flip_v": Image.Transpose.FLIP_TOP_BOTTOM,
                }
                out = img.transpose(ops.get(action, Image.Transpose.ROTATE_90))
                cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst), f"{action.replace('_', ' ').title()} applied.")
        except Exception as e:
            return ConversionResult(False, message=f"Transform failed: {str(e)}")

    @classmethod
    def _favicon_set(cls, src: Path) -> ConversionResult:
        out_folder = src.parent / f"{src.stem}_favicon"
        out_folder.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGBA")
                base.save(out_folder / "favicon.ico", format="ICO",
                          sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
                for s in (16, 32, 48, 180, 192, 512):
                    base.resize((s, s), Image.Resampling.LANCZOS).save(out_folder / f"favicon-{s}.png")
            (out_folder / "head-snippet.html").write_text(
                '<link rel="icon" type="image/x-icon" href="/favicon.ico">\n'
                '<link rel="apple-touch-icon" href="/favicon-180.png">\n'
                '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">\n',
                encoding="utf-8")
            return ConversionResult(True, str(out_folder),
                                    f"Favicon set created ({len(list(out_folder.glob('*')))} files).")
        except Exception as e:
            return ConversionResult(False, message=f"Favicon set failed: {str(e)}")

    @classmethod
    def _optimize_web(cls, src: Path) -> ConversionResult:
        dst = cls._resolve_dest_path(src, "_web", ".webp")
        try:
            with Image.open(src) as img:
                img.load()
                out = img
                if max(out.size) > 2000:
                    ratio = 2000 / max(out.size)
                    out = out.resize((int(out.width * ratio), int(out.height * ratio)),
                                     Image.Resampling.LANCZOS)
                cls._pil_save_atomic(out, dst, format="WEBP", quality=82, method=6)
            return ConversionResult(True, str(dst), f"Optimized for web ({dst.stat().st_size // 1024} KB).")
        except Exception as e:
            return ConversionResult(False, message=f"Web optimization failed: {str(e)}")

    @classmethod
    def _contact_sheet(cls, file_paths: List[str], options: Dict[str, Any]) -> ConversionResult:
        from PIL import ImageDraw, ImageFont
        cols = int(options.get("sheet_cols", 4))
        cell = int(options.get("sheet_cell", 320))
        try:
            rows = (len(file_paths) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * cell, rows * (cell + 34)), "#101118")
            d = ImageDraw.Draw(sheet)
            try:
                font = ImageFont.truetype(_system_font_path() or "arial.ttf", 13)
            except Exception:
                font = None
            for i, fp in enumerate(file_paths):
                with Image.open(fp) as im:
                    im.load()
                    thumb = im.convert("RGB")
                    thumb.thumbnail((cell - 12, cell - 12), Image.Resampling.LANCZOS)
                x = (i % cols) * cell + (cell - thumb.width) // 2
                y = (i // cols) * (cell + 34) + (cell - thumb.height) // 2
                sheet.paste(thumb, (x, y))
                d.text(((i % cols) * cell + 8, (i // cols) * (cell + 34) + cell + 6),
                       Path(fp).name, fill=(200, 200, 215), font=font)
            first = Path(file_paths[0])
            dst = cls._resolve_dest_path(first, "_contact_sheet", ".png")
            cls._pil_save_atomic(sheet, dst)
            return ConversionResult(True, str(dst), f"Contact sheet of {len(file_paths)} images.")
        except Exception as e:
            return ConversionResult(False, message=f"Contact sheet failed: {str(e)}")

    # --- PDF toolkit passthroughs ---

    @classmethod
    def _pdf_action(cls, src: Path, kind: str, options: Dict[str, Any]) -> ConversionResult:
        try:
            from opal_studio import pdf_tools as pt
            if kind == "watermark":
                out = pt.add_watermark(str(src), options.get("watermark_text", "CONFIDENTIAL"),
                                       opacity=float(options.get("watermark_opacity", 0.3)))
            elif kind == "pagenum":
                out = pt.add_page_numbers(str(src), start=int(options.get("start", 1)),
                                          fmt=options.get("format", "{n}"))
            elif kind == "flatten":
                out = pt.flatten(str(src))
            elif kind == "meta_clean":
                out = pt.set_metadata(str(src), remove_all=True)
            elif kind == "ocr":
                out = pt.ocr_pdf(str(src))
            elif kind == "reverse":
                out = pt.reverse_pages(str(src))
            else:
                return ConversionResult(False, message=f"Unknown PDF action '{kind}'.")
            return ConversionResult(True, str(out), f"PDF {kind} complete -> {Path(out).name}")
        except Exception as e:
            return ConversionResult(False, message=f"PDF {kind} failed: {str(e)}")

    @classmethod
    def _pdf_to_pptx(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        try:
            from opal_studio import pdf_tools as pt
            dst = cls._resolve_dest_path(src, "", ".pptx")
            out = pt.export_pptx(str(src), str(dst), dpi=int(options.get("dpi", 110)))
            return ConversionResult(True, str(out), f"PowerPoint created -> {Path(out).name}")
        except Exception as e:
            return ConversionResult(False, message=f"PDF to PowerPoint failed: {str(e)}")

    @classmethod
    def _pdf_to_html(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        try:
            from opal_studio import pdf_tools as pt
            dst = cls._resolve_dest_path(src, "", ".html")
            out = pt.export_html(str(src), str(dst))
            return ConversionResult(True, str(out), "HTML exported.")
        except Exception as e:
            return ConversionResult(False, message=f"PDF to HTML failed: {str(e)}")

    @classmethod
    def _pdf_to_epub(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        try:
            from ebooklib import epub
            import fitz
            dst = cls._resolve_dest_path(src, "", ".epub")
            doc = fitz.open(str(src))
            book = epub.EpubBook()
            title = src.stem or "Untitled"
            book.set_identifier(f"tangerine-{abs(hash(title))}")
            book.set_title(title)
            book.set_language("en")
            chapters = []
            for i, page in enumerate(doc):
                text = page.get_text().strip() or f"(page {i + 1}: image only)"
                body = "<p>" + "</p><p>".join(text.split("\n\n")) + "</p>"
                ch = epub.EpubHtml(title=f"Page {i + 1}", file_name=f"page_{i + 1}.xhtml", lang="en")
                ch.content = f"<h1>Page {i + 1}</h1>{body}"
                book.add_item(ch)
                chapters.append(ch)
            book.toc = chapters
            book.spine = ["nav"] + chapters
            book.add_item(epub.EpubNav())
            epub.write_epub(str(dst), book, {})
            doc.close()
            return ConversionResult(True, str(dst), f"EPUB created ({len(chapters)} text pages).")
        except Exception as e:
            return ConversionResult(False, message=f"PDF to EPUB failed: {str(e)}")

    @classmethod
    def _pdf_pages_to_images(cls, src: Path, fmt: str, options: Dict[str, Any]) -> ConversionResult:
        try:
            from opal_studio import pdf_tools as pt
            outdir = src.parent / f"{src.stem}_{fmt}s"
            files = pt.export_pages(str(src), str(outdir),
                                    dpi=int(options.get("dpi", 200)), fmt=fmt)
            return ConversionResult(True, str(outdir), f"Exported {len(files)} {fmt.upper()} pages.")
        except Exception as e:
            return ConversionResult(False, message=f"Page export failed: {str(e)}")

    # --- Documents, ebooks, subtitles ---

    @classmethod
    def _epub_to_text(cls, src: Path) -> ConversionResult:
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
            book = epub.read_epub(str(src))
            parts = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                soup = BeautifulSoup(item.get_content(), "lxml")
                parts.append(soup.get_text("\n"))
            dst = cls._resolve_dest_path(src, "_text", ".txt")
            dst.write_text("\n\n".join(parts), encoding="utf-8")
            return ConversionResult(True, str(dst), "EPUB text extracted.")
        except Exception as e:
            return ConversionResult(False, message=f"EPUB extraction failed: {str(e)}")

    @classmethod
    def _epub_to_html(cls, src: Path) -> ConversionResult:
        try:
            import ebooklib
            from ebooklib import epub
            book = epub.read_epub(str(src))
            bodies = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                raw = item.get_content()
                bodies.append(raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw))
            html = ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    f"<title>{src.stem}</title></head><body>" + "\n<hr>\n".join(bodies) + "</body></html>")
            dst = cls._resolve_dest_path(src, "", ".html")
            dst.write_text(html, encoding="utf-8")
            return ConversionResult(True, str(dst), "EPUB converted to HTML.")
        except Exception as e:
            return ConversionResult(False, message=f"EPUB to HTML failed: {str(e)}")

    @classmethod
    def _epub_to_pdf(cls, src: Path) -> ConversionResult:
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
            book = epub.read_epub(str(src))
            chapters = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                soup = BeautifulSoup(item.get_content(), "lxml")
                chapters.append(soup.get_text("\n"))
            dst = cls._resolve_dest_path(src, "", ".pdf")
            tmp = _partial_sibling(dst)
            _text_to_pdf_fit("\n\n".join(chapters), str(tmp), title=src.name)
            os.replace(str(tmp), str(dst))
            return ConversionResult(True, str(dst), "EPUB printed to PDF.")
        except Exception as e:
            return ConversionResult(False, message=f"EPUB to PDF failed: {str(e)}")

    @classmethod
    def _md_to_html(cls, src: Path) -> ConversionResult:
        try:
            import markdown as md_lib
            text = src.read_text(encoding="utf-8", errors="replace")
            body = md_lib.markdown(text, extensions=["extra", "tables", "fenced_code", "sane_lists"])
            css = ("body{max-width:46em;margin:3em auto;font-family:'Segoe UI',sans-serif;line-height:1.65;"
                   "color:#EDF1FA;background:#fff;padding:2em;} pre{background:#f2f2f6;padding:1em;border-radius:8px;}"
                   "code{font-family:Consolas,monospace;} table{border-collapse:collapse} td,th{border:1px solid #ccc;padding:6px}")
            html = (f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{src.stem}</title>"
                    f"<style>{css}</style></head><body>{body}</body></html>")
            dst = cls._resolve_dest_path(src, "", ".html")
            dst.write_text(html, encoding="utf-8")
            return ConversionResult(True, str(dst), "Markdown rendered to styled HTML.")
        except Exception as e:
            return ConversionResult(False, message=f"Markdown to HTML failed: {str(e)}")

    @classmethod
    def _md_or_html_to_pdf(cls, src: Path) -> ConversionResult:
        """Markdown/HTML -> PDF using PyMuPDF Story (real typesetting, not a text dump)."""
        try:
            import markdown as md_lib
            import fitz
            if src.suffix.lower() == ".md":
                text = src.read_text(encoding="utf-8", errors="replace")
                body = md_lib.markdown(text, extensions=["extra", "tables", "fenced_code"])
            else:
                body = src.read_text(encoding="utf-8", errors="replace")
            css = ("body{font-family:sans-serif;font-size:11px;line-height:1.5;color:#EDF1FA}"
                   "h1{font-size:22px;color:#A79FFF;margin-bottom:4px}h2{font-size:16px;margin-top:18px}"
                   "pre,code{font-family:monospace;font-size:10px;background:#f4f4f8;padding:6px;border-radius:4px}"
                   "table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #bbb;padding:4px}"
                   "img{max-width:100%}")
            dst = cls._resolve_dest_path(src, "", ".pdf")
            tmp = _partial_sibling(dst)
            writer = fitz.DocumentWriter(str(tmp))
            story = fitz.Story(html=body, user_css=css)
            rect = fitz.Rect(50, 50, 545, 790)
            more = 1
            while more:
                dev = writer.begin_page(rect)
                more, _ = story.place(rect)
                story.draw(dev, fitz.Matrix(1, 1))
                writer.end_page()
            writer.close()
            # Every Story/Writer reference must go before the OS will release the handle.
            del story, dev, writer
            import gc
            gc.collect()
            for attempt in range(5):
                try:
                    os.replace(str(tmp), str(dst))
                    break
                except OSError:
                    if attempt == 4:
                        raise
                    time.sleep(0.2)
            return ConversionResult(True, str(dst), "PDF created with clean typography.")
        except Exception as e:
            return ConversionResult(False, message=f"PDF creation failed: {str(e)}")

    @classmethod
    def _docx_to_pdf(cls, src: Path) -> ConversionResult:
        """DOCX -> PDF with Word when installed, otherwise faithful python-docx typesetting."""
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            try:
                dst = cls._resolve_dest_path(src, "", ".pdf")
                tmp = _partial_sibling(dst)
                doc = word.Documents.Open(str(src.resolve()))
                doc.SaveAs(str(tmp.resolve()), FileFormat=17)
                doc.Close()
            finally:
                word.Quit()
            os.replace(str(tmp), str(dst))
            return ConversionResult(True, str(dst), "Word printed to PDF.")
        except Exception:
            pass

        try:
            import fitz
            import docx as docx_lib
            d = docx_lib.Document(str(src))
            blocks = []
            for p in d.paragraphs:
                if p.text.strip():
                    blocks.append((p.style.name if p.style else "", p.text))
            n_tables = len(d.tables)
            dst = cls._resolve_dest_path(src, "", ".pdf")
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            y = 60
            for style, text in blocks:
                if y > 780:
                    page = doc.new_page(width=595, height=842)
                    y = 60
                size = 17 if "Heading 1" in style else 14 if "Heading" in style else 10.5
                font = "hebo" if "Heading" in style else "helv"
                page.insert_text((50, y), text[:120], fontname=font, fontsize=size,
                                 color=_c((22, 23, 34)))
                y += size + 8
            cls._doc_save_atomic(doc, dst)
            doc.close()
            msg = "Exported to PDF (python typeset layout"
            if n_tables:
                msg += f"; {n_tables} tables stayed in the DOCX"
            return ConversionResult(True, str(dst), msg + ").")
        except Exception as e:
            return ConversionResult(False, message=f"DOCX to PDF failed: {str(e)}")

    @classmethod
    def _docx_to_html(cls, src: Path) -> ConversionResult:
        try:
            import docx as docx_lib
            d = docx_lib.Document(str(src))
            out = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{src.stem}</title></head><body>"]
            for p in d.paragraphs:
                if not p.text.strip():
                    continue
                style = (p.style.name or "").lower()
                if "heading 1" in style:
                    out.append(f"<h1>{_html_escape(p.text)}</h1>")
                elif "heading" in style:
                    out.append(f"<h2>{_html_escape(p.text)}</h2>")
                elif "list" in style:
                    out.append(f"<li>{_html_escape(p.text)}</li>")
                else:
                    out.append(f"<p>{_html_escape(p.text)}</p>")
            for table in d.tables:
                out.append("<table border='1'>")
                for row in table.rows:
                    cells = "".join(f"<td>{_html_escape(c.text)}</td>" for c in row.cells)
                    out.append(f"<tr>{cells}</tr>")
                out.append("</table>")
            out.append("</body></html>")
            dst = cls._resolve_dest_path(src, "", ".html")
            dst.write_text("\n".join(out), encoding="utf-8")
            return ConversionResult(True, str(dst), "DOCX converted to HTML.")
        except Exception as e:
            return ConversionResult(False, message=f"DOCX to HTML failed: {str(e)}")

    @classmethod
    def _pptx_to_pdf(cls, src: Path) -> ConversionResult:
        try:
            from pptx import Presentation
            import fitz, io
            prs = Presentation(str(src))
            n_slides = len(prs.slides._sldIdLst)
            dst = cls._resolve_dest_path(src, "", ".pdf")
            tmp = _partial_sibling(dst)
            doc = fitz.open()
            sw, sh = prs.slide_width, prs.slide_height
            pw, ph = 960.0, 540.0
            for slide in prs.slides:
                page = doc.new_page(width=pw, height=ph)
                for shape in slide.shapes:
                    try:
                        if getattr(shape, "shape_type", None) == 13 or hasattr(shape, "image"):
                            rect = fitz.Rect(_emu_to_pt(shape.left, pw, sw), _emu_to_pt(shape.top, ph, sh),
                                             _emu_to_pt(shape.left + shape.width, pw, sw),
                                             _emu_to_pt(shape.top + shape.height, ph, sh))
                            page.insert_image(rect, stream=io.BytesIO(shape.image.blob).getvalue())
                        elif shape.has_text_frame and shape.text_frame.text.strip():
                            rect = fitz.Rect(_emu_to_pt(shape.left, pw, sw), _emu_to_pt(shape.top, ph, sh),
                                             _emu_to_pt(shape.left + (shape.width or 4 * 360000), pw, sw),
                                             _emu_to_pt(shape.top + (shape.height or 2 * 360000), ph, sh))
                            page.insert_textbox(rect, shape.text_frame.text, fontsize=16,
                                        color=_c((22, 23, 34)))
                    except Exception:
                        continue
            cls._doc_save_atomic(doc, dst)
            doc.close()
            return ConversionResult(True, str(dst), f"PowerPoint rendered to PDF ({n_slides} slides).")
        except Exception as e:
            return ConversionResult(False, message=f"PPTX to PDF failed: {str(e)}")

    @classmethod
    def _pptx_to_text(cls, src: Path) -> ConversionResult:
        try:
            from pptx import Presentation
            prs = Presentation(str(src))
            lines = []
            for i, slide in enumerate(prs.slides, 1):
                lines.append(f"--- Slide {i} ---")
                for shape in slide.shapes:
                    if shape.has_text_frame and shape.text_frame.text.strip():
                        lines.append(shape.text_frame.text.strip())
                lines.append("")
            dst = cls._resolve_dest_path(src, "_slides", ".txt")
            dst.write_text("\n".join(lines), encoding="utf-8")
            return ConversionResult(True, str(dst), f"Extracted text from {len(prs.slides._sldIdLst)} slides.")
        except Exception as e:
            return ConversionResult(False, message=f"Slide text extraction failed: {str(e)}")

    @classmethod
    def _xlsx_to_pdf(cls, src: Path) -> ConversionResult:
        try:
            import win32com.client
            xl = win32com.client.Dispatch("Excel.Application")
            xl.Visible = False
            try:
                dst = cls._resolve_dest_path(src, "", ".pdf")
                tmp = _partial_sibling(dst)
                wb = xl.Workbooks.Open(str(src.resolve()))
                wb.ExportAsFixedFormat(0, str(tmp.resolve()))
                wb.Close(False)
            finally:
                xl.Quit()
            os.replace(str(tmp), str(dst))
            return ConversionResult(True, str(dst), "Excel exported to PDF.")
        except Exception:
            pass

        try:
            import openpyxl, fitz
            wb = openpyxl.load_workbook(str(src), data_only=True)
            dst = cls._resolve_dest_path(src, "", ".pdf")
            doc = fitz.open()
            for ws in wb.worksheets:
                page = doc.new_page(width=595, height=842)
                y = 50
                page.insert_text((40, y), f"Sheet: {ws.title}", fontsize=11,
                                 color=_c((255, 122, 24)))
                y += 18
                for row in ws.iter_rows(max_row=200, values_only=True):
                    if y > 800:
                        page = doc.new_page(width=595, height=842)
                        y = 50
                    line = "  |  ".join("" if c is None else str(c)[:28] for c in row)
                    page.insert_text((40, y), line[:110], fontname="cour", fontsize=8,
                                     color=_c((30, 30, 40)))
                    y += 12
            cls._doc_save_atomic(doc, dst)
            doc.close()
            return ConversionResult(True, str(dst), "Excel typeset to PDF (openpyxl engine).")
        except Exception as e:
            return ConversionResult(False, message=f"XLSX to PDF failed: {str(e)}")

    @classmethod
    def _xlsx_to_csv(cls, src: Path) -> ConversionResult:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(src), data_only=True)
            outputs = []
            for ws in wb.worksheets:
                suffix = f"_{ws.title}" if len(wb.worksheets) > 1 else ""
                dst = cls._resolve_dest_path(src, suffix, ".csv")
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                for row in ws.iter_rows(values_only=True):
                    writer.writerow(["" if c is None else c for c in row])
                dst.write_text(buffer.getvalue(), encoding="utf-8", newline="")
                outputs.append(str(dst))
            return ConversionResult(True, outputs[0] if outputs else None,
                                    f"Exported {len(outputs)} sheet(s) to CSV.")
        except Exception as e:
            return ConversionResult(False, message=f"XLSX to CSV failed: {str(e)}")

    @classmethod
    def _csv_to_xlsx(cls, src: Path) -> ConversionResult:
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = src.stem[:28]
            with open(src, "r", newline="", encoding="utf-8", errors="replace") as f:
                for row in csv.reader(f):
                    ws.append(row)
            for col in ws.columns:
                width = max((len(str(c.value)) for c in col[:50] if c.value), default=10)
                ws.column_dimensions[col[0].column_letter].width = min(48, max(10, width + 2))
            for cell in ws[1]:
                cell.font = openpyxl.styles.Font(bold=True)
            ws.freeze_panes = "A2"
            dst = cls._resolve_dest_path(src, "", ".xlsx")
            wb.save(str(dst))
            return ConversionResult(True, str(dst), "Excel workbook created.")
        except Exception as e:
            return ConversionResult(False, message=f"CSV to XLSX failed: {str(e)}")

    @classmethod
    def _csv_to_json(cls, src: Path) -> ConversionResult:
        try:
            with open(src, "r", newline="", encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))
            dst = cls._resolve_dest_path(src, "", ".json")
            dst.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            return ConversionResult(True, str(dst), f"Converted {len(rows)} rows to JSON.")
        except Exception as e:
            return ConversionResult(False, message=f"CSV to JSON failed: {str(e)}")

    @classmethod
    def _json_to_csv(cls, src: Path) -> ConversionResult:
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = [data]
            if not data or not all(isinstance(r, dict) for r in data):
                return ConversionResult(False, message="JSON must be an object or array of objects.")
            fields = list({k for row in data for k in row.keys()})
            dst = cls._resolve_dest_path(src, "", ".csv")
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=fields)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
            dst.write_text(buffer.getvalue(), encoding="utf-8", newline="")
            return ConversionResult(True, str(dst), f"Converted {len(data)} records to CSV.")
        except Exception as e:
            return ConversionResult(False, message=f"JSON to CSV failed: {str(e)}")

    @classmethod
    def _convert_subtitles(cls, src: Path, target: str) -> ConversionResult:
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
            if src.suffix.lower() == ".srt":
                out = _srt_to_vtt(text) if target == "vtt" else text
                dst = cls._resolve_dest_path(src, "", ".vtt" if target == "vtt" else ".srt")
            else:
                out = _vtt_to_srt(text) if target == "srt" else text
                dst = cls._resolve_dest_path(src, "", ".srt" if target == "srt" else ".vtt")
            dst.write_text(out, encoding="utf-8")
            return ConversionResult(True, str(dst), f"Subtitles converted to {dst.suffix.upper()[1:]}.")
        except Exception as e:
            return ConversionResult(False, message=f"Subtitle conversion failed: {str(e)}")

    @classmethod
    def _subtitles_to_text(cls, src: Path) -> ConversionResult:
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
            lines = []
            for block in re.split(r"\n\s*\n", text):
                body = [ln for ln in block.splitlines()
                        if ln.strip() and not re.fullmatch(r"\d+", ln.strip())
                        and "-->" not in ln and not ln.strip().upper().startswith("WEBVTT")]
                if body:
                    lines.append(" ".join(body))
            dst = cls._resolve_dest_path(src, "_dialogue", ".txt")
            dst.write_text("\n".join(lines), encoding="utf-8")
            return ConversionResult(True, str(dst), f"Extracted {len(lines)} spoken lines.")
        except Exception as e:
            return ConversionResult(False, message=f"Dialogue extraction failed: {str(e)}")

    @classmethod
    def _subtitles_shift(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        try:
            seconds = float(options.get("shift_seconds", 5))
            text = src.read_text(encoding="utf-8", errors="replace")

            def shift(m):
                h, mn, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                ms = int(m.group(4) or 0)
                total = int(max(0, h * 3600 + mn * 60 + s + seconds))
                h2, rem = divmod(total, 3600)
                mn2, s2 = divmod(rem, 60)
                return f"{h2:02d}:{mn2:02d}:{s2:02d}.{ms:03d}" if ms else f"{h2:02d}:{mn2:02d}:{s2:02d}"

            shifted = re.sub(r"(\d{2}):(\d{2}):(\d{2})(?:\.(\d{3}))?", shift, text)
            dst = cls._resolve_dest_path(src, f"_shift{int(seconds):+d}s", src.suffix)
            dst.write_text(shifted, encoding="utf-8")
            return ConversionResult(True, str(dst), f"Shifted all timings by {seconds:+.0f}s.")
        except Exception as e:
            return ConversionResult(False, message=f"Subtitle shift failed: {str(e)}")

    @classmethod
    def _font_report(cls, src: Path) -> ConversionResult:
        try:
            from fontTools.ttLib import TTFont
            font = TTFont(str(src))
            lines = [f"Font report: {src.name}", ""]

            def name_of(name_id):
                return font["name"].getDebugName(name_id) or ""

            for label, nid in [("Family", 1), ("Subfamily", 2), ("Full name", 4), ("PostScript", 6),
                               ("Version", 5), ("Manufacturer", 8), ("Designer", 9), ("License", 13),
                               ("License URL", 14), ("Description", 10), ("Vendor URL", 11)]:
                value = name_of(nid)
                if value:
                    lines.append(f"{label}: {value}")
            head = font["head"]
            lines.append(f"Units per em: {head.unitsPerEm}")
            lines.append(f"Bounding box: {head.xMin}, {head.yMin}, {head.xMax}, {head.yMax}")
            glyphs = font.getGlyphOrder()
            lines.append(f"Glyph count: {len(glyphs)}")
            if "OS/2" in font:
                os2 = font["OS/2"]
                lines.append(f"Weight class: {os2.usWeightClass}  Italic: {bool(os2.fsSelection & 1)}")
            lines.append("")
            lines.append("Sample glyphs: " + " ".join(glyphs[1:40]))
            dst = cls._resolve_dest_path(src, "_report", ".txt")
            dst.write_text("\n".join(str(x) for x in lines), encoding="utf-8")
            return ConversionResult(True, str(dst), f"Font report for '{name_of(1)}' saved.")
        except Exception as e:
            return ConversionResult(False, message=f"Font report failed: {str(e)}")

    @classmethod
    def _font_preview_png(cls, src: Path) -> ConversionResult:
        try:
            from PIL import ImageFont, ImageDraw
            pangram = "The quick brown fox jumps over 12 lazy dogs. 0123456789"
            sizes = [18, 28, 44, 64]
            fonts = []
            for size in sizes:
                try:
                    fonts.append(ImageFont.truetype(str(src), size))
                except Exception:
                    fonts.append(None)
            height = 340
            for size in sizes:
                height += size + 34
            sheet = Image.new("RGB", (1400, height), "#FFFFFF")
            d = ImageDraw.Draw(sheet)
            y = 20
            try:
                title_font = ImageFont.truetype(_system_font_path() or "arial.ttf", 20)
            except Exception:
                title_font = None
            d.text((24, y), f"{src.name}", fill="#FF7A18", font=title_font)
            y += 44
            for size, fnt in zip(sizes, fonts):
                d.text((24, y), pangram, fill="#161722", font=fnt)
                y += size + 34
            dst = cls._resolve_dest_path(src, "_preview", ".png")
            cls._pil_save_atomic(sheet, dst)
            return ConversionResult(True, str(dst), "Font specimen sheet rendered.")
        except Exception as e:
            return ConversionResult(False, message=f"Font preview failed: {str(e)}")

    # --- Media extras ---

    @classmethod
    def _media_scale(cls, src: Path, target_h: int) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        dst = cls._resolve_dest_path(src, f"_{target_h}p", ".mp4")
        cmd = [ff, "-y", "-i", str(src), "-vf", f"scale=-2:{target_h}",
               "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
               "-c:a", "aac", str(dst)]
        err = cls._run_ffmpeg(cmd)
        if err or not Path(dst).exists():
            return ConversionResult(False, message=f"Resize failed: {err}")
        return ConversionResult(True, str(dst), f"Converted to {target_h}p.")

    @classmethod
    def _extract_frames(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        fps = options.get("frames_per_second", "all")
        out_folder = src.parent / f"{src.stem}_frames"
        out_folder.mkdir(parents=True, exist_ok=True)
        if fps == "all":
            cmd = [ff, "-y", "-i", str(src), str(out_folder / "frame_%05d.png")]
        else:
            cmd = [ff, "-y", "-i", str(src), "-vf", f"fps={fps}", str(out_folder / "frame_%05d.png")]
        err = cls._run_ffmpeg(cmd)
        count = len(list(out_folder.glob("*.png")))
        if count == 0:
            return ConversionResult(False, message=f"Frame extraction failed: {err}")
        return ConversionResult(True, str(out_folder), f"Extracted {count} frames.")

    @classmethod
    def _video_thumbnail_grid(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        from opal_studio.engines import EngineManager
        duration = EngineManager.media_duration(src) or 10
        tmp_dir = src.parent / f".{src.stem}_thumbs"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        try:
            for i in range(9):
                t = duration * (i + 0.5) / 9
                out = tmp_dir / f"t{i}.png"
                cls._run_ffmpeg([ff, "-y", "-ss", f"{t:.2f}", "-i", str(src),
                                 "-frames:v", "1", "-vf", "scale=320:-2", str(out)])
                if out.exists():
                    frames.append(out)
            if not frames:
                return ConversionResult(False, message="Could not grab frames from media.")
            cell = 320
            cols = 3
            rows = (len(frames) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * cell, rows * cell), "#101118")
            for i, f in enumerate(frames):
                with Image.open(f) as im:
                    im.load()
                    thumb = im.convert("RGB")
                    thumb.thumbnail((cell, cell))
                    sheet.paste(thumb, ((i % cols) * cell + (cell - thumb.width) // 2,
                                        (i // cols) * cell + (cell - thumb.height) // 2))
            dst = cls._resolve_dest_path(src, "_thumbs", ".jpg")
            cls._pil_save_atomic(sheet, dst, quality=88)
            return ConversionResult(True, str(dst), f"Thumbnail grid ({len(frames)} frames).")
        except Exception as e:
            return ConversionResult(False, message=f"Thumbnail grid failed: {str(e)}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @classmethod
    def _burn_subtitles(cls, src: Path) -> ConversionResult:
        """Puts the subtitles into the picture.

        ffmpeg's own subtitle filter needs libass, and plenty of ffmpeg builds
        (the one Homebrew ships, for one) do not have it. So the subtitle text
        is drawn here instead - which also means Indic subtitles come out
        right - and ffmpeg is only asked to lay the pictures over the video,
        a job every build can do.
        """
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        candidates = [src.with_suffix(".srt"), src.with_suffix(".vtt")]
        sub = next((c for c in candidates if c.exists()), None)
        if not sub:
            return ConversionResult(False, message=f"No matching subtitle file for {src.name}.")
        dst = cls._resolve_dest_path(src, "_subtitled", src.suffix)

        cues = _parse_subtitle_cues(sub)
        if not cues:
            return ConversionResult(False, message=f"No subtitle text found in {sub.name}.")

        width, height = cls._video_size(src)
        work = src.parent / f"{src.stem}_opal_subs"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True, exist_ok=True)
        try:
            frames = []
            for index, (start, end, text) in enumerate(cues):
                png = work / f"cue_{index:04d}.png"
                _render_subtitle_png(png, text, width, height)
                frames.append((png, start, end))

            inputs: List[str] = []
            for png, _, _ in frames:
                inputs += ["-i", str(png)]

            chain = []
            previous = "0:v"
            for index, (_, start, end) in enumerate(frames):
                source = f"{index + 1}:v"
                last = index == len(frames) - 1
                target = "vout" if last else f"v{index}"
                chain.append(
                    f"[{previous}][{source}]overlay=x=0:y=0:eof_action=repeat:"
                    f"enable='between(t,{start:.2f},{end:.2f})'[{target}]")
                previous = target

            cmd = ([ff, "-y", "-i", str(src)] + inputs + [
                "-filter_complex", ";".join(chain),
                "-map", "[vout]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", str(dst)])
            err = cls._run_ffmpeg(cmd)
        except Exception as e:
            return ConversionResult(False, message=f"Subtitle burn failed: {e}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

        if err or not Path(dst).exists():
            return ConversionResult(False, message=f"Subtitle burn failed: {err}")
        return ConversionResult(True, str(dst), f"Burned {sub.name} into the video.")

    @classmethod
    def _video_size(cls, src: Path) -> Tuple[int, int]:
        """The width and height of a video, in pixels."""
        ff = cls._ffmpeg()
        if ff:
            try:
                probe = ff.replace("ffmpeg", "ffprobe")
                if Path(probe).exists():
                    out = subprocess.run(
                        [probe, "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height",
                         "-of", "csv=p=0:s=x", str(src)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                        timeout=15).stdout.strip()
                    if "," in out:
                        w, h = out.split(",")[:2]
                        if int(w) > 0 and int(h) > 0:
                            return int(w), int(h)
            except Exception:
                pass
        try:
            import cv2
            cap = cv2.VideoCapture(str(src))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            cap.release()
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
        return 1280, 720

    @classmethod
    def _audio_normalize(cls, src: Path) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        dst = cls._resolve_dest_path(src, "_normalized", src.suffix)
        err = cls._run_ffmpeg([ff, "-y", "-i", str(src), "-af",
                               "loudnorm=I=-16:TP=-1.5:LRA=11", str(dst)])
        if err or not Path(dst).exists():
            return ConversionResult(False, message=f"Normalize failed: {err}")
        return ConversionResult(True, str(dst), "Audio normalized to -16 LUFS.")

    @classmethod
    def _audio_speed(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        rate = float(options.get("speed", 1.5))
        dst = cls._resolve_dest_path(src, f"_{rate}x", src.suffix)
        err = cls._run_ffmpeg([ff, "-y", "-i", str(src), "-filter:a", f"atempo={rate}", "-vn", str(dst)])
        if err or not Path(dst).exists():
            return ConversionResult(False, message=f"Speed change failed: {err}")
        return ConversionResult(True, str(dst), f"Audio sped up {rate}x.")

    @classmethod
    def _video_speed(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        rate = float(options.get("speed", 2.0))
        dst = cls._resolve_dest_path(src, f"_{rate}x", src.suffix)
        err = cls._run_ffmpeg([ff, "-y", "-i", str(src), "-filter:v", f"setpts=PTS/{rate}",
                               "-filter:a", f"atempo={rate}", "-c:v", "libx264",
                               "-preset", "fast", str(dst)])
        if err or not Path(dst).exists():
            return ConversionResult(False, message=f"Speed change failed: {err}")
        return ConversionResult(True, str(dst), f"Video sped up {rate}x.")

    @classmethod
    def _video_rotate(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        ff = cls._ffmpeg()
        if not ff:
            return ConversionResult(False, message="Media encoder not available.")
        degrees = int(options.get("degrees", 90))
        transpose = {90: "transpose=1", 180: "transpose=1,transpose=1",
                     270: "transpose=2"}.get(degrees, "transpose=1")
        dst = cls._resolve_dest_path(src, "_rotated", src.suffix)
        err = cls._run_ffmpeg([ff, "-y", "-i", str(src), "-vf", transpose,
                               "-c:v", "libx264", "-preset", "fast", "-c:a", "copy", str(dst)])
        if err or not Path(dst).exists():
            return ConversionResult(False, message=f"Rotate failed: {err}")
        return ConversionResult(True, str(dst), f"Video rotated {degrees}°.")

    # ------------------------------------------------------------------
    # PRINT-SHOP & EVERYDAY DOCUMENT SIZES
    # ------------------------------------------------------------------

    @classmethod
    def _resize_photo_spec(cls, src: Path, width: int, height: int, label: str) -> ConversionResult:
        """Produces an official ID-photo size (Aadhaar 413x599, passport 413x599)."""
        dst = cls._resolve_dest_path(src, f"_{label}", ".jpg")
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
                target_ratio = width / height
                current_ratio = base.width / base.height
                if current_ratio > target_ratio:
                    new_w = int(base.height * target_ratio)
                    left = (base.width - new_w) // 2
                    cropped = base.crop((left, 0, left + new_w, base.height))
                else:
                    new_h = int(base.width / target_ratio)
                    top = (base.height - new_h) // 2
                    cropped = base.crop((0, top, base.width, top + new_h))
                out = cropped.resize((width, height), Image.Resampling.LANCZOS)
                cls._pil_save_atomic(out, dst, quality=95, subsampling=0)
            return ConversionResult(True, str(dst),
                                    f"ID photo ready ({width}x{height} px) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"ID photo resize failed: {str(e)}")

    @classmethod
    def _print_size(cls, src: Path, w_inch: float, h_inch: float, dpi: int,
                    label: str) -> ConversionResult:
        """Resizes to a real print size (e.g. 4x6 inch photo paper at 300 DPI)."""
        width = int(round(w_inch * dpi))
        height = int(round(h_inch * dpi))
        dst = cls._resolve_dest_path(src, f"_{label}", ".jpg")
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
                out = base.resize((width, height), Image.Resampling.LANCZOS)
                cls._pil_save_atomic(out, dst, quality=95, subsampling=0)
            return ConversionResult(True, str(dst),
                                    f"Print size ready ({w_inch:g}x{h_inch:g} inch @ {dpi} DPI "
                                    f"= {width}x{height}px) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Print size resize failed: {str(e)}")

    @classmethod
    def _whatsapp_image(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Optimises a photo for sharing on WhatsApp (max edge + good quality)."""
        max_edge = int(options.get("max_edge", 1600))
        quality = int(options.get("quality", 82))
        dst = cls._resolve_dest_path(src, "_whatsapp", ".jpg")
        try:
            with Image.open(src) as img:
                img.load()
                out = img.convert("RGB")
                if max(out.size) > max_edge:
                    ratio = max_edge / max(out.size)
                    out = out.resize((int(out.width * ratio), int(out.height * ratio)),
                                     Image.Resampling.LANCZOS)
                cls._pil_save_atomic(out, dst, quality=quality, optimize=True)
            return ConversionResult(True, str(dst),
                                    f"WhatsApp-ready photo ({out.width}x{out.height}, "
                                    f"{dst.stat().st_size // 1024} KB) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"WhatsApp export failed: {str(e)}")

    @classmethod
    def _pdf_target_size(cls, src: Path, target_mb: float) -> ConversionResult:
        """Shrinks a PDF under a target size (e.g. 1 MB for WhatsApp)."""
        try:
            from opal_studio import pdf_tools as pt
        except Exception as e:
            return ConversionResult(False, message=f"PDF engine unavailable: {e}")
        target_bytes = int(target_mb * 1024 * 1024)
        try:
            if src.stat().st_size <= target_bytes:
                return ConversionResult(True, str(src),
                                        f"Already under {target_mb:g} MB "
                                        f"({src.stat().st_size // 1024} KB).")
        except Exception:
            pass

        out = None
        for quality in (75, 60, 45, 30):
            try:
                candidate = cls._resolve_dest_path(src, "_small", ".pdf")
                pt.compress_pdf(str(src), str(candidate), image_quality=quality)
                if candidate.stat().st_size <= target_bytes:
                    out = candidate
                    break
                if out is None:
                    out = candidate
            except Exception:
                continue

        # Still too big: rebuild the pages as smaller images.
        if out is None or out.stat().st_size > target_bytes:
            try:
                import fitz
                for dpi in (150, 110, 80, 60):
                    doc = fitz.open(str(src))
                    new_doc = fitz.open()
                    mat = fitz.Matrix(dpi / 72, dpi / 72)
                    for page in doc:
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        new_page = new_doc.new_page(width=595, height=842)
                        new_page.insert_image(new_page.rect, stream=pix.tobytes("png"))
                    candidate = cls._resolve_dest_path(src, "_small", ".pdf")
                    new_doc.save(str(candidate), deflate=True, garbage=4)
                    new_doc.close()
                    doc.close()
                    if candidate.stat().st_size <= target_bytes:
                        out = candidate
                        break
                    if out is None:
                        out = candidate
            except Exception as e:
                return ConversionResult(False, message=f"Could not shrink the PDF: {e}")

        if out is None:
            return ConversionResult(False, message="Could not shrink the PDF further.")
        size_kb = out.stat().st_size // 1024
        return ConversionResult(True, str(out),
                                f"PDF is now {size_kb} KB (under {target_mb:g} MB) - {out.name}")

    @classmethod
    def _pdf_to_a4(cls, src: Path) -> ConversionResult:
        """Fits every page onto A4 paper without changing the aspect ratio."""
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        try:
            doc = fitz.open(str(src))
            out_doc = fitz.open()
            a4_w, a4_h = 595, 842
            margin = 18
            for index in range(len(doc)):
                page = doc[index]
                new_page = out_doc.new_page(width=a4_w, height=a4_h)
                scale = min((a4_w - 2 * margin) / page.rect.width,
                            (a4_h - 2 * margin) / page.rect.height)
                w = page.rect.width * scale
                h = page.rect.height * scale
                x0 = (a4_w - w) / 2
                y0 = (a4_h - h) / 2
                new_page.show_pdf_page(fitz.Rect(x0, y0, x0 + w, y0 + h), doc, index)
            dst = cls._resolve_dest_path(src, "_a4", ".pdf")
            out_doc.save(str(dst), deflate=True, garbage=4)
            out_doc.close()
            doc.close()
            return ConversionResult(True, str(dst), f"Fitted to A4 - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"A4 fit failed: {e}")

    @classmethod
    def _add_border(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Adds a clean white border so a photo prints without touching the edges."""
        percent = int(options.get("border_pct", 5))
        color = options.get("border_color", "#FFFFFF")
        dst = cls._resolve_dest_path(src, "_bordered", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
                pad_x = max(1, int(base.width * percent / 100))
                pad_y = max(1, int(base.height * percent / 100))
                canvas = Image.new("RGB", (base.width + 2 * pad_x, base.height + 2 * pad_y), color)
                canvas.paste(base, (pad_x, pad_y))
                cls._pil_save_atomic(canvas, dst)
            return ConversionResult(True, str(dst), f"Border added ({percent}%) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Border failed: {e}")

    @classmethod
    def _pdf_dsc_sign(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Signs a PDF with a real digital signature certificate (.pfx / .p12)."""
        try:
            from opal_studio import dsc_sign
        except Exception as e:
            return ConversionResult(False, message=f"Signing engine unavailable: {e}")
        pfx = options.get("pfx_path") or options.get("certificate") or ""
        if not pfx:
            return ConversionResult(False, message="No certificate file was given.")
        password = options.get("password", "")
        page_no = int(options.get("page", 0))
        rect = options.get("rect") or (60, 60, 250, 120)
        dst = cls._resolve_dest_path(src, "_signed", ".pdf")
        try:
            dsc_sign.sign_pdf(str(src), str(dst), str(pfx), str(password),
                              page_no=page_no, rect=tuple(rect),
                              reason=options.get("reason", "Approved by the signer"),
                              location=options.get("location", "India"))
        except Exception as e:
            return ConversionResult(False, message=f"Signing failed: {e}")
        return ConversionResult(True, str(dst),
                                f"PDF signed with your digital signature certificate - {dst.name}")

    @classmethod
    def _pdf_remove_blank_pages(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Drops the empty pages that scanners leave behind."""
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        try:
            doc = fitz.open(str(src))
            total = len(doc)
            keep = []
            for index, page in enumerate(doc):
                text = page.get_text().strip()
                images = page.get_images(full=True)
                drawings = page.get_drawings()
                is_blank = (not text) and (not images) and len(drawings) < 3
                if not is_blank:
                    keep.append(index)
            if not keep:
                doc.close()
                return ConversionResult(False, message="Every page looks blank - nothing removed.")
            if len(keep) == total:
                doc.close()
                return ConversionResult(True, str(src), "No blank pages found.")
            out_doc = fitz.open()
            for index in keep:
                out_doc.insert_pdf(doc, from_page=index, to_page=index)
            dst = cls._resolve_dest_path(src, "_noblinks", ".pdf")
            out_doc.save(str(dst), deflate=True, garbage=4)
            out_doc.close()
            doc.close()
            removed = total - len(keep)
            return ConversionResult(True, str(dst),
                                    f"Removed {removed} blank page(s) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Blank page removal failed: {e}")

    # ------------------------------------------------------------------
    # PHOTO & PDF TOOLKIT (the everyday iLove-style jobs, fully offline)
    # ------------------------------------------------------------------

    @classmethod
    def _face_blur(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Blurs every detected face - the fastest way to blur a photo for sharing."""
        dst = cls._resolve_dest_path(src, "_facesblurred", src.suffix)
        try:
            import cv2
            import numpy as np
        except Exception:
            return cls._copy_with_note(src, dst, "Face blur needs the vision engine")
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
            array = cv2.cvtColor(np.array(base), cv2.COLOR_RGB2BGR)
            grey = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
            faces = []
            for cascade in ("haarcascade_frontalface_default.xml",
                            "haarcascade_profileface.xml"):
                path = os.path.join(cv2.data.haarcascades, cascade)
                if os.path.exists(path):
                    clf = cv2.CascadeClassifier(path)
                    found = clf.detectMultiScale(grey, 1.15, 5, minSize=(40, 40))
                    faces.extend(found.tolist() if len(found) else [])
            if not faces:
                cls._pil_save_atomic(base, dst)
                return ConversionResult(True, str(dst),
                                        f"No face detected - copy saved unchanged - {dst.name}")
            for (x, y, w, h) in faces:
                pad = int(max(w, h) * 0.28)
                x0, y0 = max(0, x - pad), max(0, y - pad)
                x1, y1 = min(array.shape[1], x + w + pad), min(array.shape[0], y + h + pad)
                region = array[y0:y1, x0:x1]
                blurred = cv2.GaussianBlur(region, (0, 0), sigmaX=max(12, (x1 - x0) * 0.12))
                array[y0:y1, x0:x1] = blurred
            out = Image.fromarray(cv2.cvtColor(array, cv2.COLOR_BGR2RGB))
            cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst),
                                    f"Blurred {len(faces)} face(s) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Face blur failed: {e}")

    @classmethod
    def _remove_object(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Removes an object from a photo by inpainting over a marked area."""
        dst = cls._resolve_dest_path(src, "_cleaned", src.suffix)
        try:
            import cv2
            import numpy as np
        except Exception:
            return cls._copy_with_note(src, dst, "Object removal needs the vision engine")
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
            array = cv2.cvtColor(np.array(base), cv2.COLOR_RGB2BGR)
            h, w = array.shape[:2]
            box = options.get("box")
            if box and len(box) == 4:
                x0, y0, x1, y1 = [int(v) for v in box]
            else:
                # Default: a centred square the user can adjust in the studio
                side = int(min(w, h) * 0.28)
                cx, cy = w // 2, h // 2
                x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2)
                x1, y1 = min(w, x0 + side), min(h, y0 + side)
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[y0:y1, x0:x1] = 255
            cleaned = cv2.inpaint(array, mask, 5, cv2.INPAINT_TELEA)
            out = Image.fromarray(cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB))
            cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst),
                                    f"Cleaned the marked area - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Object removal failed: {e}")

    @classmethod
    def _copy_with_note(cls, src: Path, dst: Path, note: str) -> ConversionResult:
        shutil.copy2(src, dst)
        return ConversionResult(True, str(dst), f"{note} - copy saved as {dst.name}")

    @classmethod
    def _meme(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Adds a top and/or bottom caption, meme style."""
        top = (options.get("top") or "").strip()
        bottom = (options.get("bottom") or "").strip()
        if not top and not bottom:
            top = "Your text here"
        dst = cls._resolve_dest_path(src, "_meme", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
            width, height = base.size
            bar = int(height * 0.16)
            canvas = Image.new("RGB", (width, height + bar * 2), (0, 0, 0))
            canvas.paste(base, (0, bar))
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(canvas)
            size = int(bar * 0.62)
            font = None
            font_path = None
            for name in ("Impact.ttf", "arialbd.ttf", "Arial Bold.ttf"):
                cand = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
                if cand.exists():
                    try:
                        font = ImageFont.truetype(str(cand), size)
                        font_path = str(cand)
                        break
                    except Exception:
                        font = None
            if font is None:
                font = ImageFont.load_default()

            def _fit_font(text):
                """Shrink the caption until it fits the width."""
                for candidate in range(size, 12, -2):
                    try:
                        f = ImageFont.truetype(font_path, candidate)
                    except Exception:
                        return font
                    if draw.textlength(text, font=f) <= width - 20:
                        return f
                return font

            for text, y, anchor in ((top, 4, "la"), (bottom, height + bar + 4, "la")):
                if not text:
                    continue
                draw.text((width // 2, y), text, fill=(255, 255, 255),
                           font=_fit_font(text), anchor=anchor)
            cls._pil_save_atomic(canvas, dst)
            return ConversionResult(True, str(dst), f"Meme caption added - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Meme creation failed: {e}")

    @classmethod
    def _beautify(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """A gentle, one-tap portrait fix: smooth noise, restore detail, warm the tone."""
        dst = cls._resolve_dest_path(src, "_beautified", src.suffix)
        try:
            from PIL import ImageEnhance, ImageFilter
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
            smooth = base.filter(ImageFilter.SMOOTH_MORE)
            out = Image.blend(base, smooth, 0.28)
            out = ImageEnhance.Sharpness(out).enhance(1.25)
            out = ImageEnhance.Contrast(out).enhance(1.06)
            out = ImageEnhance.Color(out).enhance(1.06)
            cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst), f"Beautified - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Beautify failed: {e}")

    @classmethod
    def _liquid_resize(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Resizes to an exact size by filling and cropping - no squashing."""
        width = int(options.get("width", 1080))
        height = int(options.get("height", 1080))
        dst = cls._resolve_dest_path(src, f"_{width}x{height}", src.suffix)
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
            scale = max(width / base.width, height / base.height)
            resized = base.resize((max(1, int(base.width * scale)),
                                  max(1, int(base.height * scale))), Image.Resampling.LANCZOS)
            left = (resized.width - width) // 2
            top = (resized.height - height) // 2
            out = resized.crop((left, top, left + width, top + height))
            cls._pil_save_atomic(out, dst)
            return ConversionResult(True, str(dst), f"Resized to {width}x{height} - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Resize failed: {e}")

    @classmethod
    def _image_ocr(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Runs OCR on a photo and writes a searchable PDF next to it."""
        dst = cls._resolve_dest_path(src, "_searchable", ".pdf")
        try:
            from opal_studio.engines import EngineManager
            import fitz
            engine = EngineManager.rapidocr_engine()
            if engine is None:
                return ConversionResult(False, message="The OCR engine is not installed.")
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            with Image.open(src) as img:
                img.load()
                picture = img.convert("RGB")
            picture.thumbnail((515, 760))
            buffer = io.BytesIO()
            picture.save(buffer, "PNG")
            png_bytes = buffer.getvalue()
            pixmap = fitz.Pixmap(png_bytes)
            page.insert_image(fitz.Rect(40, 40, 40 + picture.width, 40 + picture.height),
                              pixmap=pixmap)
            result, _ = engine(png_bytes)
            if result:
                scale = 515 / max(1, picture.width)
                for box, text, _score in result:
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    rect = fitz.Rect(40 + min(xs) * scale, 40 + min(ys) * scale,
                                     40 + max(xs) * scale, 40 + max(ys) * scale)
                    page.insert_text((rect.x0, rect.y1), text, fontsize=8, render_mode=3)
            doc.save(str(dst), deflate=True)
            doc.close()
            return ConversionResult(True, str(dst), f"Searchable PDF created - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Image OCR failed: {e}")

    @classmethod
    def _repair_pdf(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Rebuilds a broken PDF by re-writing its pages."""
        dst = cls._resolve_dest_path(src, "_repaired", ".pdf")
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        try:
            doc = fitz.open(str(src))
        except Exception as e:
            return ConversionResult(False, message=f"Could not open this PDF: {e}")
        try:
            out = fitz.open()
            for index in range(len(doc)):
                out.insert_pdf(doc, from_page=index, to_page=index)
            out.save(str(dst), deflate=True, garbage=4)
            out.close()
            doc.close()
            return ConversionResult(True, str(dst), f"PDF rebuilt and repaired - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Repair failed: {e}")

    @classmethod
    def _autocrop_pdf(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Trims the white margins a scanner leaves around a document."""
        dst = cls._resolve_dest_path(src, "_cropped", ".pdf")
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        try:
            doc = fitz.open(str(src))
            out = fitz.open()
            for page in doc:
                rect = None
                for word in page.get_text("words"):
                    r = fitz.Rect(word[:4])
                    rect = r if rect is None else rect | r
                for img in page.get_image_info():
                    r = fitz.Rect(img["bbox"])
                    rect = r if rect is None else rect | r
                for drawing in page.get_drawings():
                    r = drawing["rect"]
                    rect = r if rect is None else rect | r
                if rect is None or rect.is_empty:
                    out.insert_pdf(doc, from_page=page.number, to_page=page.number)
                    continue
                margin = int(options.get("margin", 12))
                new_rect = fitz.Rect(rect.x0 - margin, rect.y0 - margin,
                                     rect.x1 + margin, rect.y1 + margin) & page.rect
                if new_rect.is_empty or new_rect.width < 10 or new_rect.height < 10:
                    new_rect = page.rect
                out.insert_pdf(doc, from_page=page.number, to_page=page.number,
                               annots=False)
            out.save(str(dst), deflate=True, garbage=4)
            out.close()
            doc.close()
            return ConversionResult(True, str(dst), f"White margins trimmed - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Auto-crop failed: {e}")

    @classmethod
    def _grayscale_pdf(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Makes a photocopy-style black & white PDF."""
        dst = cls._resolve_dest_path(src, "_grayscale", ".pdf")
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        try:
            doc = fitz.open(str(src))
            out = fitz.open()
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY, alpha=False)
                new_page = out.new_page(width=page.rect.width, height=page.rect.height)
                new_page.insert_image(new_page.rect, stream=pix.tobytes("png"))
            out.save(str(dst), deflate=True, garbage=4)
            out.close()
            doc.close()
            return ConversionResult(True, str(dst), f"Black & white PDF created - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Greyscale failed: {e}")

    @classmethod
    def _pdf_summary(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Writes an offline summary of the document: the key sentences, no AI needed."""
        dst = cls._resolve_dest_path(src, "_summary", ".txt")
        if not fitz:
            return ConversionResult(False, message="PDF engine unavailable.")
        try:
            doc = fitz.open(str(src))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            if not text.strip():
                return ConversionResult(False, message="This PDF has no extractable text.")
            stop = set("""a an and are as at be but by for from has have he her his i in is it its
            of on or she that the their them there these they this to was were will with you
            your not no we our us can may shall should would could""".split())
            words = [w.lower().strip(".,;:!?()[]{}\"'") for w in text.split()]
            words = [w for w in words if len(w) > 3 and w not in stop and w.isalpha()]
            freq = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
            sentences = [s.strip() for s in sentences if 40 <= len(s.strip()) <= 400]
            scored = []
            for i, s in enumerate(sentences):
                tokens = [w.lower().strip(".,;:!?()[]{}\"'") for w in s.split()]
                score = sum(freq.get(t, 0) for t in tokens if len(t) > 3) / (len(tokens) ** 0.5)
                scored.append((score, i, s))
            scored.sort(reverse=True)
            keep = sorted(scored[:int(options.get("sentences", 6))], key=lambda x: x[1])
            body = "\n\n".join(s for _score, _i, s in keep)
            header = (f"SUMMARY - {Path(src).name}\n"
                      f"{'=' * 40}\n"
                      f"Key points extracted offline from {len(text.split())} words.\n\n")
            dst.write_text(header + body, encoding="utf-8")
            return ConversionResult(True, str(dst),
                                    f"Summary written ({len(keep)} key points) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Summary failed: {e}")

    @classmethod
    def _stamp_photo(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """The 50x40 mm stamp photo an Indian form asks for (at 300 DPI)."""
        width = round(options.get("width_mm", 50) / 25.4 * 300)
        height = round(options.get("height_mm", 40) / 25.4 * 300)
        dst = cls._resolve_dest_path(src, "_stamp", ".jpg")
        try:
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGB")
            ratio = width / height
            current = base.width / base.height
            if current > ratio:
                new_w = int(base.height * ratio)
                left = (base.width - new_w) // 2
                cropped = base.crop((left, 0, left + new_w, base.height))
            else:
                new_h = int(base.width / ratio)
                top = (base.height - new_h) // 2
                cropped = base.crop((0, top, base.width, top + new_h))
            out = cropped.resize((width, height), Image.Resampling.LANCZOS)
            cls._pil_save_atomic(out, dst, quality=95, subsampling=0)
            return ConversionResult(True, str(dst),
                                    f"Stamp photo ready ({width}x{height} px, 50x40 mm) - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Stamp photo failed: {e}")

    @classmethod
    def _white_bg_photo(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Cuts the subject out and places it on a clean white background."""
        dst = cls._resolve_dest_path(src, "_whitebg", ".jpg")
        try:
            from opal_studio.engines import EngineManager
            cfg = ConfigManager.load_config()
            model = options.get("bg_model", cfg.get("bg_model", "u2netp"))
            with Image.open(src) as img:
                img.load()
                base = img.convert("RGBA")
            cutout = EngineManager.remove_background(base, model=model)
            canvas = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
            canvas.alpha_composite(cutout)
            cls._pil_save_atomic(canvas.convert("RGB"), dst, quality=95, subsampling=0)
            return ConversionResult(True, str(dst),
                                    f"White-background photo saved - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"White background failed: {e}")

    @classmethod
    def _join_photos(cls, src: Path, options: Dict[str, Any]) -> ConversionResult:
        """Places two photos side by side (photo + signature for a form)."""
        other = options.get("second") or ""
        if not other or not Path(other).exists():
            return ConversionResult(False,
                                    message="Pick the second photo to place next to this one.")
        dst = cls._resolve_dest_path(src, "_joined", ".jpg")
        try:
            with Image.open(src) as a_img, Image.open(other) as b_img:
                a = a_img.convert("RGB")
                b = b_img.convert("RGB")
            height = max(a.height, b.height)
            gap = 20
            def scaled(img):
                ratio = height / img.height
                return img.resize((max(1, int(img.width * ratio)), height), Image.Resampling.LANCZOS)
            a_s, b_s = scaled(a), scaled(b)
            canvas = Image.new("RGB", (a_s.width + gap + b_s.width, height), (255, 255, 255))
            canvas.paste(a_s, (0, 0))
            canvas.paste(b_s, (a_s.width + gap, 0))
            cls._pil_save_atomic(canvas, dst, quality=95, subsampling=0)
            return ConversionResult(True, str(dst),
                                    f"Two photos joined side by side - {dst.name}")
        except Exception as e:
            return ConversionResult(False, message=f"Joining photos failed: {e}")

    @classmethod
    def get_catalog(cls) -> List[Dict[str, str]]:
        """The complete public menu of everything Opal can do (for Studio & CLI)."""
        return [
            {"id": "remove_bg", "label": "Remove Background", "kind": "image",
             "desc": "AI removes the background - transparent PNG, saved next to your file"},
            {"id": "aadhaar_photo", "label": "ID Photo 413x599", "kind": "image",
             "desc": "Aadhaar / passport / visa photo size in one click"},
            {"id": "print_4x6", "label": "Print 4R Photo", "kind": "image",
             "desc": "4R paper (4x6 in) at 300 DPI - the standard lab size"},
            {"id": "photo_whatsapp", "label": "WhatsApp Photo", "kind": "image",
             "desc": "Small and sharp photo ready to share"},
            {"id": "pdf_whatsapp", "label": "WhatsApp PDF", "kind": "pdf",
             "desc": "Shrink a PDF under 1 MB to send on WhatsApp"},
            {"id": "pdf_a4", "label": "Fit to A4", "kind": "pdf",
             "desc": "Fit every page onto A4 paper for printing"},
            {"id": "add_border", "label": "Add Border", "kind": "image",
             "desc": "White border so photos print cleanly"},
            {"id": "bg_cutout_blur", "label": "BG → Blur", "kind": "image",
             "desc": "Cutout over blurred original"},
            {"id": "upscale_2x", "label": "AI Upscale 2x/4x", "kind": "image",
             "desc": "Real-ESRGAN detail restoration"},
            {"id": "enhance_auto", "label": "Auto-Enhance", "kind": "image", "desc": "One-tap photo fix"},
            {"id": "compress_image", "label": "Compress", "kind": "image", "desc": "Shrink without quality loss"},
            {"id": "social_portrait", "label": "Social Presets", "kind": "image", "desc": "4:5 post & banners"},
            {"id": "color_palette", "label": "Color Palette", "kind": "image", "desc": "Dominant colors + hex"},
            {"id": "exif_report", "label": "EXIF Inspector", "kind": "image", "desc": "Hidden camera & GPS data"},
            {"id": "watermark_image", "label": "Watermark", "kind": "image", "desc": "Diagonal text stamp"},
            {"id": "qr_code", "label": "QR Code", "kind": "document", "desc": "Text/links to QR PNG"},
            {"id": "pdf", "label": "Anything → PDF", "kind": "document",
             "desc": "Documents, images, EPUB, markdown, slides"},
            {"id": "pptx", "label": "PDF → PowerPoint", "kind": "pdf", "desc": "Image slides deck"},
            {"id": "docx", "label": "PDF → Word", "kind": "pdf", "desc": "Editable DOCX"},
            {"id": "epub", "label": "PDF → EPUB", "kind": "pdf", "desc": "E-book export"},
            {"id": "pdf_dsc_sign", "label": "Sign with DSC", "kind": "pdf",
             "desc": "Apply a real digital signature certificate (.pfx/.p12)"},
            {"id": "pdf_pagenum", "label": "Page Numbers", "kind": "pdf", "desc": "Footer numbering"},
            {"id": "pdf_watermark", "label": "Watermark PDF", "kind": "pdf", "desc": "Diagonal stamp"},
            {"id": "pdf_ocr", "label": "OCR Searchable", "kind": "pdf", "desc": "Offline scan OCR"},
            {"id": "merge_pdf", "label": "Merge PDFs", "kind": "pdf", "desc": "Combine documents"},
            {"id": "split_pdf", "label": "Split PDF", "kind": "pdf", "desc": "One file per page"},
            {"id": "epub_txt", "label": "EPUB → TXT/PDF", "kind": "document", "desc": "E-book to text"},
            {"id": "md_html", "label": "MD → HTML/PDF", "kind": "document", "desc": "Rendered markdown"},
            {"id": "srt_vtt", "label": "Subtitle Convert", "kind": "document", "desc": "SRT ↔ VTT + shift"},
            {"id": "csv_xlsx", "label": "CSV ↔ XLSX", "kind": "document", "desc": "Spreadsheets both ways"},
            {"id": "font_report", "label": "Font Report", "kind": "font", "desc": "Family & license info"},
            {"id": "video_thumbnails", "label": "Thumbnail Grid", "kind": "video", "desc": "9-frame sheet"},
            {"id": "video_frames", "label": "All Frames", "kind": "video", "desc": "Every frame as PNG"},
            {"id": "burn_subtitles", "label": "Burn Subtitles", "kind": "video", "desc": "Permanent subs"},
            {"id": "hash_file", "label": "Checksums", "kind": "generic", "desc": "MD5/SHA1/SHA256"},
            {"id": "quick_zip", "label": "ZIP / Extract", "kind": "archive", "desc": "Bundle or unpack"},
        ]
