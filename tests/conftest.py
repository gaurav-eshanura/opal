"""Shared pytest fixtures for the Opal suite.

The suite used to be a pile of print-only scripts: each one printed PASS/FAIL
and then exited 0 whatever happened, so a broken feature still looked green in
CI.  These fixtures give pytest the three things the old scripts lacked:

  * one real Qt application, drawn offscreen, shared by every test,
  * real sample files for every format Opal handles,
  * a ledger that turns the old `check()` helpers into real failures.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Qt must never try to open a real window on a build machine.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for entry in (str(ROOT), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """One real QApplication for the whole session, drawn offscreen."""
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv[:1])
    instance.setQuitOnLastWindowClosed(False)
    yield instance


@pytest.fixture(scope="session")
def samples():
    """Real sample files, built once per session."""
    from opal_fixtures import shared_samples
    return shared_samples()


@pytest.fixture(scope="session", autouse=True)
def _no_modal_hangs(app):
    """A modal message box would freeze the whole run.

    Offscreen there is nobody to click "OK", so any dialog that reports a
    problem would block the suite forever.  A timer closes whatever modal
    window has been sitting there for more than a few seconds - long enough
    that a dialog the test drives itself (which types a value and accepts it)
    is never interrupted, and short enough that a dialog nobody is going to
    answer does not hang the build.
    """
    import time

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    PATIENCE = 3.0
    state = {"widget": None, "since": 0.0}

    def dismiss():
        widget = QApplication.activeModalWidget()
        if widget is None:
            state["widget"] = None
            return
        if state["widget"] is not widget:
            state["widget"] = widget
            state["since"] = time.monotonic()
            return
        if time.monotonic() - state["since"] > PATIENCE:
            widget.close()

    timer = QTimer()
    timer.timeout.connect(dismiss)
    timer.start(250)
    yield
    timer.stop()


@pytest.fixture(autouse=True)
def _strict_ledgers(request):
    """Make the old print-based `check()` helpers able to fail a test.

    The legacy scripts recorded their failures in module-level lists and then
    exited 0.  Under pytest those lists are cleared before each test and must
    be empty again afterwards, so a failing check is a failing test.
    """
    module = request.module
    lists: dict[str, list] = {}
    for attr in ("PASS", "FAIL", "SKIPPED", "RESULTS"):
        value = getattr(module, attr, None)
        if isinstance(value, list):
            lists[attr] = value
            value.clear()

    counters: dict[str, int] = {}
    for attr in ("_passed", "_failed"):
        if hasattr(module, attr):
            counters[attr] = getattr(module, attr)
            setattr(module, attr, 0)

    yield

    problems: list[str] = []
    failed = lists.get("FAIL")
    if failed:
        problems.append(f"{len(failed)} failed check(s): " + "; ".join(str(f) for f in failed[:8]))
    for attr, before in counters.items():
        after = getattr(module, attr, 0)
        if attr == "_failed" and after:
            problems.append(f"{after} failed check(s) in {module.__name__}")
    if problems:
        raise AssertionError(" | ".join(problems))
