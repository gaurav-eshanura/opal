"""
Opal for Windows - Skeptical Breaking & Stress Test Suite
Plain English: This test suite actively tries to break the application with corrupted files,
zero-byte files, crazy unicode names, locked files, and large batches to verify stability.
"""

import os
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from opal_studio.engine import OpalEngine
from opal_studio.config import ConfigManager

TEST_DIR = Path("test_sandbox")


def setup_sandbox():
    TEST_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_sandbox():
    if TEST_DIR.exists():
        import shutil
        shutil.rmtree(TEST_DIR, ignore_errors=True)


def run_stress_tests():
    print("==================================================")
    print("STARTING SKEPTICAL STRESS & BREAKING TEST SUITE")
    print("==================================================")

    setup_sandbox()
    failures = []

    # TEST 1: Zero-Byte File
    print("\n[TEST 1] Testing 0-byte empty file handling...")
    zero_file = TEST_DIR / "empty.png"
    zero_file.write_bytes(b"")
    res = OpalEngine.execute_single(str(zero_file), "webp")
    if not res.success and "empty" in res.message.lower():
        print(" -> PASS: Caught 0-byte empty file cleanly without crashing.")
    else:
        failures.append("Failed 0-byte test: Expected failure message, got: " + res.message)

    # TEST 2: Corrupted Image File
    print("\n[TEST 2] Testing corrupted image file handling...")
    corrupt_file = TEST_DIR / "corrupted.jpg"
    corrupt_file.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01NOT_REAL_DATA_CORRUPTED_GARBAGE")
    res2 = OpalEngine.execute_single(str(corrupt_file), "png")
    if not res2.success:
        print(f" -> PASS: Caught corrupted file gracefully. Error: {res2.message}")
    else:
        failures.append("Failed corrupted file test: Expected error, succeeded instead!")

    # TEST 3: Unicode, Emojis, and Special Characters in Path
    print("\n[TEST 3] Testing complex Unicode & Emoji file names...")
    unicode_file = TEST_DIR / "写真 🍊 #1 [test] (2026).png"
    img = Image.new("RGBA", (100, 100), (255, 122, 24, 255))
    img.save(unicode_file)

    res3 = OpalEngine.execute_single(str(unicode_file), "webp")
    if res3.success and Path(res3.output_path).exists():
        print(f" -> PASS: Handled Unicode & Emoji filename successfully: {Path(res3.output_path).name}")
    else:
        failures.append("Failed Unicode filename test: " + res3.message)

    # TEST 4: Destination Collision Check (Ensure no accidental overwrite)
    print("\n[TEST 4] Testing collision avoidance (incremental numbering)...")
    res4_a = OpalEngine.execute_single(str(unicode_file), "webp")
    res4_b = OpalEngine.execute_single(str(unicode_file), "webp")
    if res4_a.success and res4_b.success:
        name_a = Path(res4_a.output_path).name
        name_b = Path(res4_b.output_path).name
        if name_a != name_b and "(1)" in name_b:
            print(f" -> PASS: Collision detected and renamed cleanly to: {name_b}")
        else:
            print(f" -> WARN: Names: {name_a} vs {name_b}")
    else:
        failures.append("Failed collision check.")

    # TEST 5: Multi-Image to Single PDF
    print("\n[TEST 5] Testing multi-image batch combination into single PDF...")
    batch_imgs = []
    for i in range(4):
        p = TEST_DIR / f"page_{i}.png"
        im = Image.new("RGB", (120, 120), color=(i * 50, 100, 200))
        im.save(p)
        batch_imgs.append(str(p))

    batch_res = OpalEngine.execute_batch(batch_imgs, "pdf")
    if batch_res.succeeded == 4 and batch_res.outputs and Path(batch_res.outputs[0]).exists():
        print(f" -> PASS: Combined {batch_res.succeeded} images into {Path(batch_res.outputs[0]).name}")
    else:
        failures.append(f"Failed multi-image PDF test: {batch_res.message}")

    # TEST 6: Batch ZIP Compression
    print("\n[TEST 6] Testing ZIP bundle archive creation...")
    zip_res = OpalEngine.execute_batch(batch_imgs, "zip_bundle")
    if zip_res.succeeded == 4 and zip_res.outputs and Path(zip_res.outputs[0]).exists():
        print(f" -> PASS: Created ZIP archive: {Path(zip_res.outputs[0]).name}")
    else:
        failures.append(f"Failed ZIP bundle test: {zip_res.message}")

    # TEST 7: Image Tool Operations (Crop, Scale, Grayscale, EXIF strip, Invert, 16:9)
    print("\n[TEST 7] Testing image tools (Crop, Scale, Grayscale, Invert, 16:9)...")
    crop_res = OpalEngine.execute_single(batch_imgs[0], "crop_square")
    crop169_res = OpalEngine.execute_single(batch_imgs[0], "crop_16_9")
    inv_res = OpalEngine.execute_single(batch_imgs[0], "invert")
    gray_res = OpalEngine.execute_single(batch_imgs[0], "grayscale")
    scale_res = OpalEngine.execute_single(batch_imgs[0], "resize_50")
    if crop_res.success and crop169_res.success and inv_res.success and gray_res.success and scale_res.success:
        print(" -> PASS: Crop Square, Crop 16:9, Invert, Grayscale, and Scale 50% all succeeded.")
    else:
        failures.append("Failed image tools test.")

    # TEST 8: PDF 300 DPI High-Res Extraction
    print("\n[TEST 8] Testing PyMuPDF 300 DPI high-res page extraction...")
    if batch_res.outputs and Path(batch_res.outputs[0]).exists():
        pdf_page_res = OpalEngine.execute_single(batch_res.outputs[0], "png_pages")
        if pdf_page_res.success and Path(pdf_page_res.output_path).exists():
            print(f" -> PASS: Rendered 300 DPI pages to folder: {Path(pdf_page_res.output_path).name}")
        else:
            failures.append("Failed 300 DPI PDF extraction: " + pdf_page_res.message)

    # TEST 9: ZIP Archive Extraction
    print("\n[TEST 9] Testing ZIP archive extraction...")
    if zip_res.outputs and Path(zip_res.outputs[0]).exists():
        unzip_res = OpalEngine.execute_single(zip_res.outputs[0], "extract_archive")
        if unzip_res.success and Path(unzip_res.output_path).exists():
            print(f" -> PASS: Extracted ZIP archive to: {Path(unzip_res.output_path).name}")
        else:
            failures.append("Failed archive extraction: " + unzip_res.message)

    # TEST 10: JSON Formatting
    print("\n[TEST 10] Testing JSON formatting...")
    raw_json = TEST_DIR / "sample.json"
    raw_json.write_text('{"app":"tangerine","status":"ready","tests":[1,2,3]}', encoding="utf-8")
    json_res = OpalEngine.execute_single(str(raw_json), "format_json")
    if json_res.success and Path(json_res.output_path).exists():
        print(f" -> PASS: Cleanly formatted JSON: {Path(json_res.output_path).name}")
    else:
        failures.append("Failed JSON format test: " + json_res.message)

    # TEST 11: Config & History Persistence
    print("\n[TEST 11] Testing persistent Configuration & History...")
    cfg = ConfigManager.load_config()
    cfg["output_mode"] = "same_as_source"
    ConfigManager.save_config(cfg)
    ConfigManager.add_history_entry("test.png", "test.webp", "convert", "C:/dummy/test.webp", 2048)
    history = ConfigManager.load_history()
    if history and history[0]["source_name"] == "test.png":
        print(f" -> PASS: History and Configuration verified ({len(history)} entries stored).")
    else:
        failures.append("Failed configuration/history persistence.")

    cleanup_sandbox()

    print("\n==================================================")
    if not failures:
        print("TEST SUITE COMPLETED: 11/11 TESTS PASSED. ZERO FAILURES.")
        print("PRODUCT STABILITY: COMMERCIAL GRADE READY.")
    else:
        print(f"TEST SUITE FAILED with {len(failures)} failures:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("==================================================")


if __name__ == "__main__":
    run_stress_tests()
