"""
Opal - Screen gallery builder
Plain English: Copies the captured screen PNGs into a folder and writes an
index.html beside them - a labelled grid of every screen, so the whole product
can be reviewed in one page.
Usage:  python tools/build_screen_gallery.py <png_dir> <dest_dir>
"""

import html
import shutil
import sys
from pathlib import Path


def caption(stem):
    words = stem.split("-", 1)
    if words[0].isdigit():
        words = words[1:]
    return " ".join(w.capitalize() for w in "-".join(words).split("-"))


def main():
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    pngs = sorted(src.glob("*.png"))
    for p in pngs:
        shutil.copy2(p, dest / p.name)

    cards = []
    for p in pngs:
        cards.append(
            f'    <figure>\n'
            f'      <img src="{html.escape(p.name)}" alt="{html.escape(caption(p.stem))}" loading="lazy">\n'
            f'      <figcaption><b>{p.stem.split("-")[0]}</b> {html.escape(caption(p.stem))}</figcaption>\n'
            f'    </figure>'
        )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Opal - every screen, in use</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; padding: 24px; background: #0B0E18; color: #EDF1FA;
         font-family: 'Segoe UI', system-ui, sans-serif; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  p.sub {{ color: #A8B2C8; font-size: 12px; margin: 0 0 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
  figure {{ margin: 0; background: #141A2B; border: 1px solid rgba(255,255,255,0.10);
            border-radius: 18px; padding: 12px; }}
  img {{ display: block; width: 100%; height: auto; border-radius: 12px;
         background: #080B13; }}
  figcaption {{ font-size: 12px; color: #A8B2C8; padding-top: 8px; }}
  figcaption b {{ color: #8A83FF; margin-right: 6px; }}
</style>
</head>
<body>
<h1>Opal - every screen, in use</h1>
<p class="sub">{len(pngs)} screens captured offscreen from the real app, each in a used state. Grid: 24px window margins, 12px inner margins, 4/8/12/16 spacing, 8/12/18 radii, 32px controls.</p>
<div class="grid">
{chr(10).join(cards)}
</div>
</body>
</html>
"""
    (dest / "index.html").write_text(page, encoding="utf-8")
    print(f"gallery: {len(pngs)} screens -> {dest / 'index.html'}")


if __name__ == "__main__":
    main()
