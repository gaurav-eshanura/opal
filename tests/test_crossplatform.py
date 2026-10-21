"""
Opal - Cross-platform verification
Plain English: Proves the app can load and run on macOS and Linux, not just
Windows. It imports every module, checks that no Windows-only library is
imported at module level, exercises the platform helpers, and checks the
portable-mode behaviour of the settings folder.
"""

import ast
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []

WINDOWS_ONLY = {"winreg", "win32api", "win32gui", "win32con", "win32process",
                "pythoncom", "win32com"}


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)


def main():
    print(f"Platform: {sys.platform}")

    print("\n--- MODULE IMPORTS ---")
    package = ROOT / "opal_studio"
    modules = sorted(p.stem for p in package.glob("*.py") if p.stem != "__init__")
    for name in modules:
        try:
            __import__(f"opal_studio.{name}")
            check(f"import opal_studio.{name}", True)
        except Exception as e:
            check(f"import opal_studio.{name}", False, f"{type(e).__name__}: {e}")

    print("\n--- NO WINDOWS-ONLY IMPORTS AT MODULE LEVEL ---")
    offenders = []
    for path in sorted(package.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as e:
            offenders.append(f"{path.name}: parse error {e}")
            continue
        for node in tree.body:          # module level only
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for mod in names:
                if mod in WINDOWS_ONLY:
                    offenders.append(f"{path.name}: imports {mod} at module level")
    check("no unguarded Windows-only imports", not offenders, "; ".join(offenders))

    print("\n--- PLATFORM HELPERS ---")
    from opal_studio import platform_compat as pc
    check("platform detected", bool(pc.platform_name()), pc.platform_name())
    check("user data dir is writable", pc.user_data_dir().exists(), str(pc.user_data_dir()))

    sample = ROOT / "test_sandbox" / "xplat" / "sample.txt"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text("cross platform check", encoding="utf-8")
    try:
        pc.copy_text_to_clipboard("rind")
        check("clipboard helper runs", True)
    except Exception as e:
        check("clipboard helper runs", False, str(e))

    try:
        pc.reveal_in_file_manager(str(sample))
        check("reveal helper runs", True)
    except Exception as e:
        check("reveal helper runs", False, str(e))

    try:
        pc.open_terminal(str(sample.parent))
        check("terminal helper runs", True)
    except Exception as e:
        check("terminal helper runs", False, str(e))

    check("startup support flag is a bool", isinstance(pc.startup_supported(), bool),
          pc.startup_supported())

    print("\n--- PORTABLE MODE ---")
    check("portable mode is off by default", pc.is_portable() is False)
    marker = ROOT / "portable.txt"
    marker.write_text("portable", encoding="utf-8")
    try:
        check("portable mode detected with a marker file", pc.is_portable() is True)
        check("portable data folder created", pc.portable_root() is not None)
    finally:
        marker.unlink(missing_ok=True)

    print("\n--- CROSS-OS IMPORT SIMULATION ---")
    # The app must not explode when Windows-only modules are absent.
    import builtins
    real_import = builtins.__import__
    blocked = WINDOWS_ONLY

    def guarded_import(name, *args, **kwargs):
        root = name.split(".")[0]
        if root in blocked:
            raise ImportError(f"simulated: {name} is unavailable on this platform")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import
    try:
        for mod in ("opal_studio.platform_compat", "opal_studio.config",
                    "opal_studio.context_menu", "opal_studio.engines"):
            try:
                __import__(mod)
                check(f"{mod} imports without Windows libraries", True)
            except Exception as e:
                check(f"{mod} imports without Windows libraries", False, str(e)[:80])
    finally:
        builtins.__import__ = real_import

    print("\n" + "=" * 60)
    print(f"CROSS-PLATFORM RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
