"""
Opal - Liquid glass primitives
Plain English: the drawing code for panes of glass. A glass pane is not a flat
colour: it is a slab that is lit from above, that darkens where it meets the
surface below, and whose edge catches the light as it bends through the glass.
These helpers draw all of that, so every panel in the app is made the same way.

Nothing here needs a screen grab or a platform trick - it is all painting, so
it behaves identically on Windows, macOS and Linux, and in a test.
"""

import math
from typing import List, Optional, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QToolButton, QWidget

from opal_studio.theme import (ACCENT, ACCENT_HI, FIRE, FIRE_AMBER, FIRE_BLUE,
                               FIRE_ROSE, FIRE_TEAL, FIRE_VIOLET, LINE, LINE_STRONG,
                               RADIUS, RADIUS_LARGE, RADIUS_SMALL, SURFACE, TEXT, TEXT_DIM)

# How a pane of glass is put together. These are the proportions that make a
# surface read as glass rather than as a coloured rectangle.
GLASS_FILL_TOP = 26          # alpha of the lit top of the slab
GLASS_FILL_BOTTOM = 8        # alpha at the base, where it meets the field
GLASS_EDGE_TOP = 150         # alpha of the bright rim along the top
GLASS_EDGE_BOTTOM = 60       # alpha of the shadowed rim along the bottom


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    """A rounded rectangle as a path, so it can be clipped and stroked."""
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def spectral_brush(rect: QRectF, colors: Optional[Sequence[str]] = None,
                   angle: float = 45.0) -> QBrush:
    """The gradient of light travelling through the stone."""
    colors = list(colors or FIRE)
    start = QPointF(rect.left(), rect.bottom())
    end = QPointF(rect.right(), rect.top())
    gradient = QLinearGradient(start, end)
    span = len(colors)
    for i, colour in enumerate(colors):
        gradient.setColorAt(i / max(1, span - 1), QColor(colour))
    return QBrush(gradient)


def fire_brush(rect: QRectF) -> QBrush:
    """The full fire, in the order the light meets it."""
    return spectral_brush(rect, [FIRE_VIOLET, FIRE_ROSE, FIRE_AMBER])


def caustic_glow(painter: QPainter, rect: QRectF, radius: float,
                 strength: float = 1.0) -> None:
    """The coloured light a piece of glass throws onto the surface below it."""
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setClipPath(rounded_path(rect, radius))
    painter.setCompositionMode(QPainter.CompositionMode_Plus)
    for i, colour in enumerate((FIRE_VIOLET, FIRE_TEAL, FIRE_ROSE)):
        glow = QRadialGradient(QPointF(rect.center().x() + (i - 1) * rect.width() * 0.28,
                                        rect.bottom() - rect.height() * 0.10),
                                rect.width() * 0.62)
        c = QColor(colour)
        c.setAlpha(int(26 * strength))
        glow.setColorAt(0.0, c)
        glow.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setBrush(QBrush(glow))
        painter.drawRect(rect)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.restore()


def paint_glass_sheet(painter: QPainter, rect: QRectF, radius: float = RADIUS,
                      fill_top: int = GLASS_FILL_TOP, fill_bottom: int = GLASS_FILL_BOTTOM,
                      edge: bool = True, shadow: bool = False,
                      tint: Optional[QColor] = None) -> None:
    """Paints one pane of glass.

    The pane is a translucent slab: brightest along the top where the light
    lands, dimmer at the base, with a rim that is white where the light bends
    through the top edge and dark where it bends through the bottom.
    """
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = rounded_path(rect, radius)

    if shadow:
        # A soft drop shadow, built from a few stacked outlines because Qt
        # cannot blur a path directly.
        for i in range(10, 0, -1):
            spread = i * 1.6
            alpha = int(3 + (10 - i) * 1.6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(rect.adjusted(-spread, -spread + 3,
                                                   spread, spread + 5),
                                    radius + spread, radius + spread)

    # The body of the glass.
    fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    if tint is not None:
        fill.setColorAt(0.0, QColor(tint.red(), tint.green(), tint.blue(), fill_top))
        fill.setColorAt(1.0, QColor(tint.red(), tint.green(), tint.blue(), fill_bottom))
    else:
        fill.setColorAt(0.0, QColor(255, 255, 255, fill_top))
        fill.setColorAt(0.55, QColor(240, 246, 255, int((fill_top + fill_bottom) / 2)))
        fill.setColorAt(1.0, QColor(210, 224, 255, fill_bottom))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(fill))
    painter.drawPath(path)

    if edge:
        # The rim: white along the top, gathering shadow along the bottom.
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, GLASS_EDGE_TOP))
        rim.setColorAt(0.42, QColor(255, 255, 255, 26))
        rim.setColorAt(0.80, QColor(0, 0, 0, 40))
        rim.setColorAt(1.0, QColor(0, 0, 0, GLASS_EDGE_BOTTOM))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QBrush(rim), 1.0))
        painter.drawPath(path)

        # A second, brighter line just inside the top edge - the sliver of
        # light that always sits on the lip of a glass.
        painter.save()
        painter.setClipPath(path)
        lip = QLinearGradient(rect.topLeft(), QPointF(rect.right(), rect.top() + rect.height() * 0.30))
        lip.setColorAt(0.0, QColor(255, 255, 255, 0))
        lip.setColorAt(0.16, QColor(255, 255, 255, 120))
        lip.setColorAt(0.60, QColor(255, 255, 255, 40))
        lip.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(lip), 2.4))
        painter.drawPath(path)
        painter.restore()
    painter.restore()


def paint_frosted_backdrop(painter: QPainter, rect: QRectF, radius: float,
                            strength: float = 0.5) -> None:
    """A soft, deep field of colour for a window to float on.

    Stitch radial-aurora recipe (design/stitch/DESIGN.md): one violet glow
    top-left (18%), one rose glow bottom-right (8%), on the #0B0E18 ground.
    """
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = rounded_path(rect, radius)
    painter.setClipPath(path)

    base = QLinearGradient(rect.topLeft(), rect.bottomRight())
    base.setColorAt(0.0, QColor("#131A2E"))
    base.setColorAt(0.5, QColor("#0E1322"))
    base.setColorAt(1.0, QColor("#0A0D18"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(base))
    painter.drawRect(rect)

    # (x-frac, y-frac, radius-frac, alpha, colour) — the two Stitch aurora
    # glows: violet 18% top-left, rose 8% bottom-right. Painted SourceOver so
    # the glow tints the field instead of stacking with the caustic glow.
    for x_frac, y_frac, r_frac, alpha, colour in (
            (0.15, 0.10, 0.65, 0.18, FIRE_VIOLET),
            (0.85, 0.85, 0.55, 0.08, FIRE_ROSE)):
        cx = rect.left() + rect.width() * x_frac
        cy = rect.top() + rect.height() * y_frac
        glow = QRadialGradient(QPointF(cx, cy), rect.width() * r_frac)
        c = QColor(colour)
        c.setAlpha(int(alpha * 255 * strength * 0.85))
        glow.setColorAt(0.0, c)
        glow.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.setBrush(QBrush(glow))
        painter.drawRect(rect)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    # The field dim: without it the glows pool into a flat gray-blue and the
    # frosted tiles lose their separation. A gentle navy veil over the lights
    # keeps the depth (Stitch: deep ground #0B0E18 under glass).
    veil = QLinearGradient(rect.topLeft(), rect.bottomRight())
    veil.setColorAt(0.0, QColor(11, 14, 24, 90))
    veil.setColorAt(1.0, QColor(11, 14, 24, 68))
    painter.setBrush(QBrush(veil))
    painter.drawRect(rect)
    painter.restore()


def frosted(pixmap: QPixmap, strength: int = 18) -> QPixmap:
    """Blurs a picture by shrinking it and letting it grow back."""
    if pixmap.isNull() or pixmap.width() < 8:
        return pixmap
    small = pixmap.scaled(max(2, pixmap.width() // strength),
                          max(2, pixmap.height() // strength),
                          Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(pixmap.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


class GlassSheet(QFrame):
    """A widget that is a pane of glass.

    Put your content inside it and it floats on the field behind, lit from
    above, with the light bending along its edge.
    """

    def __init__(self, parent: Optional[QWidget] = None, radius: int = RADIUS_LARGE,
                 fill_top: int = GLASS_FILL_TOP, fill_bottom: int = GLASS_FILL_BOTTOM,
                 edge: bool = True, shadow: bool = False):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._radius = radius
        self._fill_top = fill_top
        self._fill_bottom = fill_bottom
        self._edge = edge
        self._shadow = shadow
        self.setFrameShape(QFrame.NoFrame)

    def set_glass(self, fill_top: Optional[int] = None, fill_bottom: Optional[int] = None,
                  radius: Optional[int] = None) -> None:
        if fill_top is not None:
            self._fill_top = fill_top
        if fill_bottom is not None:
            self._fill_bottom = fill_bottom
        if radius is not None:
            self._radius = radius
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_glass_sheet(painter, rect, self._radius, self._fill_top,
                          self._fill_bottom, self._edge, self._shadow)
        painter.end()
        super().paintEvent(event)


class GlassButton(QPushButton):
    """A button that is a small pane of glass, with the fire inside it.

    The plain variant is a clear slab. The lit variant carries the brand's
    colour gradient, the way light travels through the stone.
    """

    def __init__(self, text: str = "", parent: Optional[QWidget] = None,
                 lit: bool = False, radius: int = 12, tooltip: str = ""):
        super().__init__(text, parent)
        self._lit = lit
        self._radius = radius
        if tooltip:
            self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(32)
        self._apply()

    def _apply(self) -> None:
        if self._lit:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                    stop: 0 #8A5CF6, stop: 0.55 #EE4E8A, stop: 1 #FF9A3C);
                    color: #FFFFFF; border: none; border-radius: 12px;
                    padding: 7px 16px; font-weight: 700; font-size: 11px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                    stop: 0 #9B7BFF, stop: 0.55 #FF6BA0, stop: 1 #FFB35C);
                }
                QPushButton:pressed { background: rgba(255,255,255,0.18); }
                QPushButton:disabled { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.3); }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: rgba(255,255,255,0.07);
                    color: #EDF1FA;
                    border: 1px solid rgba(255,255,255,0.16);
                    border-radius: 12px; padding: 7px 14px;
                    font-weight: 600; font-size: 11px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.13);
                    border-color: rgba(255,255,255,0.30);
                    color: #FFFFFF;
                }
                QPushButton:pressed { background: rgba(255,255,255,0.04); }
                QPushButton:disabled {
                    background: rgba(255,255,255,0.03);
                    color: rgba(237,241,250,0.28);
                    border-color: rgba(255,255,255,0.06);
                }
            """)

    def set_lit(self, lit: bool) -> None:
        self._lit = lit
        self._apply()


class SegmentedControl(QWidget):
    """A macOS-style segmented switcher: one glass pill, several segments.

    Used wherever the app has modes (File / Organize / Annotate / Convert).
    Emits currentChanged(id) when the user picks a segment.
    """

    currentChanged = Signal(str)

    def __init__(self, items: List[Tuple[str, str]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._buttons: Dict[str, QToolButton] = {}
        self._current = ""

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        pill = QWidget()
        pill.setObjectName("segPill")
        lay = QHBoxLayout(pill)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        for sid, label in items:
            btn = QToolButton(pill)
            btn.setText(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, s=sid: self.set_current(s))
            lay.addWidget(btn)
            self._buttons[sid] = btn
        outer.addWidget(pill)

        self.setStyleSheet(f"""
            QWidget#segPill {{
                background: {SURFACE};
                border: 1px solid {LINE};
                border-radius: {RADIUS}px;
            }}
            QWidget#segPill QToolButton {{
                background: transparent;
                border: none;
                border-radius: {RADIUS_SMALL}px;
                color: {TEXT_DIM};
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 600;
            }}
            QWidget#segPill QToolButton:hover {{ background: rgba(255,255,255,0.07); color: {TEXT}; }}
            QWidget#segPill QToolButton:checked {{
                background: {ACCENT};
                color: #FFFFFF;
            }}
        """)
        if items:
            self._buttons[items[0][0]].setChecked(True)
            self._current = items[0][0]

    def set_current(self, sid: str) -> None:
        if sid not in self._buttons:
            return
        for other, btn in self._buttons.items():
            btn.setChecked(other == sid)
        if sid != self._current:
            self._current = sid
            self.currentChanged.emit(sid)

    def current(self) -> str:
        return self._current
