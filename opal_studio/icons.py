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


def page_plus_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A page with a plus: insert / blank page."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(5, 3.6), (12.6, 3.6), (15.4, 6.4), (15.4, 16.4), (5, 16.4)]))
        p.drawPath(_path([(12.6, 3.6), (12.6, 6.4), (15.4, 6.4)]))
        p.setPen(_pen(color, 1.8 * s))
        p.drawLine(QPointF(8 * s, 12.4 * s), QPointF(12 * s, 12.4 * s))
        p.drawLine(QPointF(10 * s, 10.4 * s), QPointF(10 * s, 14.4 * s))
    return _glyph(size, color, draw)


def clip_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A paperclip: attach / from file."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(13.6, 16.2), (13.6, 7.4)]))
        p.drawArc(QRectF(6.6 * s, 3.6 * s, 7.0 * s, 7.0 * s), 0 * 16, 180 * 16)
        p.drawPath(_path([(6.6, 7.4), (6.6, 13.2)]))
        p.drawPath(_path([(11.0, 16.2), (11.0, 9.6)]))
        p.drawArc(QRectF(8.4 * s, 6.8 * s, 2.6 * s, 2.6 * s), 0 * 16, 180 * 16)
        p.drawPath(_path([(8.4, 9.6), (8.4, 13.2)]))
    return _glyph(size, color, draw)


def image_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A picture frame with mountains."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.5 * s, 4.5 * s, 13 * s, 11 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(11.9 * s, 7.0 * s, 2.2 * s, 2.2 * s))
        p.setPen(_pen(color, 1.5 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(4.6, 13.6), (8.4, 9.6), (10.8, 12.0), (12.8, 10.2), (15.4, 13.6)]))
    return _glyph(size, color, draw)


def scissors_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Scissors: cut / extract / trim."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(4.6 * s, 12.6 * s, 3.6 * s, 3.6 * s))
        p.drawEllipse(QRectF(11.8 * s, 12.6 * s, 3.6 * s, 3.6 * s))
        p.drawLine(QPointF(7.6 * s, 12.2 * s), QPointF(15.2 * s, 4.4 * s))
        p.drawLine(QPointF(12.4 * s, 12.2 * s), QPointF(4.8 * s, 4.4 * s))
    return _glyph(size, color, draw)


def trash_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A bin: delete."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(4 * s, 6 * s), QPointF(16 * s, 6 * s))
        p.drawLine(QPointF(8.4 * s, 3.8 * s), QPointF(11.6 * s, 3.8 * s))
        p.drawLine(QPointF(10 * s, 3.8 * s), QPointF(10 * s, 6 * s))
        p.drawPath(_path([(5.6, 6.6), (6.4, 16.4), (13.6, 16.4), (14.4, 6.6)], closed=True))
        p.setPen(_pen(color, 1.3 * s))
        p.drawLine(QPointF(8.4 * s, 9.4 * s), QPointF(8.4 * s, 13.8 * s))
        p.drawLine(QPointF(11.6 * s, 9.4 * s), QPointF(11.6 * s, 13.8 * s))
    return _glyph(size, color, draw)


def _circular_arrow(p, s, color, clockwise: bool):
    pen = _pen(color, 1.7 * s)
    p.setPen(pen); p.setBrush(Qt.NoBrush)
    rect = QRectF(4.5 * s, 4.5 * s, 11 * s, 11 * s)
    if clockwise:
        p.drawArc(rect, 90 * 16, -270 * 16)
        head = [(4.6, 7.6), (2.8, 10.6), (6.4, 10.6)]   # at the left, pointing up
    else:
        p.drawArc(rect, -90 * 16, 270 * 16)
        head = [(4.6, 12.4), (2.8, 9.4), (6.4, 9.4)]    # at the left, pointing down
    p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
    poly = [QPointF(x * s, y * s) for x, y in head]
    p.drawPolygon(poly)


def rotate_left_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        _circular_arrow(p, s, color, clockwise=False)
    return _glyph(size, color, draw)


def rotate_right_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        _circular_arrow(p, s, color, clockwise=True)
    return _glyph(size, color, draw)


def reverse_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Two opposing arrows: reverse order."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawLine(QPointF(15 * s, 7 * s), QPointF(5.5 * s, 7 * s))
        p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(5 * s, 7 * s), QPointF(7.8 * s, 4.8 * s), QPointF(7.8 * s, 9.2 * s)])
        p.setPen(_pen(color, 1.7 * s))
        p.drawLine(QPointF(5 * s, 13 * s), QPointF(14.5 * s, 13 * s))
        p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(15 * s, 13 * s), QPointF(12.2 * s, 10.8 * s), QPointF(12.2 * s, 15.2 * s)])
    return _glyph(size, color, draw)


def split_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A page split down the middle."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.5 * s, 4 * s, 13 * s, 12 * s))
        pen = _pen(color, 1.4 * s)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(10 * s, 4.6 * s), QPointF(10 * s, 15.4 * s))
    return _glyph(size, color, draw)


def merge_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Two pages flowing into one."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.2 * s, 4.6 * s, 5 * s, 4.6 * s))
        p.drawRect(QRectF(3.2 * s, 10.8 * s, 5 * s, 4.6 * s))
        p.drawRect(QRectF(12 * s, 6.6 * s, 5 * s, 6.8 * s))
        p.drawLine(QPointF(8.4 * s, 7 * s), QPointF(11.6 * s, 9.4 * s))
        p.drawLine(QPointF(8.4 * s, 13 * s), QPointF(11.6 * s, 10.6 * s))
    return _glyph(size, color, draw)


def marker_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A highlighter: highlight text."""
    def draw(p, s, c):
        p.setPen(_pen(color, 3.4 * s))
        p.drawLine(QPointF(14.6 * s, 4.6 * s), QPointF(7.2 * s, 12.6 * s))
        p.setPen(_pen(color, 2.0 * s))
        p.drawLine(QPointF(7.2 * s, 12.6 * s), QPointF(4.6 * s, 15.8 * s))
    return _glyph(size, color, draw)


def underline_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A U with a line under it: underline."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(5.5, 4.6), (5.5, 10.6)]))
        p.drawArc(QRectF(5.5 * s, 10.2 * s, 9 * s, 5 * s), 180 * 16, 180 * 16)
        p.drawPath(_path([(14.5, 10.6), (14.5, 4.6)]))
        p.drawLine(QPointF(4.4 * s, 17 * s), QPointF(15.6 * s, 17 * s))
    return _glyph(size, color, draw)


def strike_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A line struck through: strikeout."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s))
        p.drawLine(QPointF(4.5 * s, 10 * s), QPointF(15.5 * s, 10 * s))
        p.setPen(_pen(color, 1.9 * s))
        p.drawLine(QPointF(6 * s, 15.6 * s), QPointF(14 * s, 4.4 * s))
    return _glyph(size, color, draw)


def note_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A sticky note."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(4.5, 3.6), (15.5, 3.6), (15.5, 16.4), (4.5, 16.4)], closed=True))
        p.drawPath(_path([(15.5, 3.6), (12, 7.2), (15.5, 7.2)], closed=True))
        p.setPen(_pen(color, 1.3 * s))
        p.drawLine(QPointF(7 * s, 10.6 * s), QPointF(13 * s, 10.6 * s))
        p.drawLine(QPointF(7 * s, 13.4 * s), QPointF(11 * s, 13.4 * s))
    return _glyph(size, color, draw)


def box_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A rectangle outline."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(4.5 * s, 5.5 * s, 11 * s, 9 * s))
    return _glyph(size, color, draw)


def ellipse_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A circle outline."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(4.5 * s, 5.5 * s, 11 * s, 9 * s))
    return _glyph(size, color, draw)


def line_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A diagonal line."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.8 * s))
        p.drawLine(QPointF(4.5 * s, 15.5 * s), QPointF(15.5 * s, 4.5 * s))
    return _glyph(size, color, draw)


def arrow_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A right arrow."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.8 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawLine(QPointF(4 * s, 10 * s), QPointF(14.6 * s, 10 * s))
        p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(15.4 * s, 10 * s), QPointF(11.4 * s, 6.8 * s), QPointF(11.4 * s, 13.2 * s)])
    return _glyph(size, color, draw)


def text_t_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A capital T: type text."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.9 * s))
        p.drawLine(QPointF(4.5 * s, 5 * s), QPointF(15.5 * s, 5 * s))
        p.drawLine(QPointF(10 * s, 5 * s), QPointF(10 * s, 15.5 * s))
    return _glyph(size, color, draw)


def star_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A five-point star: stamp."""
    def draw(p, s, c):
        cx, cy, R, r = 10.0, 10.6, 6.6, 2.75
        pts = []
        for i in range(10):
            ang = math.radians(-90 + i * 36)
            rad = R if i % 2 == 0 else r
            pts.append(QPointF((cx + rad * math.cos(ang)) * s, (cy + rad * math.sin(ang)) * s))
        p.setPen(_pen(color, 1.4 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(pts)
    return _glyph(size, color, draw)


def lock_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A closed padlock."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(7 * s, 3.8 * s, 6 * s, 7 * s), 0 * 16, 180 * 16)
        p.drawRect(QRectF(5 * s, 9.4 * s, 10 * s, 7 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(9.2 * s, 11.6 * s, 1.6 * s, 1.6 * s))
        p.setPen(_pen(color, 1.5 * s))
        p.drawLine(QPointF(10 * s, 13.2 * s), QPointF(10 * s, 14.8 * s))
    return _glyph(size, color, draw)


def unlock_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """An open padlock."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(7 * s, 3.8 * s, 6 * s, 7 * s), 180 * 16, 145 * 16)
        p.drawLine(QPointF(12.7 * s, 7.2 * s), QPointF(15.6 * s, 5.6 * s))
        p.drawRect(QRectF(5 * s, 9.4 * s, 10 * s, 7 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(9.2 * s, 11.6 * s, 1.6 * s, 1.6 * s))
    return _glyph(size, color, draw)


def redact_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A solid black bar: redact."""
    def draw(p, s, c):
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(color)))
        p.drawRect(QRectF(4 * s, 7 * s, 12 * s, 6 * s))
    return _glyph(size, color, draw)


def eraser_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """An eraser block."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(9.6, 4.4), (16, 10.2), (10.4, 15.8), (4, 10.2)], closed=True))
        p.setPen(_pen(color, 1.3 * s))
        p.drawLine(QPointF(6.6 * s, 11.9 * s), QPointF(13.4 * s, 6.6 * s))
    return _glyph(size, color, draw)


def clipboard_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A clipboard: form."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(5 * s, 4.6 * s, 10 * s, 11.8 * s))
        p.drawRect(QRectF(8 * s, 3 * s, 4 * s, 3 * s))
        p.setPen(_pen(color, 1.3 * s))
        p.drawLine(QPointF(7.4 * s, 9.4 * s), QPointF(12.6 * s, 9.4 * s))
        p.drawLine(QPointF(7.4 * s, 12.2 * s), QPointF(12.6 * s, 12.2 * s))
    return _glyph(size, color, draw)


def checkbox_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A ticked box."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(4.5 * s, 4.5 * s, 11 * s, 11 * s))
        p.setPen(_pen(color, 1.9 * s))
        p.drawPath(_path([(7, 10.4), (9.2, 12.8), (13.4, 7.2)]))
    return _glyph(size, color, draw)


def palette_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A painter's palette."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(3.8 * s, 5 * s, 12.4 * s, 10 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        for x, y in ((7.6, 8.2), (12.4, 8.2), (6.8, 11.8)):
            p.drawEllipse(QRectF((x - 0.95) * s, (y - 0.95) * s, 1.9 * s, 1.9 * s))
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(12.6 * s, 11.6 * s, 2.6 * s, 2.2 * s))
    return _glyph(size, color, draw)


def presentation_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A slide on a stand: PowerPoint."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.5 * s, 4 * s, 13 * s, 9 * s))
        p.setPen(_pen(color, 1.5 * s))
        p.drawLine(QPointF(10 * s, 13 * s), QPointF(10 * s, 15.4 * s))
        p.drawLine(QPointF(10 * s, 15.4 * s), QPointF(6.4 * s, 17.4 * s))
        p.drawLine(QPointF(10 * s, 15.4 * s), QPointF(13.6 * s, 17.4 * s))
        p.setPen(_pen(color, 1.3 * s))
        p.drawLine(QPointF(6 * s, 7.2 * s), QPointF(14 * s, 7.2 * s))
    return _glyph(size, color, draw)


def code_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Angle brackets with a slash: HTML."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.8 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(7, 7), (4, 10), (7, 13)]))
        p.drawPath(_path([(13, 7), (16, 10), (13, 13)]))
        p.drawLine(QPointF(11.6 * s, 5.4 * s), QPointF(8.4 * s, 14.6 * s))
    return _glyph(size, color, draw)


def book_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """An open book: EPUB."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(10, 6.2), (4.6, 4.6), (4.6, 14.6), (10, 16.2)], closed=True))
        p.drawPath(_path([(10, 6.2), (15.4, 4.6), (15.4, 14.6), (10, 16.2)], closed=True))
    return _glyph(size, color, draw)


def compress_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Four arrows pressing inward."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(QBrush(QColor(color)))
        for x0, y0, x1, y1 in [(4, 4, 8.2, 8.2), (16, 4, 11.8, 8.2),
                               (4, 16, 8.2, 11.8), (16, 16, 11.8, 11.8)]:
            p.drawLine(QPointF(x0 * s, y0 * s), QPointF(x1 * s, y1 * s))
        p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(8.2 * s, 8.2 * s), QPointF(8.2 * s, 11.2 * s), QPointF(11.2 * s, 8.2 * s)])
        p.drawPolygon([QPointF(11.8 * s, 8.2 * s), QPointF(8.8 * s, 8.2 * s), QPointF(11.8 * s, 11.2 * s)])
        p.drawPolygon([QPointF(8.2 * s, 11.8 * s), QPointF(11.2 * s, 11.8 * s), QPointF(8.2 * s, 8.8 * s)])
        p.drawPolygon([QPointF(11.8 * s, 11.8 * s), QPointF(11.8 * s, 8.8 * s), QPointF(8.8 * s, 11.8 * s)])
    return _glyph(size, color, draw)


def drop_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A water drop: watermark."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(QPointF(10 * s, 3.4 * s))
        path.lineTo(QPointF(14.8 * s, 10.6 * s))
        path.arcTo(QRectF(5 * s, 9.6 * s, 10 * s, 7 * s), 0, 180)
        path.closeSubpath()
        p.drawPath(path)
    return _glyph(size, color, draw)


def hash_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A number sign: page numbers."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.8 * s))
        p.drawLine(QPointF(8.2 * s, 4.4 * s), QPointF(7.4 * s, 15.6 * s))
        p.drawLine(QPointF(12.6 * s, 4.4 * s), QPointF(11.8 * s, 15.6 * s))
        p.drawLine(QPointF(5 * s, 8 * s), QPointF(15 * s, 8 * s))
        p.drawLine(QPointF(5 * s, 12 * s), QPointF(15 * s, 12 * s))
    return _glyph(size, color, draw)


def layers_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Stacked sheets: flatten."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(10, 3.8), (16, 7.2), (10, 10.6), (4, 7.2)], closed=True))
        p.drawPath(_path([(4, 11.4), (10, 14.8), (16, 11.4)]))
        p.drawPath(_path([(4, 14.6), (10, 18.0), (16, 14.6)]))
    return _glyph(size, color, draw)


def scan_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A scan frame over text lines: OCR."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        for pts in [[(4, 7), (4, 4), (7, 4)], [(13, 4), (16, 4), (16, 7)],
                    [(16, 13), (16, 16), (13, 16)], [(7, 16), (4, 16), (4, 13)]]:
            p.drawPath(_path(pts))
        p.setPen(_pen(color, 1.4 * s))
        p.drawLine(QPointF(7 * s, 9.6 * s), QPointF(13 * s, 9.6 * s))
        p.drawLine(QPointF(7 * s, 12.4 * s), QPointF(11 * s, 12.4 * s))
    return _glyph(size, color, draw)


def wrench_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A wrench: repair."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(10.4 * s, 3.4 * s, 6 * s, 6 * s), 40 * 16, 280 * 16)
        p.setPen(_pen(color, 2.6 * s))
        p.drawLine(QPointF(11.4 * s, 8.8 * s), QPointF(4.8 * s, 15.4 * s))
    return _glyph(size, color, draw)


def camera_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A camera: grab a frame."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.4 * s, 7 * s, 13.2 * s, 9 * s))
        p.drawPath(_path([(7, 7), (8, 4.6), (12, 4.6), (13, 7)], closed=True))
        p.drawEllipse(QRectF(7 * s, 9.5 * s, 6 * s, 6 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(14.6 * s, 8.2 * s, 1.4 * s, 1.4 * s))
    return _glyph(size, color, draw)


def film_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A film strip: video."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.4 * s, 4.4 * s, 13.2 * s, 11.2 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        for x in (5.4, 8.6, 11.8):
            p.drawRect(QRectF(x * s, 5.2 * s, 1.3 * s, 1.6 * s))
            p.drawRect(QRectF(x * s, 13.2 * s, 1.3 * s, 1.6 * s))
        p.setPen(_pen(color, 1.3 * s)); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(7.4 * s, 7.4 * s), QPointF(7.4 * s, 12.6 * s))
        p.drawLine(QPointF(12.6 * s, 7.4 * s), QPointF(12.6 * s, 12.6 * s))
    return _glyph(size, color, draw)


def music_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """An eighth note: audio."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(QRectF(5.4 * s, 13.2 * s, 3.6 * s, 2.8 * s))
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(8.9 * s, 14 * s), QPointF(8.9 * s, 4.6 * s))
        p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(8.9 * s, 4.6 * s), QPointF(14.4 * s, 6.8 * s), QPointF(8.9 * s, 9.4 * s)])
    return _glyph(size, color, draw)


def play_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(color)))
        p.drawPolygon([QPointF(7 * s, 4.6 * s), QPointF(15.6 * s, 10 * s), QPointF(7 * s, 15.4 * s)])
    return _glyph(size, color, draw)


def pause_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    def draw(p, s, c):
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(color)))
        p.drawRect(QRectF(6.2 * s, 4.8 * s, 2.8 * s, 10.4 * s))
        p.drawRect(QRectF(11 * s, 4.8 * s, 2.8 * s, 10.4 * s))
    return _glyph(size, color, draw)


def plug_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A power plug: USB token."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(6 * s, 9 * s, 8 * s, 7 * s))
        p.drawLine(QPointF(8 * s, 9 * s), QPointF(8 * s, 4.4 * s))
        p.drawLine(QPointF(12 * s, 9 * s), QPointF(12 * s, 4.4 * s))
        p.drawLine(QPointF(10 * s, 16 * s), QPointF(10 * s, 18 * s))
    return _glyph(size, color, draw)


def broom_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A broom: strip / clean."""
    def draw(p, s, c):
        p.setPen(_pen(color, 2.0 * s))
        p.drawLine(QPointF(14 * s, 3.4 * s), QPointF(9 * s, 9.4 * s))
        p.setPen(_pen(color, 1.5 * s)); p.setBrush(Qt.NoBrush)
        p.drawPath(_path([(9.4, 8.8), (4, 16.6), (13.4, 15.2)], closed=True))
        p.setPen(_pen(color, 1.3 * s))
        p.drawLine(QPointF(6.6 * s, 13.6 * s), QPointF(11.8 * s, 12.6 * s))
    return _glyph(size, color, draw)


def archive_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A storage box: archive."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(3.4 * s, 7 * s, 13.2 * s, 9.4 * s))
        p.drawRect(QRectF(2.8 * s, 4.4 * s, 14.4 * s, 2.6 * s))
        p.setPen(_pen(color, 1.5 * s))
        p.drawLine(QPointF(8.4 * s, 10.4 * s), QPointF(11.6 * s, 10.4 * s))
    return _glyph(size, color, draw)


def cursor_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """A mouse pointer: select."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.2 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawPolygon([QPointF(5 * s, 3.8 * s), QPointF(5 * s, 15.4 * s), QPointF(7.9 * s, 12.6 * s),
                       QPointF(9.9 * s, 17 * s), QPointF(12 * s, 16 * s), QPointF(10 * s, 11.7 * s),
                       QPointF(13.6 * s, 11.7 * s)])
    return _glyph(size, color, draw)


def headphones_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Headphones: audio file."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.7 * s)); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(4 * s, 3.6 * s, 12 * s, 10 * s), 180 * 16, 180 * 16)
        p.drawRect(QRectF(3.4 * s, 11 * s, 3.2 * s, 5.4 * s))
        p.drawRect(QRectF(13.4 * s, 11 * s, 3.2 * s, 5.4 * s))
    return _glyph(size, color, draw)


def flip_v_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Flip vertical: up-down triangles over a line."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawLine(QPointF(3.6 * s, 10 * s), QPointF(16.4 * s, 10 * s))
        p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(10 * s, 3.8 * s), QPointF(6.8 * s, 8.6 * s), QPointF(13.2 * s, 8.6 * s)])
        p.drawPolygon([QPointF(10 * s, 16.2 * s), QPointF(6.8 * s, 11.4 * s), QPointF(13.2 * s, 11.4 * s)])
    return _glyph(size, color, draw)


def flip_h_icon(size: int = 20, color: str = "#A8B2C8") -> QIcon:
    """Flip horizontal: left-right triangles beside a line."""
    def draw(p, s, c):
        p.setPen(_pen(color, 1.6 * s)); p.setBrush(QBrush(QColor(color)))
        p.drawLine(QPointF(10 * s, 3.6 * s), QPointF(10 * s, 16.4 * s))
        p.setPen(Qt.NoPen)
        p.drawPolygon([QPointF(3.8 * s, 10 * s), QPointF(8.6 * s, 6.8 * s), QPointF(8.6 * s, 13.2 * s)])
        p.drawPolygon([QPointF(16.2 * s, 10 * s), QPointF(11.4 * s, 6.8 * s), QPointF(11.4 * s, 13.2 * s)])
    return _glyph(size, color, draw)


ICONS = {
    "folder": folder_icon, "save": save_icon, "printer": printer_icon,
    "text": text_icon, "pen": pen_icon, "search": search_icon,
    "copy": copy_icon, "home": home_icon, "plus": plus_icon, "minus": minus_icon,
    "up": chevron_up_icon, "down": chevron_down_icon, "speaker": speaker_icon,
    "doc": doc_icon, "page_plus": page_plus_icon, "clip": clip_icon,
    "image": image_icon, "scissors": scissors_icon, "trash": trash_icon,
    "rotate_left": rotate_left_icon, "rotate_right": rotate_right_icon,
    "reverse": reverse_icon, "split": split_icon, "merge": merge_icon,
    "marker": marker_icon, "underline": underline_icon, "strike": strike_icon,
    "note": note_icon, "box": box_icon, "ellipse": ellipse_icon,
    "line": line_icon, "arrow": arrow_icon, "text_t": text_t_icon,
    "star": star_icon, "lock": lock_icon, "unlock": unlock_icon,
    "redact": redact_icon, "eraser": eraser_icon, "clipboard": clipboard_icon,
    "checkbox": checkbox_icon, "palette": palette_icon,
    "presentation": presentation_icon, "code": code_icon, "book": book_icon,
    "compress": compress_icon, "drop": drop_icon, "hash": hash_icon,
    "layers": layers_icon, "scan": scan_icon, "wrench": wrench_icon,
    "contrast": opacity_icon, "camera": camera_icon, "film": film_icon,
    "music": music_icon, "play": play_icon, "pause": pause_icon,
    "plug": plug_icon, "broom": broom_icon, "archive": archive_icon,
    "cursor": cursor_icon, "headphones": headphones_icon,
    "flip_v": flip_v_icon, "flip_h": flip_h_icon,
}
