"""Plugins: a .py file in the plugins folder becomes a real wheel tool.

Each test points OPAL_PLUGINS_DIR at its own folder, so the suite never reads
the machine's real plugins. A plugin that raises while running must come back
as a failed conversion, and one that fails to import must be skipped with a
reason - never crash the app.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from opal_studio.engine import OpalEngine
from opal_studio.plugins import PluginManager

UPPER_PLUGIN = '''
OPAL_PLUGIN = {"id": "upper", "label": "UPPERCASE",
               "desc": "Write the text back in capitals", "exts": [".txt"]}

def run(file_path, options=None):
    from pathlib import Path
    src = Path(file_path)
    dst = src.with_name(src.stem + "_upper.txt")
    dst.write_text(src.read_text(encoding="utf-8").upper(), encoding="utf-8")
    return {"success": True, "output_path": str(dst), "message": "Uppercased"}
'''

BOOM_PLUGIN = '''
OPAL_PLUGIN = {"id": "boom", "label": "Boom", "desc": "always raises"}

def run(file_path, options=None):
    raise RuntimeError("kapow")
'''

BROKEN_PLUGIN = "raise ImportError('this plugin is broken')\n"
NO_META_PLUGIN = "x = 1\n"


@pytest.fixture
def plugins_dir(tmp_path, monkeypatch):
    folder = tmp_path / "plugins"
    folder.mkdir()
    (folder / "upper.py").write_text(UPPER_PLUGIN, encoding="utf-8")
    (folder / "boom.py").write_text(BOOM_PLUGIN, encoding="utf-8")
    (folder / "broken.py").write_text(BROKEN_PLUGIN, encoding="utf-8")
    (folder / "no_meta.py").write_text(NO_META_PLUGIN, encoding="utf-8")
    monkeypatch.setenv("OPAL_PLUGINS_DIR", str(folder))
    PluginManager.reload()
    yield folder
    PluginManager.reload()


def test_a_plugin_appears_in_the_wheel_for_its_file_types(plugins_dir, samples):
    txt = str(samples.path("notes.txt"))
    png = str(samples.path("tiny.png"))

    tool_ids = [o["id"] for o in OpalEngine.get_options_for_files([txt], "tools")]
    assert "plugin:upper" in tool_ids, f"plugin missing from the wheel: {tool_ids}"

    # The plugin only declared .txt, so it must not be offered for a png.
    png_ids = [o["id"] for o in OpalEngine.get_options_for_files([png], "tools")]
    assert "plugin:upper" not in png_ids


def test_a_plugin_runs_for_real_and_produces_a_file(plugins_dir, samples, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    src = work / "note.txt"
    shutil.copy2(samples.path("notes.txt"), src)
    original = src.read_text(encoding="utf-8")

    result = OpalEngine.execute_single(str(src), "plugin:upper")

    assert result.success, f"plugin run failed: {result.message}"
    produced = Path(result.output_path)
    assert produced.exists(), f"the plugin promised an output that is not there: {produced}"
    assert produced.read_text(encoding="utf-8") == original.upper(), \
        "the plugin output is not what the plugin computed"
    assert src.read_text(encoding="utf-8") == original, "the plugin modified its input"


def test_a_raising_plugin_is_a_failed_conversion_not_a_crash(plugins_dir, samples):
    result = OpalEngine.execute_single(str(samples.path("notes.txt")), "plugin:boom")

    assert not result.success
    assert "kapow" in result.message, f"the failure lost the reason: {result.message}"


def test_broken_and_invalid_plugins_are_skipped_with_reasons(plugins_dir):
    found = {p.id for p in PluginManager.discover()}
    assert found == {"upper", "boom"}, f"unexpected plugins loaded: {found}"

    errors = PluginManager.errors()
    assert "broken.py" in errors, f"the import failure was not recorded: {errors}"
    assert "no_meta.py" in errors, f"the missing metadata was not recorded: {errors}"
    assert "OPAL_PLUGIN" in errors["no_meta.py"]

    # And none of them leak into the wheel.
    ids = sorted(o["id"] for o in PluginManager.options_for_files(["whatever.txt"]))
    assert ids == ["plugin:boom", "plugin:upper"], ids


def test_an_unknown_plugin_id_reports_a_clean_error(plugins_dir, samples):
    result = OpalEngine.execute_single(str(samples.path("notes.txt")), "plugin:nope")
    assert not result.success
    assert "no plugin" in result.message.lower()
