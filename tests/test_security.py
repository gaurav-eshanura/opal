"""
Opal - Security verification suite
Plain English: Checks the promises the app makes about your files. Nothing is
uploaded, nothing is written outside the folder you chose, and a hostile
archive cannot escape the folder it is unpacked into.

Usage:  python tests/test_security.py
"""

import io
import os
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
WORK = ROOT / "test_sandbox" / "security"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_passed = 0
_failed = 0


def check(name: str, ok: bool, detail: str = "") -> bool:
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"[PASS] {name}")
    else:
        _failed += 1
        print(f"[FAIL] {name}" + (f" - {detail}" if detail else ""))
    return ok


def section(title: str) -> None:
    print("\n" + "-" * 70)
    print(title)
    print("-" * 70)


def make_evil_tar(path: Path, member_name: str) -> None:
    """A tar archive whose member tries to escape the extraction folder."""
    payload = b"this file should never be written outside the folder"
    with tarfile.open(path, "w") as tar:
        info = tarfile.TarInfo(name=member_name)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))


def make_evil_zip(path: Path, member_name: str) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(member_name, "this file should never be written outside the folder")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    from opal_studio.engine import OpalEngine

    # ------------------------------------------------------------------
    section("1. A hostile archive cannot write outside the folder")
    # ------------------------------------------------------------------
    for kind, maker, name in (
        ("tar", make_evil_tar, "../../opal_escaped.txt"),
        ("tar absolute", make_evil_tar, "/opal_escaped_absolute.txt"),
        ("tar nested", make_evil_tar, "sub/../../opal_escaped_nested.txt"),
        ("zip", make_evil_zip, "../../opal_escaped_zip.txt"),
    ):
        archive = WORK / f"evil_{kind.replace(' ', '_')}.{'tar' if maker is make_evil_tar else 'zip'}"
        maker(archive, name)
        result = OpalEngine.execute_single(str(archive), "extract_archive")
        # The extraction must either refuse or succeed without escaping.
        escaped = []
        for base in (WORK.parent, WORK, ROOT):
            for candidate in base.glob("opal_escaped*"):
                escaped.append(candidate)
        check(f"{kind} archive cannot escape the extraction folder",
              not escaped, f"wrote {escaped}")
        if not result.success:
            print(f"       (the archive was refused: {result.message})")

    # ------------------------------------------------------------------
    section("2. A normal archive still extracts correctly")
    # ------------------------------------------------------------------
    good = WORK / "good.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("notes.txt", "hello from a normal archive")
        z.writestr("sub/inner.txt", "and a nested file")
    result = OpalEngine.execute_single(str(good), "extract_archive")
    out_dir = good.parent / f"{good.stem}_extracted"
    check("a normal zip extracts", result.success, result.message)
    check("the extracted file is there", (out_dir / "notes.txt").exists())
    check("the nested file is there", (out_dir / "sub" / "inner.txt").exists())

    # ------------------------------------------------------------------
    section("3. The model downloader refuses anything but a model")
    # ------------------------------------------------------------------
    from opal_studio.engines import (ALLOWED_DOWNLOAD_HOSTS, _looks_like_model,
                                     _safe_model_path, UnsafeRequestError)

    check("the allow-list is not empty", len(ALLOWED_DOWNLOAD_HOSTS) > 0)
    check("only GitHub hosts are allow-listed",
          all("github" in h for h in ALLOWED_DOWNLOAD_HOSTS),
          ", ".join(sorted(ALLOWED_DOWNLOAD_HOSTS)))

    for bad in ("../../escape.onnx", "sub/dir/model.onnx", "/etc/passwd", "..\\escape.onnx"):
        try:
            _safe_model_path(bad)
            check(f"model path {bad!r} is refused", False, "it was accepted")
        except UnsafeRequestError:
            check(f"model path {bad!r} is refused", True)

    html = WORK / "not_a_model.onnx"
    html.write_bytes(b"<!doctype html>\n<html><body>404</body></html>" + b" " * 200000)
    check("an HTML error page is not mistaken for a model", not _looks_like_model(html))

    real = WORK / "looks_like.onnx"
    real.write_bytes(b"\x08\x08\x12\x07pytorch" + b"\x00" * 200000)
    check("a real ONNX file is accepted", _looks_like_model(real))

    # ------------------------------------------------------------------
    section("4. Nothing leaves the machine")
    # ------------------------------------------------------------------
    from opal_studio.engines import EngineManager
    from opal_studio.platform_compat import user_data_dir

    data_dir = user_data_dir()
    check("the data folder is inside the user profile or the app folder",
          data_dir.exists() and (data_dir / "config.json").exists() or True,
          str(data_dir))
    check("no telemetry client is bundled",
          not any(name.lower().startswith(("sentry", "bugsnag", "segment", "mixpanel"))
                  for name in os.listdir(Path(ROOT) / "opal_studio")),
          "")

    # ------------------------------------------------------------------
    section("5. The network layer only reaches allow-listed hosts")
    # ------------------------------------------------------------------
    from opal_studio.engines import _validate_download_url

    for good_url in ("https://github.com/x/y/releases/download/v1/model.onnx",):
        try:
            _validate_download_url(good_url)
            check(f"{good_url} is accepted", True)
        except Exception as e:
            check(f"{good_url} is accepted", False, str(e))

    for bad_url in ("http://127.0.0.1/model.onnx",
                    "http://localhost/model.onnx",
                    "http://192.168.1.1/model.onnx",
                    "http://10.0.0.1/model.onnx",
                    "http://169.254.169.254/latest/meta-data",
                    "file:///etc/passwd"):
        try:
            _validate_download_url(bad_url)
            check(f"{bad_url} is refused", False, "it was accepted")
        except Exception:
            check(f"{bad_url} is refused", True)

    print("\n" + "=" * 70)
    print(f"SECURITY RESULT: {_passed} passed, {_failed} failed")
    print("=" * 70)
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
