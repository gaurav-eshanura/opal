"""
Opal - wheel demo GIF for launch assets (Product Hunt / social).
Plain English: renders the real radial wheel offscreen, hovering each wedge in
turn, and stitches the frames into a looping GIF at website/assets/press/.

Run:  QT_QPA_PLATFORM=offscreen python tools/make_wheel_gif.py
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint

from opal_studio.radial_widget import RadialMenuWidget

OUT = REPO / "website" / "assets" / "press" / "wheel-demo.gif"
TMP = Path(os.environ.get("TEMP", r"C:\Users\shiva\AppData\Local\Temp")) / "opal_wheel_gif"


def main():
    from PIL import Image

    TMP.mkdir(parents=True, exist_ok=True)
    sample = TMP / "portrait.jpg"
    Image.new("RGB", (96, 96), (196, 128, 84)).save(sample)

    app = QApplication([])
    w = RadialMenuWidget()
    w.show_for_files([str(sample)], QPoint(0, 0), "tools")
    app.processEvents()

    n = len(w.options)
    print(f"wheel options on this page: {n}")

    frames = []
    # intro frame: wheel open, nothing hovered
    w.hovered_index = -1
    w.update()
    app.processEvents()
    frames.append(w.grab().toImage())
    # hover every wedge in turn
    for i in range(n):
        w.hovered_index = i
        w.update()
        app.processEvents()
        frames.append(w.grab().toImage())

    paths = []
    for i, img in enumerate(frames):
        p = TMP / f"frame_{i:03d}.png"
        img.save(str(p))
        paths.append(p)

    imgs = [Image.open(p).convert("RGB") for p in paths]
    # downscale a little for a light GIF
    imgs = [im.resize((im.width // 2, im.height // 2), Image.LANCZOS) for im in imgs]
    imgs = [im.convert("P", palette=Image.ADAPTIVE, colors=128) for im in imgs]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(
        OUT, save_all=True, append_images=imgs[1:],
        duration=420, loop=0, optimize=True,
    )

    chk = Image.open(OUT)
    print(f"wrote {OUT}")
    print(f"frames={chk.n_frames} size={chk.size} bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
