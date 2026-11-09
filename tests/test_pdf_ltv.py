"""
Opal - PDF Long-Term Validation (LTV / DSS) Test Suite
Plain English: Tests Document Security Store (DSS) and VRI embedding according to
ISO 32000-1 and PAdES-LTV (ETSI EN 319 142). Verifies that digital signatures remain
indefinitely valid offline, that cryptographic hashes remain intact, and that
DocMDP certification works in lockstep with LTV.
"""

import os
import sys
import datetime
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fitz
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.asymmetric import rsa

from opal_studio import dsc_sign
from opal_studio.dsc_sign import DocMDPPermission
from opal_studio import pdf_tools as pt


@pytest.fixture
def cert_pfx(tmp_path):
    """Creates a temporary RSA 2048-bit digital certificate."""
    pfx_file = tmp_path / "signer.pfx"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Opal LTV Authority"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Opal Studio Sovereign Enclave"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))

    pfx_bytes = pkcs12.serialize_key_and_certificates(
        b"cert", key, cert, None, serialization.BestAvailableEncryption(b"testpass123")
    )
    pfx_file.write_bytes(pfx_bytes)
    return str(pfx_file)


@pytest.fixture
def blank_pdf(tmp_path):
    """Creates a blank single-page PDF."""
    pdf_path = tmp_path / "agreement.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Long-Term Validation Master Agreement", fontsize=16)
    page.insert_text((72, 140), "This contract embeds cryptographic records for multi-decade archiving.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_embed_ltv_on_signed_pdf(blank_pdf, cert_pfx, tmp_path):
    signed_pdf = str(tmp_path / "signed.pdf")
    dsc_sign.sign_pdf(
        src=blank_pdf,
        dst=signed_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        field_name="Sig1",
        rect=(50, 50, 200, 100),
    )

    # Initial check: signed but not LTV enabled
    ver_init = dsc_sign.verify_signature_deep(signed_pdf)
    assert ver_init["signed"]
    assert ver_init["all_intact"]
    assert not ver_init["ltv_enabled"]

    # Embed LTV
    ltv_pdf = str(tmp_path / "signed_ltv.pdf")
    res = dsc_sign.embed_ltv_data(signed_pdf, ltv_pdf)
    assert res["success"]
    assert res["certs_embedded"] >= 1
    assert res["vri_entries"] >= 1

    # Deep verification
    ver = dsc_sign.verify_signature_deep(ltv_pdf)
    assert ver["signed"]
    assert ver["all_intact"]
    assert ver["ltv_enabled"]
    assert ver["dss_info"] is not None
    assert ver["dss_info"]["certs_count"] >= 1
    assert ver["dss_info"]["vri_count"] >= 1

    # Verify per-signature LTV status
    sig = ver["signatures"][0]
    assert sig["intact"]
    assert sig["ltv_enabled"]


def test_sign_pdf_with_embed_ltv_flag(blank_pdf, cert_pfx, tmp_path):
    out_pdf = str(tmp_path / "auto_ltv.pdf")
    dsc_sign.sign_pdf(
        src=blank_pdf,
        dst=out_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        field_name="AutoSig",
        rect=(50, 50, 200, 100),
        embed_ltv=True,
    )

    ver = dsc_sign.verify_signature_deep(out_pdf)
    assert ver["signed"]
    assert ver["all_intact"]
    assert ver["ltv_enabled"]
    assert ver["dss_info"]["certs_count"] >= 1
    assert ver["signatures"][0]["ltv_enabled"]


def test_certify_pdf_with_embed_ltv(blank_pdf, cert_pfx, tmp_path):
    out_pdf = str(tmp_path / "certified_ltv.pdf")
    dsc_sign.certify_pdf(
        src=blank_pdf,
        dst=out_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        permission=DocMDPPermission.FILL_FORMS,
        field_name="AuthorCertSig",
        rect=(50, 50, 200, 100),
        embed_ltv=True,
    )

    ver = dsc_sign.verify_signature_deep(out_pdf)
    assert ver["signed"]
    assert ver["certified"]
    assert ver["certification_permission"] == 2
    assert ver["all_intact"]
    assert ver["ltv_enabled"]

    author_sig = ver["signatures"][0]
    assert author_sig["is_certifying"]
    assert author_sig["docmdp_ok"]
    assert author_sig["ltv_enabled"]


def test_pdf_tools_embed_ltv_api(blank_pdf, cert_pfx, tmp_path):
    signed_pdf = str(tmp_path / "pt_signed.pdf")
    dsc_sign.sign_pdf(
        src=blank_pdf,
        dst=signed_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
    )

    ltv_pdf = str(tmp_path / "pt_ltv.pdf")
    res = pt.embed_ltv(signed_pdf, ltv_pdf)
    assert res["success"]
    assert Path(ltv_pdf).exists()

    ver = dsc_sign.verify_signature_deep(ltv_pdf)
    assert ver["ltv_enabled"]
    assert ver["all_intact"]


def test_embed_ltv_on_unsigned_pdf_raises(blank_pdf, tmp_path):
    out_pdf = str(tmp_path / "unsigned_ltv.pdf")
    with pytest.raises(dsc_sign.DscError, match="contains no digital signatures"):
        dsc_sign.embed_ltv_data(blank_pdf, out_pdf)


def test_viewer_verify_signatures_dialog_headless(blank_pdf, cert_pfx, tmp_path, app):
    from opal_studio.viewer_pdf import PdfStudio
    ltv_pdf = str(tmp_path / "viewer_ltv.pdf")
    dsc_sign.sign_pdf(
        src=blank_pdf,
        dst=ltv_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        embed_ltv=True,
    )

    viewer = PdfStudio(file_path=ltv_pdf)
    assert viewer.doc is not None
    # Trigger dialog in headless mode (mock exec)
    from PySide6.QtWidgets import QDialog
    orig_exec = QDialog.exec
    QDialog.exec = lambda self: QDialog.Accepted
    try:
        viewer._verify_signatures_dialog()
    finally:
        QDialog.exec = orig_exec
    viewer.close()
