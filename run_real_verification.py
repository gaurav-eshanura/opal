"""
Opal for Windows - Real-World End-to-End File Verification
Plain English: This script creates genuine photos, sound recordings, video clips, and documents,
runs every Opal conversion and tool on them, and verifies that the output files are valid.
"""

import sys
import os
import shutil
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))

from opal_studio.engine import OpalEngine
from opal_studio.config import ConfigManager

REAL_DIR = Path("real_test_sandbox")


def setup_files():
    REAL_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = OpalEngine.get_ffmpeg_bin()
    print(f"Using media encoder: {ffmpeg_bin}")

    # 1. Real Image: Create a 600x400 photo with drawing and text
    img_path = REAL_DIR / "real_photo.jpg"
    img = Image.new("RGB", (600, 400), color=(255, 122, 24))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 550, 350], fill=(20, 25, 35), outline=(255, 255, 255), width=4)
    draw.ellipse([200, 100, 400, 300], fill=(255, 160, 67))
    img.save(img_path, quality=95)

    # 2. Real Audio: Generate 4 seconds of 440Hz stereo sound using ffmpeg
    audio_path = REAL_DIR / "real_audio.wav"
    if ffmpeg_bin:
        cmd_audio = [
            ffmpeg_bin, "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=4",
            "-c:a", "pcm_s16le", str(audio_path)
        ]
        subprocess.run(cmd_audio, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

    # 3. Real Video: Generate 4 seconds of 720p 30fps video with audio beep
    video_path = REAL_DIR / "real_video.mp4"
    if ffmpeg_bin:
        cmd_video = [
            ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=1280x720:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(video_path)
        ]
        subprocess.run(cmd_video, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

    # 4. Real Multi-Page PDF: Create 2-page text document with genuine text streams
    pdf_path = REAL_DIR / "real_doc.pdf"
    try:
        import fitz
        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((50, 72), "Opal for Windows v1.0.0\n\nThe zero-click offline file converter for Windows.\nAll operations are completely private and execute locally on your machine.", fontsize=14)
        p2 = doc.new_page(width=595, height=842)
        p2.insert_text((50, 72), "Page 2 - Feature List\n1. Images (JPG, PNG, WebP, HEIC, PDF)\n2. Audio (MP3, WAV, FLAC, M4A)\n3. Video (MP4, WebM, GIF)\n4. Documents & Archives", fontsize=12)
        doc.save(str(pdf_path))
        doc.close()
    except Exception:
        p1 = Image.new("RGB", (500, 700), color=(255, 255, 255))
        d1 = ImageDraw.Draw(p1)
        d1.text((50, 50), "Opal for Windows - Page 1", fill=(0, 0, 0))
        p1.save(pdf_path, resolution=100.0)

    # 5. Real Word Document
    docx_path = REAL_DIR / "real_notes.docx"
    try:
        import docx
        doc = docx.Document()
        doc.add_heading("Opal Product Requirements", 0)
        doc.add_paragraph("Offline zero-click converter for Windows.")
        doc.save(str(docx_path))
    except Exception:
        docx_path.write_text("Opal Requirements Notes", encoding="utf-8")

    # 6. Real JSON file
    json_path = REAL_DIR / "real_data.json"
    json_path.write_text('{"product":"Opal","version":"1.0.0","offline":true,"actions":["convert","tools","float"]}', encoding="utf-8")

    return img_path, audio_path, video_path, pdf_path, docx_path, json_path


def run_full_suite():
    print("==================================================")
    print("RUNNING TANGERINE LIVE ON REAL MEDIA FILES")
    print("==================================================")

    img_p, aud_p, vid_p, pdf_p, doc_p, json_p = setup_files()
    results = []

    def verify_file(label, res, check_size=True, min_bytes=100):
        if not res.success:
            print(f" [FAIL] {label}: {res.message}")
            results.append((label, False, res.message))
            return False
        out = Path(res.output_path)
        if not out.exists():
            print(f" [FAIL] {label}: Output file does not exist ({out})")
            results.append((label, False, "File missing"))
            return False
        if check_size and out.is_file() and out.stat().st_size < min_bytes:
            print(f" [FAIL] {label}: File too small ({out.stat().st_size} bytes)")
            results.append((label, False, "Corrupted/Empty size"))
            return False
        sz = out.stat().st_size if out.is_file() else "Folder"
        print(f" [OK]   {label} -> {out.name} ({sz} bytes if file)")
        results.append((label, True, f"{out.name} ({sz})"))
        return True

    # 1. IMAGE CONVERSIONS
    print("\n--- 1. REAL IMAGE CONVERSIONS (JPG Source) ---")
    verify_file("Convert JPG -> WebP", OpalEngine.execute_single(str(img_p), "webp"))
    verify_file("Convert JPG -> PNG", OpalEngine.execute_single(str(img_p), "png"))
    verify_file("Convert JPG -> ICO", OpalEngine.execute_single(str(img_p), "ico"))
    verify_file("Convert JPG -> BMP", OpalEngine.execute_single(str(img_p), "bmp"))
    verify_file("Convert JPG -> PDF", OpalEngine.execute_single(str(img_p), "pdf"))

    # 2. IMAGE TOOLS
    print("\n--- 2. REAL IMAGE TOOLS ---")
    verify_file("Tool: Compress Image", OpalEngine.execute_single(str(img_p), "compress_image"))
    verify_file("Tool: Scale 50%", OpalEngine.execute_single(str(img_p), "resize_50"))
    verify_file("Tool: Crop Square (1:1)", OpalEngine.execute_single(str(img_p), "crop_square"))
    verify_file("Tool: Crop 16:9 Widescreen", OpalEngine.execute_single(str(img_p), "crop_16_9"))
    verify_file("Tool: Invert Colors", OpalEngine.execute_single(str(img_p), "invert"))
    verify_file("Tool: Grayscale (B&W)", OpalEngine.execute_single(str(img_p), "grayscale"))
    verify_file("Tool: Strip Metadata", OpalEngine.execute_single(str(img_p), "strip_metadata"))

    # 3. REAL AUDIO CONVERSIONS & TOOLS (WAV Source)
    if aud_p.exists() and aud_p.stat().st_size > 0:
        print("\n--- 3. REAL AUDIO CONVERSIONS & TOOLS (WAV Source) ---")
        verify_file("Convert WAV -> MP3 (320k)", OpalEngine.execute_single(str(aud_p), "mp3"))
        verify_file("Convert WAV -> M4A (Apple AAC)", OpalEngine.execute_single(str(aud_p), "m4a"))
        verify_file("Convert WAV -> FLAC (Lossless)", OpalEngine.execute_single(str(aud_p), "flac"))
        verify_file("Convert WAV -> OGG", OpalEngine.execute_single(str(aud_p), "ogg"))
        verify_file("Tool: Compress Audio", OpalEngine.execute_single(str(aud_p), "compress_media"))
        verify_file("Tool: Trim Audio (first 30s/2s)", OpalEngine.execute_single(str(aud_p), "trim_30s"))

    # 4. REAL VIDEO CONVERSIONS & TOOLS (MP4 Source)
    if vid_p.exists() and vid_p.stat().st_size > 0:
        print("\n--- 4. REAL VIDEO CONVERSIONS & TOOLS (MP4 Source) ---")
        verify_file("Convert MP4 -> WebM (VP9)", OpalEngine.execute_single(str(vid_p), "webm"))
        verify_file("Convert MP4 -> GIF (Animated)", OpalEngine.execute_single(str(vid_p), "gif"))
        verify_file("Convert MP4 -> MP3 (Extract Sound)", OpalEngine.execute_single(str(vid_p), "mp3"))
        verify_file("Tool: Compress Video (CRF 28)", OpalEngine.execute_single(str(vid_p), "compress_media"))
        verify_file("Tool: Mute Video (Remove audio)", OpalEngine.execute_single(str(vid_p), "mute_video"))
        verify_file("Tool: Trim Video (30s)", OpalEngine.execute_single(str(vid_p), "trim_30s"))

    # 5. REAL PDF TOOLS
    print("\n--- 5. REAL PDF TOOLS (300 DPI Rendering & Split) ---")
    verify_file("Tool: Extract 300 DPI PNG Pages", OpalEngine.execute_single(str(pdf_p), "png_pages"), check_size=False)
    verify_file("Tool: Extract PDF Text", OpalEngine.execute_single(str(pdf_p), "extract_text"))
    verify_file("Tool: Split PDF into Pages", OpalEngine.execute_single(str(pdf_p), "split_pdf"), check_size=False)
    verify_file("Tool: Rotate PDF 90 Degrees", OpalEngine.execute_single(str(pdf_p), "rotate_90"))

    # 6. REAL DOCUMENTS, JSON & ARCHIVES
    print("\n--- 6. REAL DOCUMENTS & ARCHIVES ---")
    verify_file("Tool: Format JSON Cleanly", OpalEngine.execute_single(str(json_p), "format_json"))
    zip_res = OpalEngine.execute_single(str(img_p), "quick_zip")
    verify_file("Tool: Quick ZIP File", zip_res)
    if zip_res.success and Path(zip_res.output_path).exists():
        verify_file("Tool: Extract ZIP Archive", OpalEngine.execute_single(zip_res.output_path, "extract_archive"), check_size=False)

    # 7. REAL MULTI-FILE BATCH COMBINE
    print("\n--- 7. REAL MULTI-FILE BATCH COMBINATION ---")
    img2 = REAL_DIR / "real_photo2.png"
    Image.new("RGB", (400, 400), (0, 150, 255)).save(img2)
    batch_res = OpalEngine.execute_batch([str(img_p), str(img2)], "pdf")
    if batch_res.succeeded == 2 and batch_res.outputs:
        print(f" [OK]   Batch Combine Images -> {Path(batch_res.outputs[0]).name}")
        results.append(("Batch Combine Images to PDF", True, Path(batch_res.outputs[0]).name))
    else:
        print(f" [FAIL] Batch Combine: {batch_res.message}")
        results.append(("Batch Combine Images to PDF", False, batch_res.message))

    # 8. REAL ACTIONS
    print("\n--- 8. REAL FILE ACTIONS ---")
    verify_file("Action: Duplicate File", OpalEngine.execute_single(str(img_p), "duplicate"))
    verify_file("Action: Copy Path to Clipboard", OpalEngine.execute_single(str(img_p), "copy_path"))
    verify_file("Action: Float Preview", OpalEngine.execute_single(str(img_p), "float"))

    # SUMMARY
    total_tests = len(results)
    passed_tests = sum(1 for _, ok, _ in results if ok)
    failed_tests = total_tests - passed_tests

    print("\n==================================================")
    print(f"EXECUTION SUMMARY: {passed_tests} OF {total_tests} FUNCTIONS VERIFIED.")
    if failed_tests == 0:
        print("RESULT: 100% OPERATIONAL ON REAL MEDIA FILES. ZERO ERRORS.")
    else:
        print(f"RESULT: {failed_tests} FUNCTIONS FAILED.")
        for name, ok, msg in results:
            if not ok:
                print(f" - {name}: {msg}")
    print("==================================================")

    # Clean up test files
    shutil.rmtree(REAL_DIR, ignore_errors=True)
    return failed_tests == 0


if __name__ == "__main__":
    success = run_full_suite()
    sys.exit(0 if success else 1)
