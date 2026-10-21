"""
Opal - the brand mark
Plain English: draws the Opal mark, a polished opal pebble cut from glass.
An opal has no paint in it: the colour comes from light refracting inside the
stone, so it changes with the light. That is the whole product in one shape -
the file never changes, only the form it is seen in.

The same drawing code feeds the app icon, the window title bar and the website,
so the brand can never drift between them.
"""

import math
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QIcon, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QRadialGradient)

# The play of colour inside an opal. Kept in one place so the mark, the icon
# and the website always agree.
FIRE = ["#21C7D0", "#3C7BF2", "#8A5CF6", "#EE4E8A", "#FF9A3C", "#37C98A"]

# Body tones: milky, cool, almost white - the stone before the light hits it.
MILK = "#FBFCFE"
MILK_DEEP = "#D7DEEE"
RIM_DARK = "#7A87A6"


def _blob_points(cx: float, cy: float, rx: float, ry: float,
                 count: int = 72) -> List[QPointF]:
    """Points around the stone: a clean oval, cut by hand rather than machine."""
    pts: List[QPointF] = []
    for i in range(count):
        a = 2 * math.pi * i / count
        wobble = (1.0
                  + 0.018 * math.sin(3 * a + 0.7)
                  + 0.012 * math.cos(2 * a - 1.1))
        pts.append(QPointF(cx + rx * wobble * math.cos(a),
                           cy + ry * wobble * math.sin(a)))
    return pts


def _smooth_closed_path(points: List[QPointF]) -> QPainterPath:
    """A smooth closed curve through the points (midpoint quadratics)."""
    def mid(a: QPointF, b: QPointF) -> QPointF:
        return QPointF((a.x() + b.x()) / 2.0, (a.y() + b.y()) / 2.0)

    path = QPainterPath()
    path.moveTo(mid(points[-1], points[0]))
    for i, current in enumerate(points):
        following = points[(i + 1) % len(points)]
        path.quadTo(current, mid(current, following))
    path.closeSubpath()
    return path


def opal_path(size: float) -> QPainterPath:
    """The silhouette of the stone: a polished oval, tipped a few degrees."""
    c = size / 2.0
    path = _smooth_closed_path(_blob_points(c, c, size * 0.415, size * 0.335))
    return path


def _lerp_colour(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(int(ca.red() + (cb.red() - ca.red()) * t),
                  int(ca.green() + (cb.green() - ca.green()) * t),
                  int(ca.blue() + (cb.blue() - ca.blue()) * t))


def _spectral_bar(painter: QPainter, cx: float, cy: float, length: float,
                   width: float, angle: float, colours: List[str],
                   strength: int = 120) -> None:
    """A soft bar of colour laid across the stone.

    It is built from overlapping lenses of light, each carrying the colour
    of that point along the bar, so the colour shifts the way an opal's does.
    """
    steps = 14
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(angle)
    painter.setPen(Qt.NoPen)
    for i in range(steps):
        t = i / (steps - 1.0)
        pos = (t - 0.5) * length
        # Fade the bar out at both ends.
        taper = max(0.0, 1.0 - abs(t - 0.5) * 2.0) ** 0.7
        if taper <= 0.02:
            continue
        colour = _lerp_colour(colours[0], colours[-1], t)
        radius = length * 0.30
        grad = QRadialGradient(QPointF(pos, 0), radius)
        core = QColor(colour)
        core.setAlpha(int(strength * taper))
        mid = QColor(colour)
        mid.setAlpha(int(strength * taper * 0.55))
        edge = QColor(colour)
        edge.setAlpha(0)
        grad.setColorAt(0.0, core)
        grad.setColorAt(0.45, mid)
        grad.setColorAt(1.0, edge)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QRectF(pos - radius, -width / 2.0, radius * 2, width))
    painter.restore()


def _fire_layer(painter: QPainter, size: float) -> None:
    """The colour inside the stone: one broad cool band with a warm flash."""
    c = size / 2.0

    # The main bar of fire, running lower-left to upper-right.
    _spectral_bar(painter, c, c + size * 0.01, size * 0.86, size * 0.30, -20.0,
                  [FIRE[0], FIRE[1], FIRE[2]], strength=135)

    # A second, softer band crossing it - the colour deepens where they meet.
    _spectral_bar(painter, c - size * 0.04, c + size * 0.07, size * 0.62,
                  size * 0.20, 24.0, [FIRE[5], FIRE[0], FIRE[1]], strength=85)

    # A warm flash low in the stone - the orange every opal seems to keep.
    _spectral_bar(painter, c + size * 0.10, c + size * 0.115, size * 0.40,
                  size * 0.16, -14.0, [FIRE[3], FIRE[4]], strength=105)

    # A cool wash low in the stone, so the fire has somewhere to sit.
    painter.setPen(Qt.NoPen)
    wash = QRadialGradient(QPointF(c - size * 0.10, c + size * 0.12), size * 0.40)
    wash.setColorAt(0.0, QColor(120, 200, 235, 45))
    wash.setColorAt(1.0, QColor(120, 200, 235, 0))
    painter.setBrush(QBrush(wash))
    painter.drawEllipse(QRectF(c - size * 0.5, c - size * 0.5, size, size))


def _specular(painter: QPainter, size: float) -> None:
    """The wet highlight every polished stone has in the top-left."""
    c = size / 2.0
    painter.setPen(Qt.NoPen)
    painter.save()
    painter.translate(c - size * 0.15, c - size * 0.17)
    painter.rotate(-32)
    grad = QRadialGradient(QPointF(0, 0), size * 0.19)
    grad.setColorAt(0.0, QColor(255, 255, 255, 225))
    grad.setColorAt(0.55, QColor(255, 255, 255, 70))
    grad.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(grad))
    painter.drawEllipse(QRectF(-size * 0.19, -size * 0.10, size * 0.38, size * 0.20))
    painter.restore()

    # A small, hard catchlight - the reason the stone looks wet.
    painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
    painter.drawEllipse(QRectF(c - size * 0.225, c - size * 0.235,
                               size * 0.062, size * 0.045))


def paint_opal(painter: QPainter, size: float, glow: bool = True) -> None:
    """Paints the bare mark: a glass pebble with fire inside it."""
    c = size / 2.0
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = opal_path(size)

    if glow:
        # The light the stone throws onto whatever it is resting on.
        halo = QRadialGradient(QPointF(c, c), size * 0.50)
        halo.setColorAt(0.0, QColor(140, 190, 240, 30))
        halo.setColorAt(0.55, QColor(190, 140, 235, 16))
        halo.setColorAt(1.0, QColor(190, 140, 235, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QRectF(c - size * 0.50, c - size * 0.50,
                                   size, size))

    # The milky body.
    body = QLinearGradient(c - size * 0.4, c - size * 0.4, c + size * 0.4, c + size * 0.4)
    body.setColorAt(0.0, QColor(MILK))
    body.setColorAt(0.5, QColor("#EFF3FA"))
    body.setColorAt(1.0, QColor(MILK_DEEP))
    painter.setBrush(QBrush(body))
    painter.setPen(Qt.NoPen)
    painter.drawPath(path)

    # The fire, clipped inside the stone.
    painter.save()
    painter.setClipPath(path)
    _fire_layer(painter, size)

    # Depth: the far side of the stone falls into shadow.
    shade = QLinearGradient(c - size * 0.3, c - size * 0.3, c + size * 0.35, c + size * 0.4)
    shade.setColorAt(0.0, QColor(60, 72, 104, 0))
    shade.setColorAt(0.55, QColor(60, 72, 104, 0))
    shade.setColorAt(1.0, QColor(56, 68, 102, 70))
    painter.setBrush(QBrush(shade))
    painter.setPen(Qt.NoPen)
    painter.drawPath(path)
    painter.restore()

    # The rim: light bends at the edge, so the top-left is bright and the
    # bottom-right gathers colour.
    rim = QLinearGradient(c - size * 0.4, c - size * 0.4, c + size * 0.4, c + size * 0.4)
    rim.setColorAt(0.0, QColor(255, 255, 255, 245))
    rim.setColorAt(0.40, QColor(255, 255, 255, 130))
    rim.setColorAt(0.72, QColor(150, 170, 215, 120))
    rim.setColorAt(1.0, QColor(90, 105, 145, 175))
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QBrush(rim), max(1.0, size * 0.016)))
    painter.drawPath(path)

    # A thin bright arc along the top-left edge - the signature of glass.
    arc = QRectF(c - size * 0.40, c - size * 0.325, size * 0.80, size * 0.65)
    painter.setPen(QPen(QColor(255, 255, 255, 205), max(1.0, size * 0.013)))
    painter.drawArc(arc, 108 * 16, 74 * 16)

    _specular(painter, size)


def opal_pixmap(size: int) -> QPixmap:
    """The bare mark on a transparent background."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    paint_opal(painter, size)
    painter.end()
    return pix


def opal_icon(size: int = 32) -> QIcon:
    """The mark as an icon, for the title bar and the tray."""
    return QIcon(opal_pixmap(size))


def app_icon_pixmap(size: int) -> QPixmap:
    """The app tile: the stone floating in a pool of its own colour."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    radius = size * 0.225
    tile = QRectF(0, 0, size, size)

    # Deep, cool glass tile.
    plate = QLinearGradient(0, 0, size * 0.4, size)
    plate.setColorAt(0.0, QColor("#232838"))
    plate.setColorAt(0.55, QColor("#1A1E2B"))
    plate.setColorAt(1.0, QColor("#12151F"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(plate))
    painter.drawRoundedRect(tile, radius, radius)

    # Colour bleeding up through the tile from the stone.
    painter.save()
    painter.setClipPath(_smooth_closed_path(_blob_points(
        size / 2, size / 2, size * 0.42, size * 0.39)))
    for i, colour in enumerate(FIRE):
        glow = QRadialGradient(QPointF(size * 0.5, size * 0.56), size * (0.46 - i * 0.05))
        c = QColor(colour)
        c.setAlpha(70 - i * 8)
        glow.setColorAt(0.0, c)
        glow.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(tile)
    painter.restore()

    # The stone.
    painter.save()
    painter.translate(0, size * 0.005)
    paint_opal(painter, size * 0.82, glow=False)
    painter.restore()

    # A sheen across the top of the tile.
    sheen = QLinearGradient(0, 0, 0, size * 0.55)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 70))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(sheen))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size, size * 0.55), radius, radius)

    # The tile's own refractive edge.
    edge = QLinearGradient(0, 0, size, size)
    edge.setColorAt(0.0, QColor(255, 255, 255, 130))
    edge.setColorAt(0.5, QColor(255, 255, 255, 30))
    edge.setColorAt(1.0, QColor(0, 0, 0, 90))
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QBrush(edge), max(1.0, size * 0.014)))
    painter.drawRoundedRect(tile.adjusted(size * 0.007, size * 0.007,
                                          -size * 0.007, -size * 0.007),
                            radius, radius)
    painter.end()
    return pix


def wordmark_pixmap(height: int = 48, colour: str = "#1A1D26",
                    sub: str = "offline file studio") -> QPixmap:
    """The wordmark: OPAL, wide-tracked, with the product line beneath it."""
    from PySide6.QtGui import QFont

    big = max(10, int(height * 0.52))
    small = max(8, int(height * 0.19))
    width = int(height * 4.4)
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    font = QFont("Segoe UI", big, QFont.Black)
    font.setLetterSpacing(QFont.AbsoluteSpacing, height * 0.11)
    painter.setFont(font)
    painter.setPen(QColor(colour))
    painter.drawText(QRectF(0, height * 0.02, width, height * 0.62),
                     int(Qt.AlignLeft | Qt.AlignVCenter), "OPAL")

    sub_font = QFont("Segoe UI", small, QFont.DemiBold)
    sub_font.setLetterSpacing(QFont.AbsoluteSpacing, height * 0.10)
    painter.setFont(sub_font)
    painter.setPen(QColor(colour))
    painter.setOpacity(0.55)
    painter.drawText(QRectF(2, height * 0.58, width, height * 0.34),
                     int(Qt.AlignLeft | Qt.AlignVCenter), sub.upper())
    painter.end()
    return pix


def mark_image(size: int = 512) -> QImage:
    """The mark as a QImage, for the SVG/PNG writers."""
    return opal_pixmap(size).toImage()
