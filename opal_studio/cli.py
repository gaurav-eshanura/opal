"""
Opal - Command line interface
Plain English: Lets power users script Opal without opening the window.
Examples:
    Opal --convert photo.HEIC --to png
    Opal --convert invoice.pdf --to docx --out C:\\Reports
    Opal --convert clip.mp4 --to gif
    Opal --tool photo.jpg --tool remove_bg
    Opal --catalog
    Opal --info report.pdf
Everything still runs locally on your machine.
"""

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import List, Optional

# Running this file directly (or through opal_cli.bat) puts the package folder
# on the path, not the project root, so the import below needs a hand.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Libraries sometimes print a deprecation notice while they are imported.
# The command line output has to stay machine-readable, so anything printed
# during the import goes to stderr instead of stdout.
with contextlib.redirect_stdout(sys.stderr):
    from opal_studio.engine import OpalEngine

# In a windowed (no-console) build there is no stdout, so keep a buffer and
# write the result to a file (and a message box) when the app is packaged.
_BUFFER: List[str] = []


def out(message: str = "") -> None:
    text = str(message)
    _BUFFER.append(text)
    try:
        stream = sys.stdout
        if stream is None:
            return
        try:
            stream.write(text + "\n")
        except UnicodeEncodeError:
            encoding = getattr(stream, "encoding", None) or "utf-8"
            stream.write((text + "\n").encode(encoding, "replace").decode(encoding, "replace"))
        stream.flush()
    except Exception:
        pass


def flush_output(summary: str) -> None:
    """Shows the CLI result when there is no console to print to."""
    if sys.stdout is not None:
        return
    try:
        import os
        import tempfile
        path = Path(tempfile.gettempdir()) / "opal_cli_output.txt"
        path.write_text("\n".join(_BUFFER), encoding="utf-8")
    except Exception:
        path = None
    try:
        import os
        if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen" \
                or os.environ.get("TANGERINE_CLI_QUIET"):
            return
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        box = QMessageBox()
        box.setWindowTitle("Opal CLI")
        box.setText(summary)
        if path:
            box.setDetailedText(f"Full output:\n{path}")
        box.exec()
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Opal",
        description="Opal - every file, in every light. Command line mode.",
        add_help=True)
    parser.add_argument("--convert", nargs="+", metavar="FILE",
                        help="convert one or more files")
    parser.add_argument("--tool", nargs="+", metavar="FILE",
                        help="run a studio tool on one or more files")
    parser.add_argument("--to", dest="target", default="",
                        help="target format or tool id (e.g. png, docx, remove_bg)")
    parser.add_argument("--out", dest="out_dir", default="",
                        help="write results into this folder")
    parser.add_argument("--options", dest="options_json", default="",
                        help="JSON object with extra tool options")
    parser.add_argument("--catalog", action="store_true",
                        help="list every conversion and tool Opal can run")
    parser.add_argument("--info", metavar="FILE", default="",
                        help="print details about a file (type, size, PDF pages, EXIF)")
    parser.add_argument("--list-formats", action="store_true",
                        help="list the formats Opal understands")
    return parser


def _resolve_output_dir(out_dir: str) -> None:
    if out_dir:
        target = Path(out_dir).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        from opal_studio.config import ConfigManager
        cfg = ConfigManager.load_config()
        cfg["output_mode"] = "custom"
        cfg["custom_output_dir"] = str(target)
        ConfigManager.save_config(cfg)


def _cmd_catalog() -> int:
    items = OpalEngine.get_catalog()
    out(f"Opal can do {len(items)} things:")
    for item in items:
        out(f"  {item['id']:<22s} {item['label']:<28s} {item['desc']}")
    return 0


def _cmd_list_formats() -> int:
    out("Images: " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.IMAGE_EXTS)))
    out("Video  : " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.VIDEO_EXTS)))
    out("Audio  : " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.AUDIO_EXTS)))
    out("Docs   : " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.DOC_EXTS)))
    out("PDF    : " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.PDF_EXTS)))
    out("Fonts  : " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.FONT_EXTS)))
    out("Archive: " + ", ".join(sorted(e.lstrip('.') for e in OpalEngine.ARCHIVE_EXTS)))
    return 0


def _cmd_info(path: str) -> int:
    p = Path(path)
    if not p.exists():
        out(f"error: {path} does not exist")
        return 2
    info = {
        "name": p.name,
        "path": str(p.resolve()),
        "size_bytes": p.stat().st_size,
        "suffix": p.suffix.lower(),
        "category": OpalEngine.get_file_category([str(p)]),
    }
    if p.suffix.lower() == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(p))
            info["pages"] = len(doc)
            info["encrypted"] = doc.needs_pass
            info["metadata"] = {k: v for k, v in (doc.metadata or {}).items() if v}
            doc.close()
        except Exception as e:
            info["error"] = str(e)
    elif p.suffix.lower() in OpalEngine.IMAGE_EXTS:
        try:
            from PIL import Image, ExifTags
            with Image.open(p) as img:
                info["dimensions"] = f"{img.width}x{img.height}"
                info["mode"] = img.mode
                exif = img.getexif()
                if exif:
                    info["exif"] = {ExifTags.TAGS.get(k, str(k)): str(v)
                                     for k, v in exif.items()}
        except Exception as e:
            info["error"] = str(e)
    elif p.suffix.lower() in OpalEngine.VIDEO_EXTS | OpalEngine.AUDIO_EXTS:
        from opal_studio.engines import EngineManager
        info["duration_seconds"] = EngineManager.media_duration(p)
    out(json.dumps(info, indent=2, ensure_ascii=False))
    return 0


def _cmd_run(files: List[str], target: str, options: dict) -> int:
    if not target:
        out("error: --to is required with --convert, or use --tool")
        return 2
    results = []
    failed = 0
    for f in files:
        p = Path(f)
        if not p.exists():
            out(f"error: {f} does not exist")
            failed += 1
            continue
        res = OpalEngine.execute_single(str(p), target, options)
        if res.success:
            out(f"OK   {p.name} -> {res.output_path}  ({res.message})")
            results.append(res.output_path)
        else:
            out(f"FAIL {p.name}: {res.message}")
            failed += 1
    out("")
    out(f"{len(results)} succeeded, {failed} failed")
    return 1 if failed else 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    code = 0
    if args.catalog:
        code = _cmd_catalog()
    elif args.list_formats:
        code = _cmd_list_formats()
    elif args.info:
        code = _cmd_info(args.info)
    else:
        options = {}
        if args.options_json:
            try:
                options = json.loads(args.options_json)
            except Exception as e:
                out(f"error: --options is not valid JSON ({e})")
                return 2

        if args.out_dir:
            _resolve_output_dir(args.out_dir)

        if args.convert:
            code = _cmd_run(args.convert, args.target, options)
        elif args.tool:
            code = _cmd_run(args.tool, args.target or "remove_bg", options)
        else:
            parser.print_help()
            return 0

    flush_output(_BUFFER[-1] if _BUFFER else "Opal finished.")
    return code


if __name__ == "__main__":
    sys.exit(main())
