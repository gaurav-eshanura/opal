"""
Opal - Command line interface
Plain English: Lets power users script Opal without opening the window.
Examples:
    Opal --convert photo.HEIC --to png
    Opal --convert invoice.pdf --to docx --out C:\\Reports
    Opal --convert photos/ --to pdf --recursive            # a whole folder at once
    Opal --convert photos/ --to pdf --json                 # machine-readable summary
    Opal --convert clip.mp4 --to gif
    Opal --tool photo.jpg --tool remove_bg
    Opal --sign contract.pdf --token                    # sign with the plugged-in DSC USB token
    Opal --sign contract.pdf --pfx cert.pfx             # sign with a .pfx / .p12 certificate file
    Opal --sign contract.pdf --token --out signed.pdf --page 1 --tsa https://freetsa.org/tsr
    Opal --verify-signature signed.pdf                  # cryptographically validate signatures
    Opal --catalog
    Opal --info report.pdf
The DSC PIN / certificate password is read from the OPAL_DSC_PIN environment
variable or asked for interactively - never passed on the command line.
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
                or os.environ.get("OPAL_CLI_QUIET") \
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
    parser.add_argument("--recursive", action="store_true",
                        help="when a folder is given, include its subfolders too")
    parser.add_argument("--json", dest="json_mode", action="store_true",
                        help="print the run summary as one machine-readable JSON object")
    parser.add_argument("--catalog", action="store_true",
                        help="list every conversion and tool Opal can run")
    parser.add_argument("--info", metavar="FILE", default="",
                        help="print details about a file (type, size, PDF pages, EXIF)")
    parser.add_argument("--list-formats", action="store_true",
                        help="list the formats Opal understands")
    parser.add_argument("--sign", nargs="+", metavar="FILE",
                        help="digitally sign PDF file(s) with a DSC certificate")
    parser.add_argument("--pfx", default="",
                        help="sign with this PKCS#12 certificate file (.pfx/.p12)")
    parser.add_argument("--token", action="store_true",
                        help="sign with the plugged-in DSC USB token (PKCS#11)")
    parser.add_argument("--pkcs11-lib", default="",
                        help="PKCS#11 driver DLL/.so of the token (default: auto-detect)")
    parser.add_argument("--slot", type=int, default=-1,
                        help="token slot number (default: the slot the token is in)")
    parser.add_argument("--cert-label", default="",
                        help="certificate label on the token (default: the only one)")
    parser.add_argument("--page", type=int, default=1,
                        help="page to sign, 1-based (default: 1)")
    parser.add_argument("--rect", default="",
                        help='signature box "x0,y0,x1,y1" in PDF points (default "60,60,240,120")')
    parser.add_argument("--reason", default="Approved by the signer",
                        help="signature reason")
    parser.add_argument("--location", default="India",
                        help="signature location")
    parser.add_argument("--contact", default="",
                        help="signature contact info")
    parser.add_argument("--field", dest="field_name", default="OpalDSC",
                        help="signature field name (default: OpalDSC)")
    parser.add_argument("--tsa", default="",
                        help="RFC 3161 timestamp server URL for --sign (allow-listed "
                             "hosts only, e.g. https://freetsa.org/tsr; default: none, "
                             "signing stays offline)")
    parser.add_argument("--verify-signature", metavar="FILE", default="",
                        help="cryptographically validate every signature in a PDF "
                             "(prints JSON: intact / trusted / revoked / signer)")
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


def _expand_inputs(inputs: List[str], recursive: bool = False, out_dir: str = "",
                   target: str = "") -> "tuple[List[str], List[str]]":
    """Turns the --convert/--tool arguments into real files.

    A directory means "every supported file in it" (with --recursive, in its
    subfolders too).  Files that already carry the target suffix, and files
    sitting in the output folder, are skipped, so a folder run cannot feed on
    its own results.  Returns (files, missing); the caller reports missing.
    """
    files: List[str] = []
    missing: List[str] = []
    out_resolved = Path(out_dir).expanduser().resolve() if out_dir else None
    # A convert target that names a format ("pdf", "webp") must not re-eat
    # files that already have that suffix; a tool id ("remove_bg") cannot.
    target_ext = ""
    if target and f".{target.lower()}" in OpalEngine.SUPPORTED_EXTS:
        target_ext = f".{target.lower()}"

    for raw in inputs:
        p = Path(raw).expanduser()
        if p.is_dir():
            entries = sorted(p.rglob("*") if recursive else p.glob("*"))
            for q in entries:
                if not q.is_file():
                    continue
                ext = q.suffix.lower()
                if ext not in OpalEngine.SUPPORTED_EXTS:
                    continue
                if target_ext and ext == target_ext:
                    continue
                if out_resolved is not None and q.resolve().parent == out_resolved:
                    continue
                files.append(str(q))
        elif p.exists():
            files.append(str(p))
        else:
            missing.append(raw)
    return files, missing


def _cmd_run(files: List[str], target: str, options: dict, recursive: bool = False,
             out_dir: str = "", json_mode: bool = False) -> int:
    if not target:
        out("error: --to is required with --convert, or use --tool")
        return 2
    expanded, missing = _expand_inputs(files, recursive, out_dir, target)
    for m in missing:
        out(f"error: {m} does not exist")
    if not expanded:
        if missing:
            out(f"0 succeeded, {len(missing)} failed")
            return 1
        out("error: no supported files found in the given path(s)")
        return 2

    results = []
    failed = 0
    for f in expanded:
        p = Path(f)
        res = OpalEngine.execute_single(str(p), target, options)
        results.append({"file": str(p), "success": res.success,
                        "output": res.output_path or "", "message": res.message})
        if res.success:
            if not json_mode:
                out(f"OK   {p.name} -> {res.output_path}  ({res.message})")
        else:
            failed += 1
            if not json_mode:
                out(f"FAIL {p.name}: {res.message}")
    succeeded = len(results) - failed
    if json_mode:
        out(json.dumps({"action": target, "succeeded": succeeded, "failed": failed,
                        "results": results}, indent=2, ensure_ascii=False))
    else:
        out("")
        out(f"{succeeded} succeeded, {failed} failed")
    return 1 if failed else 0


def _cli_secret(prompt_text: str) -> Optional[str]:
    """The DSC PIN / certificate password: read from OPAL_DSC_PIN, else asked
    for interactively. Never taken from argv, never written to disk or logs."""
    import os
    # Presence counts, not truthiness: an explicitly empty OPAL_DSC_PIN means
    # "the certificate has no password".
    if "OPAL_DSC_PIN" in os.environ:
        return os.environ["OPAL_DSC_PIN"]
    try:
        import getpass
        # Only prompt when both ends are a real terminal - in a pipe/script the
        # prompt would hang forever, so fall through to the error instead.
        if (sys.stdin is not None and sys.stdin.isatty()
                and sys.stdout is not None and sys.stdout.isatty()):
            return getpass.getpass(prompt_text)
    except Exception:
        pass
    return None


def _sign_output_path(src: Path, out_dir: str) -> Path:
    """Where the signed copy goes: --out as a .pdf file (single input), --out
    as a folder, otherwise next to the original as <name>_signed.pdf."""
    if out_dir:
        p = Path(out_dir).expanduser()
        if out_dir.lower().endswith(".pdf") and not p.is_dir():
            return p
        if p.is_dir() or out_dir.endswith(("/", "\\")):
            return p / (src.stem + "_signed.pdf")
    return src.with_name(src.stem + "_signed.pdf")


def _cmd_sign(files: List[str], args) -> int:
    with contextlib.redirect_stdout(sys.stderr):
        from opal_studio import dsc_sign
    if not dsc_sign.available():
        out("error: the PDF signing engine (pyHanko) is not installed")
        return 2
    expanded, missing = _expand_inputs(files, args.recursive, "", "")
    for m in missing:
        out(f"error: {m} does not exist")
    pdfs = [f for f in expanded if Path(f).suffix.lower() == ".pdf"]
    if not pdfs:
        out("error: --sign needs PDF file(s)")
        return 2

    rect = (60, 60, 240, 120)
    if getattr(args, "rect", ""):
        try:
            parts = [float(v) for v in str(args.rect).replace(" ", "").split(",")]
            if len(parts) == 4:
                rect = tuple(parts)
        except ValueError:
            out("error: --rect must be four numbers: x0,y0,x1,y1")
            return 2
    page_no = max(0, (args.page or 1) - 1)

    if args.pfx and args.token:
        out("error: pass either --pfx or --token, not both")
        return 2

    if args.pfx:
        secret = _cli_secret("Certificate password: ")
        if secret is None:
            out("error: no password available - set OPAL_DSC_PIN or run in a terminal")
            return 2
        try:
            info = dsc_sign.inspect_certificate(args.pfx, secret)
        except dsc_sign.DscError as e:
            out(f"error: {e}")
            return 2
        out(f"certificate: {info['subject']}")
        out(f"  issuer: {info['issuer']}")
        out(f"  serial: {info['serial']}  valid {info['valid_from']} -> {info['valid_to']}"
            + ("  EXPIRED" if info["expired"] else ""))
        mode = ("pfx", args.pfx, secret, None)
    elif args.token:
        if not dsc_sign.token_available():
            out("error: PKCS#11 token signing is not available (python-pkcs11 missing?)")
            return 2
        lib_path = args.pkcs11_lib
        slot_no = args.slot
        try:
            if not lib_path:
                devices, errors = dsc_sign.list_dsc_devices()
                if not devices:
                    detail = "; ".join(f"{Path(k).name}: {v}" for k, v in list(errors.items())[:3])
                    out("error: no DSC token found" + (f" ({detail})" if detail else ""))
                    return 2
                dev = devices[0]
                lib_path = dev["module"]
                if slot_no < 0:
                    slot_no = int(dev["slot"])
                out(f"token: {dev['label']} ({dev['manufacturer']} {dev['model']}, serial {dev['serial']})")
            if slot_no < 0:
                slot_no = 0
            certs = dsc_sign.inspect_token(lib_path, slot_no)
        except dsc_sign.DscError as e:
            out(f"error: {e}")
            return 2
        cert = None
        if args.cert_label:
            for c in certs:
                if c["label"] == args.cert_label or c["id_hex"] == args.cert_label:
                    cert = c
                    break
            if cert is None:
                out(f"error: no certificate {args.cert_label!r} on the token; "
                    f"available: {[c['label'] for c in certs]}")
                return 2
        elif len(certs) == 1:
            cert = certs[0]
        else:
            out("error: the token holds several certificates - pass --cert-label; available: "
                + ", ".join(c["label"] for c in certs))
            return 2
        out(f"certificate: {cert['subject']}")
        out(f"  issuer: {cert['issuer']}")
        out(f"  serial: {cert['serial']}  valid {cert['valid_from']} -> {cert['valid_to']}"
            + ("  EXPIRED" if cert["expired"] else ""))
        secret = _cli_secret("Token PIN: ")
        if secret is None:
            out("error: no PIN available - set OPAL_DSC_PIN or run in a terminal")
            return 2
        mode = ("token", lib_path, secret, (slot_no, cert["label"]))
    else:
        out("error: --sign needs --pfx FILE or --token")
        return 2

    results = []
    failed = 0
    for f in pdfs:
        src = Path(f)
        dst = _sign_output_path(src, args.out_dir)
        entry = {"file": str(src), "output": str(dst), "verified": False}
        try:
            if mode[0] == "pfx":
                dsc_sign.sign_pdf(str(src), str(dst), mode[1], mode[2],
                                  page_no=page_no, rect=rect, reason=args.reason,
                                  location=args.location, contact=args.contact,
                                  field_name=args.field_name, tsa_url=args.tsa)
            else:
                slot_no, cert_label = mode[3]
                dsc_sign.sign_pdf_token(str(src), str(dst), mode[1], mode[2],
                                        slot_no=slot_no, cert_label=cert_label,
                                        page_no=page_no, rect=rect, reason=args.reason,
                                        location=args.location, contact=args.contact,
                                        field_name=args.field_name, tsa_url=args.tsa)
            check = dsc_sign.verify_signature(str(dst))
            ok = bool(check.get("signed")) and not check.get("error")
            entry["verified"] = ok
            entry["signatures"] = check.get("count", 0)
            if not ok:
                failed += 1
                entry["error"] = check.get("error", "no signature field in the output")
                if not args.json_mode:
                    out(f"FAIL {src.name}: the signed file did not verify ({entry['error']})")
            else:
                if not args.json_mode:
                    out(f"OK   {src.name} -> {dst}  (signature verified, {entry['signatures']} field)")
        except dsc_sign.DscError as e:
            failed += 1
            entry["error"] = str(e)
            if not args.json_mode:
                out(f"FAIL {src.name}: {e}")
        results.append(entry)
    if args.json_mode:
        out(json.dumps({"action": "sign", "mode": mode[0],
                        "succeeded": len(results) - failed, "failed": failed,
                        "results": results}, indent=2, ensure_ascii=False))
    else:
        out("")
        out(f"{len(results) - failed} signed, {failed} failed")
    return 1 if failed else 0


def _cmd_verify_signature(path: str) -> int:
    with contextlib.redirect_stdout(sys.stderr):
        from opal_studio import dsc_sign
    p = Path(path)
    if not p.exists():
        out(f"error: {path} does not exist")
        return 2
    res = dsc_sign.verify_signature_deep(str(p))
    res["file"] = str(p.resolve())
    out(json.dumps(res, indent=2, ensure_ascii=False))
    sigs = res.get("signatures", [])
    return 0 if (sigs and res.get("all_intact") and not any(s.get("revoked") for s in sigs)) else 1


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    code = 0
    if args.sign:
        code = _cmd_sign(args.sign, args)
    elif args.verify_signature:
        code = _cmd_verify_signature(args.verify_signature)
    elif args.catalog:
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
            code = _cmd_run(args.convert, args.target, options,
                            recursive=args.recursive, out_dir=args.out_dir,
                            json_mode=args.json_mode)
        elif args.tool:
            code = _cmd_run(args.tool, args.target or "remove_bg", options,
                            recursive=args.recursive, out_dir=args.out_dir,
                            json_mode=args.json_mode)
        else:
            parser.print_help()
            return 0

    flush_output(_BUFFER[-1] if _BUFFER else "Opal finished.")
    return code


if __name__ == "__main__":
    sys.exit(main())
