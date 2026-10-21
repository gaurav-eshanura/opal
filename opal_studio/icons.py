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
