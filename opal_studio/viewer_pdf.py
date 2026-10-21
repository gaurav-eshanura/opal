"""
Opal - Floating PDF Studio (Adobe Acrobat Replacement)
Plain English: This is a full document workspace that pins on top of your screen.
View and search PDFs, add highlights, notes, drawings, shapes, text, stamps and
hand-drawn signatures, fill form fields, redact private data, reorder or delete
pages, add watermarks and page numbers, make scans searchable with offline OCR,
lock or unlock documents, compare two documents visually, print, and export to
Word, PowerPoint, EPUB, HTML and images - all locally, no Acrobat required.
"""

import os
import io
import time
import math
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QSize, QTimer, Signal, QThread, QRect
from PySide6.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QPixmap, QImage, QCursor,
                           QKeySequence, QShortcut, QIcon, QPageSize, QFontMetricsF)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QTextEdit, QFileDialog, QLineEdit, QSplitter, QFrame, QMessageBox,
                               QDialog, QComboBox, QListWidget, QListWidgetItem,
                               QTreeWidget, QTreeWidgetItem, QTabWidget, QToolButton, QColorDialog,
                               QInputDialog, QApplication, QSizePolicy, QProgressBar, QCheckBox,
                               QFormLayout)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter

try:
    import fitz
except ImportError:
    fitz = None


# ---------------------------------------------------------------------------
# Shared visuals
# ---------------------------------------------------------------------------

CITRUS = QColor(255, 122, 24)

INK_STYLE = """
    QDialog { background-color: #101625; color: #EDF1FA; }
    QPushButton { background-color: rgba(255,255,255,0.06); color: #EDF1FA; border: 1px solid rgba(255,255,255,0.16);
                  border-radius: 10px; padding: 6px 14px; font-weight: 600; }
    QPushButton:hover { background-color: rgba(255,255,255,0.13); color: #FFFFFF; border-color: rgba(255,255,255,0.30); }
    QPushButton:disabled { background-color: rgba(255,255,255,0.03); color: rgba(237,241,250,0.28); border-color: rgba(255,255,255,0.06); }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: rgba(255,255,255,0.05); color: #EDF1FA;
                  border: 1px solid rgba(255,255,255,0.16); border-radius: 10px; padding: 5px; }
    QLabel { color: #EDF1FA; }
"""


def _tool_btn(text: str, tooltip: str = "", checkable: bool = False, accent: bool = False) -> QToolButton:
    btn = QToolButton()
    btn.setText(text)
    btn.setToolTip(tooltip or text)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    if accent:
        # The lit control: the fire inside the stone.
        btn.setStyleSheet("""
            QToolButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                stop: 0 #8A5CF6, stop: 0.55 #EE4E8A, stop: 1 #FF9A3C);
                color: #FFFFFF; border: none;
                border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 700;
            }
            QToolButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                stop: 0 #9B7BFF, stop: 0.55 #FF6BA0, stop: 1 #FFB35C);
            }
        """)
    else:
        btn.setStyleSheet("""
            QToolButton {
                background-color: rgba(255,255,255,0.06); color: #EDF1FA;
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 10px; padding: 5px 10px; font-size: 11px; font-weight: 600;
            }
            QToolButton:hover {
                background-color: rgba(255,255,255,0.13);
                border-color: rgba(255,255,255,0.30); color: #FFFFFF;
            }
            QToolButton:checked {
                background-color: rgba(108,99,255,0.35);
                border-color: rgba(140,131,255,0.75); color: #FFFFFF;
            }
            QToolButton:disabled {
                background-color: rgba(255,255,255,0.03);
                color: rgba(237,241,250,0.28); border-color: rgba(255,255,255,0.06);
            }
        """)
    return btn


def _range_dialog(parent, title: str, page_count: int) -> Tuple[str, bool]:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setStyleSheet(INK_STYLE)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(f"Enter pages (1-{page_count}). Examples: 1,3,5-8 or 'odd' or 'all':"))
    edit = QLineEdit("1")
    edit.setMinimumWidth(320)
    layout.addWidget(edit)
    row = QHBoxLayout()
    row.addStretch()
    ok = QPushButton("OK")
    cancel = QPushButton("Cancel")
    ok.clicked.connect(dlg.accept)
    cancel.clicked.connect(dlg.reject)
    row.addWidget(ok)
    row.addWidget(cancel)
    layout.addLayout(row)
    if dlg.exec() == QDialog.Accepted:
        return edit.text().strip(), True
    return "", False


# ---------------------------------------------------------------------------
# Signature dialog: draw with the mouse or type a styled signature
# ---------------------------------------------------------------------------

class SignatureDialog(QDialog):
    """Creates a transparent signature PNG by drawing or typing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign Document")
        self.setMinimumSize(480, 340)
        self.setStyleSheet(INK_STYLE)
        self.signature_png: Optional[bytes] = None
        lay = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid rgba(255,255,255,0.16); } "
                                "QTabBar::tab { background:rgba(255,255,255,0.05); color:#727E96; padding:6px 14px; } "
                                "QTabBar::tab:selected { background:#6C63FF; color:#fff; }")

        draw_tab = QWidget()
        d_lay = QVBoxLayout(draw_tab)
        self.canvas_img = QImage(440, 180, QImage.Format_ARGB32)
        self.canvas_img.fill(Qt.transparent)
        self.canvas_lbl = QLabel()
        self.canvas_lbl.setFixedSize(440, 180)
        self.canvas_lbl.setStyleSheet("background: #FFFFFF; border-radius: 10px;")
        self.canvas_lbl.setMouseTracking(True)
        self._drawing = False
        self._last_pt = None
        d_lay.addWidget(self.canvas_lbl)
        row = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_canvas)
        row.addWidget(clear_btn)
        row.addStretch()
        d_lay.addLayout(row)
        self.tabs.addTab(draw_tab, "Draw")

        type_tab = QWidget()
        t_lay = QFormLayout(type_tab)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Type your name")
        self.font_combo = QComboBox()
        for fam in ("Segoe Script", "Lucida Handwriting", "Brush Script MT", "Ink Free", "Segoe UI"):
            self.font_combo.addItem(fam)
        self.font_combo.setCurrentText("Segoe Script")
        self.size_spin = QComboBox()
        for s in ("28", "36", "44", "56"):
            self.size_spin.addItem(s)
        self.size_spin.setCurrentText("36")
        t_lay.addRow("Name", self.name_edit)
        t_lay.addRow("Font", self.font_combo)
        t_lay.addRow("Size", self.size_spin)
        initials_btn = QPushButton("Use initials instead")
        initials_btn.setToolTip("Signs with 1-3 letters, the way initials are usually signed")
        initials_btn.clicked.connect(self._use_initials)
        t_lay.addRow("", initials_btn)
        self.tabs.addTab(type_tab, "Type")

        # --- image tab: use a signature picture (the usual e-signature flow) ---
        image_tab = QWidget()
        i_lay = QVBoxLayout(image_tab)
        self.image_preview = QLabel("No signature image loaded")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(150)
        self.image_preview.setStyleSheet("background:#FFFFFF; border-radius:6px; color:#888;")
        i_lay.addWidget(self.image_preview)
        row_img = QHBoxLayout()
        pick_btn = QPushButton("Choose signature image…")
        pick_btn.clicked.connect(self._pick_signature_image)
        row_img.addWidget(pick_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_signature_image)
        row_img.addWidget(clear_btn)
        i_lay.addLayout(row_img)
        self.signature_image_path = None
        self.tabs.addTab(image_tab, "Image")

        lay.addWidget(self.tabs)

        row2 = QHBoxLayout()
        row2.addStretch()
        apply_btn = QPushButton("Apply Signature")
        apply_btn.setStyleSheet("background-color: #6C63FF;")
        apply_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        row2.addWidget(apply_btn)
        row2.addWidget(cancel_btn)
        lay.addLayout(row2)

    def mousePressEvent(self, event):
        if self.canvas_lbl.underMouse() and event.button() == Qt.LeftButton:
            self._drawing = True
            self._last_pt = self.canvas_lbl.mapFrom(self, event.position().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drawing and self._last_pt is not None:
            pt = self.canvas_lbl.mapFrom(self, event.position().toPoint())
            p = QPainter(self.canvas_img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(Qt.black, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(self._last_pt, pt)
            p.end()
            self._last_pt = pt
            self.canvas_lbl.setPixmap(QPixmap.fromImage(self.canvas_img))
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drawing = False
            self._last_pt = None
            event.accept()

    def _clear_canvas(self):
        self.canvas_img.fill(Qt.transparent)
        self.canvas_lbl.setPixmap(QPixmap.fromImage(self.canvas_img))

    def _use_initials(self):
        """Fills the name field with 1-3 initials."""
        current = self.name_edit.text().strip()
        if current:
            parts = [p for p in current.split() if p]
            initials = "".join(p[0].upper() for p in parts[:3])
            self.name_edit.setText(initials)
        else:
            self.name_edit.setText("RS")
        self.tabs.setCurrentIndex(1)

    def _pick_signature_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose your signature image", "",
            "Signature images (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)")
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Signature Image", "That file could not be read as an image.")
            return
        self.signature_image_path = path
        self.image_preview.setPixmap(image.scaled(400, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image_preview.setText("")

    def _clear_signature_image(self):
        self.signature_image_path = None
        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText("No signature image loaded")

    def _apply(self):
        if self.tabs.currentIndex() == 2:
            if not self.signature_image_path:
                QMessageBox.information(self, "Signature Image",
                                        "Please choose a signature image first.")
                return
            image = QImage(self.signature_image_path)
            if image.isNull():
                QMessageBox.warning(self, "Signature Image", "That file could not be read.")
                return
            self.signature_png = _qimage_to_png(image)
        elif self.tabs.currentIndex() == 1:
            png = self._typed_signature()
            if png is None:
                QMessageBox.information(self, "Name Required", "Please type a name for the signature.")
                return
            self.signature_png = png
        else:
            rect = self._content_rect()
            if rect.isNull():
                QMessageBox.information(self, "Signature Needed", "Please draw a signature first.")
                return
            self.signature_png = _qimage_to_png(self.canvas_img.copy(rect))
        self.accept()

    def _content_rect(self) -> QRect:
        img = self.canvas_img
        w, h = img.width(), img.height()
        min_x, min_y, max_x, max_y = w, h, -1, -1
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                if QColor.fromRgba(img.pixel(x, y)).alpha() > 8:
                    min_x, min_y = min(min_x, x), min(min_y, y)
                    max_x, max_y = max(max_x, x), max(max_y, y)
        if max_x < 0:
            return QRect()
        return QRect(min_x, min_y, max_x - min_x + 3, max_y - min_y + 3)

    def _typed_signature(self) -> Optional[bytes]:
        name = self.name_edit.text().strip()
        if not name:
            return None
        family = self.font_combo.currentText()
        size = int(self.size_spin.currentText())
        font = QFont(family, int(size * 0.6))
        font.setStyleStrategy(QFont.PreferQuality)
        fm = QFontMetricsF(font)
        img = QImage(max(20, int(fm.horizontalAdvance(name)) + 40), max(20, int(size * 1.5)),
                     QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(font)
        p.setPen(QPen(Qt.black))
        p.drawText(img.rect(), Qt.AlignCenter, name)
        p.end()
        return _qimage_to_png(img)


# ---------------------------------------------------------------------------
# Page canvas with overlays and tool interaction
# ---------------------------------------------------------------------------

class PdfPageView(QWidget):
    """Renders one PDF page plus live overlays (search, selection, tool preview)."""

    def __init__(self, studio, page_index: int, doc=None, parent=None):
        super().__init__(parent)
        self.studio = studio
        self.page_index = page_index
        self.doc = doc if doc is not None else studio.doc
        self.read_only = doc is not None
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self._press_pos: Optional[QPointF] = None
        self._current_pos: Optional[QPointF] = None
        self._draw_points: List[QPointF] = []

    # -- geometry --
    def pdf_rect(self) -> "fitz.Rect":
        return self.doc[self.page_index].rect

    def scale(self) -> float:
        return self.studio.zoom

    def to_pdf(self, point: QPointF) -> "fitz.Point":
        s = self.scale()
        return fitz.Point(point.x() / s, point.y() / s)

    def sizeHint(self) -> QSize:
        r = self.pdf_rect()
        return QSize(int(r.width * self.scale()) + 2, int(r.height * self.scale()) + 2)

    # -- painting --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        size = self.sizeHint()
        page_rect = QRectF(0, 0, size.width(), size.height())

        # The sheet of paper, floating on the field. A soft, wide shadow so it
        # reads as a physical page rather than a rectangle.
        for i in range(12, 0, -1):
            spread = i * 1.5
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 4 + (12 - i) * 2)))
            painter.drawRoundedRect(page_rect.adjusted(-spread, -spread + 4,
                                                       spread, spread + 8), 4, 4)
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(page_rect)

        pix = self.studio.page_pixmap(self.page_index, self.doc)
        if pix is not None:
            painter.drawPixmap(0, 0, pix)

        s = self.scale()

        # search highlights (main document only)
        if not self.read_only:
            for r in self.studio.search_rects_for(self.page_index):
                painter.setBrush(QBrush(QColor(255, 220, 40, 120)))
                painter.setPen(QPen(QColor(255, 170, 0, 200), 1))
                painter.drawRect(QRectF(r.x0 * s, r.y0 * s, (r.x1 - r.x0) * s, (r.y1 - r.y0) * s))
            active = self.studio.active_search_rect()
            if active and active[0] == self.page_index:
                r = active[1]
                painter.setBrush(QBrush(QColor(255, 122, 24, 150)))
                painter.setPen(QPen(Qt.white, 1.5))
                painter.drawRect(QRectF(r.x0 * s, r.y0 * s, (r.x1 - r.x0) * s, (r.y1 - r.y0) * s))

        # form field outlines (main document only)
        if not self.read_only and self.studio.show_form_fields:
            try:
                for w in self.doc[self.page_index].widgets() or []:
                    rr = w.rect
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor(0, 140, 255, 220), 1.2, Qt.DashLine))
                    painter.drawRect(QRectF(rr.x0 * s, rr.y0 * s, (rr.x1 - rr.x0) * s, (rr.y1 - rr.y0) * s))
            except Exception:
                pass

        if not self.read_only:
            self._paint_tool_preview(painter, s)

    def _paint_tool_preview(self, painter: QPainter, s: float):
        tool = self.studio.active_tool
        if self._press_pos is not None and self._current_pos is not None:
            preview_color = self.studio.tool_color
            painter.setPen(QPen(preview_color, self.studio.tool_width, Qt.SolidLine,
                                Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            start, end = self._press_pos, self._current_pos
            if tool in ("rect", "highlight", "underline", "strikeout", "redact"):
                r = QRectF(start, end).normalized()
                painter.drawRect(r)
            elif tool == "ellipse":
                r = QRectF(start, end).normalized()
                painter.drawEllipse(r)
            elif tool == "line":
                painter.drawLine(start, end)
            elif tool == "arrow":
                self._draw_arrow(painter, start, end)
            elif tool == "draw" and len(self._draw_points) > 1:
                for i in range(len(self._draw_points) - 1):
                    painter.drawLine(self._draw_points[i], self._draw_points[i + 1])

        # selection overlay
        if self.studio.selection_page == self.page_index and self.studio.selection_rect is not None:
            painter.setBrush(QBrush(QColor(120, 180, 255, 60)))
            painter.setPen(QPen(QColor(120, 180, 255, 200), 1))
            painter.drawRect(self.studio.selection_rect)

        # pending signature ghost follows cursor
        if tool == "sign" and self.studio.pending_signature and self._current_pos is not None:
            painter.setBrush(QBrush(QColor(255, 122, 24, 40)))
            painter.setPen(QPen(CITRUS, 1, Qt.DashLine))
            painter.drawRoundedRect(self._current_pos.x() - 60, self._current_pos.y() - 20,
                                    120, 40, 6, 6)

    def _draw_arrow(self, painter: QPainter, a: QPointF, b: QPointF):
        painter.drawLine(a, b)
        angle = math.atan2(b.y() - a.y(), b.x() - a.x())
        head = 12.0
        for delta in (2.6, -2.6):
            painter.drawLine(b, QPointF(b.x() - head * math.cos(angle + delta),
                                        b.y() - head * math.sin(angle + delta)))

    # -- mouse tools --
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.read_only:
            return
        pos = event.position()
        self._press_pos = pos
        self._current_pos = pos
        self._draw_points = [pos]
        tool = self.studio.active_tool
        s = self.studio

        if tool == "select":
            s.selection_page = self.page_index
            s.selection_rect = QRectF(pos, pos)
            self.update()
            return

        if tool == "sign" and s.pending_signature:
            s.place_signature(self.page_index, self.to_pdf(pos))
            return

        if tool == "dsc":
            s.place_dsc_signature(self.page_index, self.to_pdf(pos))
            return

        if tool == "eraser":
            s.erase_annotation_at(self.page_index, self.to_pdf(pos))
            return

        if tool == "form":
            widget = s.widget_at(self.page_index, self.to_pdf(pos))
            if widget is not None:
                s.edit_widget(widget)
            return

        if tool in ("form_build", "form_check"):
            s.add_form_field(self.page_index, self.to_pdf(pos), tool)
            return

        if tool == "note":
            try:
                page = self.doc[self.page_index]
                annot = page.add_text_annot(self.to_pdf(pos), "Note")
                annot.set_info(title="Opal", content="Note added by Opal")
                annot.set_colors(stroke=(1.0, 0.48, 0.09))
                annot.update()
                s.mark_dirty()
                s.refresh_page(self.page_index)
                s.refresh_comments()
            except Exception as e:
                QMessageBox.warning(self, "Note Failed", str(e))
            return

        if tool == "text":
            text, ok = QInputDialog.getText(self, "Insert Text", "Enter text to place on the page:")
            if ok and text.strip():
                try:
                    page = self.doc[self.page_index]
                    pt = self.to_pdf(pos)
                    page.insert_text((pt.x, pt.y), text.strip(), fontname="helv",
                                     fontsize=s.tool_width + 8,
                                     color=self._rgb(s.tool_color))
                    s.mark_dirty()
                    s.refresh_page(self.page_index)
                except Exception as e:
                    QMessageBox.warning(self, "Insert Failed", str(e))
            return

        if tool == "stamp":
            s.place_stamp(self.page_index, self.to_pdf(pos))
            return

        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._current_pos = pos
        tool = self.studio.active_tool
        if tool == "select" and self._press_pos is not None and (event.buttons() & Qt.LeftButton):
            self.studio.selection_rect = QRectF(self._press_pos, pos).normalized()
            self.update()
            return
        if tool == "draw" and self._press_pos is not None and (event.buttons() & Qt.LeftButton):
            if len(self._draw_points) < 2000:
                self._draw_points.append(pos)
        if self._press_pos is not None and tool in ("rect", "ellipse", "line", "arrow",
                                                    "highlight", "underline", "strikeout",
                                                    "redact", "draw"):
            self.update()
        elif tool == "sign" and self.studio.pending_signature:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._press_pos is None or self.read_only:
            return
        tool = self.studio.active_tool
        start, end = self._press_pos, self._current_pos or self._press_pos
        self._press_pos = None
        self._current_pos = None
        s = self.studio

        if tool == "select":
            rect = QRectF(start, end).normalized()
            s.selection_rect = rect
            text = s.copy_text_in_rect(self.page_index, rect)
            if text:
                QApplication.clipboard().setText(text)
                s.status.setText(f"Copied {len(text)} characters to the clipboard.")
            else:
                s.status.setText("No text in that area.")
            self.update()
            return

        if tool == "draw":
            if len(self._draw_points) > 1:
                try:
                    points = [self.to_pdf(p) for p in self._draw_points]
                    annot = self.doc[self.page_index].add_ink_annot(points)
                    annot.set_colors(stroke=self._rgb(s.tool_color))
                    annot.set_opacity(0.9)
                    annot.update()
                    s.mark_dirty()
                    s.refresh_page(self.page_index)
                    s.refresh_comments()
                except Exception as e:
                    QMessageBox.warning(self, "Draw Failed", str(e))
            self._draw_points = []
            self.update()
            return

        if tool in ("rect", "ellipse", "line", "arrow", "highlight", "underline",
                    "strikeout", "redact"):
            if abs(end.x() - start.x()) < 4 or abs(end.y() - start.y()) < 4:
                self.update()
                return
            try:
                page = self.doc[self.page_index]
                sc = self.scale()
                pdf_rect = fitz.Rect(start.x() / sc, start.y() / sc,
                                     end.x() / sc, end.y() / sc)
                stroke = self._rgb(s.tool_color)
                if tool == "highlight":
                    annot = page.add_highlight_annot(pdf_rect)
                    annot.set_colors(stroke=stroke)
                    annot.set_opacity(0.45)
                    annot.update()
                elif tool == "underline":
                    annot = page.add_underline_annot(pdf_rect)
                    annot.set_colors(stroke=stroke)
                    annot.update()
                elif tool == "strikeout":
                    annot = page.add_strikeout_annot(pdf_rect)
                    annot.set_colors(stroke=stroke)
                    annot.update()
                elif tool == "redact":
                    page.add_redact_annot(pdf_rect)
                    try:
                        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
                    except Exception:
                        page.apply_redactions()
                elif tool == "rect":
                    annot = page.add_rect_annot(pdf_rect)
                    annot.set_colors(stroke=stroke)
                    annot.update()
                elif tool == "ellipse":
                    annot = page.add_circle_annot(pdf_rect)
                    annot.set_colors(stroke=stroke)
                    annot.update()
                elif tool == "line":
                    annot = page.add_line_annot(fitz.Point(start.x() / sc, start.y() / sc),
                                                fitz.Point(end.x() / sc, end.y() / sc))
                    annot.set_colors(stroke=stroke)
                    annot.update()
                elif tool == "arrow":
                    shape = page.new_shape()
                    p0 = fitz.Point(start.x() / sc, start.y() / sc)
                    p1 = fitz.Point(end.x() / sc, end.y() / sc)
                    shape.draw_line(p0, p1)
                    angle = math.atan2(p1.y - p0.y, p1.x - p0.x)
                    shape.draw_line(p1, fitz.Point(p1.x - 12 * math.cos(angle + 2.6),
                                                   p1.y - 12 * math.sin(angle + 2.6)))
                    shape.draw_line(p1, fitz.Point(p1.x - 12 * math.cos(angle - 2.6),
                                                   p1.y - 12 * math.sin(angle - 2.6)))
                    shape.finish(color=stroke, width=1.5)
                    shape.commit()
                s.mark_dirty()
                s.refresh_page(self.page_index)
                s.refresh_comments()
            except Exception as e:
                QMessageBox.warning(self, "Annotation Failed", str(e))
            self.update()

    @staticmethod
    def _rgb(color: QColor) -> Tuple[float, float, float]:
        return (color.red() / 255.0, color.green() / 255.0, color.blue() / 255.0)


# ---------------------------------------------------------------------------
# Background worker for heavy PDF operations
# ---------------------------------------------------------------------------

class StudioWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(bool, str, str)

    def __init__(self, kind: str, src: str, options: Dict):
        super().__init__()
        self.kind = kind
        self.src = src
        self.options = options

    def run(self):
        try:
            from opal_studio import pdf_tools as pt
            from opal_studio.engine import OpalEngine

            def cb(done, total):
                self.progress.emit(done, total, self.kind)

            if self.kind == "ocr":
                out = pt.ocr_pdf(self.src, progress=cb)
                msg = "OCR complete - the document is now searchable"
            elif self.kind == "pptx":
                out = pt.export_pptx(self.src, self._dest(".pptx"),
                                     dpi=int(self.options.get("dpi", 110)), progress=cb)
                msg = "PowerPoint exported"
            elif self.kind == "watermark":
                out = pt.add_watermark(self.src, self.options.get("text", "CONFIDENTIAL"),
                                       opacity=float(self.options.get("opacity", 0.3)))
                msg = "Watermark applied"
            elif self.kind == "pagenum":
                out = pt.add_page_numbers(self.src, start=int(self.options.get("start", 1)),
                                          fmt=self.options.get("format", "{n}"))
                msg = "Page numbers applied"
            elif self.kind == "docx":
                res = OpalEngine.execute_single(self.src, "docx")
                if not res.success:
                    self.done.emit(False, res.message, "")
                    return
                out, msg = res.output_path, "Word export complete"
            else:
                self.done.emit(False, f"Unknown worker '{self.kind}'", "")
                return
            self.done.emit(True, msg, str(out))
        except Exception as e:
            self.done.emit(False, str(e), "")

    def _dest(self, ext: str) -> str:
        p = Path(self.src)
        candidate = p.with_name(f"{p.stem}{ext}")
        counter = 1
        while candidate.exists():
            candidate = p.with_name(f"{p.stem} ({counter}){ext}")
            counter += 1
        return str(candidate)


# ---------------------------------------------------------------------------
# The PDF Studio
# ---------------------------------------------------------------------------

class PdfStudio(QWidget):
    """Complete in-window PDF workspace: view, annotate, organize, protect, convert."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        from opal_studio.theme import apply_field
        apply_field(self)
        self.file_path = str(Path(file_path).resolve())
        self.doc = None
        self.zoom = 1.25
        self.active_tool = "select"
        self.tool_color = QColor(255, 122, 24)
        self.tool_width = 2
        self.dirty = False
        self.show_form_fields = True
        self.pending_signature: Optional[bytes] = None
        self.dsc_context: Optional[dict] = None
        self.auto_save = True
        self._autosave_timer = None
        self.search_matches: List[Tuple[int, "fitz.Rect"]] = []
        self.active_match = -1
        self.selection_rect: Optional[QRectF] = None
        self.selection_page = -1
        self.compare_doc = None
        self.views: List[PdfPageView] = []
        self._pix_cache: Dict[Tuple[int, int], QPixmap] = {}
        self._pix_refs: Dict[Tuple[int, int], object] = {}
        self._thumb_pix: Dict[int, QPixmap] = {}
        self.worker = None
        self.current_page = 0

        self._build_ui()
        self._load_document()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        root.addLayout(self._file_toolbar())
        root.addLayout(self._organize_toolbar())
        root.addLayout(self._annotate_toolbar())
        root.addLayout(self._convert_toolbar())
        root.addWidget(self._search_bar())

        splitter = QSplitter(Qt.Horizontal)

        self.thumb_list = QListWidget()
        self.thumb_list.setViewMode(QListWidget.IconMode)
        self.thumb_list.setIconSize(QSize(86, 122))
        self.thumb_list.setSpacing(6)
        self.thumb_list.setFixedWidth(118)
        self.thumb_list.setStyleSheet("""
            QListWidget { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; }
            QListWidget::item { border-radius: 4px; padding: 2px; }
            QListWidget::item:selected { background: rgba(255,122,24,0.25); }
        """)
        self.thumb_list.itemClicked.connect(self._thumb_clicked)
        self.thumb_list.setDragDropMode(QListWidget.InternalMove)
        self.thumb_list.model().rowsMoved.connect(self._thumbs_reordered)
        splitter.addWidget(self.thumb_list)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        self.center_split = QSplitter(Qt.Horizontal)
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setStyleSheet(
            "QScrollArea { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; }")
        self.page_container = QWidget()
        self.page_layout = QVBoxLayout(self.page_container)
        self.page_layout.setSpacing(10)
        self.page_layout.setContentsMargins(12, 12, 12, 12)
        self.page_layout.setAlignment(Qt.AlignHCenter)
        self.page_scroll.setWidget(self.page_container)
        self.page_scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.center_split.addWidget(self.page_scroll)
        center_lay.addWidget(self.center_split)
        splitter.addWidget(center)

        right = QTabWidget()
        right.setStyleSheet("QTabWidget::pane { border: 1px solid rgba(255,255,255,0.10); } "
                            "QTabBar::tab { background:rgba(255,255,255,0.05); color:#727E96; padding:5px 10px; } "
                            "QTabBar::tab:selected { color:#8A83FF; }")
        right.addTab(self._outline_tab(), "Outline")
        right.addTab(self._comments_tab(), "Comments")
        right.addTab(self._inspector_tab(), "Inspector")
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([118, 800, 300])

        root.addWidget(splitter, 1)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        root.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #727E96; font-size: 10px; padding: 2px 6px;")
        root.addWidget(self.status)

    def _file_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        for text, tip, slot in [
            ("📂 Open", "Open another PDF in a new tab", self._open_external),
            ("💾 Save", "Save changes (Ctrl+S)", self._save_document),
            ("🖨️ Print", "Print document (Ctrl+P)", self._print_document),
            ("📋 Text", "Copy all text to the clipboard", self._copy_all_text),
            ("📁 Folder", "Reveal file in Explorer", self._reveal_file),
            ("🗕 Compare", "Open a second document side-by-side", self._open_compare),
            ("✍️ Sign", "Draw or type a signature", self.open_signature_pad),
            ("🔏 Sign with DSC", "Apply a real digital signature certificate (.pfx/.p12)",
             self._open_dsc),
        ]:
            btn = _tool_btn(text, tip)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch()
        zoom_out = _tool_btn("－", "Zoom out")
        zoom_out.clicked.connect(lambda: self.set_zoom(self.zoom - 0.25))
        self.zoom_lbl = QLabel("125%")
        self.zoom_lbl.setStyleSheet("color: #EDF1FA; font-size: 11px;")
        zoom_in = _tool_btn("＋", "Zoom in")
        zoom_in.clicked.connect(lambda: self.set_zoom(self.zoom + 0.25))
        fit_w = _tool_btn("Fit Width", "Fit page width to the window")
        fit_w.clicked.connect(self._fit_width)
        for w in (zoom_out, self.zoom_lbl, zoom_in, fit_w):
            row.addWidget(w)
        return row

    def _organize_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        for text, tip, slot in [
            ("➕ Blank Page", "Insert a blank page", self._insert_blank),
            ("📎 From PDF", "Insert pages from another PDF", self._insert_from_pdf),
            ("🖼️ From Images", "Insert images as pages", self._insert_images),
            ("✂️ Extract", "Extract a page range to a new PDF", self._extract_range),
            ("🗑️ Delete", "Delete the current page", self._delete_page),
            ("↺ Rotate L", "Rotate current page left", lambda: self._rotate_page(-90)),
            ("↻ Rotate R", "Rotate current page right", lambda: self._rotate_page(90)),
            ("🔃 Reverse", "Reverse all pages", self._reverse_pages),
            ("📑 Split", "Split into one PDF per page", self._split_pages),
            ("🧩 Merge", "Merge another PDF into this one", self._merge_pdfs),
        ]:
            btn = _tool_btn(text, tip)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch()
        return row

    def _annotate_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.tool_buttons: Dict[str, QToolButton] = {}
        for tool, text, tip in [
            ("select", "⤣ Select", "Pan the document"),
            ("highlight", "🖍 Highlight", "Drag over text to highlight"),
            ("underline", "U̲ Underline", "Drag over text to underline"),
            ("strikeout", "S̶ Strike", "Drag over text to strike out"),
            ("note", "📝 Note", "Click to attach a note"),
            ("draw", "✏️ Draw", "Freehand ink drawing"),
            ("rect", "▭ Rectangle", "Drag a rectangle"),
            ("ellipse", "◯ Ellipse", "Drag an ellipse"),
            ("line", "╱ Line", "Drag a line"),
            ("arrow", "→ Arrow", "Drag an arrow"),
            ("text", "🔤 Text", "Click to type on the page"),
            ("stamp", "★ Stamp", "Click to stamp star / date / approved"),
            ("sign", "✍️ Sign", "Click the page to place your signature"),
            ("dsc", "🔏 DSC", "Sign with a digital signature certificate"),
            ("redact", "⬛ Redact", "Drag to permanently remove content"),
            ("eraser", "🧽 Eraser", "Click an annotation to delete it"),
            ("form", "📋 Fill Form", "Click form fields to fill them"),
            ("form_build", "➕ Text Field", "Add a fillable text field to the page"),
            ("form_check", "☑ Checkbox", "Add a fillable tick box to the page"),
        ]:
            btn = _tool_btn(text, tip, checkable=True)
            btn.clicked.connect(lambda checked=False, t=tool: self.set_tool(t))
            self.tool_buttons[tool] = btn
            row.addWidget(btn)
        self.color_btn = _tool_btn("🎨 Color", "Annotation color")
        self.color_btn.clicked.connect(self._pick_color)
        self.width_combo = QComboBox()
        self.width_combo.addItems(["1", "2", "3", "5", "8"])
        self.width_combo.setCurrentText("2")
        self.width_combo.setToolTip("Brush / border width")
        self.width_combo.setFixedWidth(48)
        self.width_combo.currentTextChanged.connect(
            lambda t: setattr(self, "tool_width", int(t)))
        fields_btn = _tool_btn("◻️ Fields", "Highlight form fields")
        fields_btn.setCheckable(True)
        fields_btn.setChecked(True)
        fields_btn.clicked.connect(lambda: setattr(self, "show_form_fields",
                                                    not self.show_form_fields) or self._repaint_all())
        row.addWidget(self.color_btn)
        row.addWidget(self.width_combo)
        row.addWidget(fields_btn)
        row.addStretch()
        return row

    def _convert_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        for text, tip, slot in [
            ("📝 Word", "Export to an editable Word document", lambda: self._run_worker("docx")),
            ("📽️ PowerPoint", "Export to PowerPoint slides", lambda: self._run_worker("pptx")),
            ("🖼️ PNG Pages", "Export every page as PNG", lambda: self._export_images("png")),
            ("🏞️ JPG Pages", "Export every page as JPG", lambda: self._export_images("jpg")),
            ("📄 HTML", "Export as HTML", self._export_html),
            ("📚 EPUB", "Export as EPUB e-book", self._export_epub),
            ("🗜️ Compress", "Shrink file size", self._compress_document),
            ("💧 Watermark", "Add a diagonal watermark", self._watermark_dialog),
            ("🔢 Page #", "Add page numbers", self._pagenum_dialog),
            ("📌 Flatten", "Flatten annotations permanently", self._flatten_document),
            ("🔤 OCR", "Make scans searchable (offline AI)", lambda: self._run_worker("ocr")),
            ("🔒 Protect", "Add password protection", self._protect_dialog),
            ("🔓 Unlock", "Remove password protection", self._unlock_document),
            ("🛠 Repair", "Rebuild a damaged PDF", self._repair_document),
            ("✂ Trim", "Cut away white scanner margins", self._trim_margins),
            ("◐ B&W", "Black and white photocopy", self._grayscale_document),
            ("📝 Summary", "Key points, extracted offline", self._summarize_document),
            ("📎 Attachments", "Extract embedded files", self._extract_attachments),
        ]:
            btn = _tool_btn(text, tip)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch()
        return row

    def _search_bar(self) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Find in document (Ctrl+F)...")
        self.search_input.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,0.05); color: #fff; border: 1px solid rgba(255,255,255,0.16); "
            "border-radius: 6px; padding: 5px 9px; }")
        self.search_input.textChanged.connect(self._run_search)
        self.search_input.returnPressed.connect(self._search_next)
        prev = _tool_btn("▲", "Previous match")
        prev.clicked.connect(self._search_prev)
        nxt = _tool_btn("▼", "Next match")
        nxt.clicked.connect(self._search_next)
        self.search_count = QLabel("")
        self.search_count.setStyleSheet("color: #727E96; font-size: 10px;")
        read_aloud = _tool_btn("🔊 Read", "Read the current page aloud (offline)")
        read_aloud.clicked.connect(self._read_aloud)
        lay.addWidget(self.search_input, 1)
        lay.addWidget(prev)
        lay.addWidget(nxt)
        lay.addWidget(self.search_count)
        lay.addWidget(read_aloud)
        return bar

    def _outline_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.setStyleSheet(
            "QTreeWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; border: 1px solid rgba(255,255,255,0.10); }"
            "QTreeWidget::item:selected { background:#6C63FF; color:#fff; }")
        self.outline_tree.itemClicked.connect(self._outline_clicked)
        lay.addWidget(self.outline_tree)
        b = _tool_btn("＋ Bookmark this page", "Add a bookmark for the current page")
        b.clicked.connect(self._add_bookmark)
        lay.addWidget(b)
        return w

    def _comments_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.comment_list = QListWidget()
        self.comment_list.setStyleSheet(
            "QListWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; border:1px solid rgba(255,255,255,0.10); }")
        lay.addWidget(self.comment_list)
        b = _tool_btn("🗑 Delete selected", "Delete the selected annotation")
        b.clicked.connect(self._delete_selected_comment)
        lay.addWidget(b)
        return w

    def _inspector_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.inspector = QTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setStyleSheet(
            "QTextEdit { background:rgba(255,255,255,0.05); color:#EDF1FA; border:1px solid rgba(255,255,255,0.10); "
            "font-family: Consolas, monospace; font-size: 10px; }")
        lay.addWidget(self.inspector)
        return w

    # ------------------------------------------------------------------
    # Document loading
    # ------------------------------------------------------------------

    def _load_document(self):
        try:
            self.doc = _open_with_password(self.file_path, self)
        except Exception as e:
            QMessageBox.critical(self, "Cannot Open PDF", str(e))
            return
        if self.doc is None:
            return
        self._build_pages()
        self._build_thumbs()
        self._build_outline()
        self.refresh_comments()
        self._update_inspector()
        self._update_status()
        QTimer.singleShot(50, self._render_visible)

    def _build_pages(self):
        while self.page_layout.count():
            item = self.page_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.views = []
        self._pix_cache.clear()
        self._pix_refs.clear()
        for i in range(len(self.doc)):
            view = PdfPageView(self, i)
            view.setFixedSize(view.sizeHint())
            self.page_layout.addWidget(view)
            self.views.append(view)
        self.set_tool(self.active_tool)

    def _build_thumbs(self):
        self.thumb_list.clear()
        self._thumb_pix.clear()
        for i in range(min(len(self.doc), 400)):
            try:
                pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(0.16, 0.16), alpha=False)
                qimg = QImage(pix.samples, pix.width, pix.height, pix.stride,
                              QImage.Format_RGB888).copy()
                thumb = QPixmap.fromImage(qimg).scaledToWidth(86, Qt.SmoothTransformation)
                self._thumb_pix[i] = thumb
                item = QListWidgetItem(QIcon(thumb), f"{i + 1}")
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, i)
                self.thumb_list.addItem(item)
            except Exception:
                continue

    def _build_outline(self):
        self.outline_tree.clear()
        try:
            toc = self.doc.get_toc(simple=True) or []
        except Exception:
            toc = []
        for level, title, page in toc:
            item = QTreeWidgetItem([title, str(page)])
            item.setData(0, Qt.UserRole, max(0, page - 1))
            self.outline_tree.addTopLevelItem(item)

    def refresh_comments(self):
        self.comment_list.clear()
        if not self.doc:
            return
        for i, page in enumerate(self.doc):
            try:
                for annot in page.annots() or []:
                    kind = annot.type[1] if annot.type else "annot"
                    text = (annot.info.get("content") or "").strip()
                    label = f"p{i + 1}: {kind}" + (f" - {text[:60]}" if text else "")
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, (i, annot.rect))
                    self.comment_list.addItem(item)
            except Exception:
                continue

    def _update_inspector(self):
        if not self.doc:
            return
        try:
            meta = self.doc.metadata or {}
            lines = ["DOCUMENT PROPERTIES", ""]
            for key in ("title", "author", "subject", "keywords", "creator", "producer",
                        "creationDate", "modDate"):
                if meta.get(key):
                    lines.append(f"{key.capitalize()}: {meta[key]}")
            lines.append("")
            lines.append(f"Pages: {len(self.doc)}")
            lines.append(f"Encrypted: {self.doc.is_encrypted}")
            page = self.doc[0]
            lines.append(f"Page size: {page.rect.width:.0f} x {page.rect.height:.0f} pt")
            fonts = page.get_fonts()
            lines.append(f"Fonts on page 1: {len(fonts)}")
            for f in fonts[:8]:
                lines.append(f"  - {f[3]}")
            lines.append(f"Images on page 1: {len(page.get_images(full=True))}")
            try:
                embeds = self.doc.embfile_names()
                lines.append(f"Attachments: {len(embeds)}")
                for name in embeds[:10]:
                    lines.append(f"  - {name}")
            except Exception:
                pass
            form_pages = sum(1 for p in self.doc if p.first_widget is not None)
            lines.append(f"Pages containing form fields: {form_pages}")
            lines.append("")
            lines.append(f"File: {self.file_path}")
            lines.append(f"Size: {Path(self.file_path).stat().st_size / 1024:.0f} KB")
            self.inspector.setPlainText("\n".join(lines))
        except Exception as e:
            self.inspector.setPlainText(f"Inspector error: {e}")

    # ------------------------------------------------------------------
    # Rendering & caching
    # ------------------------------------------------------------------

    def page_pixmap(self, index: int, doc=None) -> Optional[QPixmap]:
        doc = doc if doc is not None else self.doc
        key = (id(doc), index)
        if key in self._pix_cache:
            return self._pix_cache[key]
        try:
            pix = doc[index].get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride,
                          QImage.Format_RGB888).copy()
            pm = QPixmap.fromImage(qimg)
            self._pix_cache[key] = pm
            self._pix_refs[key] = pix
            return pm
        except Exception:
            return None

    def _render_visible(self):
        viewport = self.page_scroll.viewport().rect()
        top = self.page_scroll.viewport().mapTo(self.page_container, QPoint(0, 0)).y()
        bottom = top + viewport.height()
        y = 0
        for i, view in enumerate(self.views):
            h = view.height()
            if y + h >= top - 80 and y <= bottom + 80:
                if (id(self.doc), i) not in self._pix_cache:
                    self.page_pixmap(i)
                    view.update()
            y += h + self.page_layout.spacing()

    def refresh_page(self, index: int):
        self._pix_cache.pop((id(self.doc), index), None)
        self._pix_refs.pop((id(self.doc), index), None)
        if 0 <= index < len(self.views):
            view = self.views[index]
            view.setFixedSize(view.sizeHint())
            self.page_pixmap(index)
            view.update()
        try:
            pix = self.doc[index].get_pixmap(matrix=fitz.Matrix(0.16, 0.16), alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride,
                          QImage.Format_RGB888).copy()
            self._thumb_pix[index] = QPixmap.fromImage(qimg).scaledToWidth(86, Qt.SmoothTransformation)
            if index < self.thumb_list.count():
                self.thumb_list.item(index).setIcon(QIcon(self._thumb_pix[index]))
        except Exception:
            pass

    def set_zoom(self, value: float):
        self.zoom = max(0.3, min(5.0, round(float(value), 2)))
        self.zoom_lbl.setText(f"{int(self.zoom * 100)}%")
        self._pix_cache.clear()
        self._pix_refs.clear()
        for view in self.views:
            view.setFixedSize(view.sizeHint())
        QTimer.singleShot(30, self._render_visible)

    def _fit_width(self):
        if not self.doc:
            return
        page_w = self.doc[0].rect.width
        view_w = self.page_scroll.viewport().width() - 30
        if page_w > 0:
            self.set_zoom(round(max(0.3, min(3.0, view_w / page_w)), 2))

    def _on_scroll(self):
        self._render_visible()
        viewport_top = self.page_scroll.viewport().mapTo(self.page_container, QPoint(0, 0)).y()
        y = 0
        current = 0
        for i, view in enumerate(self.views):
            h = view.height()
            if y >= viewport_top - 50:
                current = i
                break
            y += h + self.page_layout.spacing()
        else:
            current = max(0, len(self.views) - 1)
        self.current_page = current
        self._update_status()

    def go_to_page(self, index: int, scroll: bool = True):
        if not (0 <= index < len(self.views)):
            return
        if scroll:
            y = 0
            for i, view in enumerate(self.views):
                if i == index:
                    break
                y += view.height() + self.page_layout.spacing()
            self.page_scroll.verticalScrollBar().setValue(y)
        self.current_page = index
        self._update_status()

    def _thumb_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if isinstance(idx, int):
            self.go_to_page(idx)

    def _thumbs_reordered(self):
        order = [self.thumb_list.item(row).data(Qt.UserRole)
                 for row in range(self.thumb_list.count())]
        if sorted(order) != list(range(len(self.doc))):
            return
        try:
            self.doc.select(order)
            self.mark_dirty()
            self._build_pages()
            self._build_thumbs()
            self.refresh_comments()
        except Exception as e:
            QMessageBox.warning(self, "Reorder Failed", str(e))

    def _outline_clicked(self, item: QTreeWidgetItem):
        page = item.data(0, Qt.UserRole)
        if isinstance(page, int):
            self.go_to_page(page)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def set_tool(self, tool: str):
        self.active_tool = tool
        for name, btn in self.tool_buttons.items():
            btn.setChecked(name == tool)
        cursors = {
            "select": Qt.ArrowCursor, "highlight": Qt.IBeamCursor, "underline": Qt.IBeamCursor,
            "strikeout": Qt.IBeamCursor, "text": Qt.IBeamCursor, "eraser": Qt.PointingHandCursor,
            "form": Qt.PointingHandCursor,
        }
        cursor = QCursor(cursors.get(tool, Qt.CrossCursor))
        for view in self.views:
            view.setCursor(cursor)

    def _pick_color(self):
        color = QColorDialog.getColor(self.tool_color, self, "Annotation Color")
        if color.isValid():
            self.tool_color = color
            self.color_btn.setText("🎨 " + color.name())

    # --- Digital Signature Certificate (DSC) ---

    def _open_dsc(self):
        """Picks a certificate, shows its details, then lets the user place the signature."""
        try:
            from opal_studio import dsc_sign
        except Exception as e:
            QMessageBox.warning(self, "Signing Unavailable", str(e))
            return
        if not dsc_sign.available():
            QMessageBox.warning(self, "Signing Unavailable",
                                "The PDF signing engine is not installed on this machine.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose your Digital Signature Certificate",
            "", "Certificates (*.pfx *.p12 *.p7b);;All Files (*.*)")
        if not path:
            return
        password, ok = QInputDialog.getText(self, "Certificate Password",
                                            "Enter the password for this certificate:",
                                            QLineEdit.Password)
        if not ok:
            return
        try:
            info = dsc_sign.inspect_certificate(path, password)
        except Exception as e:
            QMessageBox.critical(self, "Certificate Error", str(e))
            return

        detail = QDialog(self)
        detail.setWindowTitle("Certificate Details")
        detail.setStyleSheet(INK_STYLE)
        lay = QVBoxLayout(detail)
        summary = QLabel("Please confirm this is the right certificate:")
        summary.setWordWrap(True)
        lay.addWidget(summary)
        table = QTextEdit()
        table.setReadOnly(True)
        table.setStyleSheet("QTextEdit { background:#101625; color:#EDF1FA; "
                            "border:1px solid rgba(255,255,255,0.10); border-radius:10px; padding:8px; "
                            "font-family: Consolas, monospace; font-size: 11px; }")
        body = (f"Subject : {info['subject']}\n"
                f"Issuer  : {info['issuer']}\n"
                f"Serial  : {info['serial']}\n"
                f"Valid   : {info['valid_from']}  to  {info['valid_to']}\n"
                f"SHA-256 : {info['sha256_fingerprint']}")
        if info.get("expired"):
            body += "\n\nWARNING: this certificate has EXPIRED."
        if info.get("not_yet_valid"):
            body += "\n\nWARNING: this certificate is not valid yet."
        table.setPlainText(body)
        lay.addWidget(table)
        row = QHBoxLayout()
        row.addStretch()
        ok_btn = QPushButton("Use this certificate")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(detail.accept)
        cancel_btn.clicked.connect(detail.reject)
        row.addWidget(ok_btn)
        row.addWidget(cancel_btn)
        lay.addLayout(row)
        if detail.exec() != QDialog.Accepted:
            return

        self.dsc_context = {"pfx": path, "password": password, "info": info}
        self.set_tool("dsc")
        self.status.setText("Certificate loaded - click on the page to place the signature.")

    def sign_with_dsc(self, page_index: int, point: "fitz.Point") -> Optional[str]:
        """
        Signs the page with the loaded certificate and returns the path of the
        signed copy (saved next to the original). Pure logic - no dialogs, so it
        can be driven from scripts and tests as well as the UI.
        """
        ctx = getattr(self, "dsc_context", None)
        if not ctx:
            return None
        from opal_studio import dsc_sign
        page = self.doc[page_index]
        width, height = 190.0, 60.0
        # PyMuPDF page coordinates start at the bottom-left of the page.
        x0 = max(0.0, min(point.x, page.rect.width - width))
        y1 = max(0.0, min(point.y, page.rect.height - 10))
        rect = (x0, max(0.0, y1 - height), x0 + width, y1)
        out = self._sibling_output("_signed.pdf")
        dsc_sign.sign_pdf(self.file_path, out, ctx["pfx"], ctx["password"],
                          page_no=page_index, rect=rect,
                          reason="Approved by the signer",
                          location="India")
        return out

    def place_dsc_signature(self, page_index: int, point: "fitz.Point"):
        """Signs the page with the loaded certificate and saves the signed copy."""
        if not getattr(self, "dsc_context", None):
            return
        try:
            out = self.sign_with_dsc(page_index, point)
        except Exception as e:
            QMessageBox.critical(self, "Signing Failed", str(e))
            return
        if not out:
            return
        from opal_studio import dsc_sign
        check = dsc_sign.verify_signature(out)
        QMessageBox.information(
            self, "Document Signed",
            f"Signed successfully.\n\nSaved to:\n{out}\n\n"
            f"Signature fields: {check.get('count', 0)}\n"
            f"The file is saved next to the original - nothing else to do.")
        self.status.setText(f"Signed copy saved: {Path(out).name}")

    def open_signature_pad(self):
        dlg = SignatureDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.signature_png:
            self.pending_signature = dlg.signature_png
            self.set_tool("sign")
            self.status.setText("Signature ready: click the page to place it.")

    def place_signature(self, page_index: int, point: "fitz.Point"):
        if not self.pending_signature or not self.doc:
            return
        try:
            page = self.doc[page_index]
            w, h = 140.0, 48.0
            rect = fitz.Rect(point.x - w / 2, point.y - h / 2, point.x + w / 2, point.y + h / 2)
            page.insert_image(rect, stream=self.pending_signature)
            self.pending_signature = None
            self.mark_dirty()
            self.refresh_page(page_index)
            self.refresh_comments()
            self.set_tool("select")
        except Exception as e:
            QMessageBox.warning(self, "Sign Failed", str(e))

    def place_stamp(self, page_index: int, point: "fitz.Point"):
        if not self.doc:
            return
        options = ["Star ★", "Date stamp", "Approved ✓", "Draft ✎", "Confidential"]
        choice, ok = QInputDialog.getItem(self, "Stamp", "Choose a stamp:", options, 0, False)
        if not ok:
            return
        text_map = {"Star ★": "★", "Date stamp": time.strftime("%Y-%m-%d"),
                    "Approved ✓": "APPROVED", "Draft ✎": "DRAFT", "Confidential": "CONFIDENTIAL"}
        text = text_map.get(choice, choice)
        try:
            page = self.doc[page_index]
            page.insert_text((point.x - 20, point.y), text, fontname="hebo", fontsize=13,
                             color=(self.tool_color.red() / 255.0,
                                    self.tool_color.green() / 255.0,
                                    self.tool_color.blue() / 255.0))
            self.mark_dirty()
            self.refresh_page(page_index)
        except Exception as e:
            QMessageBox.warning(self, "Stamp Failed", str(e))

    def erase_annotation_at(self, page_index: int, point: "fitz.Point"):
        if not self.doc:
            return
        page = self.doc[page_index]
        for annot in list(page.annots() or []):
            if annot.rect.contains(point):
                try:
                    page.delete_annot(annot)
                    self.mark_dirty()
                    self.refresh_page(page_index)
                    self.refresh_comments()
                except Exception as e:
                    QMessageBox.warning(self, "Cannot Delete", str(e))
                return

    # --- forms ---

    def copy_text_in_rect(self, page_index: int, view_rect: QRectF) -> str:
        """Copies the text that sits inside a dragged rectangle (Acrobat-style)."""
        if not self.doc:
            return ""
        s = self.zoom
        target = fitz.Rect(view_rect.x() / s, view_rect.y() / s,
                           view_rect.right() / s, view_rect.bottom() / s)
        if target.is_empty:
            return ""
        try:
            words = self.doc[page_index].get_text("words")
        except Exception:
            return ""
        picked = [w for w in words if fitz.Rect(w[0], w[1], w[2], w[3]).intersects(target)]
        if not picked:
            return ""
        lines = {}
        for w in picked:
            lines.setdefault((w[5], w[6]), []).append(w)
        out = []
        for key in sorted(lines, key=lambda k: (k[0], k[1])):
            row = sorted(lines[key], key=lambda w: w[0])
            out.append(" ".join(w[4] for w in row))
        return "\n".join(out).strip()

    def copy_all_text(self) -> str:
        if not self.doc:
            return ""
        parts = []
        for i, page in enumerate(self.doc):
            try:
                text = page.get_text().strip()
            except Exception:
                text = ""
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def add_form_field(self, page_index: int, point: "fitz.Point", kind: str = "form_build"):
        """Asks for a name and adds a fillable field to the page."""
        if not self.doc:
            return
        default_name = "field" if kind == "form_build" else "checkbox"
        name, ok = QInputDialog.getText(self, "Field Name",
                                        "Name for this field (shown to whoever fills it):",
                                        text=default_name)
        if not ok or not name.strip():
            return
        if self.create_form_field(page_index, point, kind, name.strip()):
            self.status.setText(f"Added field '{name.strip()}' - remember to save the document.")

    def create_form_field(self, page_index: int, point: "fitz.Point",
                          kind: str = "form_build", name: str = "field") -> bool:
        """Adds a fillable field to the page (pure logic - no dialogs)."""
        if not self.doc:
            return False
        try:
            page = self.doc[page_index]
            widget = fitz.Widget()
            widget.field_name = name
            if kind == "form_check":
                widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
                widget.field_value = False
                size = 16.0
                widget.rect = fitz.Rect(point.x, point.y, point.x + size, point.y + size)
            else:
                widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                widget.field_value = ""
                widget.text_fontsize = 12
                widget.text_maxlen = 200
                width = 200.0
                widget.rect = fitz.Rect(point.x, point.y, point.x + width, point.y + 24)
            page.add_widget(widget)
            self.mark_dirty()
            self.refresh_page(page_index)
            return True
        except Exception as e:
            QMessageBox.warning(self, "Could Not Add Field", str(e))
            return False

    def widget_at(self, page_index: int, point: "fitz.Point"):
        if not self.doc:
            return None
        # Keep the page proxy alive: form widgets stay bound to it, otherwise
        # widget.update() fails with "Annot is not bound to a page".
        page = self.doc[page_index]
        self._form_page = page
        for w in page.widgets() or []:
            if w.rect.contains(point):
                return w
        return None

    def edit_widget(self, widget):
        try:
            self._form_page  # noqa: B018  (keep the owning page alive)
        except AttributeError:
            pass
        ftype = (widget.field_type_string or "").lower()
        if ftype == "checkbox":
            widget.field_value = not widget.field_value
            widget.update()
        elif ftype in ("combobox", "listbox", "radio_button", "radiobutton"):
            values = widget.choice_values or []
            if not values:
                return
            choice, ok = QInputDialog.getItem(self, f"Field: {widget.field_name}",
                                              "Choose value:", [str(v) for v in values], 0, False)
            if ok:
                widget.field_value = choice
                widget.update()
        else:
            current = widget.field_value or ""
            text, ok = QInputDialog.getText(self, f"Field: {widget.field_name}",
                                            "Enter value:", text=str(current))
            if ok:
                widget.field_value = text
                widget.update()
        self.mark_dirty()
        self.refresh_page(self.current_page)

    # --- search ---

    def _run_search(self, _text: Optional[str] = None):
        query = self.search_input.text().strip()
        self.search_matches = []
        self.active_match = -1
        if not query or not self.doc:
            self.search_count.setText("")
            self._repaint_all()
            return
        for i, page in enumerate(self.doc):
            try:
                for r in page.search_for(query):
                    self.search_matches.append((i, r))
            except Exception:
                continue
        if self.search_matches:
            self.active_match = 0
            self.go_to_page(self.search_matches[0][0])
        self.search_count.setText(f"{len(self.search_matches)} matches")
        self._repaint_all()

    def search_rects_for(self, page_index: int) -> List["fitz.Rect"]:
        return [r for (i, r) in self.search_matches if i == page_index]

    def active_search_rect(self):
        if 0 <= self.active_match < len(self.search_matches):
            return self.search_matches[self.active_match]
        return None

    def _search_next(self):
        if not self.search_matches:
            return
        self.active_match = (self.active_match + 1) % len(self.search_matches)
        self.go_to_page(self.search_matches[self.active_match][0])
        self.search_count.setText(f"{self.active_match + 1} of {len(self.search_matches)}")
        self._repaint_all()

    def _search_prev(self):
        if not self.search_matches:
            return
        self.active_match = (self.active_match - 1) % len(self.search_matches)
        self.go_to_page(self.search_matches[self.active_match][0])
        self.search_count.setText(f"{self.active_match + 1} of {len(self.search_matches)}")
        self._repaint_all()

    def _repaint_all(self):
        for view in self.views:
            view.update()

    # ------------------------------------------------------------------
    # Page operations
    # ------------------------------------------------------------------

    def mark_dirty(self):
        self.dirty = True
        self._update_status()
        self._schedule_autosave()

    def _schedule_autosave(self):
        """Saves the document by itself a moment after the last edit."""
        if not getattr(self, "auto_save", True):
            return
        if getattr(self, "_autosave_timer", None) is None:
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setSingleShot(True)
            self._autosave_timer.timeout.connect(self._autosave_now)
        self._autosave_timer.start(1800)

    def _autosave_now(self):
        if not self.dirty or not self.doc:
            return
        try:
            from opal_studio.pdf_tools import save_doc
            save_doc(self.doc, self.file_path)
            self.dirty = False
            self.status.setText(f"Saved automatically to {Path(self.file_path).name}")
            self._update_status()
        except Exception as e:
            self.status.setText(f"Auto-save failed: {e}")

    def _rotate_page(self, degrees: int):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        page.set_rotation((page.rotation + degrees) % 360)
        self.mark_dirty()
        self.refresh_page(self.current_page)

    def _delete_page(self):
        if not self.doc or len(self.doc) <= 1:
            QMessageBox.information(self, "Keep One Page",
                                    "A document must keep at least one page.")
            return
        idx = self.current_page
        if QMessageBox.question(self, "Delete Page",
                                f"Delete page {idx + 1}?") == QMessageBox.Yes:
            self.doc.delete_pages([idx])
            self.mark_dirty()
            self._build_pages()
            self._build_thumbs()
            self.refresh_comments()
            self._update_inspector()
            self.go_to_page(max(0, idx - 1), scroll=False)

    def _insert_blank(self):
        if not self.doc:
            return
        sizes = {"A4": (595, 842), "Letter": (612, 792), "Square": (595, 595), "Wide": (842, 595)}
        choice, ok = QInputDialog.getItem(self, "Insert Blank Page", "Page size:",
                                          list(sizes), 0, False)
        if not ok:
            return
        w, h = sizes[choice]
        pno = min(self.current_page + 1, len(self.doc))
        self.doc.new_page(width=w, height=h, pno=pno)
        self.mark_dirty()
        self._build_pages()
        self._build_thumbs()
        self.go_to_page(pno, scroll=False)

    def _insert_from_pdf(self):
        if not self.doc:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        try:
            from opal_studio import pdf_tools as pt
            other = _open_with_password(path, self)
            try:
                spec, ok = _range_dialog(self, "Insert Page Range", len(other))
                if not ok:
                    return
                pages = parse_page_range(spec, len(other))
                self.doc.insert_pdf(other, start_at=self.current_page + 1,
                                    from_page=min(pages), to_page=max(pages))
            finally:
                other.close()
            self.mark_dirty()
            self._build_pages()
            self._build_thumbs()
        except Exception as e:
            QMessageBox.warning(self, "Insert Failed", str(e))

    def _insert_images(self):
        if not self.doc:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose Images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)")
        if not paths:
            return
        try:
            for p in paths:
                page = self.doc.new_page(width=595, height=842, pno=len(self.doc))
                page.insert_image(fitz.Rect(40, 40, 555, 800), filename=p, keep_proportion=True)
            self.mark_dirty()
            self._build_pages()
            self._build_thumbs()
        except Exception as e:
            QMessageBox.warning(self, "Insert Failed", str(e))

    def _extract_range(self):
        if not self.doc:
            return
        spec, ok = _range_dialog(self, "Extract Page Range", len(self.doc))
        if not ok:
            return
        try:
            from opal_studio import pdf_tools as pt
            pages = parse_page_range(spec, len(self.doc))
            out = pt.extract_pages(self.file_path, None, pages)
            QMessageBox.information(self, "Extracted", f"Saved as:\n{out}")
            self._open_in_new_tab(out)
        except Exception as e:
            QMessageBox.warning(self, "Extract Failed", str(e))

    def _reverse_pages(self):
        if not self.doc:
            return
        self.doc.select(list(reversed(range(len(self.doc)))))
        self.mark_dirty()
        self._build_pages()
        self._build_thumbs()

    def _split_pages(self):
        try:
            from opal_studio import pdf_tools as pt
            out = pt.split_pages(self.file_path)
            QMessageBox.information(self, "Split Complete", f"Pages saved to:\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Split Failed", str(e))

    def _merge_pdfs(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose PDF to Merge", "", "PDF Files (*.pdf)")
        if not path:
            return
        try:
            from opal_studio import pdf_tools as pt
            out = pt.insert_pdf(self.file_path, path, None,
                                position=min(self.current_page + 1, len(self.doc)))
            QMessageBox.information(self, "Merged", f"Saved as:\n{out}")
            self._open_in_new_tab(out)
        except Exception as e:
            QMessageBox.warning(self, "Merge Failed", str(e))

    def _add_bookmark(self):
        if not self.doc:
            return
        title, ok = QInputDialog.getText(self, "Bookmark", "Bookmark title:",
                                         text=f"Page {self.current_page + 1}")
        if not ok or not title.strip():
            return
        toc = self.doc.get_toc(simple=True) or []
        toc.append([1, title.strip(), self.current_page + 1])
        toc.sort(key=lambda t: t[2])
        self.doc.set_toc(toc)
        self.mark_dirty()
        self._build_outline()

    # ------------------------------------------------------------------
    # Convert & protect operations
    # ------------------------------------------------------------------

    def _run_worker(self, kind: str, options: Optional[Dict] = None):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Busy", "Another operation is still running.")
            return
        self.worker = StudioWorker(kind, self.file_path, options or {})
        self.worker.progress.connect(self._worker_progress)
        self.worker.done.connect(self._worker_done)
        self.progress.show()
        self.status.setText(f"Running {kind}...")
        self.worker.start()

    def _worker_progress(self, done: int, total: int, kind: str):
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self.status.setText(f"{kind}: {done}/{total}")

    def _worker_done(self, ok: bool, message: str, output: str):
        self.progress.hide()
        self.status.setText(message)
        if ok:
            if output and output != self.file_path:
                QMessageBox.information(self, "Done", f"{message}\nSaved to:\n{output}")
                self._open_in_new_tab(output)
            else:
                QMessageBox.information(self, "Done", message)
                self._reload()
        else:
            QMessageBox.warning(self, "Operation Failed", message)

    def _run_engine_tool(self, action_id: str, title: str, options: Optional[dict] = None):
        """Runs an engine tool on this document and offers the result in a new tab."""
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, action_id, options or {})
        if not res.success:
            QMessageBox.warning(self, title, res.message)
            return None
        QMessageBox.information(self, title, f"{res.message}\n\nSaved to:\n{res.output_path}")
        return res.output_path

    def _repair_document(self):
        out = self._run_engine_tool("repair_pdf", "Repair PDF")
        if out:
            self._open_in_new_tab(out)

    def _trim_margins(self):
        out = self._run_engine_tool("autocrop_pdf", "Trim Margins")
        if out:
            self._open_in_new_tab(out)

    def _grayscale_document(self):
        out = self._run_engine_tool("grayscale_pdf", "Black & White")
        if out:
            self._open_in_new_tab(out)

    def _summarize_document(self):
        out = self._run_engine_tool("pdf_summary", "Summary")
        if out:
            try:
                text = Path(out).read_text(encoding="utf-8")
                box = QMessageBox(self)
                box.setWindowTitle("Summary")
                box.setText("Key points from the document:")
                box.setDetailedText(text)
                box.exec()
            except Exception:
                pass

    def _extract_attachments(self):
        """Pulls any embedded files out of the PDF (Acrobat's attachments panel)."""
        if not self.doc:
            return
        try:
            names = list(self.doc.embfile_names() or [])
        except Exception:
            names = []
        if not names:
            QMessageBox.information(self, "Attachments", "This document has no embedded files.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Save attachments to")
        if not folder:
            return
        out = Path(folder)
        saved = []
        for name in names:
            try:
                info = self.doc.embfile_info(name)
                data = self.doc.embfile_get(name)
                target = out / Path(name).name
                target.write_bytes(data)
                saved.append(target.name)
            except Exception:
                continue
        QMessageBox.information(self, "Attachments Extracted",
                                f"Saved {len(saved)} file(s) to:\n{out}")

    def _copy_all_text(self):
        text = self.copy_all_text()
        if not text.strip():
            QMessageBox.information(self, "Copy Text", "This document has no extractable text.")
            return
        QApplication.clipboard().setText(text)
        self.status.setText(f"Copied {len(text)} characters to the clipboard.")

    def _export_html(self):
        try:
            from opal_studio import pdf_tools as pt
            out = pt.export_html(self.file_path, self._sibling_output(".html"))
            QMessageBox.information(self, "HTML Exported", f"Saved to:\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _export_epub(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "epub")
        if res.success:
            QMessageBox.information(self, "EPUB Created", f"Saved to:\n{res.output_path}")
        else:
            QMessageBox.warning(self, "Export Failed", res.message)

    def _compress_document(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "compress_pdf")
        if res.success:
            QMessageBox.information(self, "Compressed", f"{res.message}\nSaved to:\n{res.output_path}")
            self._open_in_new_tab(res.output_path)
        else:
            QMessageBox.warning(self, "Compression Failed", res.message)

    def _export_images(self, fmt: str):
        res = self._engine_action("jpg" if fmt == "jpg" else "png_pages")
        if not res.success:
            QMessageBox.warning(self, "Export Failed", res.message)
        else:
            QMessageBox.information(self, "Pages Exported", f"{res.message}\n{res.output_path}")

    def _engine_action(self, action_id: str, options: Optional[Dict] = None):
        from opal_studio.engine import OpalEngine
        return OpalEngine.execute_single(self.file_path, action_id, options)

    def _watermark_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Watermark")
        dlg.setStyleSheet(INK_STYLE)
        lay = QFormLayout(dlg)
        text = QLineEdit("CONFIDENTIAL")
        opacity = QComboBox()
        opacity.addItems(["10%", "20%", "30%", "40%", "50%"])
        opacity.setCurrentText("30%")
        lay.addRow("Text", text)
        lay.addRow("Opacity", opacity)
        row = QHBoxLayout()
        ok = QPushButton("Apply")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addRow(row)
        if dlg.exec() != QDialog.Accepted:
            return
        self._run_worker("watermark", {
            "text": text.text().strip() or "CONFIDENTIAL",
            "opacity": float(opacity.currentText().rstrip("%")) / 100.0})

    def _pagenum_dialog(self):
        choices = ["{n}", "Page {n}", "Page {n} of {total}", "{n} / {total}"]
        fmt, ok = QInputDialog.getItem(self, "Page Numbers", "Number format:", choices, 1, False)
        if not ok:
            return
        start, ok2 = QInputDialog.getInt(self, "Page Numbers", "Start at:", 1)
        if not ok2:
            return
        self._run_worker("pagenum", {"format": fmt, "start": start})

    def _flatten_document(self):
        res = self._engine_action("pdf_flatten")
        if res.success:
            QMessageBox.information(self, "Flattened", f"{res.message}\nSaved to:\n{res.output_path}")
            self._open_in_new_tab(res.output_path)
        else:
            QMessageBox.warning(self, "Flatten Failed", res.message)

    def _protect_dialog(self):
        owner, ok = QInputDialog.getText(self, "Protect Document",
                                         "Set an owner password (locks the document):",
                                         QLineEdit.Password)
        if not ok or not owner:
            return
        try:
            from opal_studio import pdf_tools as pt
            out = pt.protect_pdf(self.file_path, None, owner_password=owner, user_password="")
            QMessageBox.information(self, "Protected", f"Password-protected copy saved to:\n{out}")
        except Exception as e:
            QMessageBox.warning(self, "Protect Failed", str(e))

    def _unlock_document(self):
        password, ok = QInputDialog.getText(self, "Unlock Document",
                                            "Enter the document password:", QLineEdit.Password)
        if not ok:
            return
        try:
            from opal_studio import pdf_tools as pt
            out = pt.unlock_pdf(self.file_path, None, password)
            QMessageBox.information(self, "Unlocked", f"Unlocked copy saved to:\n{out}")
            self._open_in_new_tab(out)
        except Exception as e:
            QMessageBox.warning(self, "Unlock Failed", str(e))

    # ------------------------------------------------------------------
    # Compare
    # ------------------------------------------------------------------

    def _open_compare(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Second PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        try:
            if self.compare_doc:
                try:
                    self.compare_doc.close()
                except Exception:
                    pass
                self.compare_doc = None
            self.compare_doc = _open_with_password(path, self)
            if self.compare_doc is None:
                return
            self._build_compare_view()
        except Exception as e:
            QMessageBox.warning(self, "Compare Failed", str(e))

    def _build_compare_view(self):
        if getattr(self, "compare_scroll", None) is not None:
            self.compare_scroll.setParent(None)
            self.compare_scroll.deleteLater()
            self.compare_scroll = None

        self.compare_scroll = QScrollArea()
        self.compare_scroll.setWidgetResizable(True)
        self.compare_scroll.setStyleSheet(
            "QScrollArea { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; }")
        self.compare_container = QWidget()
        c_layout = QVBoxLayout(self.compare_container)
        c_layout.setSpacing(10)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setAlignment(Qt.AlignHCenter)
        for i in range(min(len(self.compare_doc), 400)):
            view = PdfPageView(self, i, doc=self.compare_doc)
            view.setFixedSize(view.sizeHint())
            c_layout.addWidget(view)
            # render immediately so the pane is never blank
            QTimer.singleShot(20 + i * 4, lambda v=view: self.page_pixmap(v.page_index, v.doc))
        self.compare_scroll.setWidget(self.compare_container)
        self.center_split.addWidget(self.compare_scroll)
        self.center_split.setSizes([800, 800])
        self.compare_scroll.verticalScrollBar().valueChanged.connect(
            self._sync_scroll_from_compare)
        self.page_scroll.verticalScrollBar().valueChanged.connect(
            self._sync_scroll_from_main)
        self.status.setText(f"Comparing with {Path(self.compare_doc.name).name}. Scrolling is synchronized.")

    def _sync_scroll_from_compare(self, value):
        bar = self.page_scroll.verticalScrollBar()
        if bar.value() != value:
            bar.blockSignals(True)
            bar.setValue(value)
            bar.blockSignals(False)

    def _sync_scroll_from_main(self, value):
        bar = getattr(self, "compare_scroll", None)
        if bar is not None:
            bar = bar.verticalScrollBar()
            if bar.value() != value:
                bar.blockSignals(True)
                bar.setValue(value)
                bar.blockSignals(False)

    # ------------------------------------------------------------------
    # Print & save
    # ------------------------------------------------------------------

    def _print_document(self):
        if not self.doc:
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.Accepted:
            return
        painter = QPainter()
        if not painter.begin(printer):
            return
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        margin = 24
        target = QRectF(page_rect.x() + margin, page_rect.y() + margin,
                        page_rect.width() - 2 * margin, page_rect.height() - 2 * margin)
        for i in range(len(self.doc)):
            pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride,
                          QImage.Format_RGB888).copy()
            pm = QPixmap.fromImage(qimg)
            scaled = pm.scaled(int(target.width()), int(target.height()),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = target.x() + (target.width() - scaled.width()) / 2
            y = target.y() + (target.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            if i < len(self.doc) - 1:
                printer.newPage()
        painter.end()
        self.status.setText("Sent to printer.")

    def _save_document(self):
        if not self.doc:
            return
        try:
            from opal_studio import pdf_tools as pt
            pt.save_doc(self.doc, self.file_path)
            self.dirty = False
            try:
                self.doc.close()
            except Exception:
                pass
            self.doc = _open_with_password(self.file_path, self)
            self._build_pages()
            self._build_thumbs()
            self.refresh_comments()
            self._update_inspector()
            self.status.setText(f"Saved {Path(self.file_path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    def _reload(self):
        try:
            if self.doc:
                self.doc.close()
            self.doc = _open_with_password(self.file_path, self)
            self._build_pages()
            self._build_thumbs()
            self.refresh_comments()
            self._update_inspector()
        except Exception as e:
            QMessageBox.warning(self, "Reload Failed", str(e))

    def _sibling_output(self, ext: str) -> str:
        p = Path(self.file_path)
        candidate = p.with_name(f"{p.stem}{ext}")
        counter = 1
        while candidate.exists():
            candidate = p.with_name(f"{p.stem} ({counter}){ext}")
            counter += 1
        return str(candidate)

    def _open_in_new_tab(self, path: str):
        parent = self.parent()
        while parent is not None and not hasattr(parent, "open_pdf_tab"):
            parent = parent.parent()
        if parent is not None:
            try:
                parent.open_pdf_tab(path)
            except Exception:
                pass
        else:
            try:
                from opal_studio.platform_compat import open_with_default
                open_with_default(str(path))
            except Exception:
                pass

    def _open_external(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if path:
            self._open_in_new_tab(path)

    def _reveal_file(self):
        try:
            from opal_studio.platform_compat import reveal_in_file_manager
            reveal_in_file_manager(self.file_path)
        except Exception:
            pass

    def _read_aloud(self):
        if not self.doc:
            return
        text = self.doc[self.current_page].get_text().strip()
        if not text:
            QMessageBox.information(self, "Read Aloud", "This page has no selectable text.")
            return
        from opal_studio.engines import EngineManager
        self.status.setText("Reading page aloud...")

        def _speak():
            ok = EngineManager.tts_speak(text[:3000])
            QTimer.singleShot(0, lambda: self.status.setText(
                "Read aloud finished." if ok else "Read-aloud engine unavailable."))

        import threading
        threading.Thread(target=_speak, daemon=True).start()

    def _delete_selected_comment(self):
        item = self.comment_list.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        page_index, rect = data
        for annot in list(self.doc[page_index].annots() or []):
            if annot.rect == rect:
                try:
                    self.doc[page_index].delete_annot(annot)
                    self.mark_dirty()
                    self.refresh_page(page_index)
                    self.refresh_comments()
                except Exception as e:
                    QMessageBox.warning(self, "Delete Failed", str(e))
                break

    # ------------------------------------------------------------------
    # Status & lifecycle
    # ------------------------------------------------------------------

    def _update_status(self):
        if not self.doc:
            self.status.setText("No document")
            return
        current = min(self.current_page, len(self.doc) - 1)
        form_note = ""
        try:
            names = [w.field_name for w in (self.doc[current].widgets() or []) if w.field_name]
            if names:
                form_note = f" | {len(names)} form field(s) on this page"
        except Exception:
            pass
        dirty = " | unsaved changes" if self.dirty else ""
        self.status.setText(
            f"{Path(self.file_path).name} | Page {current + 1} of {len(self.doc)} | "
            f"Zoom {int(self.zoom * 100)}%{dirty}{form_note}")

    def close_document(self) -> bool:
        if self.dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "This document has unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self._save_document()
            elif reply == QMessageBox.Cancel:
                return False
        try:
            if self.compare_doc:
                self.compare_doc.close()
        except Exception:
            pass
        return True


def _qimage_to_png(image: QImage) -> bytes:
    """Encodes a QImage as PNG bytes (Qt needs a QIODevice, not a Python file object)."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def _open_with_password(file_path: str, parent=None):
    """Opens a PDF, prompting for a password when the document is protected."""
    from opal_studio.pdf_tools import open_pdf, PdfToolError
    try:
        return open_pdf(file_path)
    except Exception as first_error:
        if "password" not in str(first_error).lower():
            raise
    for _ in range(3):
        password, ok = QInputDialog.getText(
            parent, "Password Required",
            "This document is password protected.\nEnter password:", QLineEdit.Password)
        if not ok:
            raise PdfToolError("Password entry cancelled.")
        try:
            return open_pdf(file_path, password)
        except Exception:
            QMessageBox.warning(parent, "Wrong Password", "That password did not work.")
    raise PdfToolError("Password entry cancelled.")
