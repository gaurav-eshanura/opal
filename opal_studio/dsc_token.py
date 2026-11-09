"""
Opal - Connected DSC token support (PKCS#11)
Plain English: signs a PDF with a DSC USB token that is plugged in, the way
Adobe Acrobat does. The token's PKCS#11 driver DLL is found automatically, the
certificate is read straight off the token, and the signature is computed
inside the token - the private key never leaves the device.

The PIN is only ever passed in memory (dialog / getpass / env var); it is
never written to disk, logged, or put on a command line.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import pkcs11 as _p11
    HAVE_PKCS11 = True
except Exception:
    _p11 = None
    HAVE_PKCS11 = False

try:
    from pyhanko.sign import signers
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    HAVE_PYHANKO = True
except Exception:
    HAVE_PYHANKO = False


class TokenError(Exception):
    """Raised when a DSC token cannot be found, read, or used to sign."""


# Substrings that mark a file as a PKCS#11 driver, plus the vendor names the
# Indian DSC tokens ship under. Vendors are matched against the START of the
# file name only - a bare "p11" substring would match msvcp110.dll & co.
_STRONG_HINTS = ("pkcs11", "csp11")
_VENDOR_PREFIXES = (
    "hyp2003", "epass", "watchdata", "wdpkcs", "etoken", "mtoken", "mtok",
    "safenet", "proxkey", "trustkey", "idprime", "oberthur", "gemalto",
    "pteid", "starsign", "esign", "axalto", "athena",
)


def _looks_like_pkcs11(filename: str) -> bool:
    low = filename.lower()
    if not low.endswith((".dll", ".so", ".dylib")):
        return False
    return any(h in low for h in _STRONG_HINTS) or low.startswith(_VENDOR_PREFIXES)


def pkcs11_available() -> bool:
    """True when the PKCS#11 binding and the signing engine are installed."""
    return HAVE_PKCS11 and HAVE_PYHANKO


def candidate_modules() -> List[str]:
    """Every PKCS#11 driver DLL that plausibly belongs to a plugged-in token.

    Order: the OPAL_PKCS11_LIB override, then the Windows smart-card module
    registry, then well-known DLL names in System32 / SysWOW64, then the
    vendor folders under Program Files. Only files that exist are returned.
    """
    found: List[str] = []

    def add(p):
        p = str(Path(p))
        if p.lower().endswith((".dll", ".so", ".dylib")) and os.path.isfile(p) \
                and p.lower() not in {f.lower() for f in found}:
            found.append(p)

    env = os.environ.get("OPAL_PKCS11_LIB")
    if env:
        # An explicit driver path is an override, not a hint: use exactly it
        # and load no other vendor module into this process.
        return [env]

    # Windows registers each smart card's PKCS#11 module here.
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE,):
            for sub in (r"SOFTWARE\Microsoft\Cryptography\Calais\SmartCardModules",
                        r"SOFTWARE\WOW6432Node\Microsoft\Cryptography\Calais\SmartCardModules"):
                try:
                    key = winreg.OpenKey(hive, sub)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        if isinstance(value, str) and value.lower().endswith(".dll"):
                            add(value)
                        i += 1
                    winreg.CloseKey(key)
                except OSError:
                    pass
    except Exception:
        pass

    # SysWOW64 holds the 32-bit copies of every DLL; loading one into a 64-bit
    # process is a hard crash, not a catchable error, so only scan it when we
    # really are a 32-bit interpreter.
    _sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    _system_dirs = [_sysroot + r"\System32"]
    if sys.maxsize <= 2 ** 32:
        _system_dirs.append(_sysroot + r"\SysWOW64")
    for system_dir in _system_dirs:
        try:
            for name in os.listdir(system_dir):
                if _looks_like_pkcs11(name):
                    add(os.path.join(system_dir, name))
        except OSError:
            pass

    for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"),
               os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
               os.environ.get("ProgramW6432", r"C:\Program Files")):
        if not pf:
            continue
        try:
            for vendor in os.listdir(pf):
                vlow = vendor.lower()
                if any(h in vlow for h in ("pkcs", "epass", "watchdata", "token",
                                           "safenet", "proxkey", "trustkey", "dsc",
                                           "hyper", "crypto", "smartcard", "ccid")):
                    vdir = os.path.join(pf, vendor)
                    for dirpath, _, files in os.walk(vdir):
                        for name in files:
                            if _looks_like_pkcs11(name):
                                add(os.path.join(dirpath, name))
        except OSError:
            pass

    return found


def list_devices() -> Tuple[List[Dict[str, object]], Dict[str, str]]:
    """(devices, errors): one entry per slot that holds a token, across every
    candidate driver module. Never raises - a driver that fails to load is
    just recorded in errors."""
    if not HAVE_PKCS11:
        raise TokenError("The PKCS#11 binding (python-pkcs11) is not installed.")
    devices: List[Dict[str, object]] = []
    errors: Dict[str, str] = {}
    for module in candidate_modules():
        try:
            lib = _p11.lib(module)
            for slot_no, slot in enumerate(lib.get_slots()):
                try:
                    token = slot.get_token()
                except Exception:
                    continue  # empty slot

                def _prop(name):
                    try:
                        value = getattr(token, name) or ""
                    except Exception:
                        return ""
                    if isinstance(value, bytes):
                        return value.decode("utf-8", "replace").strip("\x00 ")
                    return str(value).strip("\x00 ")

                devices.append({
                    "module": module,
                    "slot": slot_no,
                    "label": _prop("label"),
                    "manufacturer": _prop("manufacturer_id"),
                    "model": _prop("model"),
                    "serial": _prop("serial"),
                })
        except Exception as e:
            errors[module] = f"{type(e).__name__}: {e}"
    return devices, errors


def list_token_certs(lib_path: str, slot_no: int = 0) -> List[Dict[str, object]]:
    """Reads the X.509 certificates off the token (public objects - no PIN
    needed) and returns them in the same shape inspect_certificate() uses."""
    if not HAVE_PKCS11:
        raise TokenError("The PKCS#11 binding (python-pkcs11) is not installed.")
    import hashlib
    import datetime
    from asn1crypto import x509

    if not os.path.isfile(lib_path):
        raise TokenError(f"PKCS#11 driver not found: {lib_path}")
    try:
        lib = _p11.lib(lib_path)
        slots = lib.get_slots()
    except Exception as e:
        raise TokenError(f"Could not load the PKCS#11 driver {Path(lib_path).name}: "
                         f"{str(e).splitlines()[0]}")
    if slot_no >= len(slots):
        raise TokenError(f"Slot {slot_no} does not exist - the driver has {len(slots)} slot(s).")
    try:
        token = slots[slot_no].get_token()
    except Exception as e:
        raise TokenError(f"No token in slot {slot_no} of {Path(lib_path).name}: {e}")
    session = token.open()  # read-only: public objects only
    try:
        certs = []
        for obj in session.get_objects({
                _p11.Attribute.CLASS: _p11.ObjectClass.CERTIFICATE}):
            try:
                der = obj[_p11.Attribute.VALUE]
                cert = x509.Certificate.load(der)
                label = obj[_p11.Attribute.LABEL]
                cid = obj[_p11.Attribute.ID]
                validity = cert["tbs_certificate"]["validity"]
                nb, na = validity["not_before"].native, validity["not_after"].native
                now = datetime.datetime.now(datetime.timezone.utc)
                certs.append({
                    "label": label if isinstance(label, str) else label.decode("utf-8", "replace"),
                    "id_hex": cid.hex() if cid else "",
                    "subject": cert.subject.human_friendly,
                    "issuer": cert.issuer.human_friendly,
                    "serial": format(cert.serial_number, "X"),
                    "valid_from": nb.strftime("%d %b %Y, %H:%M"),
                    "valid_to": na.strftime("%d %b %Y, %H:%M"),
                    "expired": na < now,
                    "not_yet_valid": nb > now,
                    "sha256_fingerprint": hashlib.sha256(der).hexdigest().upper(),
                })
            except Exception:
                continue  # a non-X.509 certificate object on the token
        if not certs:
            raise TokenError(f"No certificates found on the token in slot {slot_no}.")
        return certs
    finally:
        session.close()


def _pick_cert(lib_path: str, slot_no: int, cert_label: Optional[str]) -> Dict[str, object]:
    certs = list_token_certs(lib_path, slot_no)
    if cert_label:
        for c in certs:
            if c["label"] == cert_label or c["id_hex"] == cert_label:
                return c
        raise TokenError(f"No certificate labelled {cert_label!r} on the token. "
                         f"Available: {[c['label'] for c in certs]}")
    if len(certs) > 1:
        raise TokenError("The token holds more than one certificate - pass cert_label. "
                         f"Available: {[c['label'] for c in certs]}")
    return certs[0]


def open_token_signer(lib_path: str, pin: Optional[str], slot_no: int = 0,
                      cert_label: Optional[str] = None):
    """Opens a logged-in session on the token and builds a pyHanko signer that
    computes signatures inside the token. Returns (signer, session); the
    caller must close the session when done."""
    if not pkcs11_available():
        raise TokenError("PKCS#11 signing needs python-pkcs11 and pyHanko installed.")
    from pyhanko.sign import pkcs11 as hanko_pkcs11

    cert = _pick_cert(lib_path, slot_no, cert_label)
    session = hanko_pkcs11.open_pkcs11_session(
        lib_path, slot_no=slot_no, user_pin=pin if pin else None)
    try:
        signer = hanko_pkcs11.PKCS11Signer(
            session,
            cert_label=cert["label"],
            cert_id=bytes.fromhex(cert["id_hex"]) if cert["id_hex"] else None,
        )
    except Exception:
        session.close()
        raise
    return signer, session


def _signature_field_spec(field_name: str, page_no: int, rect):
    box = tuple(int(round(v)) for v in rect)
    try:
        from pyhanko.sign.fields import SigFieldSpec
        return SigFieldSpec(sig_field_name=field_name, on_page=page_no, box=box)
    except Exception:
        return (field_name, box)


def sign_pdf_with_token(src: str, dst: str, lib_path: str, pin: Optional[str],
                        slot_no: int = 0, cert_label: Optional[str] = None,
                        page_no: int = 0, rect: Tuple[float, float, float, float] = (60, 60, 240, 120),
                        reason: str = "Approved by the signer",
                        location: str = "India", contact: str = "",
                        field_name: str = "OpalDSC",
                        use_existing_field: bool = True,
                        tsa_url: str = "",
                        certify: bool = False,
                        mdp_permission: int = 2) -> str:
    """Signs src with the certificate on the connected token and writes the
    signed copy to dst. The private key never leaves the token. When the form
    has an empty signature field it is signed into; tsa_url optionally embeds
    an RFC 3161 timestamp from an allow-listed server (default: offline)."""
    if not HAVE_PYHANKO:
        raise TokenError("The PDF signing engine (pyHanko) is not installed.")
    source = Path(src)
    if not source.exists():
        raise TokenError(f"Document not found: {source}")

    signer, session = open_token_signer(lib_path, pin, slot_no=slot_no, cert_label=cert_label)
    try:
        # shared helpers live in dsc_sign (imported lazily to avoid a cycle)
        from opal_studio import dsc_sign as _ds
        spec, effective_name = _ds.resolve_field_spec(source, field_name, page_no, rect,
                                                      use_existing_field)
        timestamper = _ds.make_timestamper(tsa_url)
        with open(source, "rb") as fh:
            writer = IncrementalPdfFileWriter(fh)
            docmdp_perm = None
            if certify:
                from pyhanko.sign.fields import MDPPerm
                perm_map = {
                    1: MDPPerm.NO_CHANGES,
                    2: MDPPerm.FILL_FORMS,
                    3: MDPPerm.ANNOTATE,
                }
                docmdp_perm = perm_map.get(mdp_permission, MDPPerm.FILL_FORMS)

            meta = signers.PdfSignatureMetadata(
                field_name=effective_name, reason=reason, location=location,
                contact_info=contact, embed_validation_info=False,
                certify=certify, docmdp_permissions=docmdp_perm)
            signed = signers.sign_pdf(writer, meta, signer=signer,
                                      timestamper=timestamper, new_field_spec=spec)
        if hasattr(signed, "getvalue"):
            payload = signed.getvalue()
        elif hasattr(signed, "read"):
            signed.seek(0)
            payload = signed.read()
        else:
            payload = bytes(signed)
        Path(dst).write_bytes(payload)
        return dst
    except TokenError:
        raise
    except Exception as e:
        raise TokenError(f"Signing with the token failed: {e}")
    finally:
        try:
            session.close()
        except Exception:
            pass
