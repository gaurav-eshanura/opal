"""
Opal - PDF Modification Detection and Prevention (DocMDP) Certification Test Suite
Plain English: Tests author-grade document certification (ISO 32000-1 DocMDP).
Verifies that certifying a PDF locks the document permissions (No Changes, Form Filling,
Annotations), and ensures verify_signature_deep accurately detects the author signature
and permission state.
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
    """Creates a temporary RSA 2048-bit digital certificate for author signing."""
    pfx_file = tmp_path / "author.pfx"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Opal Author Authority"),
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
    pdf_path = tmp_path / "contract.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Master Services Agreement (Author Copy)", fontsize=16)
    page.insert_text((72, 140), "This contract requires author certification before countersigning.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_certify_pdf_p2_allows_form_fill_and_signatures(blank_pdf, cert_pfx, tmp_path):
    out_pdf = str(tmp_path / "contract_certified_p2.pdf")
    dsc_sign.certify_pdf(
        src=blank_pdf,
        dst=out_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        permission=DocMDPPermission.FILL_FORMS,
        reason="Certified by Author - Form fill & signatures permitted",
    )

    assert Path(out_pdf).exists()

    # Deep verification
    ver = dsc_sign.verify_signature_deep(out_pdf)
    assert ver["signed"]
    assert ver["certified"]
    assert ver["certification_permission"] == 2
    assert "Form Filling" in ver["certification_permission_label"]
    assert ver["all_intact"]

    # Check that signature list identifies certifying status
    assert len(ver["signatures"]) == 1
    sig = ver["signatures"][0]
    assert sig["intact"]
    assert sig["docmdp_ok"]
    assert sig["is_certifying"]
    assert "Opal Author" in sig["signer"]


def test_certify_pdf_p1_locks_document_completely(blank_pdf, cert_pfx, tmp_path):
    out_pdf = str(tmp_path / "contract_certified_p1.pdf")
    pt.certify_pdf(
        src=blank_pdf,
        dst=out_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        permission=DocMDPPermission.NO_CHANGES,
        reason="Final Legal Execution - No changes permitted",
    )

    assert Path(out_pdf).exists()
    ver = dsc_sign.verify_signature_deep(out_pdf)
    assert ver["certified"]
    assert ver["certification_permission"] == 1
    assert "No Changes" in ver["certification_permission_label"]
    assert ver["all_intact"]

    # Attempting to sign or alter P=1 document must be rejected
    illegal_pdf = str(tmp_path / "illegal_signed.pdf")
    with pytest.raises(dsc_sign.DscError, match="Author signature forbids all changes"):
        dsc_sign.sign_pdf(
            src=out_pdf,
            dst=illegal_pdf,
            pfx_path=cert_pfx,
            password="testpass123",
            field_name="IllegalSig",
            rect=(50, 50, 200, 100),
        )


def test_subsequent_counter_signature_under_p3_annotation_certification(blank_pdf, cert_pfx, tmp_path):
    # Under P=3 (DocMDPPermission.ANNOTATE), appending new annotation fields is explicitly permitted
    certified_pdf = str(tmp_path / "certified_p3.pdf")
    dsc_sign.certify_pdf(
        src=blank_pdf,
        dst=certified_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        permission=DocMDPPermission.ANNOTATE,
        field_name="AuthorCertSig",
        rect=(50, 50, 200, 100),
    )

    # Countersign with a new signature annotation
    countersigned_pdf = str(tmp_path / "countersigned_p3.pdf")
    dsc_sign.sign_pdf(
        src=certified_pdf,
        dst=countersigned_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        field_name="CounterSig",
        rect=(250, 50, 400, 100),
        reason="Approved and countersigned",
    )

    ver = dsc_sign.verify_signature_deep(countersigned_pdf)
    assert ver["certified"]
    assert ver["certification_permission"] == 3
    assert len(ver["signatures"]) == 2
    assert ver["all_intact"]

    author_sigs = [s for s in ver["signatures"] if s["is_certifying"]]
    assert len(author_sigs) == 1
    assert author_sigs[0]["docmdp_ok"]

    approval_sigs = [s for s in ver["signatures"] if not s["is_certifying"]]
    assert len(approval_sigs) == 1
    assert approval_sigs[0]["intact"]


def test_subsequent_signature_into_prepared_field_under_p2(cert_pfx, tmp_path):
    # Under P=2 (DocMDPPermission.FILL_FORMS), signing into a prepared form field is allowed
    form_pdf = str(tmp_path / "form_with_fields.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Prepared Corporate Agreement", fontsize=16)

    # Add prepared empty signature field for the counter-signer
    w = fitz.Widget()
    w.field_name = "CounterSignerField"
    w.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
    w.rect = fitz.Rect(250, 50, 450, 120)
    page.add_widget(w)
    doc.save(form_pdf)
    doc.close()

    # Step 1: Author certifies document under P=2
    certified_pdf = str(tmp_path / "certified_form_p2.pdf")
    dsc_sign.certify_pdf(
        src=form_pdf,
        dst=certified_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        permission=DocMDPPermission.FILL_FORMS,
        field_name="AuthorCertSig",
        rect=(50, 50, 200, 120),
    )

    # Step 2: Recipient signs into their prepared field
    countersigned_pdf = str(tmp_path / "countersigned_form_p2.pdf")
    dsc_sign.sign_pdf(
        src=certified_pdf,
        dst=countersigned_pdf,
        pfx_path=cert_pfx,
        password="testpass123",
        field_name="CounterSignerField",
        use_existing_field=True,
    )

    ver = dsc_sign.verify_signature_deep(countersigned_pdf)
    assert ver["certified"]
    assert ver["certification_permission"] == 2
    assert len(ver["signatures"]) == 2
    assert ver["all_intact"]

    author_sigs = [s for s in ver["signatures"] if s["is_certifying"]]
    assert len(author_sigs) == 1
    assert author_sigs[0]["docmdp_ok"]
