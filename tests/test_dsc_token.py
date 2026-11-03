"""Connected DSC token (PKCS#11) signing.

Most tests never need a physical token: the PKCS#11 session is replaced with an
in-memory certificate, so the whole token signing path runs on any machine and
the produced PDF is verified cryptographically. One test probes a real
plugged-in token when one happens to be present (skipped otherwise).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from opal_studio import dsc_sign, dsc_token
from opal_studio.engine import OpalEngine


def _make_pfx(path: Path, password: str = "test123") -> Path:
    """A throwaway certificate that stands in for the token's certificate."""
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Token Test Signer"),
                      x509.NameAttribute(NameOID.COUNTRY_NAME, "IN")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))
    blob = pkcs12.serialize_key_and_certificates(
        b"token-test", key, cert, None,
        serialization.BestAvailableEncryption(password.encode()))
    path.write_bytes(blob)
    return path


class _FakeSession:
    """Stands in for the PKCS#11 session; must be closed by the caller."""
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_token(tmp_path, monkeypatch):
    """Replaces the PKCS#11 login with a pfx-backed signer, so the entire
    token signing path runs without a physical token."""
    pfx = _make_pfx(tmp_path / "token_cert.pfx")
    from pyhanko.sign import signers
    signer = signers.SimpleSigner.load_pkcs12(str(pfx), passphrase=b"test123")
    session = _FakeSession()
    seen = {}

    def fake_open(lib_path, pin, slot_no=0, cert_label=None):
        seen.update(lib=lib_path, pin=pin, slot=slot_no, cert_label=cert_label)
        assert pin == "test123", "the PIN must reach the token layer in memory"
        return signer, session

    monkeypatch.setattr(dsc_token, "open_token_signer", fake_open)
    return {"signer": signer, "session": session, "seen": seen}


def _assert_signature_cryptographically_valid(pdf_path: Path) -> None:
    check = dsc_sign.verify_signature(str(pdf_path))
    assert check["signed"], f"no signature field in the output: {check}"
    assert check["count"] >= 1
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.pdf_utils.reader import PdfFileReader
    with open(pdf_path, "rb") as fh:
        reader = PdfFileReader(fh)
        sigs = reader.embedded_signatures
        assert sigs, "pyHanko found no embedded CMS signature"
        # validation reads the covered byte ranges through the same stream
        status = validate_pdf_signature(sigs[0])
    assert status.intact, "the signature does not cover the file bytes - it is not valid"


def test_facade_reports_availability_consistently():
    assert dsc_sign.token_available() == (dsc_token.HAVE_PKCS11 and dsc_token.HAVE_PYHANKO)


def test_a_bogus_driver_is_reported_not_raised(tmp_path, monkeypatch):
    fake = tmp_path / ("fakepkcs11.dll" if os.name == "nt" else "fakepkcs11.so")
    fake.write_bytes(b"not a real pkcs11 module")
    monkeypatch.setenv("OPAL_PKCS11_LIB", str(fake))
    devices, errors = dsc_token.list_devices()  # must not raise
    assert str(fake) in errors, f"the bad driver was not recorded: {list(errors)}"
    assert isinstance(devices, list)


def test_missing_driver_file_is_a_clean_error(tmp_path):
    with pytest.raises(dsc_token.TokenError, match="not found"):
        dsc_token.list_token_certs(str(tmp_path / "nope.dll"))


def test_unusable_driver_is_a_clean_error(tmp_path):
    fake = tmp_path / ("badpkcs11.dll" if os.name == "nt" else "badpkcs11.so")
    fake.write_bytes(b"MZ but not pkcs11")
    with pytest.raises(dsc_token.TokenError):
        dsc_token.list_token_certs(str(fake))


def test_token_signing_produces_a_cryptographically_valid_pdf(samples, tmp_path, fake_token):
    import shutil
    src = tmp_path / "contract.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    dst = tmp_path / "contract_signed.pdf"

    out = dsc_sign.sign_pdf_token(str(src), str(dst), "fakepkcs11.dll", "test123",
                                  slot_no=0, cert_label="token-cert")

    assert out == str(dst) and dst.exists()
    assert fake_token["session"].closed, "the token session must be closed after signing"
    assert fake_token["seen"]["cert_label"] == "token-cert"
    _assert_signature_cryptographically_valid(dst)
    # The original is untouched.
    assert src.read_bytes() == samples.path("contract.pdf").read_bytes()


def test_token_errors_surface_as_dsc_errors(samples, monkeypatch):
    def boom(*a, **k):
        raise dsc_token.TokenError("no token in slot 0")
    monkeypatch.setattr(dsc_token, "sign_pdf_with_token", boom)
    with pytest.raises(dsc_sign.DscError, match="no token in slot 0"):
        dsc_sign.sign_pdf_token(str(samples.path("contract.pdf")), "out.pdf", "x.dll", "1234")


def test_engine_route_signs_via_token(samples, tmp_path, fake_token):
    import shutil
    src = tmp_path / "contract.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    result = OpalEngine.execute_single(
        str(src), "pdf_dsc_sign",
        {"token": {"lib": "fakepkcs11.dll", "slot": 0, "cert_label": "token-cert",
                   "pin": "test123"}})
    assert result.success, f"engine sign failed: {result.message}"
    out = Path(result.output_path)
    assert out.exists() and "_signed" in out.name
    _assert_signature_cryptographically_valid(out)


def test_engine_route_without_any_certificate_fails_cleanly(samples):
    result = OpalEngine.execute_single(str(samples.path("contract.pdf")), "pdf_dsc_sign", {})
    assert not result.success
    assert "No certificate" in result.message


def test_cli_sign_with_pfx_end_to_end(samples, tmp_path, monkeypatch):
    from opal_studio import cli
    import shutil
    pfx = _make_pfx(tmp_path / "cli_cert.pfx", "test123")
    src = tmp_path / "doc.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    out = tmp_path / "doc_signed.pdf"
    monkeypatch.setenv("OPAL_DSC_PIN", "test123")

    code = cli.main(["--sign", str(src), "--pfx", str(pfx), "--out", str(out)])

    assert code == 0, "CLI sign failed"
    assert out.exists()
    _assert_signature_cryptographically_valid(out)


def test_cli_sign_requires_pfx_or_token(samples, monkeypatch, capsys):
    from opal_studio import cli
    monkeypatch.delenv("OPAL_DSC_PIN", raising=False)
    code = cli.main(["--sign", str(samples.path("contract.pdf"))])
    assert code == 2
    assert "--pfx" in capsys.readouterr().out


def test_cli_sign_with_token_but_no_pin_fails_fast_not_hangs(samples, monkeypatch, capsys):
    from opal_studio import cli
    monkeypatch.delenv("OPAL_DSC_PIN", raising=False)
    # Under pytest stdin is not a terminal, so the PIN prompt must not block.
    code = cli.main(["--sign", str(samples.path("contract.pdf")), "--token"])
    assert code == 2
    text = capsys.readouterr().out
    assert "PIN" in text or "token" in text.lower()


def test_viewer_sign_with_dsc_token_context(app, samples, tmp_path, fake_token):
    import shutil
    from opal_studio.viewer_pdf import PdfStudio
    import fitz
    src = tmp_path / "contract.pdf"
    shutil.copy2(samples.path("contract.pdf"), src)
    studio = PdfStudio(str(src))
    studio.dsc_context = {"token": {"lib": "fakepkcs11.dll", "slot": 0,
                                    "cert_label": "token-cert"},
                          "pin": "test123", "info": {"subject": "CN=Token Test Signer"}}
    out = studio.sign_with_dsc(0, fitz.Point(80, 700))
    assert out and Path(out).exists()
    assert fake_token["seen"]["pin"] == "test123"
    _assert_signature_cryptographically_valid(Path(out))
    studio.close() if hasattr(studio, "close") else None


def test_real_token_enumeration_when_one_is_plugged_in():
    """Live probe: runs only when python-pkcs11 is installed AND a physical
    DSC token is present; skips everywhere else."""
    if not dsc_token.HAVE_PKCS11:
        pytest.skip("python-pkcs11 is not installed")
    devices, _errors = dsc_token.list_devices()
    if not devices:
        pytest.skip("no physical DSC token plugged in on this machine")
    dev = devices[0]
    assert dev["label"], f"token enumerated without a label: {dev}"
    certs = dsc_token.list_token_certs(dev["module"], int(dev["slot"]))
    assert certs, "a token was found but holds no certificates"
    assert certs[0]["subject"] and certs[0]["sha256_fingerprint"]
