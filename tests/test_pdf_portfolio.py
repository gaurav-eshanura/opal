"""
Opal - PDF Portfolio & Package Test Suite
Plain English: Tests ISO 32000-1 Collections (Adobe Acrobat PDF Portfolios).
Verifies that multiple files can be packaged into a master PDF, that catalog
collection dictionaries and schemas are properly structured, that attachments
can be inspected and extracted offline, and that the UI manager functions cleanly.
"""

import os
import sys
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz
from opal_studio import pdf_portfolio as pp
from opal_studio import pdf_tools as pt


@pytest.fixture
def sample_payload_files(tmp_path):
    """Creates a diverse collection of files for packaging."""
    f1 = tmp_path / "model.csv"
    f1.write_text("Year,Revenue,Profit\n2025,1000000,250000\n2026,2500000,800000\n", encoding="utf-8")

    f2 = tmp_path / "brief.txt"
    f2.write_text("Executive strategic briefing notes for v2.2.0 release.", encoding="utf-8")

    f3 = tmp_path / "spec.json"
    f3.write_text('{"project": "Opal", "version": "2.2.0", "offline": true}', encoding="utf-8")

    return [
        {"path": str(f1), "name": "Financial_Model.csv", "description": "Quarterly financial projections"},
        {"path": str(f2), "name": "Strategic_Brief.txt", "description": "Executive briefing document"},
        {"path": str(f3), "name": "System_Spec.json", "description": "Product configuration schema"},
    ]


def test_create_portfolio_creates_compliant_collection(sample_payload_files, tmp_path):
    out_pdf = str(tmp_path / "executive_package.pdf")
    res = pp.create_portfolio(
        files=sample_payload_files,
        dst_pdf=out_pdf,
        title="Executive Deliverable Package",
        description="Confidential deliverables and models",
        default_view="details",
    )

    assert res["success"]
    assert Path(out_pdf).exists()
    assert res["files_count"] == 3
    assert res["total_size_bytes"] > 0

    # Verify detection
    assert pp.is_portfolio(out_pdf)

    # Inspect PDF Catalog directly via PyMuPDF
    doc = fitz.open(out_pdf)
    try:
        cat_xref = doc.pdf_catalog()
        ktype, val = doc.xref_get_key(cat_xref, "Collection")
        assert ktype == "dict"
        assert "/Schema" in val
        assert "/Name" in val
        assert "/Size" in val
        assert doc.embfile_count() == 3
        assert "Financial_Model.csv" in doc.embfile_names()
    finally:
        doc.close()


def test_get_portfolio_info(sample_payload_files, tmp_path):
    out_pdf = str(tmp_path / "test_info.pdf")
    pp.create_portfolio(sample_payload_files, out_pdf)

    info = pp.get_portfolio_info(out_pdf)
    assert info["is_portfolio"]
    assert info["has_embedded_files"]
    assert info["files_count"] == 3
    assert len(info["files"]) == 3

    names = [f["name"] for f in info["files"]]
    assert "Financial_Model.csv" in names
    assert "Strategic_Brief.txt" in names

    # Check that human sizes and mime types are resolved
    csv_file = next(f for f in info["files"] if f["name"] == "Financial_Model.csv")
    assert csv_file["size"] > 0
    assert "B" in csv_file["size_human"] or "KB" in csv_file["size_human"]
    assert csv_file["extension"] == ".csv"
    assert csv_file["description"] == "Quarterly financial projections"


def test_extract_single_file_from_portfolio(sample_payload_files, tmp_path):
    out_pdf = str(tmp_path / "test_extract.pdf")
    pp.create_portfolio(sample_payload_files, out_pdf)

    dst_extracted = str(tmp_path / "extracted_brief.txt")
    result_path = pp.extract_portfolio_file(out_pdf, "Strategic_Brief.txt", dst_extracted)

    assert Path(result_path).exists()
    extracted_text = Path(result_path).read_text(encoding="utf-8")
    assert "Executive strategic briefing notes" in extracted_text


def test_extract_all_portfolio_files(sample_payload_files, tmp_path):
    out_pdf = str(tmp_path / "test_extract_all.pdf")
    pp.create_portfolio(sample_payload_files, out_pdf)

    extract_folder = tmp_path / "all_extracted"
    extracted_files = pp.extract_all_portfolio_files(out_pdf, str(extract_folder))

    assert len(extracted_files) == 3
    assert (extract_folder / "Financial_Model.csv").exists()
    assert (extract_folder / "Strategic_Brief.txt").exists()
    assert (extract_folder / "System_Spec.json").exists()


def test_add_and_remove_file_from_portfolio(sample_payload_files, tmp_path):
    out_pdf = str(tmp_path / "test_modify.pdf")
    pp.create_portfolio(sample_payload_files, out_pdf)

    extra_file = tmp_path / "extra_notes.md"
    extra_file.write_text("# Extra Appendices\nAdditional details.", encoding="utf-8")

    # Add file
    updated_info = pp.add_file_to_portfolio(out_pdf, str(extra_file), description="Additional markdown notes")
    assert updated_info["files_count"] == 4
    assert any(f["name"] == "extra_notes.md" for f in updated_info["files"])

    # Remove file
    after_del_info = pp.remove_file_from_portfolio(out_pdf, "extra_notes.md")
    assert after_del_info["files_count"] == 3
    assert not any(f["name"] == "extra_notes.md" for f in after_del_info["files"])


def test_pdf_tools_portfolio_api(sample_payload_files, tmp_path):
    out_pdf = str(tmp_path / "pt_portfolio.pdf")
    res = pt.create_portfolio(
        files=sample_payload_files,
        dst=out_pdf,
        title="Tools API Portfolio",
    )
    assert res["success"]
    assert pt.is_portfolio(out_pdf)

    info = pt.get_portfolio_info(out_pdf)
    assert info["files_count"] == 3

    extract_dir = str(tmp_path / "pt_extracted")
    extracted = pt.extract_portfolio(out_pdf, extract_dir)
    assert len(extracted) == 3


def test_portfolio_dialog_headless_lifecycle(sample_payload_files, tmp_path, app):
    from opal_studio.viewer_pdf import PortfolioDialog, CreatePortfolioDialog, PdfStudio
    out_pdf = str(tmp_path / "dialog_portfolio.pdf")
    pp.create_portfolio(sample_payload_files, out_pdf, title="Headless Test Package")

    # Initialize PortfolioDialog
    dlg = PortfolioDialog(out_pdf)
    assert dlg.info["files_count"] == 3
    assert dlg.table.rowCount() == 3
    dlg.close()

    # Initialize CreatePortfolioDialog
    create_dlg = CreatePortfolioDialog()
    assert create_dlg.list_widget.count() == 0
    create_dlg.close()

    # Load into PdfStudio
    viewer = PdfStudio(file_path=out_pdf)
    assert viewer.doc is not None
    viewer.close()
