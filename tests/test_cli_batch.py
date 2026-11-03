"""The CLI has to handle a whole folder in one command, not just single files.

A counter PC gets a folder of scans, not one file at a time, so --convert and
--tool accept directories: every supported file in them is run, files that
already have the target format are skipped, and --json gives scripts one
machine-readable summary instead of human lines.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from opal_artifacts import validate_path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_cli(args, timeout=300):
    return subprocess.run(
        [sys.executable, str(ROOT / "opal_studio" / "cli.py")] + args,
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace", timeout=timeout)


def _folder_with_samples(samples, tmp_path: Path) -> Path:
    """A folder shaped like a real counter drop: images, a pdf that is
    already in the target format, an unsupported file, and a subfolder."""
    folder = tmp_path / "drop"
    (folder / "sub").mkdir(parents=True)
    shutil.copy2(samples.path("photo.jpg"), folder / "a.jpg")
    shutil.copy2(samples.path("contract.pdf"), folder / "b.pdf")
    shutil.copy2(samples.path("tiny.png"), folder / "sub" / "d.png")
    (folder / "c.xyz").write_text("not a supported file", encoding="utf-8")
    return folder


def test_cli_converts_every_supported_file_in_a_folder(samples, tmp_path):
    folder = _folder_with_samples(samples, tmp_path)
    out_dir = tmp_path / "out"

    proc = _run_cli(["--convert", str(folder), "--to", "pdf", "--out", str(out_dir)])

    assert proc.returncode == 0, f"code={proc.returncode} out={proc.stdout[-300:]}"
    assert "1 succeeded, 0 failed" in proc.stdout, proc.stdout[-300:]
    produced = list(out_dir.glob("*.pdf"))
    assert len(produced) == 1, f"expected the one top-level image as pdf, got {produced}"
    ok, detail = validate_path(produced[0])
    assert ok, f"the folder conversion produced an unusable pdf: {detail}"
    # The pdf that was already a pdf, the .xyz and the subfolder file were
    # all correctly left out of a non-recursive run.
    assert not list(out_dir.glob("b*")), "the already-pdf file was converted again"
    assert not list(out_dir.glob("d*")), "the subfolder file ran without --recursive"


def test_cli_recursive_includes_subfolders(samples, tmp_path):
    folder = _folder_with_samples(samples, tmp_path)
    out_dir = tmp_path / "out"

    proc = _run_cli(["--convert", str(folder), "--to", "pdf", "--recursive",
                     "--out", str(out_dir)])

    assert proc.returncode == 0, f"code={proc.returncode} out={proc.stdout[-300:]}"
    assert "2 succeeded, 0 failed" in proc.stdout, proc.stdout[-300:]
    names = sorted(p.name for p in out_dir.glob("*.pdf"))
    assert names == ["a_pdf.pdf", "d_pdf.pdf"], f"unexpected outputs: {names}"


def test_cli_json_mode_prints_one_machine_readable_summary(samples, tmp_path):
    src = tmp_path / "photo.jpg"
    shutil.copy2(samples.path("photo.jpg"), src)
    out_dir = tmp_path / "out"

    proc = _run_cli(["--convert", str(src), "--to", "webp", "--out", str(out_dir),
                     "--json"])

    assert proc.returncode == 0, f"code={proc.returncode} err={proc.stderr[-300:]}"
    payload = json.loads(proc.stdout)
    assert payload["succeeded"] == 1 and payload["failed"] == 0, payload
    assert payload["action"] == "webp"
    entry = payload["results"][0]
    assert entry["success"] is True
    produced = Path(entry["output"])
    assert produced.exists()
    ok, detail = validate_path(produced)
    assert ok, f"--json promised an output that is unusable: {detail}"


def test_cli_reports_a_missing_path_as_a_failure(samples, tmp_path):
    proc = _run_cli(["--convert", str(tmp_path / "nope.jpg"), "--to", "pdf"])

    assert proc.returncode == 1, f"code={proc.returncode}"
    assert "does not exist" in proc.stdout
    assert "0 succeeded, 1 failed" in proc.stdout


def test_cli_empty_folder_is_an_error_not_a_silent_success(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()

    proc = _run_cli(["--convert", str(folder), "--to", "pdf"])

    assert proc.returncode == 2, f"code={proc.returncode} out={proc.stdout[-200:]}"
    assert "no supported files" in proc.stdout
