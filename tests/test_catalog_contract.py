"""Every action the catalog advertises must really work.

`OpalEngine.get_catalog()` is the public menu of 36 actions shown on the Home
grid and in the CLI.  Each one is run here against a real sample file, and a
test passes only when the produced artifact opens with the matching reader.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from opal_artifacts import validate_path
from opal_fixtures import shared_samples
from opal_studio.engine import OpalEngine

SAMPLES = shared_samples()
RUN_SLOW = os.environ.get("OPAL_RUN_SLOW") == "1"

# action id -> (sample, options, slow?)
CATALOG_RUNS = {
    "remove_bg":        ("portrait.jpg", {"bg_model": "u2netp"}, False),
    "aadhaar_photo":    ("portrait.jpg", {}, False),
    "print_4x6":        ("photo.jpg",    {}, False),
    "photo_whatsapp":   ("photo.jpg",    {}, False),
    "pdf_whatsapp":     ("big.pdf",      {}, False),
    "pdf_a4":           ("contract.pdf", {}, False),
    "add_border":       ("photo.jpg",    {}, False),
    "bg_cutout_blur":   ("portrait.jpg", {"bg_model": "u2netp"}, False),
    "upscale_2x":       ("tiny.png",     {}, True),
    "enhance_auto":     ("photo.jpg",    {}, False),
    "compress_image":   ("photo.jpg",    {}, False),
    "social_portrait":  ("photo.jpg",    {}, False),
    "color_palette":    ("photo.jpg",    {}, False),
    "exif_report":      ("photo.jpg",    {}, False),
    "watermark_image":  ("photo.jpg",    {"watermark_text": "OPAL"}, False),
    "qr_code":          ("notes.txt",    {}, False),
    "pdf":              ("readme.md",    {}, False),
    "pptx":             ("contract.pdf", {}, False),
    "docx":             ("contract.pdf", {}, False),
    "epub":             ("contract.pdf", {}, False),
    "pdf_dsc_sign":     ("contract.pdf", {}, False),   # options filled in below
    "pdf_verify_signature": ("contract.pdf", {}, False),
    "pdf_search_redact":    ("contract.pdf", {"query": "Contract"}, False),
    "pdf_pagenum":      ("contract.pdf", {}, False),
    "pdf_watermark":    ("contract.pdf", {"watermark_text": "OPAL"}, False),
    "pdf_ocr":          ("scan.pdf",     {}, False),
    "split_pdf":        ("contract.pdf", {}, False),
    "epub_txt":         ("novel.epub",   {}, False),
    "md_html":          ("readme.md",    {}, False),
    "srt_vtt":          ("subs.srt",     {}, False),
    "csv_xlsx":         ("data.csv",     {}, False),
    "font_report":      ("arial.ttf",    {}, False),
    "video_thumbnails": ("clip.mp4",     {}, False),
    "video_frames":     ("clip.mp4",     {"frames_per_second": "all"}, False),
    "burn_subtitles":   ("clip.mp4",     {}, False),
    "hash_file":        ("photo.jpg",    {}, False),
    "quick_zip":        ("notes.txt",    {}, False),
}


def test_the_catalog_and_the_contract_agree():
    """No action may be advertised without a test, or tested unadvertised."""
    catalog_ids = {c["id"] for c in OpalEngine.get_catalog()}
    contract_ids = set(CATALOG_RUNS) | {"merge_pdf"}   # merge_pdf is batch-only
    missing = catalog_ids - contract_ids
    extra = contract_ids - catalog_ids
    assert not missing, f"catalog advertises actions the contract never runs: {sorted(missing)}"
    assert not extra, f"the contract runs actions the catalog does not advertise: {sorted(extra)}"
    assert len(OpalEngine.get_catalog()) == 38, "the catalog changed size"
    assert len({c["id"] for c in OpalEngine.get_catalog()}) == len(OpalEngine.get_catalog()), \
        "the catalog advertises the same action twice"


@pytest.mark.parametrize(
    "action_id",
    [a for a, (_, _, slow) in CATALOG_RUNS.items() if not slow],
)
def test_catalog_action_produces_a_real_artifact(action_id):
    sample, options, _ = CATALOG_RUNS[action_id]
    source = SAMPLES.path(sample)
    assert source.exists(), f"the sample {sample} was not built on this machine"

    resolved = dict(options)
    if action_id == "pdf_dsc_sign":
        assert SAMPLES.has("cert.p12"), \
            "no certificate could be built, so the DSC signature cannot be tested"
        resolved = {"pfx_path": str(SAMPLES.path("cert.p12")),
                    "password": "", "page": 0}

    result = OpalEngine.execute_single(str(source), action_id, resolved)

    assert result.success, f"{action_id} failed: {result.message}"
    assert result.output_path, f"{action_id} reported no output path"

    ok, detail = validate_path(result.output_path)
    assert ok, f"{action_id} produced an unusable artifact: {detail}"


@pytest.mark.parametrize(
    "action_id",
    [a for a, (_, _, slow) in CATALOG_RUNS.items() if slow],
)
def test_slow_catalog_action_produces_a_real_artifact(action_id):
    if not RUN_SLOW:
        pytest.skip("Real-ESRGAN on the CPU takes minutes; set OPAL_RUN_SLOW=1 to run it")
    sample, _, _ = CATALOG_RUNS[action_id]
    source = SAMPLES.path(sample)
    result = OpalEngine.execute_single(str(source), action_id)
    assert result.success, f"{action_id} failed: {result.message}"
    ok, detail = validate_path(result.output_path)
    assert ok, f"{action_id} produced an unusable artifact: {detail}"


def test_merge_pdf_combines_documents():
    """merge_pdf is batch-only: it needs two documents to make sense."""
    batch = OpalEngine.execute_batch([str(SAMPLES.path("contract.pdf")),
                                      str(SAMPLES.path("contract2.pdf"))], "merge_pdf")
    assert batch.succeeded == 2, f"merge_pdf failed: {batch.message}"
    assert batch.outputs, "merge_pdf reported no output"
    ok, detail = validate_path(batch.outputs[0])
    assert ok, f"merge_pdf produced an unusable artifact: {detail}"

    import fitz
    doc = fitz.open(str(batch.outputs[0]))
    try:
        assert len(doc) == 5, \
            f"a 3-page and a 2-page merge must give 5 pages, got {len(doc)}"
    finally:
        doc.close()


def test_single_file_merge_pdf_explains_itself():
    """One file has nothing to merge with; the answer must say so honestly."""
    result = OpalEngine.execute_single(str(SAMPLES.path("contract.pdf")), "merge_pdf")
    assert not result.success, "merge_pdf on one file must not pretend to succeed"
    assert "two" in (result.message or "").lower(), result.message


def test_dsc_signature_is_cryptographically_real():
    """The signature must be verifiable, not just a rendered picture.

    The test signs its own PDF so it does not depend on the order in which
    the other catalog actions ran.
    """
    if not SAMPLES.has("cert.p12"):
        pytest.skip("no certificate could be built on this machine")

    result = OpalEngine.execute_single(str(SAMPLES.path("contract.pdf")), "pdf_dsc_sign",
                                       {"pfx_path": str(SAMPLES.path("cert.p12")),
                                        "password": "", "page": 0})
    assert result.success, f"pdf_dsc_sign failed: {result.message}"
    ok, detail = validate_path(result.output_path)
    assert ok, f"the signed PDF is not usable: {detail}"

    from opal_studio import dsc_sign
    info = dsc_sign.verify_signature(result.output_path)
    assert info.get("signed") is True and info.get("count", 0) >= 1, \
        f"the signature did not verify: {info}"
