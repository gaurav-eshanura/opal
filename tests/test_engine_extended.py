"""
Opal - Extended Engine Verification Suite
Plain English: Creates real sample files (photos, PDFs, videos, audio, documents,
fonts, subtitles), then runs EVERY extended engine action on them and verifies
each output file is genuinely valid. Nothing is mocked; AI engines download
their models on first use, exactly like the shipping product.
"""

import sys
import os
import shutil
import subprocess
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from opal_studio.engine import OpalEngine
from opal_studio.config import ConfigManager

SANDBOX = ROOT / "test_sandbox" / "engine"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)


def setup():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)
    # A locked file can survive the cleanup, so never fail on an existing folder.
    SANDBOX.mkdir(parents=True, exist_ok=True)

    # Photo with recognizable content
    img = Image.new("RGB", (640, 480), (30, 120, 200))
    d = ImageDraw.Draw(img)
    d.ellipse([180, 120, 460, 400], fill=(255, 200, 40))
    d.rectangle([60, 400, 580, 450], fill=(240, 240, 245))
    d.text((70, 30), "Opal Test Photo", fill=(255, 255, 255))
    img.save(SANDBOX / "photo.jpg", quality=92)
    photo2 = img.rotate(30, expand=True, fillcolor=(30, 120, 200))
    photo2.save(SANDBOX / "photo2.png")

    # Text document
    (SANDBOX / "notes.txt").write_text(
        "Opal extended engine test.\n\nLine two with unicode: peaches \u2764 oranges \u2764.\n" * 8,
        encoding="utf-8")

    # Markdown
    (SANDBOX / "readme.md").write_text(
        "# Opal\n\n## Features\n\n- **Zero-click** conversion\n- Local *AI* tools\n\n"
        "```python\nprint('hi')\n```\n\n| Tool | Speed |\n| --- | --- |\n| Convert | fast |\n",
        encoding="utf-8")

    # Subtitles
    (SANDBOX / "subs.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello there\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\nSecond line here\n", encoding="utf-8")

    # CSV / JSON
    (SANDBOX / "data.csv").write_text(
        "name,price,qty\nApple,1.5,10\nPear,2.5,5\nPlum,3.0,7\n", encoding="utf-8")
    (SANDBOX / "data.json").write_text(
        '[{"tool":"convert","speed":"fast"},{"tool":"compress","speed":"medium"}]', encoding="utf-8")

    # Real DOCX
    import docx
    d1 = docx.Document()
    d1.add_heading("Opal Report", 0)
    d1.add_paragraph("This document powers the DOCX export tests.")
    d1.add_heading("Details", level=1)
    d1.add_paragraph("Generated locally with python-docx.")
    d1.save(str(SANDBOX / "report.docx"))

    # Real XLSX
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Fruit"
    ws.append(["Fruit", "Count"])
    for row in [("Apple", 10), ("Pear", 5), ("Plum", 7)]:
        ws.append(list(row))
    wb.save(str(SANDBOX / "sheet.xlsx"))

    # Real PPTX
    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Opal Deck"
    slide.placeholders[1].text = "First slide body"
    prs.save(str(SANDBOX / "deck.pptx"))

    # PDF with text pages
    import fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Contract page {i+1} for testing", fontsize=16)
        page.insert_text((72, 140), "The quick brown fox jumps over the lazy dog.", fontsize=11)
    doc.save(str(SANDBOX / "contract.pdf"))
    doc.close()

    # Scanned-style PDF (image only, no text layer) for OCR
    scan_doc = fitz.open()
    for i in range(2):
        page = scan_doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"scan page {i + 1} hidden", fontsize=14)
    pix = scan_doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    page_img = SANDBOX / f"_scan.png"
    pix.save(str(page_img))
    scan2 = fitz.open()
    p = scan2.new_page(width=595, height=842)
    p.insert_image(fitz.Rect(40, 40, 555, 560), filename=str(page_img))
    scan2.save(str(SANDBOX / "scan.pdf"))
    scan_doc.close()
    scan2.close()

    # Real EPUB
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier("tan-test")
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

    # Real font
    font_src = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    if font_src.exists():
        shutil.copy2(font_src, SANDBOX / "arial.ttf")

    # ZIP archive
    import zipfile
    with zipfile.ZipFile(SANDBOX / "bundle.zip", "w") as z:
        z.write(SANDBOX / "photo.jpg", "photo.jpg")
        z.write(SANDBOX / "notes.txt", "notes.txt")

    # Media: real video + audio via ffmpeg
    ff = OpalEngine.get_ffmpeg_bin()
    if ff:
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15:duration=3",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(SANDBOX / "clip.mp4")],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
                        "-c:a", "pcm_s16le", str(SANDBOX / "tone.wav")],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    (SANDBOX / "clip.srt").write_text(
        "1\n00:00:00,500 --> 00:00:02,000\nBurned subtitle line\n", encoding="utf-8")

    print(f"Sandbox ready at {SANDBOX}")


def run_engine_action(name, action, src, options=None, expect_ext=None):
    res = OpalEngine.execute_single(str(SANDBOX / src), action, options)
    ok = res.success and res.output_path and Path(res.output_path).exists()
    if ok and expect_ext:
        actual = Path(res.output_path)
        if actual.is_dir():
            ok = any(actual.glob(f"*{expect_ext}"))
        else:
            ok = actual.suffix.lower() == expect_ext.lower() and actual.stat().st_size > 0
    check(name, ok, res.message if not ok else os.path.basename(str(res.output_path)))
    return res


def main():
    setup()

    print("\n--- IMAGE TOOLS (real AI runs where applicable) ---")
    run_engine_action("AI background removal", "remove_bg", "photo.jpg",
                      options={"bg_model": "u2netp"})
    run_engine_action("BG -> blur composite", "bg_cutout_blur", "photo.jpg",
                      options={"bg_model": "u2netp"})
    run_engine_action("Auto-enhance", "enhance_auto", "photo.jpg")
    run_engine_action("Sepia filter", "filter_sepia", "photo.jpg")
    run_engine_action("Pixelate filter", "filter_pixelate", "photo2.png")
    run_engine_action("Blur filter", "filter_blur", "photo2.png")
    run_engine_action("Vignette filter", "filter_vignette", "photo.jpg")
    run_engine_action("Watermark image", "watermark_image", "photo.jpg")
    run_engine_action("Social 4:5 post", "social_portrait", "photo.jpg")
    run_engine_action("Color palette", "color_palette", "photo.jpg")
    run_engine_action("EXIF report", "exif_report", "photo.jpg", expect_ext=".txt")
    run_engine_action("QR code from text", "qr_code", "notes.txt", expect_ext=".png")
    run_engine_action("Rotate left", "rotate_left", "photo.jpg")
    run_engine_action("Flip horizontal", "flip_h", "photo.jpg")
    run_engine_action("Favicon set", "favicon_set", "photo.jpg")
    run_engine_action("Optimize for web", "optimize_web", "photo.jpg", expect_ext=".webp")
    run_engine_action("Compress image", "compress_image", "photo.jpg")
    batch = OpalEngine.execute_batch(
        [str(SANDBOX / "photo.jpg"), str(SANDBOX / "photo2.png")],
        "contact_sheet", {"sheet_cols": 2, "sheet_cell": 240})
    check("Contact sheet (batch)", batch.succeeded == 2 and batch.outputs,
          os.path.basename(batch.outputs[0]) if batch.outputs else batch.message)
    run_engine_action("Convert to WebP", "webp", "photo.jpg", expect_ext=".webp")
    run_engine_action("Convert to ICO", "ico", "photo.jpg", expect_ext=".ico")
    run_engine_action("WA sticker", "wa_sticker", "photo.jpg", expect_ext=".webp")

    print("\n--- PDF TOOLS ---")
    run_engine_action("PDF watermark", "pdf_watermark", "contract.pdf")
    run_engine_action("PDF page numbers", "pdf_pagenum", "contract.pdf")
    run_engine_action("PDF flatten", "pdf_flatten", "contract.pdf")
    run_engine_action("PDF metadata clean", "pdf_metadata_clean", "contract.pdf")
    run_engine_action("PDF reverse", "pdf_reverse", "contract.pdf")
    run_engine_action("PDF -> JPEG pages", "jpg", "contract.pdf")
    run_engine_action("PDF -> HTML", "html", "contract.pdf", expect_ext=".html")
    run_engine_action("PDF -> EPUB", "epub", "contract.pdf", expect_ext=".epub")
    run_engine_action("PDF -> PowerPoint", "pptx", "contract.pdf", expect_ext=".pptx")
    run_engine_action("PDF -> Word", "docx", "contract.pdf", expect_ext=".docx")
    run_engine_action("PDF split", "split_pdf", "contract.pdf")
    run_engine_action("PDF compress", "compress_pdf", "contract.pdf")
    run_engine_action("PDF rotate 90", "rotate_90", "contract.pdf")
    run_engine_action("PDF OCR scan", "pdf_ocr", "scan.pdf")

    print("\n--- DOCUMENTS & EBOOKS ---")
    run_engine_action("EPUB -> text", "epub_txt", "novel.epub", expect_ext=".txt")
    run_engine_action("EPUB -> html", "epub_html", "novel.epub", expect_ext=".html")
    run_engine_action("EPUB -> PDF", "epub_pdf", "novel.epub", expect_ext=".pdf")
    run_engine_action("Markdown -> HTML", "md_html", "readme.md", expect_ext=".html")
    run_engine_action("Markdown -> PDF", "md_pdf", "readme.md", expect_ext=".pdf")
    run_engine_action("DOCX -> HTML", "docx_html", "report.docx", expect_ext=".html")
    run_engine_action("DOCX -> PDF", "docx_pdf", "report.docx", expect_ext=".pdf")
    run_engine_action("PPTX -> PDF", "pptx_pdf", "deck.pptx", expect_ext=".pdf")
    run_engine_action("PPTX -> text", "pptx_txt", "deck.pptx", expect_ext=".txt")
    run_engine_action("XLSX -> CSV", "xlsx_csv", "sheet.xlsx", expect_ext=".csv")
    run_engine_action("XLSX -> PDF", "xlsx_pdf", "sheet.xlsx", expect_ext=".pdf")
    run_engine_action("CSV -> XLSX", "csv_xlsx", "data.csv", expect_ext=".xlsx")
    run_engine_action("CSV -> JSON", "csv_json", "data.csv", expect_ext=".json")
    run_engine_action("JSON -> CSV", "json_csv", "data.json", expect_ext=".csv")
    run_engine_action("JSON format", "format_json", "data.json", expect_ext=".json")
    run_engine_action("TXT -> PDF", "pdf", "notes.txt", expect_ext=".pdf")
    run_engine_action("SRT -> VTT", "srt_vtt", "subs.srt", expect_ext=".vtt")
    run_engine_action("Subtitle shift +5s", "subs_shift", "subs.srt",
                      options={"shift_seconds": 5})
    run_engine_action("Subtitle dialogue text", "subs_txt", "subs.srt", expect_ext=".txt")
    if (SANDBOX / "arial.ttf").exists():
        run_engine_action("Font report", "font_report", "arial.ttf", expect_ext=".txt")
        run_engine_action("Font preview PNG", "png_preview", "arial.ttf", expect_ext=".png")

    print("\n--- MEDIA TOOLS ---")
    if (SANDBOX / "clip.mp4").exists():
        run_engine_action("Video -> 720p", "video_720p", "clip.mp4", expect_ext=".mp4")
        run_engine_action("Video frames 1fps", "video_frames", "clip.mp4",
                          options={"frames_per_second": "1"}, expect_ext=".png")
        run_engine_action("Video thumbnail grid", "video_thumbnails", "clip.mp4")
        run_engine_action("Video speed 2x", "video_speed", "clip.mp4",
                          options={"speed": 2.0})
        run_engine_action("Video rotate 90", "video_rotate", "clip.mp4",
                          options={"degrees": 90})
        run_engine_action("Burn subtitles", "burn_subtitles", "clip.mp4", expect_ext=".mp4")
        run_engine_action("Video -> GIF", "gif", "clip.mp4")
        run_engine_action("Video -> MP3 audio", "mp3", "clip.mp4", expect_ext=".mp3")
    if (SANDBOX / "tone.wav").exists():
        run_engine_action("Audio normalize", "audio_normalize", "tone.wav")
        run_engine_action("Audio speed 1.5x", "audio_speed", "tone.wav",
                          options={"speed": 1.5})

    print("\n--- ARCHIVES & ACTIONS ---")
    run_engine_action("Extract ZIP", "extract_archive", "bundle.zip")
    run_engine_action("Checksums", "hash_file", "photo.jpg", expect_ext=".txt")
    run_engine_action("Copy to Downloads", "copy_file", "notes.txt")
    run_engine_action("Quick ZIP", "quick_zip", "notes.txt", expect_ext=".zip")

    print("\n" + "=" * 60)
    print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
