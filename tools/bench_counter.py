"""
Opal - counter-job benchmark
Plain English: Runs the kind of jobs a print-shop counter does all day -
one after another, back to back - and reports how long they took.

This is the number the website quotes, so it has to be measured, not guessed.

    python tools/bench_counter.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from opal_fixtures import shared_samples  # noqa: E402
from opal_studio.engine import OpalEngine  # noqa: E402

# The jobs a counter really does: a photo to print, a document to PDF, a file
# squeezed down for WhatsApp, a video's sound for a ringtone.
JOBS = [
    ("photo.jpg", "pdf", "photo to PDF for printing"),
    ("portrait.jpg", "jpg", "passport photo for a form"),
    ("contract.pdf", "png_pages", "scanned pages to images"),
    ("report.docx", "pdf", "Word document to PDF"),
    ("notes.txt", "pdf", "typed note to PDF"),
    ("data.csv", "csv_xlsx", "CSV to a spreadsheet"),
    ("clip.mp4", "mp3", "video sound to MP3"),
    ("tone.wav", "mp3", "recording to MP3"),
    ("tiny.png", "webp", "image to WebP"),
    ("subs.srt", "srt_vtt", "subtitles to the other format"),
]


def main() -> int:
    samples = shared_samples()
    workdir = Path(tempfile.mkdtemp(prefix="opal_bench_"))
    failed = 0
    total = 0.0
    try:
        missing = []
        for source, target, label in JOBS:
            if source not in samples:
                missing.append(f"{source} ({label})")
                continue
            src = samples.path(source)
            # Work on a copy in a scratch folder so the benchmark never
            # touches the shared sample set.
            local = workdir / src.name
            shutil.copy2(src, local)
            start = time.perf_counter()
            result = OpalEngine.execute_single(str(local), target)
            elapsed = time.perf_counter() - start
            total += elapsed
            status = "ok" if result.success else "FAILED"
            print(f"  {elapsed:6.2f}s  {source:<14} -> {target:<8} {status}"
                  f"   ({label})")
            if not result.success:
                failed += 1
                print(f"            {result.message}")

        if missing:
            print("\nnot measured (sample could not be built here):")
            for item in missing:
                print(f"  - {item}")
        print(f"\nJOBS: {len(JOBS)}   TOTAL: {total:.2f}s   FAILED: {failed}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
