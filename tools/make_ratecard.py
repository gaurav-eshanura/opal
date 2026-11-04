"""
Opal - printable counter rate card (bilingual EN + Hindi), one A4 page.
Plain English: renders the card with PIL (Segoe UI + Nirmala UI for Devanagari)
at 200 dpi and embeds it into a one-page PDF at website/assets/counter-ratecard.pdf.
Prices are suggestions for CSC operators - "your counter, your rates".

Run:  python tools/make_ratecard.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
OUT_PDF = REPO / "website" / "assets" / "counter-ratecard.pdf"
OUT_PNG = REPO / "website" / "assets" / "counter-ratecard.png"

SEGOE = r"C:\Windows\Fonts\segoeui.ttf"
SEGOE_B = r"C:\Windows\Fonts\segoeuib.ttf"
NIRMALA = r"C:\Windows\Fonts\Nirmala.ttc"

W, H = 1654, 2339  # A4 @ 200 dpi
M = 90

INK = (5, 7, 13)
PANEL = (14, 18, 30)
TEXT = (242, 245, 251)
DIM = (169, 179, 201)
FAINT = (111, 122, 147)
ACCENT = (138, 92, 246)
ACCENT2 = (238, 78, 138)
AMBER = (255, 154, 60)
GREEN = (55, 201, 138)

ROWS = [
    ("ID photo (Aadhaar / passport, 413x599)", "आईडी फोटो (आधार / पासपोर्ट)", "<1s", "₹10"),
    ("Print photo 4R / 5R / 6R · 300 DPI", "प्रिंट फोटो 4R / 5R / 6R · 300 DPI", "<1s", "₹20–40"),
    ("WhatsApp PDF (under 1 MB)", "व्हाट्सऐप PDF (1 MB से कम)", "<1s", "₹5"),
    ("Remove background (transparent PNG)", "पृष्ठभूमि हटाना (पारदर्शी PNG)", "~1s", "₹20"),
    ("AI upscale 2x / 4x", "AI अपस्केल 2x / 4x", "seconds", "₹20"),
    ("Blur a face (privacy)", "चेहरा blur करना (गोपनीयता)", "<1s", "₹10"),
    ("Sign PDF with DSC USB token", "DSC USB token से PDF sign", "~3s", "₹50"),
    ("Verify a signed PDF (intact / trusted)", "signed PDF verify (intact / trusted)", "instant", "Free"),
    ("Repair / OCR a scanned PDF", "टूटी / स्कैन PDF repair + OCR", "<1s", "₹10"),
    ("Merge / split / reorder PDF pages", "PDF merge / split / reorder", "<1s", "₹10"),
    ("Trim / compress video for WhatsApp", "व्हाट्सऐप के लिए video trim / compress", "<1s", "₹10"),
    ("QR code from text or link", "text / link से QR code", "instant", "₹5"),
    ("Anything → PDF", "कुछ भी → PDF", "<1s", "₹5"),
]


def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def main():
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # header band with a fire-gradient strip
    d.rectangle([0, 0, W, 300], fill=PANEL)
    for x in range(W):
        t = x / W
        if t < 0.5:
            k = t / 0.5
            c = tuple(int(ACCENT[i] + (ACCENT2[i] - ACCENT[i]) * k) for i in range(3))
        else:
            k = (t - 0.5) / 0.5
            c = tuple(int(ACCENT2[i] + (AMBER[i] - ACCENT2[i]) * k) for i in range(3))
        d.line([(x, 0), (x, 8)], fill=c)

    f_title = font(SEGOE_B, 84)
    f_title_hi = font(NIRMALA, 52, index=0)
    f_sub = font(SEGOE, 34)
    f_sub_hi = font(NIRMALA, 32, index=0)

    d.text((M, 60), "OPAL — Counter Rate Card", font=f_title, fill=TEXT)
    d.text((M, 165), "काउंटर रेट कार्ड", font=f_title_hi, fill=TEXT)
    d.text((M, 235), "Print this at the counter  ·  काउंटर पर प्रिंट करके रखें", font=f_sub_hi, fill=DIM)
    d.text((M, 262), "", font=f_sub, fill=DIM)

    y = 340
    # table header
    f_head = font(SEGOE_B, 30)
    f_row = font(SEGOE, 31)
    f_row_hi = font(NIRMALA, 29, index=0)
    f_meta = font(SEGOE, 27)
    f_price = font(SEGOE_B, 33)

    x_svc, x_hi, x_time, x_price = M, M + 640, M + 1210, M + 1390
    d.text((x_svc, y), "Service", font=f_head, fill=FAINT)
    d.text((x_hi, y), "सेवा", font=f_row_hi, fill=FAINT)
    d.text((x_time, y), "Time", font=f_head, fill=FAINT)
    d.text((x_price, y), "Rate", font=f_head, fill=FAINT)
    y += 52
    d.line([(M, y), (W - M, y)], fill=(52, 58, 76), width=2)
    y += 18

    row_h = 108
    for i, (en, hi, t, price) in enumerate(ROWS):
        if i % 2 == 0:
            d.rectangle([M - 20, y - 10, W - M + 20, y + row_h - 14], fill=(18, 23, 37))
        d.text((x_svc, y), en, font=f_row, fill=TEXT)
        d.text((x_hi, y + 2), hi, font=f_row_hi, fill=DIM)
        d.text((x_time, y + 4), t, font=f_meta, fill=AMBER)
        pc = GREEN if price == "Free" else TEXT
        d.text((x_price, y), price, font=f_price, fill=pc)
        y += row_h
        d.line([(M, y - 16), (W - M, y - 16)], fill=(38, 44, 62), width=1)

    y += 30
    f_note = font(SEGOE, 28)
    f_note_hi = font(NIRMALA, 27, index=0)
    d.text((M, y), "Suggested prices — your counter, your rates.", font=f_note, fill=DIM); y += 40
    d.text((M, y), "सुझाए गए मूल्य — आपका काउंटर, आपके रेट।", font=f_note_hi, fill=DIM); y += 56
    d.text((M, y), "DSC signing: the customer brings their own USB token or .pfx — the private key never leaves it.",
           font=f_note, fill=DIM); y += 40
    d.text((M, y), "DSC sign: grahak apna USB token ya .pfx laata hai — private key kabhi token se bahar nahi niklti.",
           font=f_note_hi, fill=DIM); y += 62

    d.line([(M, y), (W - M, y)], fill=(52, 58, 76), width=2)
    y += 24
    f_foot = font(SEGOE_B, 30)
    f_foot_hi = font(NIRMALA, 28, index=0)
    d.text((M, y), "Opal — free · fully offline · 0 bytes uploaded · no account", font=f_foot, fill=TEXT); y += 44
    d.text((M, y), "Opal — निःशुल्क · poori tarah offline · 0 bytes upload · koi account nahi", font=f_foot_hi, fill=DIM)
    y += 44
    d.text((M, y), "github.com/gaurav-eshanura/opal  ·  © 2026 Opal v2.0.1", font=f_meta, fill=FAINT)

    img.save(OUT_PNG, optimize=True)
    print(f"png {OUT_PNG} {img.size}")

    import fitz  # pymupdf
    jpg = OUT_PNG.with_suffix(".jpg")
    img.convert("RGB").save(jpg, quality=88)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 points
    page.insert_image(fitz.Rect(0, 0, 595, 842), filename=str(jpg))
    doc.save(str(OUT_PDF), deflate=True, garbage=3)
    doc.close()
    chk = fitz.open(str(OUT_PDF))
    print(f"pdf {OUT_PDF} pages={chk.page_count} size={OUT_PDF.stat().st_size}")


if __name__ == "__main__":
    main()
