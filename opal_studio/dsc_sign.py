"""
Opal - Digital Signature Certificate (DSC) support
Plain English: Signs a PDF with a real digital signature certificate, exactly
like the .pfx / .p12 token files that Indian certificate authorities issue.
Signing happens locally: your private key never leaves your machine, and the
signed file keeps a verifiable cryptographic signature that any reader can check.
"""

import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

try:
    from pyhanko.sign import signers
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from cryptography.hazmat.primitives import hashes
    HAVE_PYHANKO = True
except Exception:
    HAVE_PYHANKO = False



class DocMDPPermission:
    NO_CHANGES = 1
    FILL_FORMS = 2
    ANNOTATE = 3

    LABELS = {
        1: "No Changes Allowed (Document Locked)",
        2: "Form Filling & Signatures Allowed",
        3: "Annotations, Form Filling & Signatures Allowed",
    }

class DscError(Exception):
    """Raised when a certificate cannot be read or a document cannot be signed."""


def available() -> bool:
    """True when the signing engine is installed."""
    return HAVE_PYHANKO


def _load_signer(pfx_path: str, password: str):
    if not HAVE_PYHANKO:
        raise DscError("The PDF signing engine (pyHanko) is not installed.")
    path = Path(pfx_path)
    if not path.exists():
        raise DscError(f"Certificate file not found: {path}")
    try:
        # cryptography wants the passphrase as bytes.
        secret = password.encode("utf-8") if password else None
        signer = signers.SimpleSigner.load_pkcs12(str(path), passphrase=secret)
    except Exception as e:
        raise DscError(f"Could not open the certificate: {e}")
    if signer is None:
        # pyHanko logs the underlying error and returns None on a bad password.
        raise DscError("Could not open the certificate - wrong password?")
    return signer


def _cert_der(cert) -> bytes:
    """Returns the DER bytes of a certificate, whichever library produced it."""
    try:
        return cert.dump()  # asn1crypto
    except AttributeError:
        from cryptography.hazmat.primitives import serialization
        return cert.public_bytes(serialization.Encoding.DER)


def _cert_name(cert, which: str) -> str:
    """Human readable subject/issuer, for both cryptography and asn1crypto objects."""
    name = getattr(cert, which, None)
    if name is None:
        return ""
    for attr in ("rfc4514_string", "human_friendly"):
        getter = getattr(name, attr, None)
        if callable(getter):
            try:
                return str(getter())
            except Exception:
                pass
    try:
        native = name.native
        if isinstance(native, dict):
            return ", ".join(f"{k}={v}" for k, v in native.items())
        return str(native)
    except Exception:
        return str(name)


def _cert_dates(cert) -> Tuple[datetime.datetime, datetime.datetime]:
    """Validity window as timezone-aware datetimes."""
    # asn1crypto style
    try:
        validity = cert["tbs_certificate"]["validity"]
        start = validity["not_before"].native
        end = validity["not_after"].native
        return start, end
    except Exception:
        pass
    start = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before
    end = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
    return start, end


def _cert_serial(cert) -> str:
    try:
        return format(cert.serial_number, "X")
    except AttributeError:
        try:
            return format(cert.serial_number, "X")
        except Exception:
            return ""


def inspect_certificate(pfx_path: str, password: str) -> Dict[str, str]:
    """Reads the certificate and returns its details for the user to confirm."""
    import hashlib
    signer = _load_signer(pfx_path, password)
    cert = signer.signing_cert
    not_before, not_after = _cert_dates(cert)
    now = datetime.datetime.now(datetime.timezone.utc)

    def _aware(value):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value

    return {
        "subject": _cert_name(cert, "subject"),
        "issuer": _cert_name(cert, "issuer"),
        "serial": _cert_serial(cert),
        "valid_from": _aware(not_before).strftime("%d %b %Y, %H:%M"),
        "valid_to": _aware(not_after).strftime("%d %b %Y, %H:%M"),
        "expired": _aware(not_after) < now,
        "not_yet_valid": _aware(not_before) > now,
        "sha256_fingerprint": hashlib.sha256(_cert_der(cert)).hexdigest().upper(),
    }


def sign_pdf(src: str, dst: str, pfx_path: str, password: str,
              page_no: int = 0, rect: Tuple[float, float, float, float] = (60, 60, 240, 120),
              reason: str = "Approved by the signer",
              location: str = "India",
              contact: str = "",
              field_name: str = "OpalDSC",
              use_existing_field: bool = True,
              tsa_url: str = "",
              certify: bool = False,
              mdp_permission: int = 2) -> str:
    """
    Signs the PDF with the given certificate and writes the signed copy to dst.
    rect is in PDF points with the origin at the BOTTOM-LEFT of the page.
    When the form already has an empty signature field, it is signed into
    (use_existing_field). tsa_url optionally embeds an RFC 3161 timestamp from
    an allow-listed server; empty (the default) keeps signing fully offline.
    """
    if not HAVE_PYHANKO:
        raise DscError("The PDF signing engine (pyHanko) is not installed.")
    signer = _load_signer(pfx_path, password)
    source = Path(src)
    if not source.exists():
        raise DscError(f"Document not found: {source}")
    timestamper = make_timestamper(tsa_url)

    try:
        spec, effective_name = resolve_field_spec(source, field_name, page_no, rect,
                                                  use_existing_field)
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
                field_name=effective_name,
                reason=reason,
                location=location,
                contact_info=contact,
                embed_validation_info=False,
                certify=certify,
                docmdp_permissions=docmdp_perm,
            )
            signed = signers.sign_pdf(
                writer,
                meta,
                signer=signer,
                timestamper=timestamper,
                new_field_spec=spec,
            )
        # pyHanko returns either raw bytes or a file-like stream depending on version.
        if hasattr(signed, "getvalue"):
            payload = signed.getvalue()
        elif hasattr(signed, "read"):
            signed.seek(0)
            payload = signed.read()
        else:
            payload = bytes(signed)
        Path(dst).write_bytes(payload)
        return dst
    except DscError:
        raise
    except Exception as e:
        raise DscError(f"Signing failed: {e}")



def certify_pdf(src: str, dst: str, pfx_path: str, password: str,
                permission: int = DocMDPPermission.FILL_FORMS,
                page_no: int = 0, rect: Tuple[float, float, float, float] = (60, 60, 240, 120),
                reason: str = "Certified original document by Author",
                location: str = "India",
                contact: str = "",
                field_name: str = "OpalAuthorCert",
                tsa_url: str = "") -> str:
    """
    Plain English: Certifies the PDF with an Author DocMDP signature, locking down
    unauthorized edits according to the chosen permission level.
    """
    return sign_pdf(
        src=src,
        dst=dst,
        pfx_path=pfx_path,
        password=password,
        page_no=page_no,
        rect=rect,
        reason=reason,
        location=location,
        contact=contact,
        field_name=field_name,
        use_existing_field=False,
        tsa_url=tsa_url,
        certify=True,
        mdp_permission=permission,
    )


def _signature_field_spec(field_name: str, page_no: int,
                          rect: Tuple[float, float, float, float]):
    """Builds the signature-field specification (works across pyHanko versions)."""
    box = tuple(int(round(v)) for v in rect)
    try:
        from pyhanko.sign.fields import SigFieldSpec
        return SigFieldSpec(sig_field_name=field_name, on_page=page_no, box=box)
    except Exception:
        return (field_name, box)


def verify_signature_deep(pdf_path: str) -> Dict[str, object]:
    """Cryptographic validation of every embedded signature (pyHanko):
    intact = the file bytes are unmodified and covered by the signature,
    trusted = the signer certificate chains to a known root, revoked = the
    revocation info says so. Includes DocMDP author certification checks.
    Fully offline - no AIA or CRL/OCSP fetching."""
    result: Dict[str, object] = {
        "signatures": [],
        "signed": False,
        "certified": False,
        "certification_permission": None,
        "certification_permission_label": "",
        "all_intact": False,
        "all_trusted": False,
    }
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature, read_certification_data
        with open(pdf_path, "rb") as fh:
            reader = PdfFileReader(fh)

            # Check for DocMDP Author Certification
            cert_data = None
            try:
                cert_data = read_certification_data(reader)
            except Exception:
                pass

            if cert_data is not None:
                p_val = getattr(cert_data.permission, "value", cert_data.permission)
                try:
                    p_int = int(p_val)
                except Exception:
                    p_int = 2
                result["certified"] = True
                result["certification_permission"] = p_int
                result["certification_permission_label"] = DocMDPPermission.LABELS.get(
                    p_int, f"Permission Level {p_int}"
                )

            author_sig_obj = getattr(cert_data, "author_sig", None) if cert_data else None

            # Diff policy: allow new visible signature fields after certification (matching Adobe Acrobat behavior)
            diff_policy = None
            try:
                from pyhanko.sign.diff_analysis import (
                    StandardDiffPolicy, FormUpdatingRule, SigFieldCreationRule,
                    SigFieldModificationRule, GenericFieldModificationRule,
                    CatalogModificationRule, DocInfoRule, XrefStreamRule,
                    ObjectStreamRule, DSSCompareRule, MetadataUpdateRule, ModificationLevel
                )
                diff_policy = StandardDiffPolicy(
                    global_rules=[
                        CatalogModificationRule(),
                        DocInfoRule().as_qualified(ModificationLevel.LTA_UPDATES),
                        XrefStreamRule().as_qualified(ModificationLevel.LTA_UPDATES),
                        ObjectStreamRule().as_qualified(ModificationLevel.LTA_UPDATES),
                        DSSCompareRule().as_qualified(ModificationLevel.LTA_UPDATES),
                        MetadataUpdateRule().as_qualified(ModificationLevel.LTA_UPDATES),
                    ],
                    form_rule=FormUpdatingRule(
                        field_rules=[
                            SigFieldCreationRule(allow_new_visible_after_certify=True),
                            SigFieldModificationRule(),
                            GenericFieldModificationRule(),
                        ],
                    ),
                )
            except Exception:
                diff_policy = None

            for s in reader.embedded_signatures:
                try:
                    st = validate_pdf_signature(s, diff_policy=diff_policy)
                    cert = getattr(st, "signing_cert", None)
                    is_cert = bool(author_sig_obj is not None and getattr(s, "sig_object", None) == author_sig_obj)
                    result["signatures"].append({
                        "field": s.field_name,
                        "intact": bool(getattr(st, "intact", False)),
                        "trusted": bool(getattr(st, "trusted", False)),
                        "revoked": bool(getattr(st, "revoked", False)),
                        "docmdp_ok": bool(getattr(st, "docmdp_ok", True)),
                        "is_certifying": is_cert,
                        "bottom_line": str(getattr(st, "bottom_line", "")),
                        "signer": cert.subject.human_friendly if cert is not None else "",
                        "signing_time": str(getattr(st, "signer_reported_dt", "") or ""),
                    })
                except Exception as e:
                    result["signatures"].append({"field": s.field_name, "error": str(e)})
        sigs = result["signatures"]
        result["signed"] = bool(sigs)
        result["all_intact"] = bool(sigs) and all(bool(e.get("intact")) for e in sigs)
        result["all_trusted"] = bool(sigs) and all(bool(e.get("trusted")) for e in sigs)
        return result
    except Exception as e:
        result["error"] = str(e)
        return result


def verify_signature(pdf_path: str) -> Dict[str, object]:
    """Reads back the signature fields of a PDF and reports what is present."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        try:
            fields = []
            for index in range(len(doc)):
                for widget in doc[index].widgets() or []:
                    # PyMuPDF field type 6 == signature
                    if widget.field_type == 6:
                        fields.append({
                            "page": index + 1,
                            "name": widget.field_name,
                            "signed": bool(widget.field_value),
                        })
            return {"signatures": fields, "signed": bool(fields),
                    "count": len(fields)}
        finally:
            doc.close()
    except Exception as e:
        return {"signatures": [], "signed": False, "error": str(e)}


# --- Connected DSC token (PKCS#11) ----------------------------------------
# The same facade as the .pfx path above, but the certificate and the private
# key live on a plugged-in USB token: only the signature ever comes back, the
# key never leaves the device. The PIN is passed in memory only.

try:
    from . import dsc_token
except Exception:  # imported as a loose module
    try:
        import dsc_token
    except Exception:
        dsc_token = None

HAVE_TOKEN = dsc_token is not None

try:
    from .pdf_tools import find_empty_sig_field
except Exception:
    try:
        from pdf_tools import find_empty_sig_field
    except Exception:
        find_empty_sig_field = None


# Public RFC 3161 timestamp servers Opal may contact - and ONLY these. A TSA
# receives just the hash of the signature, never the document. Timestamping is
# off by default: without it, signing stays 100% offline.
ALLOWED_TSA_HOSTS = {
    "freetsa.org",
    "timestamp.digicert.com",
    "timestamp.sectigo.com",
    "tsa.swisssign.net",
    "time.certum.pl",
}


def check_tsa_url(url: str) -> str:
    """Validates a TSA URL against the allow-list; returns the URL or raises."""
    from urllib.parse import urlparse
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https") or not host:
        raise DscError(f"Not a valid timestamp server URL: {url!r}")
    if host not in ALLOWED_TSA_HOSTS and not any(host.endswith("." + h) for h in ALLOWED_TSA_HOSTS):
        raise DscError(f"Timestamp server host {host!r} is not on Opal's allow-list "
                       f"({', '.join(sorted(ALLOWED_TSA_HOSTS))}).")
    return url


def make_timestamper(tsa_url: str = ""):
    """An RFC 3161 timestamper for the given server, or None when no URL is
    given (the default - signing then never touches the network)."""
    if not tsa_url:
        return None
    url = check_tsa_url(tsa_url)
    from pyhanko.sign.timestamps.requests_client import RequestsHTTPTimeStamper
    return RequestsHTTPTimeStamper(url, timeout=15)


def resolve_field_spec(src, field_name: str, page_no: int, rect, use_existing_field: bool = True):
    """(spec, effective_field_name): signs into an existing EMPTY signature field
    when the form has one (the way Acrobat does with prepared forms like
    INC-33); otherwise creates a new field at rect."""
    if use_existing_field and find_empty_sig_field is not None:
        existing = find_empty_sig_field(str(src), page_no)
        if existing:
            epage, ename = existing
            try:
                from pyhanko.sign.fields import SigFieldSpec
                return SigFieldSpec(sig_field_name=ename, on_page=epage, box=None), ename
            except Exception:
                pass
    return _signature_field_spec(field_name, page_no, rect), field_name


def token_available() -> bool:
    """True when signing with a plugged-in DSC token is possible here."""
    return HAVE_TOKEN and dsc_token.pkcs11_available()


def _wrap_token_errors(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        if HAVE_TOKEN and isinstance(e, dsc_token.TokenError):
            raise DscError(str(e))
        raise


def list_dsc_devices():
    """(devices, errors): one entry per slot holding a token, across all
    PKCS#11 driver modules found on this machine."""
    if not HAVE_TOKEN:
        raise DscError("Token support is not available.")
    return _wrap_token_errors(dsc_token.list_devices)


def default_device() -> Optional[Dict[str, object]]:
    """The first plugged-in token found, or None."""
    try:
        devices, _ = list_dsc_devices()
    except DscError:
        return None
    return devices[0] if devices else None


def inspect_token(lib_path: str, slot_no: int = 0) -> list:
    """Certificates readable off the token - public objects, no PIN needed."""
    if not HAVE_TOKEN:
        raise DscError("Token support is not available.")
    return _wrap_token_errors(dsc_token.list_token_certs, lib_path, slot_no)


def sign_pdf_token(src: str, dst: str, lib_path: str, pin: Optional[str],
                   slot_no: int = 0, cert_label: Optional[str] = None,
                   page_no: int = 0,
                   rect: Tuple[float, float, float, float] = (60, 60, 240, 120),
                   reason: str = "Approved by the signer",
                   location: str = "India",
                   contact: str = "",
                   field_name: str = "OpalDSC",
                   use_existing_field: bool = True,
                   tsa_url: str = "") -> str:
    """Signs src with the certificate on the connected token; writes the signed
    copy to dst. The private key is used inside the token and never exported."""
    if not HAVE_TOKEN:
        raise DscError("Token support is not available.")
    return _wrap_token_errors(
        dsc_token.sign_pdf_with_token, src, dst, lib_path, pin,
        slot_no=slot_no, cert_label=cert_label, page_no=page_no, rect=rect,
        reason=reason, location=location, contact=contact, field_name=field_name,
        use_existing_field=use_existing_field, tsa_url=tsa_url)
