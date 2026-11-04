"""
Opal - Pixel grid audit
Plain English: Measures the rendered PNGs of every screen and reports the real
pixel geometry - window margins, panel gaps on scanlines, and corner radius -
so "one 12px rhythm" can be checked in actual pixels, not just in source.
Usage:  python tools/measure_screen_grid.py <png_dir>
"""

import sys
from pathlib import Path
from collections import Counter

from PIL import Image
import numpy as np


def runs_along(mask_1d):
    """Content runs (start, end) along a 1-D boolean scanline."""
    runs = []
    start = None
    for i, v in enumerate(mask_1d):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask_1d)))
    return runs


def corner_radius(rgb, bg):
    """Estimate the top-left corner radius of the content bounding box:
    walk down the left edge of the bbox until the first row whose content is
    inset from the bbox left by ~1px; the inset growth over the first rows
    approximates a circle of radius r."""
    diff = np.abs(rgb.astype(int) - bg.astype(int)).max(axis=2)
    mask = diff > 14
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) < 40 or len(cols) < 40:
        return None
    top, left = rows[0], cols[0]
    # for a rounded corner of radius r, the row at offset d from the top
    # starts at left + (r - sqrt(r^2 - (r-d)^2)); solve by scanning
    best = None
    for r in range(2, 40):
        ok = True
        for d in range(0, min(r, 30)):
            expect = left + int(r - (r * r - (r - d) * (r - d)) ** 0.5) if r - d > 0 else left
            row_cols = np.where(mask[top + d])[0]
            actual = row_cols[0] if len(row_cols) else left
            if abs(actual - expect) > 2:
                ok = False
                break
        if ok:
            best = r
            break
    return best


def measure(path):
    img = Image.open(path).convert("RGB")
    rgb = np.array(img)
    h, w = rgb.shape[:2]
    flat = rgb.reshape(-1, 3)
    bg = np.array(Counter(map(tuple, flat[::7])).most_common(1)[0][0])
    diff = np.abs(rgb.astype(int) - bg.astype(int)).max(axis=2)
    mask = diff > 14
    rows = np.where(mask.sum(axis=1) > w * 0.05)[0]
    cols = np.where(mask.sum(axis=0) > h * 0.05)[0]
    if not len(rows) or not len(cols):
        return None
    left, top, right, bottom = cols[0], rows[0], w - 1 - cols[-1], h - 1 - rows[-1]

    # scanline through the vertical middle: report content runs and the gaps
    mid = (rows[0] + rows[-1]) // 2
    line_runs = runs_along(mask[mid])
    gaps = [b[0] - a[1] for a, b in zip(line_runs, line_runs[1:]) if b[0] - a[1] >= 3]
    big_runs = [r for r in line_runs if r[1] - r[0] > w * 0.05]

    radius = corner_radius(rgb, bg)
    return dict(size=(w, h), bg=tuple(int(c) for c in bg), margins=(left, top, right, bottom),
                mid_runs=len(big_runs), mid_gaps=sorted(set(gaps)), radius=radius)


def main():
    d = Path(sys.argv[1])
    print(f"{'screen':<28} {'size':<12} {'margins L/T/R/B':<18} {'mid gaps':<18} radius")
    for p in sorted(d.glob("*.png")):
        m = measure(p)
        if not m:
            print(f"{p.stem:<28} (no content)")
            continue
        w, h = m["size"]
        mg = "/".join(str(x) for x in m["margins"])
        gaps = ",".join(str(g) for g in m["mid_gaps"][:6])
        print(f"{p.stem:<28} {w}x{h:<6} {mg:<18} {gaps:<18} {m['radius']}")


if __name__ == "__main__":
    main()
