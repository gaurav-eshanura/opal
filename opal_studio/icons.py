"""
Opal - Vector icon set
Plain English: Draws the small interface icons as vectors so they stay crisp at
any size and never depend on an emoji font being installed. One function per
icon, each returning a QIcon ready for a button.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _canvas(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    return pix


def _pen(color: str, width: float, cap=Qt.RoundCap) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(cap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def pin_icon(size: int = 20, color: str = "#636D64") -> QIcon:
    """A pin: the studio stays on top."""
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    p.setPen(_pen(color, 1.7 * s))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(7 * s, 3.2 * s), QPointF(13 * s, 3.2 * s))
    p.drawLine(QPointF(10 * s, 3.2 * s), QPointF(10 * s, 11.5 * s))
    p.drawArc(QRectF(6.2 * s, 9.6 * s, 7.6 * s, 7.6 * s), 200 * 16, 140 * 16)
    p.drawLine(QPointF(5.5 * s, 16.6 * s), QPointF(14.5 * s, 16.6 * s))
    p.end()
    return QIcon(pix)


def opacity_icon(size: int = 20, color: str = "#636D64") -> QIcon:
    """A half-filled circle: the window fades."""
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    p.setPen(_pen(color, 1.6 * s))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(3.6 * s, 3.6 * s, 12.8 * s, 12.8 * s))
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.NoPen)
    p.drawPie(QRectF(3.6 * s, 3.6 * s, 12.8 * s, 12.8 * s), 90 * 16, 180 * 16)
    p.end()
    return QIcon(pix)


def ghost_icon(size: int = 20, color: str = "#636D64") -> QIcon:
    """A ghost: click-through mode."""
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    p.setPen(_pen(color, 1.6 * s))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(4.6 * s, 15.6 * s)
    path.lineTo(4.6 * s, 8.2 * s)
    path.arcTo(QRectF(4.6 * s, 3.2 * s, 10.8 * s, 10.8 * s), 90, 180)
    path.lineTo(15.4 * s, 15.6 * s)
    path.lineTo(13.0 * s, 13.8 * s)
    path.lineTo(10.8 * s, 15.6 * s)
    path.lineTo(8.6 * s, 13.8 * s)
    path.lineTo(6.8 * s, 15.6 * s)
    path.closeSubpath()
    p.drawPath(path)
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(QRectF(7.4 * s, 7.2 * s, 1.8 * s, 2.4 * s))
    p.drawEllipse(QRectF(11.0 * s, 7.2 * s, 1.8 * s, 2.4 * s))
    p.end()
    return QIcon(pix)


def maximize_icon(size: int = 20, color: str = "#636D64") -> QIcon:
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    p.setPen(_pen(color, 1.6 * s))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(4.4 * s, 4.4 * s, 11.2 * s, 11.2 * s))
    p.end()
    return QIcon(pix)


def restore_icon(size: int = 20, color: str = "#636D64") -> QIcon:
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    p.setPen(_pen(color, 1.6 * s))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(4.0 * s, 7.2 * s, 9.2 * s, 9.2 * s))
    p.drawPolyline([QPointF(7.2 * s, 7.2 * s), QPointF(7.2 * s, 4.2 * s),
                    QPointF(16.0 * s, 4.2 * s), QPointF(16.0 * s, 12.6 * s),
                    QPointF(13.4 * s, 12.6 * s)])
    p.end()
    return QIcon(pix)


def close_icon(size: int = 20, color: str = "#636D64") -> QIcon:
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    p.setPen(_pen(color, 1.8 * s))
    p.drawLine(QPointF(5.4 * s, 5.4 * s), QPointF(14.6 * s, 14.6 * s))
    p.drawLine(QPointF(14.6 * s, 5.4 * s), QPointF(5.4 * s, 14.6 * s))
    p.end()
    return QIcon(pix)


def mark_icon(size: int = 32, with_plate: bool = True) -> QIcon:
    """The Opal mark, used in the title bar."""
    from opal_studio.brand import app_icon_pixmap, opal_pixmap
    if with_plate:
        return QIcon(app_icon_pixmap(size))
    return QIcon(opal_pixmap(size))


# ---------------------------------------------------------------------------
# Generic toolbar glyphs (20x20 grid, stroked, round caps) so no button ever
# depends on an emoji font being installed.
# ---------------------------------------------------------------------------

def _glyph(size: int, color: str, draw) -> QIcon:
    pix = _canvas(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20.0
    draw(p, s, QColor(color))
    p.end()
    return QIcon(pix)


def folder_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        pen = _pen(color, 1.6 * s)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(4, 7), (4, 17), (16, 17), (16, 7), (11, 7), (9.4, 4.6), (4, 4.6)]))
    return _glyph(size, color, draw)


def save_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(4, 4), (13.4, 4), (16, 6.6), (16, 16), (4, 16)]))
        p.drawRect(QRectF(7 * s, 4 * s, 6 * s, 5 * s))
        p.drawRect(QRectF(7 * s, 11 * s, 6 * s, 5 * s))
    return _glyph(size, color, draw)


def printer_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(4.5 * s, 8 * s, 11 * s, 5 * s))
        p.drawPath(_path([(6.5, 13), (6.5, 17), (13.5, 17), (13.5, 13)]))
        p.drawRect(QRectF(6.5 * s, 3.6 * s, 7 * s, 4.4 * s))
    return _glyph(size, color, draw)


def text_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s))
        for y in (5.5, 10, 14.5):
            p.drawLine(QPointF(4 * s, y * s), QPointF(16 * s, y * s))
    return _glyph(size, color, draw)


def pen_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(13.8, 3.6), (16.4, 6.2), (7.4, 15.2), (4.2, 16.2), (5.2, 13)]))
        p.drawLine(QPointF(12.6 * s, 4.8 * s), QPointF(15.2 * s, 7.4 * s))
    return _glyph(size, color, draw)


def search_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.8 * s)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(4 * s, 4 * s, 8.6 * s, 8.6 * s))
        p.drawLine(QPointF(10.4 * s, 10.4 * s), QPointF(16 * s, 16 * s))
    return _glyph(size, color, draw)


def copy_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(7 * s, 7 * s, 9 * s, 9 * s))
        p.drawPath(_path([(13, 4), (6.5, 4), (4, 6.5), (4, 13), (6.5, 15.5), (13, 15.5)]))
    return _glyph(size, color, draw)


def home_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(3.4, 10.4), (10, 4), (16.6, 10.4), (14.8, 10.4), (14.8, 16.4), (5.2, 16.4), (5.2, 10.4)]))
    return _glyph(size, color, draw)


def plus_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.9 * s))
        p.drawLine(QPointF(10 * s, 4.5 * s), QPointF(10 * s, 15.5 * s))
        p.drawLine(QPointF(4.5 * s, 10 * s), QPointF(15.5 * s, 10 * s))
    return _glyph(size, color, draw)


def minus_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.9 * s))
        p.drawLine(QPointF(4.5 * s, 10 * s), QPointF(15.5 * s, 10 * s))
    return _glyph(size, color, draw)


def chevron_up_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.9 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(4.5, 12.5), (10, 6.5), (15.5, 12.5)]))
    return _glyph(size, color, draw)


def chevron_down_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.9 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(4.5, 7.5), (10, 13.5), (15.5, 7.5)]))
    return _glyph(size, color, draw)


def speaker_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawPath(_path([(4, 8), (7, 8), (11, 4.4), (11, 15.6), (7, 12), (4, 12)], closed=True))
        p.setPen(_pen(color, 1.5 * s)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(12 * s, 7 * s, 5 * s, 6 * s), -70 * 16, 140 * 16)
    return _glyph(size, color, draw)


def doc_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(5, 3.6), (12.6, 3.6), (15.4, 6.4), (15.4, 16.4), (5, 16.4)]))
        p.drawPath(_path([(12.6, 3.6), (12.6, 6.4), (15.4, 6.4)]))
        p.setPen(_pen(color, 1.4 * s))
        for y in (10, 12.6, 15.2):
            p.drawLine(QPointF(7.4 * s, y * s), QPointF(13 * s, y * s))
    return _glyph(size, color, draw)


def _path(points, closed=False) -> QPainterPath:
    """Build a QPainterPath from a list of (x, y) points in the 20-grid."""
    path = QPainterPath()
    path.moveTo(QPointF(points[0][0], points[0][1]))
    for x, y in points[1:]:
        path.lineTo(QPointF(x, y))
    if closed:
        path.closeSubpath()
    return path


ICONS = {
    "folder": folder_icon, "save": save_icon, "printer": printer_icon,
    "text": text_icon, "pen": pen_icon, "search": search_icon,
    "copy": copy_icon, "home": home_icon, "plus": plus_icon, "minus": minus_icon,
    "up": chevron_up_icon, "down": chevron_down_icon, "speaker": speaker_icon,
    "doc": doc_icon,
}
