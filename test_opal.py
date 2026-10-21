"""
Opal - Master verification runner
Plain English: Runs every Opal test suite in one go and prints a summary.
Usage:
    python test_opal.py            # core suites (fast, ~2 minutes)
    python test_opal.py --full     # adds the slow real-world suites
    python test_opal.py --list     # show what would run
"""

import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CORE_SUITES = [
    ("Engine toolkit (70 conversions & tools)", ROOT / "tests" / "test_engine_extended.py"),
    ("PDF Studio (Acrobat replacement)", ROOT / "tests" / "test_viewer_pdf.py"),
    ("Viewers & floating shell", ROOT / "tests" / "test_viewers.py"),
    ("Application smoke test", ROOT / "tests" / "test_app_smoke.py"),
    ("Customer journey (CSC / print shop)", ROOT / "tests" / "test_customer_journey.py"),
    ("Cross-platform & portable mode", ROOT / "tests" / "test_crossplatform.py"),
    ("Security guarantees", ROOT / "tests" / "test_security.py"),
]

FULL_SUITES = CORE_SUITES + [
    ("Every feature (exhaustive audit)", ROOT / "tests" / "test_every_feature.py"),
    ("Real-world end-to-end conversions", ROOT / "run_real_verification.py"),
    ("Stress & stability", ROOT / "stress_test.py"),
]


def run_suite(name: str, path: Path) -> tuple:
    print("\n" + "=" * 78)
    print(f"RUNNING: {name}")
    print("=" * 78)
    start = time.time()
    if not path.exists():
        print(f"  (skipped - {path.name} not found)")
        return name, None, 0.0
    env = {"QT_QPA_PLATFORM": "offscreen"}
    import os
    merged = {**os.environ, **env}
    proc = subprocess.run([sys.executable, str(path)], cwd=str(ROOT),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace", env=merged)
    elapsed = time.time() - start
    output = proc.stdout or ""
    for line in output.splitlines():
        if line.startswith("[FAIL]") or "RESULT" in line or "Traceback" in line:
            print("  " + line)
    passed = output.count("[PASS]")
    failed = output.count("[FAIL]")
    print(f"  -> exit {proc.returncode} | {passed} passed | {failed} failed | {elapsed:.1f}s")
    return name, proc.returncode, elapsed


def main():
    args = sys.argv[1:]
    suites = FULL_SUITES if "--full" in args else CORE_SUITES
    if "--list" in args:
        for name, path in suites:
            print(f"{'✔' if path.exists() else '✖'} {name}  ({path.name})")
        return 0

    results = []
    for name, path in suites:
        results.append(run_suite(name, path))

    print("\n" + "=" * 78)
    print("OPAL VERIFICATION SUMMARY")
    print("=" * 78)
    failures = 0
    for name, code, elapsed in results:
        if code is None:
            status = "SKIPPED"
        elif code == 0:
            status = "PASSED"
        else:
            status = "FAILED"
            failures += 1
        print(f"  {status:8s} {name} ({elapsed:.1f}s)")
    print("=" * 78)
    if failures:
        print(f"{failures} suite(s) failed.")
        return 1
    print("All suites passed. Opal is working end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
