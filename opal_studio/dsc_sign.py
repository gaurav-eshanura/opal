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
        return signers.SimpleSigner.load_pkcs12(str(path), passphrase=secret)
    except Exception as e:
        raise DscError(f"Could not open the certificate: {e}")


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
              field_name: str = "OpalDSC") -> str:
    """
    Signs the PDF with the given certificate and writes the signed copy to dst.
    rect is in PDF points with the origin at the BOTTOM-LEFT of the page.
    """
    if not HAVE_PYHANKO:
        raise DscError("The PDF signing engine (pyHanko) is not installed.")
    signer = _load_signer(pfx_path, password)
    source = Path(src)
    if not source.exists():
        raise DscError(f"Document not found: {source}")

    try:
        with open(source, "rb") as fh:
            writer = IncrementalPdfFileWriter(fh)
            meta = signers.PdfSignatureMetadata(
                field_name=field_name,
                reason=reason,
                location=location,
                contact_info=contact,
                embed_validation_info=False,
            )
            spec = _signature_field_spec(field_name, page_no, rect)
            signed = signers.sign_pdf(
                writer,
                meta,
                signer=signer,
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


def _signature_field_spec(field_name: str, page_no: int,
                          rect: Tuple[float, float, float, float]):
    """Builds the signature-field specification (works across pyHanko versions)."""
    box = tuple(int(round(v)) for v in rect)
    try:
        from pyhanko.sign.fields import SigFieldSpec
        return SigFieldSpec(sig_field_name=field_name, on_page=page_no, box=box)
    except Exception:
        return (field_name, box)


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
