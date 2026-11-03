"""A helper process for the Word and Excel COM conversions.

Word and Excel are out-of-process COM servers: when Office misbehaves, its RPC
layer can abort the calling process, and a document conversion must never be
able to kill Opal.  The engine runs this worker in its own python process, so
the worst case is a failed conversion - never a dead app.

Usage:  python office_worker.py <payload.json>
        (or Opal.exe --opal-office-worker <payload.json> in a frozen build)

The payload names the job, the source file and the temp target:

    {"job": "docx_to_pdf", "src": "...", "tmp": "..."}
    {"job": "xlsx_to_pdf", "src": "...", "tmp": "..."}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _docx_to_pdf(src: str, tmp: str) -> str:
    import win32com.client
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(Path(src).resolve()))
        doc.SaveAs(str(Path(tmp).resolve()), FileFormat=17)
        doc.Close()
    finally:
        word.Quit()
    return "Word printed to PDF."


def _xlsx_to_pdf(src: str, tmp: str) -> str:
    import win32com.client
    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    target = Path(tmp)
    try:
        wb = xl.Workbooks.Open(str(Path(src).resolve()))
        wb.ExportAsFixedFormat(0, str(target.resolve()))
        wb.Close(False)
    finally:
        xl.Quit()
    # Excel appends ".pdf" when the target does not already end in .pdf, so a
    # crash-safe temp name like p.pdf.tan_partial comes out as
    # p.pdf.tan_partial.pdf.  Put it where the engine expects it.
    if not target.exists():
        misplaced = target.with_suffix(target.suffix + ".pdf")
        if misplaced.exists():
            misplaced.replace(target)
    return "Excel exported to PDF."


def Excel_visible_flag() -> bool:
    return False


def main() -> int:
    return main_with_payload(sys.argv[1] if len(sys.argv) == 2 else "")


def main_with_payload(payload_path: str) -> int:
    """Entry point shared by the CLI and the packaged app's hidden flag."""
    if not payload_path:
        _emit(False, "the worker needs exactly one JSON payload path")
        return 2
    try:
        payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    except Exception as exc:
        _emit(False, f"bad payload: {type(exc).__name__}: {exc}")
        return 2

    jobs = {
        "docx_to_pdf": _docx_to_pdf,
        "xlsx_to_pdf": _xlsx_to_pdf,
    }
    job = payload.get("job")
    handler = jobs.get(job)
    if handler is None:
        _emit(False, f"unknown job {job!r}")
        return 2

    try:
        message = handler(payload["src"], payload["tmp"])
    except Exception as exc:
        _emit(False, f"{type(exc).__name__}: {exc}")
        return 0
    _emit(True, message)
    return 0


def _emit(ok: bool, message: str) -> None:
    sys.stdout.write(json.dumps({"ok": ok, "message": message}) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
