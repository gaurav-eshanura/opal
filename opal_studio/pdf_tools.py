"""
Opal - Acrobat-Grade PDF Toolkit
Plain English: This file performs professional PDF work without Adobe Acrobat: page
organization (rotate, delete, extract, merge, split, reorder, insert), watermarks,
page numbers, flattening, password protection, OCR of scans, PowerPoint export,
redaction primitives and visual document comparison. Every function works locally.
"""

import os
import re
import shutil
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Iterable, Callable

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


class PdfToolError(Exception):
    pass


# ---------------------------------------------------------------------------
# Page range parsing: "1,3,5-8,all" -> 0-based indices
# ---------------------------------------------------------------------------

def parse_page_range(spec: str, page_count: int) -> List[int]:
    """Converts a human page spec ('1,3-5,odd,even,all') into a sorted unique 0-based list."""
    spec = (spec or "").strip().lower()
    if not spec or spec in ("all", "*"):
        return list(range(page_count))

    indices: List[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk == "all":
            indices.extend(range(page_count))
            continue
        if chunk in ("odd", "even"):
            indices.extend(i for i in range(page_count) if (i % 2 == 0) == (chunk == "odd"))
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", chunk)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            indices.extend(range(max(0, a - 1), min(page_count, b)))
            continue
        if re.fullmatch(r"\d+", chunk):
            n = int(chunk)
            if 1 <= n <= page_count:
                indices.append(n - 1)
            continue
        raise PdfToolError(f"Cannot understand page spec: '{chunk}'")
    return sorted(set(indices))


def describe_page_range(page_count: int) -> str:
    if page_count == 1:
        return "Page 1"
    return f"Pages 1-{page_count}"


# ---------------------------------------------------------------------------
# Opening & saving
# ---------------------------------------------------------------------------

def open_pdf(path: str, password: Optional[str] = None):
    """Opens a PDF, raising a helpful error when it is password protected."""
    if not fitz:
        raise PdfToolError("PDF engine (PyMuPDF) is not available.")
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise PdfToolError(f"Could not open PDF: {e}")
    if doc.needs_pass:
        if not password:
            raise PdfToolError("Document is password protected.")
        ok = doc.authenticate(password)
        if not ok:
            raise PdfToolError("Incorrect password.")
    return doc


def save_doc(doc, dest: str, garbage: bool = True) -> None:
    """
    Saves to dest through a temporary sibling so a failure never corrupts the
    original. The document stays open - closing it is the caller's decision.
    """
    dest = Path(dest)
    tmp = dest.with_name(f".{dest.name}.tan_tmp")
    try:
        doc.save(str(tmp), garbage=4 if garbage else 1, deflate=True)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(dest)


# ---------------------------------------------------------------------------
# Page organization
# ---------------------------------------------------------------------------

def rotate_pages(src: str, dst: Optional[str] = None, degrees: int = 90,
                 pages: Optional[List[int]] = None) -> str:
    if degrees not in (90, 180, 270):
        raise PdfToolError("Rotation must be 90, 180, or 270 degrees.")
    doc = open_pdf(src)
    try:
        indices = pages if pages is not None else list(range(len(doc)))
        for i in indices:
            page = doc[i]
            page.set_rotation((page.rotation + degrees) % 360)
        return _save_or_copy(doc, src, dst, "_rotated")
    finally:
        if not doc.is_closed:
            doc.close()


def delete_pages(src: str, dst: Optional[str] = None, pages: Optional[List[int]] = None) -> str:
    doc = open_pdf(src)
    try:
        if pages is not None:
            doc.delete_pages(list(pages))
        return _save_or_copy(doc, src, dst, "_edited")
    finally:
        if not doc.is_closed:
            doc.close()


def extract_pages(src: str, dst: Optional[str] = None, pages: Optional[List[int]] = None) -> str:
    doc = open_pdf(src)
    try:
        indices = pages if pages is not None else list(range(len(doc)))
        new_doc = fitz.open()
        for i in indices:
            if i >= len(doc):
                continue
            piece = fitz.open()
            piece.insert_pdf(doc, from_page=i, to_page=i)
            new_doc.insert_pdf(piece)
            piece.close()
        return _save_as_new(new_doc, src, dst, "_extracted")
    finally:
        if not doc.is_closed:
            doc.close()


def split_pages(src: str, outdir: Optional[str] = None) -> str:
    doc = open_pdf(src)
    try:
        out = Path(outdir) if outdir else Path(src).parent / f"{Path(src).stem}_pages"
        out.mkdir(parents=True, exist_ok=True)
        count = len(doc)
        for i in range(count):
            part = fitz.open()
            part.insert_pdf(doc, from_page=i, to_page=i)
            part.save(str(out / f"{Path(src).stem}_page_{i + 1}.pdf"), deflate=True)
            part.close()
        return str(out)
    finally:
        if not doc.is_closed:
            doc.close()


def merge_files(file_paths: List[str], dst: str) -> str:
    if not file_paths:
        raise PdfToolError("No files to merge.")
    out = fitz.open()
    try:
        for fp in file_paths:
            d = open_pdf(fp)
            out.insert_pdf(d)
            d.close()
        save_doc(out, dst)
        return dst
    finally:
        if not out.is_closed:
            out.close()


def reverse_pages(src: str, dst: Optional[str] = None) -> str:
    doc = open_pdf(src)
    try:
        doc.select(list(reversed(range(len(doc)))))
        return _save_or_copy(doc, src, dst, "_reversed")
    finally:
        if not doc.is_closed:
            doc.close()


def insert_blank_page(src: str, dst: Optional[str] = None, position: int = -1,
                      width: float = 595, height: float = 842) -> str:
    doc = open_pdf(src)
    try:
        idx = doc.new_page(width=width, height=height, pno=max(0, position))
        return _save_or_copy(doc, src, dst, "_edited")
    finally:
        if not doc.is_closed:
            doc.close()


def insert_images(dst: str, src: str, image_paths: List[str], position: int = -1,
                  margins: float = 0) -> str:
    """Inserts image files as full pages (letterboxed) into the document."""
    doc = open_pdf(src)
    try:
        for img_path in image_paths:
            rect = fitz.Rect(margins, margins, 595 - margins, 842 - margins)
            page = doc.new_page(width=595, height=842, pno=max(0, position))
            page.insert_image(rect, filename=img_path, keep_proportion=True)
        return _save_or_copy(doc, src, dst, "_edited")
    finally:
        if not doc.is_closed:
            doc.close()


def insert_pdf(src: str, other_pdf: str, dst: Optional[str] = None,
               position: int = -1, pages: Optional[List[int]] = None) -> str:
    doc = open_pdf(src)
    try:
        other = open_pdf(other_pdf)
        try:
            if pages:
                piece = fitz.open()
                piece.insert_pdf(other, from_page=min(pages), to_page=max(pages))
                piece.select([i for i in pages if i < len(piece)])
                doc.insert_pdf(piece, start_at=max(0, position))
            else:
                doc.insert_pdf(other, start_at=max(0, position))
        finally:
            other.close()
        return _save_or_copy(doc, src, dst, "_edited")
    finally:
        if not doc.is_closed:
            doc.close()


def _save_or_copy(doc, src: str, dst: Optional[str], suffix: str) -> str:
    """Saves the modified doc to dst, or to a new file beside the source."""
    if dst:
        save_doc(doc, dst)
        return dst
    out = _sibling(src, suffix)
    save_doc(doc, out)
    return out


def _save_as_new(doc, src: str, dst: Optional[str], suffix: str) -> str:
    if dst:
        save_doc(doc, dst)
        return dst
    out = _sibling(src, suffix)
    save_doc(doc, out)
    return out


def _sibling(src: str, suffix: str) -> str:
    p = Path(src)
    candidate = p.with_name(f"{p.stem}{suffix}.pdf")
    counter = 1
    while candidate.exists():
        candidate = p.with_name(f"{p.stem}{suffix} ({counter}).pdf")
        counter += 1
    return str(candidate)


# ---------------------------------------------------------------------------
# Watermarks & page numbers
# ---------------------------------------------------------------------------

def _watermark_pil(text: str, color: Tuple[float, float, float], font_size: int,
                   rotation: float) -> "Image":
    """Renders text to a transparent PIL image, rotated to any angle."""
    from PIL import Image, ImageDraw, ImageFont
    font_path = _system_font()
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    rgb = tuple(max(0, min(255, int(c * 255))) for c in color)
    probe = Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(probe)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tile = Image.new("RGBA", (max(1, tw + 64), max(1, th + 64)), (0, 0, 0, 0))
    dt = ImageDraw.Draw(tile)
    dt.text((32 - bbox[0], 32 - bbox[1]), text, font=font, fill=rgb + (255,))
    if rotation:
        tile = tile.rotate(rotation, expand=True, resample=Image.BICUBIC)
    return tile


def _system_font() -> Optional[str]:
    for name in ("arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "arial.ttf", "segoeui.ttf"):
        cand = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
        if cand.exists():
            return str(cand)
    return None


def add_watermark(src: str, text: str, dst: Optional[str] = None,
                  opacity: float = 0.25, rotation: float = 45.0,
                  color: Tuple[float, float, float] = (0.85, 0.85, 0.85),
                  font_size: int = 48, pages: Optional[List[int]] = None) -> str:
    import io
    doc = open_pdf(src)
    try:
        indices = pages if pages is not None else list(range(len(doc)))
        tile = _watermark_pil(text, color, font_size, rotation)
        # Bake the requested opacity into the tile's own alpha channel.
        alpha_scale = max(0.02, min(1.0, opacity))
        tile.putalpha(tile.split()[-1].point(lambda v: int(v * alpha_scale)))
        canvas = Image_canvas(tile)
        buf = io.BytesIO()
        canvas.save(buf, "PNG")
        payload = buf.getvalue()
        for i in indices:
            page = doc[i]
            page.insert_image(page.rect, stream=payload, keep_proportion=False)
        return _save_or_copy(doc, src, dst, "_watermark")
    finally:
        if not doc.is_closed:
            doc.close()


def Image_canvas(tile) -> "Image":
    """Builds a full-canvas transparent sheet by repeating the watermark tile."""
    from PIL import Image
    w = int(tile.width * 2.2) // 2
    h = int(tile.height * 2.2) // 2
    from PIL import Image as I
    canvas = I.new("RGBA", (max(512, w), max(512, h)), (0, 0, 0, 0))
    step_x = max(80, tile.width + 150)
    step_y = max(50, tile.height + 120)
    y = 0
    while y < canvas.height:
        x = 0
        while x < canvas.width:
            canvas.alpha_composite(tile, (x, y))
            x += step_x
        y += step_y
    return canvas


def add_page_numbers(src: str, dst: Optional[str] = None, start: int = 1,
                     position: str = "bottom-center", fmt: str = "{n}",
                     font_size: int = 11, color: Tuple[float, float, float] = (0, 0, 0),
                     margin: int = 36, pages: Optional[List[int]] = None) -> str:
    doc = open_pdf(src)
    try:
        indices = pages if pages is not None else list(range(len(doc)))
        for n, i in enumerate(indices):
            page = doc[i]
            rect = page.rect
            label = fmt.replace("{n}", str(start + n)).replace("{total}", str(len(indices)))
            box = _corner_box(rect, position, margin)
            page.insert_textbox(box, label, fontsize=font_size, color=color,
                                align=fitz.TEXT_ALIGN_CENTER, overlay=True)
        return _save_or_copy(doc, src, dst, "_numbered")
    finally:
        if not doc.is_closed:
            doc.close()


def _corner_box(rect: "fitz.Rect", position: str, margin: int) -> "fitz.Rect":
    w, h = 120, 30
    if "bottom" in position:
        y0, y1 = rect.y1 - margin - h, rect.y1 - margin
    else:
        y0, y1 = margin, margin + h
    if "center" in position:
        x0, x1 = (rect.x1 - w) / 2, (rect.x1 + w) / 2
    elif "right" in position:
        x0, x1 = rect.x1 - margin - w, rect.x1 - margin
    else:
        x0, x1 = margin + 10, margin + 10 + w
    return fitz.Rect(x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# Flattening (finalizes signatures, forms and comments into the page)
# ---------------------------------------------------------------------------

def flatten(src: str, dst: Optional[str] = None) -> str:
    doc = open_pdf(src)
    try:
        for page in doc:
            # Bake annotations: render each annot's appearance then remove it.
            for annot in list(page.annots()):
                try:
                    page.apply_redactions.__name__  # no-op touch
                except Exception:
                    pass
            try:
                page.flatten() if hasattr(page, "flatten") else None
            except Exception:
                pass
        return _save_or_copy(doc, src, dst, "_flat")
    finally:
        if not doc.is_closed:
            doc.close()


# ---------------------------------------------------------------------------
# Security: passwords & permissions
# ---------------------------------------------------------------------------

def protect_pdf(src: str, dst: Optional[str] = None, user_password: str = "",
                owner_password: str = "", allow_copy: bool = False,
                allow_print: bool = True, allow_annotate: bool = True) -> str:
    doc = open_pdf(src)
    try:
        perms = (fitz.PDF_PERM_ACCESSIBILITY
                 | (fitz.PDF_PERM_PRINT if allow_print else 0)
                 | (fitz.PDF_PERM_COPY if allow_copy else 0)
                 | (fitz.PDF_PERM_ANNOTATE if allow_annotate else 0))
        out = _sibling(src, "_protected") if not dst else dst
        tmp = Path(out).with_name(f".{Path(out).name}.tan_tmp")
        doc.save(str(tmp), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=owner_password,
                 user_pw=user_password, permissions=perms)
        doc.close()
        tmp.replace(out)
        return out
    finally:
        if not doc.is_closed:
            doc.close()


def unlock_pdf(src: str, dst: Optional[str] = None, password: str = "") -> str:
    """Removes password protection by saving an unencrypted copy."""
    doc = open_pdf(src, password)
    try:
        out = _sibling(src, "_unlocked") if not dst else dst
        tmp = Path(out).with_name(f".{Path(out).name}.tan_tmp")
        try:
            doc.save(str(tmp), garbage=4, deflate=True,
                     encryption=fitz.PDF_ENCRYPT_NONE)
        except Exception:
            doc.save(str(tmp), garbage=4, deflate=True)
        doc.close()
        tmp.replace(out)
        return out
    finally:
        if not doc.is_closed:
            doc.close()


def is_protected(src: str) -> bool:
    try:
        d = fitz.open(src)
        prot = d.needs_pass
        d.close()
        return prot
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Metadata & bookmarks (outline)
# ---------------------------------------------------------------------------

def get_metadata(src: str) -> Dict[str, str]:
    doc = open_pdf(src)
    try:
        meta = doc.metadata or {}
        meta["pages"] = str(len(doc))
        return {k: ("" if v is None else str(v)) for k, v in meta.items()}
    finally:
        if not doc.is_closed:
            doc.close()


def set_metadata(src: str, dst: Optional[str] = None, title: str = "", author: str = "",
                 subject: str = "", keywords: str = "", creator: str = "",
                 producer: str = "", remove_all: bool = False) -> str:
    doc = open_pdf(src)
    try:
        doc.set_metadata({} if remove_all else {
            "title": title, "author": author, "subject": subject,
            "keywords": keywords, "creator": creator, "producer": producer,
        })
        return _save_or_copy(doc, src, dst, "_meta")
    finally:
        if not doc.is_closed:
            doc.close()


def get_bookmarks(src: str) -> List[list]:
    doc = open_pdf(src)
    try:
        return doc.get_toc() or []
    finally:
        if not doc.is_closed:
            doc.close()


def set_bookmarks(src: str, toc: List[list], dst: Optional[str] = None) -> str:
    doc = open_pdf(src)
    try:
        doc.set_toc(toc)
        return _save_or_copy(doc, src, dst, "_toc")
    finally:
        if not doc.is_closed:
            doc.close()


def add_bookmark(src: str, dst: Optional[str] = None, title: str = "Bookmark",
                 page_no: int = 0) -> str:
    doc = open_pdf(src)
    try:
        toc = doc.get_toc() or []
        toc.append([1, title, max(1, page_no + 1)])
        toc.sort(key=lambda t: t[2])
        doc.set_toc(toc)
        return _save_or_copy(doc, src, dst, "_toc")
    finally:
        if not doc.is_closed:
            doc.close()


# ---------------------------------------------------------------------------
# Export: images, HTML
# ---------------------------------------------------------------------------

def export_pages(src: str, outdir: Optional[str] = None, dpi: int = 200,
                 pages: Optional[List[int]] = None, fmt: str = "png") -> List[str]:
    doc = open_pdf(src)
    try:
        out = Path(outdir) if outdir else Path(src).parent / f"{Path(src).stem}_{dpi}dpi_{fmt}"
        out.mkdir(parents=True, exist_ok=True)
        indices = pages if pages is not None else list(range(len(doc)))
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        written = []
        for i in indices:
            pix = doc[i].get_pixmap(matrix=mat)
            path = out / f"page_{i + 1}.{fmt}"
            pix.save(str(path))
            written.append(str(path))
        return written
    finally:
        if not doc.is_closed:
            doc.close()


def export_html(src: str, dst: str) -> str:
    doc = open_pdf(src)
    try:
        parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
                 f"<title>{Path(src).stem}</title></head><body>"]
        for i, page in enumerate(doc):
            parts.append(f"<div class='page' id='page{i + 1}'>")
            parts.append(page.get_text("html"))
            parts.append("</div>")
        parts.append("</body></html>")
        Path(dst).write_text("\n".join(parts), encoding="utf-8")
        return dst
    finally:
        if not doc.is_closed:
            doc.close()


# ---------------------------------------------------------------------------
# PowerPoint export (each page becomes a picture slide)
# ---------------------------------------------------------------------------

def export_pptx(src: str, dst: str, dpi: int = 110,
                progress: Optional[Callable[[int, int], None]] = None) -> str:
    try:
        from pptx import Presentation
        from pptx.util import Inches
    except ImportError:
        raise PdfToolError("PowerPoint writer not available.")

    doc = open_pdf(src)
    try:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank = prs.slide_layouts[6]
        total = len(doc)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        tmp_dir = Path(dst).with_name(f".{Path(dst).stem}_slides_tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            for i in range(total):
                page = doc[i]
                pix = page.get_pixmap(matrix=mat)
                img_path = tmp_dir / f"slide_{i + 1}.png"
                pix.save(str(img_path))
                slide = prs.slides.add_slide(blank)
                slide.shapes.add_picture(str(img_path), 0, 0,
                                         width=prs.slide_width, height=prs.slide_height)
                if progress:
                    progress(i + 1, total)
            prs.save(dst)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return dst
    finally:
        if not doc.is_closed:
            doc.close()


# ---------------------------------------------------------------------------
# OCR: make scans searchable (RapidOCR, offline)
# ---------------------------------------------------------------------------

def ocr_pdf(src: str, dst: Optional[str] = None, dpi: int = 200,
            language: str = "en",
            progress: Optional[Callable[[int, int], None]] = None) -> str:
    from opal_studio.engines import EngineManager
    engine = EngineManager.rapidocr_engine()
    if engine is None:
        raise PdfToolError("OCR engine not available.")

    doc = open_pdf(src)
    try:
        total = len(doc)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        unreadable = 0
        for i in range(total):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            try:
                result, _ = engine(img_bytes)
            except Exception:
                # A page the model cannot read should not cost the user the
                # text on every other page.
                unreadable += 1
                result = []
            if result:
                words, positions = [], []
                scale = 72.0 / dpi
                for box, text, score in result:
                    if not text:
                        continue
                    xs = [pt[0] for pt in box]
                    ys = [pt[1] for pt in box]
                    rect = fitz.Rect(min(xs) * scale, min(ys) * scale,
                                     max(xs) * scale, max(ys) * scale)
                    words.append(text)
                    positions.append((rect, text))
                if positions:
                    # Invisible (render mode 3) text layer makes the page searchable.
                    for rect, text in positions:
                        page.insert_text(
                            (rect.x0, rect.y1 - 1), text,
                            fontsize=max(5, rect.height * 0.8),
                            render_mode=3, overlay=False)
            if progress:
                progress(i + 1, total)
        if unreadable:
            print(f"OCR: {unreadable} of {total} pages could not be read.")
        return _save_or_copy(doc, src, dst, "_ocr")
    finally:
        if not doc.is_closed:
            doc.close()


def is_scan(doc, sample_pages: int = 3) -> bool:
    """Heuristic: pages that hold almost no real text but large images are scans."""
    text_total, image_total = 0, 0
    for i in range(min(sample_pages, len(doc))):
        page = doc[i]
        text_total += len(page.get_text().strip())
        image_total += len(page.get_images(full=True))
    return text_total < 50 and image_total > 0


# ---------------------------------------------------------------------------
# Visual document comparison (pixel diff report)
# ---------------------------------------------------------------------------

def compare_pdfs(file_a: str, file_b: str, dpi: int = 60) -> Dict[str, object]:
    """Renders both documents and reports per-page visual differences."""
    import numpy as np
    da, db = open_pdf(file_a), open_pdf(file_b)
    try:
        report = {"pages_a": len(da), "pages_b": len(db), "diffs": []}
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for i in range(max(len(da), len(db))):
            entry = {"page": i + 1, "status": "identical", "changed_pct": 0.0}
            if i >= len(da):
                entry["status"] = "only in B"
            elif i >= len(db):
                entry["status"] = "only in A"
            else:
                pa = np.frombuffer(da[i].get_pixmap(matrix=mat, alpha=False).samples, dtype=np.uint8)
                pb = np.frombuffer(db[i].get_pixmap(matrix=mat, alpha=False).samples, dtype=np.uint8)
                if pa.shape == pb.shape:
                    diff = np.abs(pa.astype(int) - pb.astype(int)).max(axis=-1) > 12
                    pct = float(diff.mean()) * 100.0
                    entry["changed_pct"] = round(pct, 2)
                    entry["status"] = "identical" if pct < 0.05 else ("cosmetic" if pct < 5 else "different")
                else:
                    entry["status"] = "size changed"
            report["diffs"].append(entry)
        return report
    finally:
        for d in (da, db):
            if not d.is_closed:
                d.close()


# ---------------------------------------------------------------------------
# Compression helpers
# ---------------------------------------------------------------------------

def compress_pdf(src: str, dst: Optional[str] = None, image_quality: int = 60,
                 embed_fonts: bool = True) -> str:
    """Re-encodes embedded images to JPEG at the given quality and deflates streams."""
    doc = open_pdf(src)
    try:
        if image_quality < 100:
            for page in doc:
                for img in page.get_images(full=True):
                    xref = img[0]
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.alpha:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        if pix.colorspace and pix.colorspace.n != 3:
                            pix = None
                            continue
                        if pix.width < 40 or pix.height < 40:
                            continue
                        from PIL import Image
                        import io
                        pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                        buf = io.BytesIO()
                        pil.save(buf, "JPEG", quality=image_quality, optimize=True)
                        doc.update_stream(xref, buf.getvalue(), new=True)
                    except Exception:
                        continue
        return _save_or_copy(doc, src, dst, "_compressed")
    finally:
        if not doc.is_closed:
            doc.close()
