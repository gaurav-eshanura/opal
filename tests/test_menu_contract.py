"""Every entry the radial wheel offers must really work on that file type.

For each sample file the engine is asked what the wheel would show, and then
every one of those entries is run for real.  A test passes only when the
engine reports success *and* the produced artifact opens with the matching
reader - a conversion that writes a broken or empty file fails here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from opal_artifacts import validate_path
from opal_fixtures import SAMPLE_NAMES, shared_samples
from opal_studio.engine import OpalEngine

SAMPLES = shared_samples()

# The options the UI would supply for the entries that need them.
OPTIONS = {
    "remove_object": {"box": [0.1, 0.1, 0.4, 0.5]},
    "watermark_image": {"watermark_text": "OPAL"},
    "pdf_watermark": {"watermark_text": "OPAL"},
    "pdf_search_redact": {"query": "Contract"},
    "pdf_verify_signature": {},
    "meme": {"top": "hello", "bottom": "world"},
    "qr_code": {"qr_text": "https://opal.local"},
    "subs_shift": {"shift_seconds": 2},
    "add_border": {"border_pct": 5},
    "video_speed": {"speed": 1.5},
    "audio_speed": {"speed": 1.5},
    "video_rotate": {"degrees": 90},
}

# Real-ESRGAN on the CPU takes minutes per image.  These are real tests, but
# they only run when asked for, and they are reported as skipped - never as
# passed - when they are left out.
SLOW_ACTIONS = {"upscale_2x", "upscale_4x"}
RUN_SLOW = os.environ.get("OPAL_RUN_SLOW") == "1"

# Which samples the wheel is exercised against.
WHEEL_SAMPLES = [
    "photo.jpg", "portrait.jpg", "tiny.png", "alpha.png", "pic.webp",
    "contract.pdf", "notes.txt", "readme.md", "page.html", "app.log",
    "rich.rtf", "data.csv", "data.json", "subs.srt", "subs.vtt",
    "report.docx", "sheet.xlsx", "deck.pptx", "novel.epub", "arial.ttf",
    "bundle.zip", "clip.mp4", "tone.wav",
]


def _cases():
    found = []
    for name in WHEEL_SAMPLES:
        if name not in SAMPLES:
            continue
        path = str(SAMPLES.path(name))
        for mode in ("convert", "tools"):
            for option in OpalEngine.get_options_for_files([path], mode):
                found.append((name, mode, option["id"]))
    return found


CASES = _cases()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_wheel_offers_more_than_a_handful_of_entries():
    """A guard against the contract silently shrinking to nothing."""
    assert len(CASES) > 200, f"only {len(CASES)} wheel entries were discovered"


@pytest.mark.parametrize(
    "sample,mode,action_id",
    CASES,
    ids=[f"{s}-{m}-{a}" for s, m, a in CASES],
)
def test_wheel_entry_produces_a_real_artifact(sample, mode, action_id):
    if action_id in SLOW_ACTIONS and not RUN_SLOW:
        pytest.skip(
            f"{action_id} runs Real-ESRGAN on the CPU and takes minutes; "
            f"set OPAL_RUN_SLOW=1 to run it"
        )

    source = SAMPLES.path(sample)
    source_hash = _sha256(source)

    result = OpalEngine.execute_single(str(source), action_id, OPTIONS.get(action_id))

    assert result.success, f"{action_id} on {sample} failed: {result.message}"
    assert result.output_path, f"{action_id} on {sample} reported no output path"

    produced = Path(result.output_path)
    assert produced.exists(), f"{action_id} on {sample} wrote nothing to {produced}"

    ok, detail = validate_path(produced)
    assert ok, f"{action_id} on {sample} produced an unusable artifact: {detail}"

    if produced.resolve() == source.resolve():
        # An action with nothing to do - the file is already under the target
        # size, or has no blank pages - may hand the original back.  That is
        # fine, but only if it left the original alone.
        assert _sha256(source) == source_hash, \
            f"{action_id} on {sample} overwrote the input instead of producing a new file"


def test_every_sample_opens_with_its_own_reader():
    """The samples themselves must be genuine, or the contract proves nothing."""
    for name in SAMPLE_NAMES:
        if name not in SAMPLES:
            continue
        ok, detail = validate_path(SAMPLES.path(name))
        assert ok, f"the sample {name} is not a usable file: {detail}"
