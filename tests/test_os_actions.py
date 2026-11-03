"""The eight OS-level wheel actions, tested for real.

The menu contract exercises the convert and tools modes; these eight live in
the wheel's actions mode and hand work to the operating system, so they get
a suite of their own.  Actions that would launch Explorer, a terminal or the
default app on the machine running the test have the platform layer replaced
with a recorder, and the test proves the engine called it with the right
path.  The real launches stay in the OPAL_RUN_DESKTOP group, where a desktop
is actually present.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from opal_artifacts import validate_path
from opal_studio import platform_compat
from opal_studio.engine import OpalEngine

RUN_DESKTOP = os.environ.get("OPAL_RUN_DESKTOP") == "1"

OS_ACTIONS = [
    "float", "open_with", "copy_path", "copy_file",
    "show_explorer", "open_terminal", "duplicate", "trash",
]


def _work_copy(samples, tmp_path: Path, name: str) -> Path:
    """A private copy of a sample in the test's own folder, so the shared
    sample set is never written to by an action under test."""
    dst = tmp_path / name
    shutil.copy2(samples.path(name), dst)
    return dst


@pytest.fixture
def recorded(monkeypatch):
    """Replace the platform layer with recorders and return what was called."""
    calls: dict[str, list] = {}

    def make_recorder(func_name: str, ret=True):
        def recorder(arg):
            calls.setdefault(func_name, []).append(arg)
            return ret
        monkeypatch.setattr(platform_compat, func_name, recorder)

    for func_name in ("copy_text_to_clipboard", "reveal_in_file_manager",
                      "open_terminal", "open_with_default"):
        make_recorder(func_name)
    return calls


def test_actions_wheel_offers_every_os_action(samples):
    """A guard: if an action drops out of the wheel, this fails."""
    for name in ("photo.jpg", "contract.pdf", "notes.txt"):
        if name not in samples:
            continue
        offered = {o["id"] for o in
                   OpalEngine.get_options_for_files([str(samples.path(name))], "actions")}
        missing = [a for a in OS_ACTIONS if a not in offered]
        assert not missing, f"actions wheel for {name} is missing {missing}"


def test_duplicate_makes_a_real_copy_next_to_the_file(samples, tmp_path):
    src = _work_copy(samples, tmp_path, "alpha.png")
    before = src.read_bytes()

    result = OpalEngine.execute_single(str(src), "duplicate")

    assert result.success, f"duplicate failed: {result.message}"
    produced = Path(result.output_path)
    assert produced == tmp_path / "alpha_copy.png"
    assert produced.exists()
    assert produced.read_bytes() == before, "the copy differs from the original"
    ok, detail = validate_path(produced)
    assert ok, f"duplicate produced an unusable artifact: {detail}"
    assert src.read_bytes() == before, "duplicate touched the original"


def test_duplicate_never_overwrites_an_existing_copy(samples, tmp_path):
    src = _work_copy(samples, tmp_path, "tiny.png")

    first = OpalEngine.execute_single(str(src), "duplicate")
    second = OpalEngine.execute_single(str(src), "duplicate")

    assert first.success and second.success
    assert Path(first.output_path).exists()
    assert Path(second.output_path).exists()
    assert first.output_path != second.output_path, \
        "the second duplicate overwrote the first"
    assert src.exists(), "duplicate removed the original"


def test_copy_file_lands_in_downloads(samples, tmp_path, monkeypatch):
    """Copy-to-Downloads writes into the user's real Downloads folder, so the
    test points Path.home() at its own folder and proves the copy lands there."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    src = _work_copy(samples, tmp_path, "notes.txt")
    before = src.read_bytes()

    result = OpalEngine.execute_single(str(src), "copy_file")

    assert result.success, f"copy_file failed: {result.message}"
    produced = Path(result.output_path)
    assert produced == tmp_path / "Downloads" / "notes.txt"
    assert produced.exists()
    assert produced.read_bytes() == before

    again = OpalEngine.execute_single(str(src), "copy_file")
    assert again.success
    assert Path(again.output_path) == tmp_path / "Downloads" / "notes (1).txt", \
        "copy_file overwrote the earlier copy instead of making a new name"


def test_copy_path_puts_the_exact_path_on_the_clipboard(samples, tmp_path, recorded):
    src = _work_copy(samples, tmp_path, "page.html")

    result = OpalEngine.execute_single(str(src), "copy_path")

    assert result.success, f"copy_path failed: {result.message}"
    assert recorded["copy_text_to_clipboard"] == [str(src.resolve())]


def test_show_explorer_reveals_the_file(samples, tmp_path, recorded):
    src = _work_copy(samples, tmp_path, "data.csv")

    result = OpalEngine.execute_single(str(src), "show_explorer")

    assert result.success, f"show_explorer failed: {result.message}"
    assert recorded["reveal_in_file_manager"] == [str(src.resolve())]


def test_open_terminal_targets_the_files_folder(samples, tmp_path, recorded):
    src = _work_copy(samples, tmp_path, "readme.md")

    result = OpalEngine.execute_single(str(src), "open_terminal")

    assert result.success, f"open_terminal failed: {result.message}"
    assert recorded["open_terminal"] == [str(src.parent.resolve())]


def test_open_with_uses_the_default_app(samples, tmp_path, recorded):
    src = _work_copy(samples, tmp_path, "pic.webp")

    result = OpalEngine.execute_single(str(src), "open_with")

    assert result.success, f"open_with failed: {result.message}"
    assert recorded["open_with_default"] == [str(src.resolve())]


def test_open_with_reports_failure_when_no_default_app(samples, tmp_path, monkeypatch):
    src = _work_copy(samples, tmp_path, "subs.vtt")
    monkeypatch.setattr(platform_compat, "open_with_default", lambda arg: False)

    result = OpalEngine.execute_single(str(src), "open_with")

    assert not result.success
    assert "No default application" in result.message


def test_trash_really_removes_the_file(samples, tmp_path):
    """A real send to the recycle bin: the file must be gone afterwards."""
    src = _work_copy(samples, tmp_path, "app.log")
    assert src.exists()

    result = OpalEngine.execute_single(str(src), "trash")

    assert result.success, f"trash failed: {result.message}"
    assert not src.exists(), "the file is still on disk after trashing it"
    assert result.output_path == str(src.resolve())


def test_float_hands_the_file_to_the_floating_studio(samples, tmp_path):
    src = _work_copy(samples, tmp_path, "photo.jpg")

    result = OpalEngine.execute_single(str(src), "float")

    assert result.success, f"float failed: {result.message}"
    assert result.output_path == str(src.resolve())
    assert "floating studio" in result.message.lower()


@pytest.mark.skipif(not RUN_DESKTOP,
                    reason="really opens Explorer / a terminal / the default app; "
                           "set OPAL_RUN_DESKTOP=1 on a desktop machine")
def test_desktop_launches_really_fire(samples, tmp_path):
    """With no recorder in the way, the platform layer is the real one."""
    src = _work_copy(samples, tmp_path, "notes.txt")
    for action_id in ("show_explorer", "open_terminal", "open_with", "copy_path"):
        result = OpalEngine.execute_single(str(src), action_id)
        assert result.success, f"{action_id} failed on a desktop: {result.message}"
