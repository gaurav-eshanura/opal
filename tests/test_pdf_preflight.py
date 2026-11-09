"""
Opal - PDF Preflight & Compliance Test Suite
Plain English: Tests the preflight engine against ISO standards (PDF/X-1a, PDF/X-3,
PDF/X-4, PDF/A-1b). Verifies detection of non-compliant fonts, missing geometry boxes,
missing output intents, image resolution issues, and confirms that auto-fixups produce
100% compliant documents.
"""

import os
import sys
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz
from PIL import Image
import io

from opal_studio.pdf_preflight import (
    run_preflight,
    apply_preflight_fixups,
    PreflightProfile,
    CheckSeverity,
    PreflightReport,
)
from opal_studio import pdf_tools as pt


@pytest.fixture
def sample_pdf(tmp_path):
    """Creates a basic raw PDF without trimbox or output intent."""
    pdf_path = tmp_path / "sample_raw.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Preflight Verification Sample", fontsize=16)
    page.insert_text((72, 140), "Standard text on a white canvas.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


@pytest.fixture
def sample_pdf_with_image(tmp_path):
    """Creates a PDF with both high-res and low-res images."""
    pdf_path = tmp_path / "sample_images.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # 1. Low res image (72 DPI)
    img_low = Image.new("RGB", (100, 100), color=(200, 50, 50))
    buf_low = io.BytesIO()
    img_low.save(buf_low, format="PNG")
    # 100px over 100pt -> 72 DPI
    page.insert_image(fitz.Rect(50, 50, 150, 150), stream=buf_low.getvalue())

    # 2. High res image (300 DPI)
    img_hi = Image.new("RGB", (600, 600), color=(50, 200, 50))
    buf_hi = io.BytesIO()
    img_hi.save(buf_hi, format="PNG")
    # 600px over 144pt -> 300 DPI
    page.insert_image(fitz.Rect(50, 200, 194, 344), stream=buf_hi.getvalue())

    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_preflight_detects_missing_output_intent_and_trimbox(sample_pdf):
    report = run_preflight(sample_pdf, profile=PreflightProfile.PDFX_1A)
    assert not report.passed
    assert report.error_count >= 2

    rules = [i.rule for i in report.issues]
    assert "missing-output-intent" in rules
    assert "missing-trimbox" in rules


def test_preflight_commercial_print_evaluates_image_dpi(sample_pdf_with_image):
    report = run_preflight(sample_pdf_with_image, profile=PreflightProfile.COMMERCIAL_PRINT)
    rules = [i.rule for i in report.issues]
    # Low resolution image must trigger a warning
    assert "low-image-resolution" in rules

    # Check that images summary captured both images
    assert len(report.images_summary) == 2
    dpis = [img["effective_dpi"] for img in report.images_summary]
    assert any(dpi < 150 for dpi in dpis)
    assert any(dpi >= 300 for dpi in dpis)


def test_apply_preflight_fixups_generates_compliant_pdfx(sample_pdf, tmp_path):
    dest_path = str(tmp_path / "sample_compliant_pdfx.pdf")
    report = apply_preflight_fixups(
        sample_pdf,
        dest_path,
        profile=PreflightProfile.PDFX_1A,
        preset_name="FOGRA39",
        trim_margin_pt=9.0,
        flatten_transparency=True,
        rasterize_unembedded_fonts=True,
    )

    # Re-inspect the produced document
    assert Path(dest_path).exists()
    assert report.passed, f"Fixup failed to achieve compliance: {[i.message for i in report.issues]}"
    assert report.error_count == 0

    # Verify structural internals in PyMuPDF
    doc = fitz.open(dest_path)
    assert len(doc) == 1
    page = doc[0]

    # Explicit trimbox is present
    trim_type, trim_val = doc.xref_get_key(page.xref, "TrimBox")
    assert trim_type == "array"

    # Explicit output intent is present in catalog
    catalog = doc.pdf_catalog()
    oi_type, oi_val = doc.xref_get_key(catalog, "OutputIntents")
    assert oi_type == "array" and "FOGRA39" in doc.xref_object(int(oi_val.strip("[] ").split()[0]))

    # Standard XMP metadata exists
    xmp = doc.get_xml_metadata()
    assert "PDF/X-1a:2001" in xmp

    doc.close()


def test_pdf_tools_preflight_and_convert_api(sample_pdf, tmp_path):
    # Test pt.preflight_pdf
    rep1 = pt.preflight_pdf(sample_pdf, profile=PreflightProfile.PDFX_1A)
    assert isinstance(rep1, PreflightReport)

    # Test pt.convert_to_pdfx
    out_file, rep2 = pt.convert_to_pdfx(sample_pdf, profile=PreflightProfile.PDFX_1A)
    assert Path(out_file).exists()
    assert rep2.passed
    Path(out_file).unlink(missing_ok=True)


def test_preflight_report_formats(sample_pdf):
    report = run_preflight(sample_pdf, profile=PreflightProfile.PDFX_1A)

    json_str = report.to_json()
    assert "missing-output-intent" in json_str

    md_str = report.to_markdown()
    assert "# Opal PDF Preflight Report" in md_str

    html_str = report.to_html()
    assert "<!DOCTYPE html>" in html_str
    assert "Opal PDF Preflight Report" in html_str


def test_preflight_dialog_headless_lifecycle(sample_pdf, app):
    from opal_studio.viewer_pdf import PreflightDialog
    dlg = PreflightDialog(sample_pdf)
    assert dlg.current_report is not None
    assert dlg.profile_combo.count() >= 4

    # Change profile to PDF/X-4 and verify re-inspection
    dlg.profile_combo.setCurrentIndex(2)
    assert dlg.current_report.profile == PreflightProfile.PDFX_4
    dlg.close()
