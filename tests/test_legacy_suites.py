"""The legacy suites, now able to fail.

The old scripts printed PASS/FAIL and most exited 0 whatever happened.  Each
one is run here as its own process: a crash is a non-zero exit, a failing check
is a `[FAIL]` line, and both fail the test.  The suites that open Explorer, a
terminal or MS Office on the real desktop run only when asked for, and are
reported as skipped - never as passed - otherwise.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

# name -> timeout in seconds
LEGACY_SUITES = {
    "test_security": 180,
    "test_app_smoke": 300,
    "test_engine_extended": 420,
    "test_viewer_pdf": 420,
}

# Suites that touch the real desktop or drive real MS Office.
DESKTOP_SUITES = {
    "test_crossplatform": 420,
    "test_customer_journey": 1800,
}


def _run_script(name: str, timeout: int) -> None:
    script = HERE / f"{name}.py"
    assert script.exists(), f"{name}.py is missing"
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run([sys.executable, str(script)], capture_output=True,
                              timeout=timeout, cwd=str(HERE.parent), env=env)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{name} did not finish in {timeout} s - it hung")
    output = (proc.stdout + proc.stderr).decode("utf-8", "replace")
    fails = [line for line in output.splitlines() if line.startswith("[FAIL]")]

    if proc.returncode != 0:
        tail = output.strip().splitlines()[-8:] if output.strip() else ["<no output>"]
        detail = "\n".join(fails[:6] + tail)
        pytest.fail(f"{name} crashed with exit code {proc.returncode}:\n{detail}")

    assert not fails, (
        f"{name}: {len(fails)} check(s) failed:\n" + "\n".join(fails[:10])
    )


@pytest.mark.parametrize("name", sorted(LEGACY_SUITES), ids=sorted(LEGACY_SUITES))
def test_legacy_suite(name):
    _run_script(name, LEGACY_SUITES[name])


@pytest.mark.parametrize("name", sorted(DESKTOP_SUITES), ids=sorted(DESKTOP_SUITES))
def test_desktop_suite(name):
    if not os.environ.get("OPAL_RUN_DESKTOP"):
        pytest.skip("opens Explorer, a terminal or MS Office on the real desktop; "
                    "set OPAL_RUN_DESKTOP=1 to run it")
    _run_script(name, DESKTOP_SUITES[name])
