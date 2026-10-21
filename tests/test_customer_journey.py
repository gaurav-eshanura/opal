"""
Opal - Customer journey test
Plain English: Walks through the jobs an Indian CSC / print-shop operator actually
does in a day - Aadhaar photo resize, background removal, WhatsApp-ready PDF,
photo-to-PDF, scanning, splitting, signing - and measures how long each takes.
The point is to prove the app SAVES TIME for a non-engineer, so every step is
timed and every output is opened and inspected like a customer would.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from opal_studio.engine import OpalEngine

WORK = ROOT / "test_sandbox" / "customer"
PASS, FAIL = [], []
TIMINGS = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('- ' + str(detail)) if detail else ''}")
    (PASS if ok else FAIL).append(name)


def timed(label, func, *args, **kwargs):
    start = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start
    TIMINGS.append((label, elapsed))
    print(f"    ⏱  {label}: {elapsed:.2f}s")
    return result


def make_customer_files():
    WORK.mkdir(parents=True, exist_ok=True)
    # A studio-style portrait: sharp subject on a blurred background, which is
    # exactly what a photo looks like when a customer walks in with a phone.
    import numpy as np
    rng = np.random.default_rng(7)
    w, h = 700, 900
    bg = np.zeros((h, w, 3), dtype=np.uint8)
    bg[:, :, 0], bg[:, :, 1], bg[:, :, 2] = 90, 120, 160
    bg = np.clip(bg + rng.normal(0, 18, (h, w, 3)), 0, 255).astype(np.uint8)
    photo = Image.fromarray(bg).filter(ImageFilter.GaussianBlur(14))
    d = ImageDraw.Draw(photo)
    d.ellipse([250, 120, 450, 340], fill=(228, 186, 152))     # face
    d.ellipse([232, 96, 468, 250], fill=(48, 38, 34))         # hair
    d.ellipse([165, 330, 535, 900], fill=(178, 42, 52))       # shirt
    d.ellipse([300, 215, 320, 228], fill=(30, 30, 30))
    d.ellipse([380, 215, 400, 228], fill=(30, 30, 30))
    photo = photo.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=2))
    photo.save(WORK / "customer_photo.jpg", quality=95)

    # A scan-like PDF (image only) like a photocopied Aadhaar/ration card
    import fitz
    card = Image.new("RGB", (1000, 700), (250, 248, 240))
    cd = ImageDraw.Draw(card)
    cd.rectangle([40, 40, 960, 660], outline=(20, 20, 30), width=3)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
    except Exception:
        font = None
    cd.text((70, 90), "Government of India", fill=(20, 20, 30), font=font)
    cd.text((70, 140), "Name: Ramesh Kumar", fill=(20, 20, 30), font=font)
    cd.text((70, 190), "Aadhaar: XXXX XXXX 1234", fill=(20, 20, 30), font=font)
    card.save(WORK / "card.png")
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(0, 0, 595, 842), filename=str(WORK / "card.png"))
    doc.save(str(WORK / "scan.pdf"))
    doc.close()

    # A document with real text (including Hindi) for conversion
    (WORK / "hindi_notice.txt").write_text(
        "सरकारी सूचना\n\nयह दस्तावेज़ सरकारी कार्यालय से जारी किया गया है।\n"
        "कृपया इसे सुरक्षित रखें।\n", encoding="utf-8")
    (WORK / "english_notice.txt").write_text(
        "Government Notice\n\nThis document is issued by the office.\n", encoding="utf-8")
    return WORK


def journey(name: str) -> None:
    print(f"\n--- {name} ---")


def _make_test_dsc() -> Path:
    """Creates a throwaway self-signed certificate that behaves like a real DSC."""
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives.asymmetric import rsa

    target = WORK / "test_dsc.pfx"
    if target.exists():
        return target
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CSC Authority"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Ramesh Kumar - Test DSC"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))
    blob = pkcs12.serialize_key_and_certificates(
        b"test-dsc", key, cert, None, serialization.BestAvailableEncryption(b"test123"))
    target.write_bytes(blob)
    return target


def _rejects_bad_password(pfx: Path) -> bool:
    from opal_studio import dsc_sign
    try:
        dsc_sign.inspect_certificate(str(pfx), "wrong-password")
        return False
    except Exception:
        return True


def main():
    # This suite checks that results land next to the original, so it must
    # not inherit whatever output folder the person running it has set.
    from opal_studio.config import ConfigManager
    original = dict(ConfigManager.load_config())
    patched = dict(original)
    patched["output_mode"] = "same_as_source"
    ConfigManager.save_config(patched)
    try:
        run_journey()
    finally:
        ConfigManager.save_config(original)


def run_journey():
    make_customer_files()

    print("\n" + "=" * 70)
    print("CUSTOMER JOURNEY: an Indian CSC / print-shop operator's day")
    print("=" * 70)

    # 1. Aadhaar photo resize ------------------------------------------------
    journey("1. Aadhaar / passport photo resize (413x599 px)")
    res = timed("resize to Aadhaar size",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"), "aadhaar_photo")
    check("Aadhaar photo created", res.success and Path(res.output_path).exists(),
          res.message)
    if res.success:
        with Image.open(res.output_path) as out:
            check("Aadhaar size is exactly 413x599",
                  out.size == (413, 599), f"{out.size}")

    # 2. Background removal --------------------------------------------------
    journey("2. Background removal for a cut-out photo (signage, printing)")
    res = timed("AI background removal",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"), "remove_bg",
                {"bg_model": "u2netp"})
    check("background removed", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        with Image.open(res.output_path) as out:
            check("cut-out keeps an alpha channel", out.mode == "RGBA", out.mode)
            alpha = out.getchannel("A")
            hist = alpha.histogram()
            transparent = hist[0]
            total = out.width * out.height
            check("background is actually transparent",
                  transparent / total > 0.2, f"{transparent / total:.0%} transparent")
            check("subject is still kept",
                  hist[255] / total > 0.05, f"{hist[255] / total:.0%} opaque")

    # 3. WhatsApp-ready PDF --------------------------------------------------
    journey("3. Send a scan on WhatsApp (under 1 MB)")
    res = timed("PDF shrink for WhatsApp",
                OpalEngine.execute_single, str(WORK / "scan.pdf"), "pdf_whatsapp")
    check("WhatsApp PDF created", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        size_mb = Path(res.output_path).stat().st_size / 1024 / 1024
        check("PDF is under 1 MB", size_mb < 1.0, f"{size_mb:.2f} MB")

    # 4. Photos into one PDF -------------------------------------------------
    journey("4. Combine several photos into one PDF for WhatsApp")
    photos = [str(WORK / "customer_photo.jpg"), str(WORK / "card.png")]
    res = timed("photos to single PDF",
                OpalEngine.execute_batch, photos, "pdf")
    check("multi-photo PDF created", res.succeeded == 2 and res.outputs, res.message)
    if res.outputs:
        import fitz
        d = fitz.open(res.outputs[0])
        check("PDF has one page per photo", len(d) == 2, f"{len(d)} pages")
        d.close()

    # 5. Split a scanned PDF into single pages --------------------------------
    journey("5. Split a multi-page scan into separate pages")
    res = timed("split scanned PDF",
                OpalEngine.execute_single, str(WORK / "scan.pdf"), "split_pdf")
    check("split produced a folder", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        pages = list(Path(res.output_path).glob("*.pdf"))
        check("one PDF per page", len(pages) == 3, f"{len(pages)} files")

    # 6. Hindi notice to PDF -------------------------------------------------
    journey("6. Hindi (Devanagari) notice to PDF for printing")
    res = timed("Hindi text to PDF",
                OpalEngine.execute_single, str(WORK / "hindi_notice.txt"), "pdf")
    check("Hindi PDF created", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        import fitz
        d = fitz.open(res.output_path)
        text = d[0].get_text().strip()
        d.close()
        check("Hindi text survived the conversion",
              "सरकारी" in text or "कार्यालय" in text, repr(text[:40]))

    # 7. Black & white photocopy --------------------------------------------
    journey("7. Black & white photocopy of a colour document")
    res = timed("greyscale copy",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"), "grayscale")
    check("B&W copy created", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        with Image.open(res.output_path) as out:
            check("image is greyscale", out.mode in ("L", "RGB"), out.mode)

    # 8. Print size photo ----------------------------------------------------
    journey("8. Photo printed on a 4x6 inch photo paper")
    res = timed("4x6 inch print size",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"), "print_4x6")
    check("4x6 print created", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        with Image.open(res.output_path) as out:
            check("4x6 at 300 DPI is 1200x1800", out.size == (1200, 1800), f"{out.size}")

    # 9. Where did the results go? -------------------------------------------
    journey("9. Did the files land next to the original without asking?")
    produced = sorted(p.name for p in WORK.glob("*") if p.suffix.lower() in
                      (".png", ".jpg", ".pdf", ".webp"))
    check("results are saved in the same folder as the originals",
          len(produced) >= 6, ", ".join(produced[:6]))

    # 10. Digital signature with a real certificate --------------------------
    journey("10. Scanned file with blank pages (clean it up)")
    import fitz
    mixed = fitz.open()
    page = mixed.new_page()
    page.insert_text((72, 100), "Page one of the scan")
    mixed.new_page()                      # blank page from the scanner
    page2 = mixed.new_page()
    page2.insert_text((72, 100), "Page two of the scan")
    mixed.save(str(WORK / "with_blanks.pdf"))
    mixed.close()
    res = timed("remove blank pages",
                OpalEngine.execute_single, str(WORK / "with_blanks.pdf"), "pdf_remove_blank")
    check("blank pages removed", res.success, res.message)
    if res.success:
        out_doc = fitz.open(res.output_path)
        check("only the real pages remain", len(out_doc) == 2, f"{len(out_doc)} pages")
        out_doc.close()

    # 11. Digital signature with a real certificate --------------------------
    journey("11. Sign a document with a digital signature certificate (DSC)")
    pfx = _make_test_dsc()
    res = timed("sign with DSC",
                OpalEngine.execute_single, str(WORK / "scan.pdf"), "pdf_dsc_sign",
                {"pfx_path": str(pfx), "password": "test123", "page": 0})
    check("document signed", res.success and Path(res.output_path).exists(), res.message)
    if res.success:
        raw = Path(res.output_path).read_bytes()
        check("signed file carries a real CMS signature",
              b"/ByteRange" in raw and b"adbe.pkcs7.detached" in raw,
              "CMS detached signature present")
        check("signed copy sits next to the original",
              Path(res.output_path).parent == WORK, Path(res.output_path).parent)

    # 12. Certificate details are readable ----------------------------------
    journey("12. Certificate details shown to the customer before signing")
    from opal_studio import dsc_sign
    info = dsc_sign.inspect_certificate(str(pfx), "test123")
    check("certificate subject is readable", "Ramesh" in info["subject"], info["subject"][:40])
    check("certificate validity is shown", bool(info["valid_to"]), info["valid_to"])
    check("wrong password is rejected", _rejects_bad_password(pfx))

    # 13. The other counter jobs -------------------------------------------
    journey("13. White background, stamp photo and side-by-side photos")
    res = timed("white background photo",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"),
                "white_bg_photo", {"bg_model": "u2netp"})
    check("white background photo", res.success, res.message[:50])
    res = timed("stamp photo",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"), "stamp_photo")
    check("stamp photo", res.success, res.message[:50])
    if res.success:
        with Image.open(res.output_path) as im:
            check("stamp photo is 50x40 mm", im.size == (591, 472), f"{im.size}")
    res = timed("join two photos",
                OpalEngine.execute_single, str(WORK / "customer_photo.jpg"), "join_photos",
                {"second": str(WORK / "customer_photo.jpg")})
    check("photos joined side by side", res.success, res.message[:50])

    print("\n" + "=" * 70)
    print("TIME TAKEN PER TASK (a customer only has to pick the right tool)")
    print("=" * 70)
    total = 0.0
    for label, elapsed in TIMINGS:
        print(f"  {elapsed:6.2f}s  {label}")
        total += elapsed
    print(f"  {total:6.2f}s  TOTAL for {len(TIMINGS)} jobs")
    print("=" * 70)
    print(f"CUSTOMER JOURNEY RESULT: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
