"""Acrobat-parity additions: sign into a prepared signature field, cryptographic
signature verification, search-and-redact, and optional TSA timestamping.

Everything here runs offline against real files; the timestamp test uses
pyHanko's DummyTimeStamper so no network is touched.
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from opal_studio import dsc_sign
from opal_studio.engine import OpalEngine
from opal_studio.pdf_tools import find_empty_sig_field


def _make_pfx(path: Path, password: str = "test123") -> Path:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Parity Test Signer"),
                      x509.NameAttribute(NameOID.COUNTRY_NAME, "IN")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))
    path.write_bytes(pkcs12.serialize_key_and_certificates(
        b"parity", key, cert, None, serialization.BestAvailableEncryption(password.encode())))
    return path


def _make_form_with_sig_field(path: Path) -> Path:
    """A PDF with a prepared EMPTY signature field, like the INC-33 forms."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Form INC-33 test", fontsize=18)
    w = fitz.Widget()
    w.field_name = "sigfield1"
    w.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
    w.rect = fitz.Rect(100, 600, 320, 660)
    page.add_widget(w)
    doc.save(str(path))
    doc.close()
    return path


def _sig_fields(path: Path):
    import fitz
    doc = fitz.open(str(path))
    try:
        return [(i, w.field_name) for i in range(len(doc))
                for w in (doc[i].widgets() or []) if w.field_type == 6]
    finally:
        doc.close()


def _embedded_field_names(path: Path):
    from pyhanko.pdf_utils.reader import PdfFileReader
    with open(path, "rb") as fh:
        return [s.field_name for s in PdfFileReader(fh).embedded_signatures]


def test_signing_uses_a_prepared_empty_signature_field(tmp_path):
    pfx = _make_pfx(tmp_path / "c.pfx")
    form = _make_form_with_sig_field(tmp_path / "form.pdf")
    out = tmp_path / "form_signed.pdf"

    assert find_empty_sig_field(str(form), 0) == (0, "sigfield1")

    dsc_sign.sign_pdf(str(form), str(out), str(pfx), "test123")

    # the prepared field was signed into - no extra field was created
    assert _sig_fields(out) == [(0, "sigfield1")], _sig_fields(out)
    assert _embedded_field_names(out) == ["sigfield1"]
    deep = dsc_sign.verify_signature_deep(str(out))
    assert deep["signed"] and deep["all_intact"]
    assert "Parity Test Signer" in deep["signatures"][0]["signer"]


def test_signing_without_a_prepared_field_creates_one(samples, tmp_path):
    import shutil
    pfx = _make_pfx(tmp_path / "c.pfx")
    src = tmp_path / "plain.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    out = tmp_path / "plain_signed.pdf"

    dsc_sign.sign_pdf(str(src), str(out), str(pfx), "test123")

    assert _embedded_field_names(out) == ["OpalDSC"]
    assert dsc_sign.verify_signature_deep(str(out))["all_intact"]


def test_deep_verify_reports_unsigned_documents(samples):
    res = dsc_sign.verify_signature_deep(str(samples.path("contract.pdf")))
    assert res["signed"] is False and res["signatures"] == []


def test_engine_verify_signature_action(samples, tmp_path):
    unsigned = OpalEngine.execute_single(str(samples.path("contract.pdf")),
                                         "pdf_verify_signature", {})
    assert unsigned.success and "No digital signatures" in unsigned.message

    import shutil
    pfx = _make_pfx(tmp_path / "c.pfx")
    src = tmp_path / "doc.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    signed_path = tmp_path / "doc_signed.pdf"
    dsc_sign.sign_pdf(str(src), str(signed_path), str(pfx), "test123")
    res = OpalEngine.execute_single(str(signed_path), "pdf_verify_signature", {})
    assert res.success, res.message
    assert "intact=True" in res.message and "Parity Test Signer" in res.message


def test_search_and_redact_blacks_out_every_occurrence(tmp_path):
    import fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Contract page {i + 1} - SECRET-{i}", fontsize=14)
    src = tmp_path / "doc.pdf"
    doc.save(str(src))
    doc.close()

    res = OpalEngine.execute_single(str(src), "pdf_search_redact", {"query": "SECRET"})

    assert res.success, res.message
    out = Path(res.output_path)
    assert out.exists() and "_redacted" in out.name
    check = fitz.open(str(out))
    remaining = "".join(p.get_text() for p in check)
    check.close()
    assert "SECRET" not in remaining, f"text survived redaction: {remaining!r}"
    assert "Contract page 1" in remaining, "unrelated text must survive"


def test_search_and_redact_requires_a_query(samples):
    res = OpalEngine.execute_single(str(samples.path("contract.pdf")), "pdf_search_redact", {})
    assert not res.success and "query" in res.message


def test_tsa_url_is_allowlisted():
    assert dsc_sign.make_timestamper("") is None
    with pytest.raises(dsc_sign.DscError, match="allow-list"):
        dsc_sign.check_tsa_url("https://evil.example.com/tsr")
    assert dsc_sign.check_tsa_url("https://freetsa.org/tsr") == "https://freetsa.org/tsr"
    with pytest.raises(dsc_sign.DscError):
        dsc_sign.check_tsa_url("not-a-url")


def test_signing_with_a_timestamp_embeds_one(tmp_path, monkeypatch):
    """The TSA wiring end to end, offline: pyHanko's DummyTimeStamper stands in
    for the network server."""
    from pyhanko.sign.timestamps.dummy_client import DummyTimeStamper
    from asn1crypto import x509 as ax509, keys as akeys
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    tsa_cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(tsa_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=365))
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=False)
                .sign(tsa_key, hashes.SHA256()))
    dummy = DummyTimeStamper(
        ax509.Certificate.load(tsa_cert.public_bytes(serialization.Encoding.DER)),
        akeys.PrivateKeyInfo.load(tsa_key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())))
    monkeypatch.setattr(dsc_sign, "make_timestamper",
                        lambda url="": dummy if url else None)

    import shutil
    pfx = _make_pfx(tmp_path / "c.pfx")
    src = tmp_path / "doc.pdf"
    shutil.copy2(Path(__file__).parent / "opal_fixtures.py", tmp_path / "x.py")  # noqa: keep tmp used
    import fitz
    d = fitz.open()
    d.new_page(width=595, height=842)
    src = tmp_path / "doc.pdf"
    d.save(str(src))
    d.close()
    out = tmp_path / "doc_ts.pdf"

    dsc_sign.sign_pdf(str(src), str(out), str(pfx), "test123",
                      tsa_url="https://freetsa.org/tsr")

    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    with open(out, "rb") as fh:
        sigs = list(PdfFileReader(fh).embedded_signatures)
        assert sigs
        st = validate_pdf_signature(sigs[0])  # reads covered bytes through the open stream
    assert st.intact
    assert st.timestamp_validity is not None, "the embedded timestamp was not recorded"


def test_cli_verify_signature_prints_json(samples, tmp_path, monkeypatch, capsys):
    from opal_studio import cli
    import shutil
    pfx = _make_pfx(tmp_path / "c.pfx")
    src = tmp_path / "doc.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    signed = tmp_path / "doc_signed.pdf"
    dsc_sign.sign_pdf(str(src), str(signed), str(pfx), "test123")

    code = cli.main(["--verify-signature", str(signed)])
    assert code == 0
    import json
    payload = json.loads(capsys.readouterr().out)
    assert payload["signed"] and payload["all_intact"]
    assert payload["signatures"][0]["field"] == "OpalDSC"

    code = cli.main(["--verify-signature", str(src)])
    assert code == 1  # unsigned document: nothing valid to report
