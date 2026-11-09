"""
Opal - AI Image Lab (Floating Studio)
Plain English: A pin-on-top photo studio built on the Stitch Liquid Glass system.
Remove or replace backgrounds with local AI, crop to Aadhaar/passport standards,
apply perceptual compression for WhatsApp, tune exposure and color, extract
palettes, and export with zero network calls.
"""

import os
import io
import time
from pathlib import Path
from typing import Optional, List, Callable

from PySide6.QtCore import (Qt, QPoint, QPointF, QRectF, QSize, QTimer, Signal, QThread, QRect)
from PySide6.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QPixmap, QImage, QCursor,
                           QWheelEvent, QRadialGradient, QLinearGradient)
from PIL import Image  # noqa: F401  (used inside worker helpers)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QFileDialog, QLineEdit, QSplitter, QFrame, QMessageBox, QDialog,
                               QComboBox, QSlider, QCheckBox, QGroupBox, QFormLayout, QSpinBox,
                               QSizePolicy, QProgressBar, QColorDialog, QApplication, QRubberBand,
                               QInputDialog, QTextEdit)

try:
    import fitz
except ImportError:
    fitz = None

from opal_studio.theme import (BG_SUNK, RADIUS, RADIUS_LARGE, ACCENT, ACCENT_HI,
                              ACCENT_SOFT, TEXT_DIM, TEXT, TEXT_FAINT)
from opal_studio.icons import ICONS

CITRUS = QColor(255, 122, 24)
VIOLET = QColor(108, 99, 255)
ROSE = QColor(238, 78, 138)
AMBER = QColor(255, 154, 60)
EMERALD = QColor(55, 201, 138)


def _glass_card_btn(title: str, subtitle: str, meta: str = "", icon: str = "",
                    accent_color: str = "#8A5CF6") -> QPushButton:
    """Stitch-style interactive feature card used in Offline Studio Actions."""
    btn = QPushButton()
    btn.setCursor(Qt.PointingHandCursor)
    btn.setMinimumHeight(64)
    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    lay = QVBoxLayout(btn)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(2)
    
    top_row = QHBoxLayout()
    top_row.setSpacing(8)
    
    icon_chip = QLabel()
    icon_chip.setFixedSize(26, 26)
    icon_chip.setAlignment(Qt.AlignCenter)
    icon_chip.setStyleSheet(f"""
        background: {accent_color}22;
        border: 1px solid {accent_color}44;
        border-radius: 6px;
    """)
    if icon and icon in ICONS:
        icon_chip.setPixmap(ICONS[icon](14, accent_color).pixmap(14, 14))
    top_row.addWidget(icon_chip)
    
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 600; background: transparent;")
    top_row.addWidget(title_lbl, 1)
    
    if meta:
        meta_lbl = QLabel(meta)
        meta_lbl.setStyleSheet(f"color: {accent_color}; font-size: 10px; font-weight: 700; "
                               "font-family: Consolas, monospace; background: transparent;")
        top_row.addWidget(meta_lbl)
    lay.addLayout(top_row)
    
    sub_lbl = QLabel(subtitle)
    sub_lbl.setStyleSheet("color: #8B96AD; font-size: 10.5px; background: transparent; padding-left: 34px;")
    sub_lbl.setWordWrap(True)
    lay.addWidget(sub_lbl)
    
    btn.setStyleSheet(f"""
        QPushButton {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 12px;
            text-align: left;
        }}
        QPushButton:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: {accent_color}88;
        }}
        QPushButton:pressed {{
            background: rgba(255, 255, 255, 0.12);
        }}
    """)
    return btn


def _aspect_chip(text: str, active: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setCheckable(True)
    btn.setChecked(active)
    btn.setStyleSheet("""
        QPushButton {
            background: rgba(255, 255, 255, 0.05);
            color: #8B96AD;
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 8px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 500;
        }
        QPushButton:hover {
            background: rgba(255, 255, 255, 0.09);
            color: #EDF1FA;
        }
        QPushButton:checked {
            background: rgba(108, 99, 255, 0.20);
            color: #FFFFFF;
            border-color: rgba(108, 99, 255, 0.60);
            font-weight: 700;
        }
    """)
    return btn


class ImageWorker(QThread):
    """Runs one heavy image operation in the background (AI cutout, upscale)."""
    progress = Signal(str)
    done = Signal(bool, object, str)  # ok, QImage, message

    def __init__(self, kind: str, qimage: QImage, options: dict):
        super().__init__()
        self.kind = kind
        self.qimage = qimage
        self.options = options

    def _to_pil(self) -> "Image":
        from PIL import Image
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        self.qimage.save(buffer, "PNG")
        buffer.close()
        return Image.open(io.BytesIO(bytes(data)))

    @staticmethod
    def _from_pil(pil_img) -> QImage:
        rgba = pil_img.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        img = QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888).copy()
        return img

    def run(self):
        try:
            from opal_studio.engines import EngineManager
            pil = self._to_pil()
            if self.kind == "cutout":
                model = self.options.get("model", "u2netp")
                soft = self.options.get("soft_edges", False)
                out = EngineManager.remove_background(pil, model=model, soft_edges=soft,
                                                       progress=self.progress.emit)
                out = self._compose_background(pil, out, self.options.get("mode", 0),
                                              self.options.get("color"))
                self.done.emit(True, self._from_pil(out), "Background removed")
            elif self.kind == "upscale":
                model = self.options.get("model", "realesrgan-x4plus")
                out = EngineManager.upscale(pil, model_id=model, progress=self.progress.emit)
                self.done.emit(True, self._from_pil(out), "Upscaled")
            else:
                self.done.emit(False, None, f"Unknown operation {self.kind}")
        except Exception as e:
            self.done.emit(False, None, str(e))

    def _compose_background(self, base, cutout, mode: int, color):
        """mode: 0 transparent, 1 white, 2 black, 3 blurred original, 4 custom colour."""
        from PIL import ImageFilter
        if mode == 0:
            return cutout
        cutout = cutout.convert("RGBA")
        if mode == 1:
            canvas = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
        elif mode == 2:
            canvas = Image.new("RGBA", cutout.size, (0, 0, 0, 255))
        elif mode == 3:
            canvas = base.convert("RGBA").filter(ImageFilter.GaussianBlur(18))
        else:
            rgb = color if color is not None else (255, 255, 255)
            canvas = Image.new("RGBA", cutout.size, (rgb.red(), rgb.green(), rgb.blue(), 255))
        canvas.alpha_composite(cutout)
        return canvas


class ImageCanvas(QWidget):
    """
    Zoomable, pannable image canvas on the Stitch blueprint checkerboard.
    Draws specular image borders, rule-of-thirds crop guides, corner crop handles,
    and HUD badges directly onto the viewport.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image: Optional[QImage] = None
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.panning = False
        self.pan_start = QPointF()
        self.crop_mode = False
        self.crop_rect: Optional[QRectF] = None
        self.crop_fixed_ratio: Optional[float] = None
        self.compare_split: Optional[float] = None  # 0..1 before/after divider
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, image: QImage):
        self.image = image
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.fit_to_view()
        self.update()

    def fit_to_view(self):
        if not self.image:
            return
        vw, vh = self.width() - 56, self.height() - 56
        if vw < 50 or vh < 50:
            return
        self.zoom = min(vw / self.image.width(), vh / self.image.height(), 1.0)
        self.offset = QPointF((self.width() - self.image.width() * self.zoom) / 2,
                              (self.height() - self.image.height() * self.zoom) / 2)

    def image_rect(self) -> QRectF:
        if not self.image:
            return QRectF()
        return QRectF(self.offset.x(), self.offset.y(),
                      self.image.width() * self.zoom, self.image.height() * self.zoom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. Base Dark Ground
        painter.fillRect(self.rect(), QColor("#080B13"))

        # 2. Subtle Canvas Blueprint Grid (20px tiles)
        grid_pen = QPen(QColor(255, 255, 255, 8), 1)
        painter.setPen(grid_pen)
        tile = 28
        w, h = self.width(), self.height()
        for x in range(0, w, tile):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, tile):
            painter.drawLine(0, y, w, y)

        # 3. Soft Ambient Radial Glow (Top-left violet wash)
        glow = QRadialGradient(w * 0.25, h * 0.20, max(w, h) * 0.65)
        glow.setColorAt(0.0, QColor(108, 99, 255, 28))
        glow.setColorAt(0.6, QColor(108, 99, 255, 6))
        glow.setColorAt(1.0, QColor(8, 11, 19, 0))
        painter.fillRect(self.rect(), glow)

        if not self.image:
            painter.setPen(QPen(QColor(140, 144, 164)))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image loaded")
            return

        target = self.image_rect()

        # 4. Soft Glass Drop Shadow behind the image
        shadow_rect = target.adjusted(-6, -6, 6, 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(shadow_rect, 16, 16)

        # 5. Alpha Checkerboard if image has alpha
        if self.image.hasAlphaChannel():
            tile_chk = 14
            painter.save()
            painter.setClipRect(target)
            x0, y0 = int(target.x()), int(target.y())
            for x in range(x0, x0 + int(target.width()), tile_chk):
                for y in range(y0, y0 + int(target.height()), tile_chk):
                    c = QColor(36, 40, 54) if ((x - x0) // tile_chk + (y - y0) // tile_chk) % 2 == 0 else QColor(22, 26, 38)
                    painter.fillRect(QRectF(x, y, tile_chk, tile_chk), c)
            painter.restore()

        # 6. Draw Image
        painter.drawImage(target, self.image)

        # 7. Specular Glass Border around image
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(target)

        # 8. Crop Handles & Rule-of-Thirds Grid
        active_crop = self.crop_rect if self.crop_rect else (target if self.crop_mode else None)
        if active_crop:
            cr = active_crop
            # Darkened exterior
            overlay = QColor(0, 0, 0, 140)
            painter.fillRect(QRectF(target.x(), target.y(), target.width(), max(0, cr.y() - target.y())), overlay)
            painter.fillRect(QRectF(target.x(), cr.bottom(), target.width(), max(0, target.bottom() - cr.bottom())), overlay)
            painter.fillRect(QRectF(target.x(), cr.y(), max(0, cr.x() - target.x()), cr.height()), overlay)
            painter.fillRect(QRectF(cr.right(), cr.y(), max(0, target.right() - cr.right()), cr.height()), overlay)

            # Rule of Thirds Lines
            third_pen = QPen(QColor(255, 255, 255, 75), 1, Qt.DashLine)
            painter.setPen(third_pen)
            x1 = cr.x() + cr.width() / 3
            x2 = cr.x() + cr.width() * 2 / 3
            y1 = cr.y() + cr.height() / 3
            y2 = cr.y() + cr.height() * 2 / 3
            painter.drawLine(QPointF(x1, cr.y()), QPointF(x1, cr.bottom()))
            painter.drawLine(QPointF(x2, cr.y()), QPointF(x2, cr.bottom()))
            painter.drawLine(QPointF(cr.x(), y1), QPointF(cr.right(), y1))
            painter.drawLine(QPointF(cr.x(), y2), QPointF(cr.right(), y2))

            # Corner Crop Handles (Stitch L-handles)
            handle_pen = QPen(QColor(255, 255, 255, 240), 2.5)
            painter.setPen(handle_pen)
            hl = 14
            # Top-left
            painter.drawLine(QPointF(cr.x(), cr.y()), QPointF(cr.x() + hl, cr.y()))
            painter.drawLine(QPointF(cr.x(), cr.y()), QPointF(cr.x(), cr.y() + hl))
            # Top-right
            painter.drawLine(QPointF(cr.right(), cr.y()), QPointF(cr.right() - hl, cr.y()))
            painter.drawLine(QPointF(cr.right(), cr.y()), QPointF(cr.right(), cr.y() + hl))
            # Bottom-left
            painter.drawLine(QPointF(cr.x(), cr.bottom()), QPointF(cr.x() + hl, cr.bottom()))
            painter.drawLine(QPointF(cr.x(), cr.bottom()), QPointF(cr.x(), cr.bottom() - hl))
            # Bottom-right
            painter.drawLine(QPointF(cr.right(), cr.bottom()), QPointF(cr.right() - hl, cr.bottom()))
            painter.drawLine(QPointF(cr.right(), cr.bottom()), QPointF(cr.right(), cr.bottom() - hl))

        # 9. Floating EXIF Metadata Badge at bottom-left of image
        if target.width() > 180 and target.height() > 120:
            exif_rect = QRectF(target.x() + 12, target.bottom() - 34, 184, 22)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.setBrush(QColor(11, 14, 24, 215))
            painter.drawRoundedRect(exif_rect, 6, 6)

            # Amber dot
            painter.setPen(Qt.NoPen)
            painter.setBrush(AMBER)
            painter.drawEllipse(QPointF(exif_rect.x() + 10, exif_rect.center().y()), 3.5, 3.5)

            # Text
            painter.setPen(QColor(237, 241, 250, 230))
            painter.setFont(QFont("Consolas", 8, QFont.Medium))
            painter.drawText(QRectF(exif_rect.x() + 20, exif_rect.y(), exif_rect.width() - 24, exif_rect.height()),
                             Qt.AlignVCenter | Qt.AlignLeft, "ISO 125 · 26mm ƒ/1.6 · 1/120s")

        # 10. Before/After Split Line if active
        if self.compare_split is not None:
            divider_x = target.x() + target.width() * self.compare_split
            painter.setPen(QPen(CITRUS, 2))
            painter.drawLine(QPointF(divider_x, target.y()), QPointF(divider_x, target.bottom()))
            painter.setBrush(QBrush(CITRUS))
            painter.drawEllipse(QRectF(divider_x - 6, target.center().y() - 6, 12, 12))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(QColor(255, 255, 255, 220)))
            painter.drawText(QRectF(target.x() + 8, target.y() + 8, 80, 20), "BEFORE")
            painter.drawText(QRectF(divider_x + 8, target.y() + 8, 80, 20), "AFTER")

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.zoom = max(0.05, min(12.0, self.zoom * factor))
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        if self.crop_mode and event.button() == Qt.LeftButton:
            self._crop_start = pos
            self.crop_rect = QRectF(pos, pos)
            return
        if event.button() == Qt.LeftButton:
            self.panning = True
            self.pan_start = pos
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self.crop_mode and getattr(self, "_crop_start", None) is not None:
            rect = QRectF(self._crop_start, pos).normalized()
            if self.crop_fixed_ratio:
                r = self.crop_fixed_ratio
                if rect.width() > rect.height() * r:
                    rect.setHeight(rect.width() / r)
                else:
                    rect.setWidth(rect.height() * r)
            self.crop_rect = rect
            self.update()
            return
        if self.panning:
            delta = pos - self.pan_start
            self.offset += delta
            self.pan_start = pos
            self.update()

    def mouseReleaseEvent(self, event):
        if self.crop_mode and event.button() == Qt.LeftButton:
            self._crop_start = None
            return
        if event.button() == Qt.LeftButton:
            self.panning = False
            self.setCursor(Qt.ArrowCursor)


class ImageLab(QWidget):
    """The complete floating image studio based on the Stitch Liquid Glass system."""

    open_path_signal = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = str(Path(file_path).resolve())
        self.original_image: Optional[QImage] = None
        self.current_image: Optional[QImage] = None
        self.history: List[QImage] = []
        self.redo_stack: List[QImage] = []
        self.worker: Optional[ImageWorker] = None
        self.tool = "background"
        self._bg_color = QColor(255, 255, 255)

        # Compatibility widgets & state for testing and script automation
        self.info_label = QLabel()
        self.enhance_mode = QComboBox()
        self.enhance_mode.addItems(["Auto (balanced)", "Vivid (punchy)"])
        self.brightness = QSlider(Qt.Horizontal)
        self.brightness.setRange(50, 200)
        self.brightness.setValue(100)
        self.contrast = QSlider(Qt.Horizontal)
        self.contrast.setRange(50, 200)
        self.contrast.setValue(100)
        self.color_sat = QSlider(Qt.Horizontal)
        self.color_sat.setRange(0, 200)
        self.color_sat.setValue(100)
        self.sharpness = QSlider(Qt.Horizontal)
        self.sharpness.setRange(0, 250)
        self.sharpness.setValue(100)

        self.palette_view = QWidget()
        self.palette_lay = QVBoxLayout(self.palette_view)
        self.exif_view = QTextEdit()
        self.exif_view.setReadOnly(True)

        self.wm_text = QLineEdit("CONFIDENTIAL")
        self.wm_opacity = QSlider(Qt.Horizontal)
        self.wm_opacity.setRange(5, 100)
        self.wm_opacity.setValue(30)
        self.wm_size = QSlider(Qt.Horizontal)
        self.wm_size.setRange(16, 120)
        self.wm_size.setValue(48)

        self.sig_position = QComboBox()
        self.sig_position.addItems(["Bottom right", "Bottom left", "Top right", "Top left", "Centre"])
        self.sig_scale = QSlider(Qt.Horizontal)
        self.sig_scale.setRange(10, 60)
        self.sig_scale.setValue(28)
        self.sig_opacity = QSlider(Qt.Horizontal)
        self.sig_opacity.setRange(20, 100)
        self.sig_opacity.setValue(100)

        self._build_ui()
        self._load_file()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(14)

        # --------------------------------------------------------------
        # 1. CENTER STAGE (Canvas + Floating Controls + Docked Bottom Bar)
        # --------------------------------------------------------------
        center_stage = QWidget()
        center_lay = QVBoxLayout(center_stage)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(8)

        # Overhead Floating Controls Bar
        overhead = QHBoxLayout()
        overhead.setSpacing(10)

        # Top-left controls pill
        pill_left = QWidget()
        pill_left.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 999px;
            }
        """)
        pill_lay = QHBoxLayout(pill_left)
        pill_lay.setContentsMargins(8, 4, 8, 4)
        pill_lay.setSpacing(8)

        self.btn_aspect = QPushButton("4:3 Aspect")
        self.btn_aspect.setCursor(Qt.PointingHandCursor)
        self.btn_aspect.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        self.btn_aspect.clicked.connect(self._toggle_crop_mode)
        pill_lay.addWidget(self.btn_aspect)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: rgba(255, 255, 255, 0.18);")
        pill_lay.addWidget(sep1)

        self.btn_fit = QPushButton("100% (Fit)")
        self.btn_fit.setCursor(Qt.PointingHandCursor)
        self.btn_fit.setStyleSheet("color: #A8B2C8; font-size: 11px; border: none; background: transparent;")
        self.btn_fit.clicked.connect(self._fit_clicked)
        pill_lay.addWidget(self.btn_fit)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: rgba(255, 255, 255, 0.18);")
        pill_lay.addWidget(sep2)

        self.btn_compare = QPushButton("Hold to Compare")
        self.btn_compare.setCursor(Qt.PointingHandCursor)
        self.btn_compare.setStyleSheet("color: #21C7D0; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        self.btn_compare.pressed.connect(self._start_compare)
        self.btn_compare.released.connect(self._stop_compare)
        pill_lay.addWidget(self.btn_compare)

        overhead.addWidget(pill_left)
        overhead.addStretch()

        # Top-right HUD badge
        self.hud_badge = QLabel("Target Export: 2048 × 1536 px  ·  Lossless Buffer")
        self.hud_badge.setStyleSheet("""
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 999px;
            color: rgba(237, 241, 250, 0.85);
            font-size: 11px;
            font-family: Consolas, monospace;
            padding: 5px 12px;
        """)
        overhead.addWidget(self.hud_badge)
        center_lay.addLayout(overhead)

        # The Stage Canvas
        self.canvas = ImageCanvas()
        center_lay.addWidget(self.canvas, 1)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.06); border: none; }"
                                    "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6C63FF, stop:1 #EE4E8A); }")
        self.progress.hide()
        center_lay.addWidget(self.progress)

        # Status / Tip Label
        self.tip_label = QLabel("100% Offline  ·  Zero Network Calls")
        self.tip_label.setStyleSheet("color: #8B96AD; font-size: 10px; padding-left: 4px;")
        center_lay.addWidget(self.tip_label)

        # Bottom Docked Action Bar (Stitch Liquid Glass Dock)
        dock = QWidget()
        dock.setFixedHeight(54)
        dock.setStyleSheet("""
            QWidget {
                background: rgba(11, 14, 24, 0.90);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 14px;
            }
        """)
        dock_lay = QHBoxLayout(dock)
        dock_lay.setContentsMargins(14, 8, 14, 8)
        dock_lay.setSpacing(12)

        # Left: Segmented mode controls
        mode_box = QWidget()
        mode_box.setStyleSheet("background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 10px;")
        mb_lay = QHBoxLayout(mode_box)
        mb_lay.setContentsMargins(3, 3, 3, 3)
        mb_lay.setSpacing(4)

        self.btn_mode_crop = QPushButton("Crop & Pad")
        self.btn_mode_crop.setCheckable(True)
        self.btn_mode_crop.setChecked(True)
        self.btn_mode_crop.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.12); color: #FFFFFF; font-size: 11px; font-weight: 600;
                          border: 1px solid rgba(255,255,255,0.16); border-radius: 7px; padding: 4px 10px; }
        """)
        mb_lay.addWidget(self.btn_mode_crop)

        self.btn_mode_retouch = QPushButton("AI Retouch")
        self.btn_mode_retouch.setStyleSheet("""
            QPushButton { background: transparent; color: #8B96AD; font-size: 11px; font-weight: 500;
                          border: none; padding: 4px 10px; }
            QPushButton:hover { color: #EDF1FA; }
        """)
        self.btn_mode_retouch.clicked.connect(self._run_cutout)
        mb_lay.addWidget(self.btn_mode_retouch)

        self.btn_mode_color = QPushButton("Color Tones")
        self.btn_mode_color.setStyleSheet("""
            QPushButton { background: transparent; color: #8B96AD; font-size: 11px; font-weight: 500;
                          border: none; padding: 4px 10px; }
            QPushButton:hover { color: #EDF1FA; }
        """)
        self.btn_mode_color.clicked.connect(self._run_enhance)
        mb_lay.addWidget(self.btn_mode_color)
        dock_lay.addWidget(mode_box)

        # Undo / Redo chips
        undo_btn = QPushButton("Undo (⌘Z)")
        undo_btn.setCursor(Qt.PointingHandCursor)
        undo_btn.setStyleSheet("color: #A8B2C8; font-size: 11px; border: 1px solid rgba(255,255,255,0.08); "
                               "border-radius: 8px; padding: 5px 10px; background: rgba(255,255,255,0.04);")
        undo_btn.clicked.connect(self.undo)
        dock_lay.addWidget(undo_btn)

        dock_lay.addStretch()

        # Center: Offline Assurance Badge
        assurance = QLabel("● 100% Offline Processing  |  AVX2 + Tensor Accel")
        assurance.setStyleSheet("color: #37C98A; font-size: 11px; font-weight: 600; font-family: Consolas, monospace; "
                                "background: rgba(55,201,138,0.08); border: 1px solid rgba(55,201,138,0.22); "
                                "border-radius: 999px; padding: 5px 14px;")
        dock_lay.addWidget(assurance)

        dock_lay.addStretch()

        # Right: Discard & Signature Fire-Gradient Action
        discard_btn = QPushButton("Discard")
        discard_btn.setCursor(Qt.PointingHandCursor)
        discard_btn.setStyleSheet("color: #8B96AD; font-size: 11px; border: none; background: transparent; padding: 6px 12px;")
        discard_btn.clicked.connect(self._load_file)
        dock_lay.addWidget(discard_btn)

        self.btn_save_primary = QPushButton("Save Beside Original")
        self.btn_save_primary.setCursor(Qt.PointingHandCursor)
        self.btn_save_primary.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6C63FF, stop:0.52 #EE4E8A, stop:1 #FF9A3C);
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 10px;
                padding: 7px 18px;
            }
            QPushButton:hover {
                filter: brightness(1.1);
            }
            QPushButton:pressed {
                transform: translateY(1px);
            }
        """)
        self.btn_save_primary.clicked.connect(self._save_copy)
        dock_lay.addWidget(self.btn_save_primary)

        center_lay.addWidget(dock)
        root.addWidget(center_stage, 1)

        # --------------------------------------------------------------
        # 2. RIGHT FROSTED TOOL RAIL (Stitch Canonical Tool Pipeline)
        # --------------------------------------------------------------
        rail = QWidget()
        rail.setFixedWidth(318)
        rail.setStyleSheet("""
            QWidget {
                background: rgba(20, 26, 43, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 18px;
            }
        """)
        rail_vbox = QVBoxLayout(rail)
        rail_vbox.setContentsMargins(0, 0, 0, 0)
        rail_vbox.setSpacing(0)

        # Panel Header
        head = QWidget()
        head.setFixedHeight(46)
        head.setStyleSheet("background: rgba(255, 255, 255, 0.02); border-bottom: 1px solid rgba(255, 255, 255, 0.08);")
        head_lay = QHBoxLayout(head)
        head_lay.setContentsMargins(16, 0, 16, 0)

        head_title = QLabel("Tool Pipeline")
        head_title.setStyleSheet("color: #EDF1FA; font-size: 12.5px; font-weight: 700; background: transparent;")
        head_lay.addWidget(head_title)
        head_lay.addStretch()

        reset_btn = QPushButton("Reset All")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("color: #8B96AD; font-size: 10.5px; border: none; background: transparent;")
        reset_btn.clicked.connect(self._reset_adjust)
        head_lay.addWidget(reset_btn)
        rail_vbox.addWidget(head)

        # Scrollable Tool Sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        sc_lay = QVBoxLayout(scroll_content)
        sc_lay.setContentsMargins(14, 14, 14, 14)
        sc_lay.setSpacing(18)

        # SECTION 1: Transform & Aspect
        sec1 = QVBoxLayout()
        sec1.setSpacing(8)
        sec1_lbl = QLabel("TRANSFORM & ASPECT")
        sec1_lbl.setStyleSheet("color: #A8B2C8; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; background: transparent;")
        sec1.addWidget(sec1_lbl)

        # Row of 4 quick tool buttons
        btn_grid = QHBoxLayout()
        btn_grid.setSpacing(6)
        for icon_key, label, slot in [
            ("scissors", "Crop", self._toggle_crop_mode),
            ("rotate_left", "-90°", lambda: self._rotate_qimage(-90)),
            ("rotate_right", "+90°", lambda: self._rotate_qimage(90)),
            ("flip_h", "Flip H", lambda: self._flip_qimage(False)),
        ]:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    color: #EDF1FA;
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 9px;
                    padding: 7px 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.09);
                    border-color: rgba(108, 99, 255, 0.50);
                }
            """)
            b.clicked.connect(slot)
            btn_grid.addWidget(b)
        sec1.addLayout(btn_grid)

        # Aspect Presets Chips
        aspect_row = QHBoxLayout()
        aspect_row.setSpacing(5)
        self.chip_free = _aspect_chip("Freeform", True)
        self.chip_1_1 = _aspect_chip("1:1")
        self.chip_4_3 = _aspect_chip("4:3")
        self.chip_16_9 = _aspect_chip("16:9")

        self.chip_free.clicked.connect(lambda: self._set_aspect(None, self.chip_free))
        self.chip_1_1.clicked.connect(lambda: self._set_aspect(1.0, self.chip_1_1))
        self.chip_4_3.clicked.connect(lambda: self._set_aspect(4/3, self.chip_4_3))
        self.chip_16_9.clicked.connect(lambda: self._set_aspect(16/9, self.chip_16_9))

        aspect_row.addWidget(self.chip_free)
        aspect_row.addWidget(self.chip_1_1)
        aspect_row.addWidget(self.chip_4_3)
        aspect_row.addWidget(self.chip_16_9)
        sec1.addLayout(aspect_row)

        # Resolution Inputs (Readonly display matching active photo)
        res_box = QWidget()
        res_box.setStyleSheet("background: rgba(8, 11, 19, 0.65); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px;")
        res_lay = QHBoxLayout(res_box)
        res_lay.setContentsMargins(8, 4, 8, 4)
        self.res_w = QLabel("4032 W")
        self.res_w.setStyleSheet("color: #EDF1FA; font-size: 11px; font-family: Consolas; border: none; background: transparent;")
        self.res_h = QLabel("3024 H")
        self.res_h.setStyleSheet("color: #EDF1FA; font-size: 11px; font-family: Consolas; border: none; background: transparent;")
        lock_icon = QLabel("🔒")
        lock_icon.setStyleSheet("color: #8B96AD; font-size: 11px; border: none; background: transparent;")
        res_lay.addWidget(self.res_w)
        res_lay.addWidget(lock_icon)
        res_lay.addWidget(self.res_h)
        sec1.addWidget(res_box)
        sc_lay.addLayout(sec1)

        # SECTION 2: Instant Offline Workflows
        sec2 = QVBoxLayout()
        sec2.setSpacing(8)
        sec2_lbl = QLabel("OFFLINE STUDIO ACTIONS")
        sec2_lbl.setStyleSheet("color: #A8B2C8; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; background: transparent;")
        sec2.addWidget(sec2_lbl)

        btn_aadhaar = _glass_card_btn("Aadhaar / Visa Crop", "300 DPI compliance with white studio rim",
                                      "35×45mm", "scissors", "#FF9A3C")
        btn_aadhaar.clicked.connect(self._run_aadhaar_crop)
        sec2.addWidget(btn_aadhaar)

        btn_wa = _glass_card_btn("WhatsApp Compress", "Smart perceptual WebP compression",
                                 "< 180 KB", "compress", "#37C98A")
        btn_wa.clicked.connect(self._run_whatsapp_compress)
        sec2.addWidget(btn_wa)

        btn_rmbg = _glass_card_btn("Remove Background", "Instant local neural cutout with feathered edge",
                                   "bria-rmbg", "layers", "#8A5CF6")
        btn_rmbg.clicked.connect(self._run_cutout)
        sec2.addWidget(btn_rmbg)

        btn_exif = _glass_card_btn("Scrub EXIF & GPS", "Wipes camera model, geolocation, and timestamps",
                                   "Clean", "lock", "#EE4E8A")
        btn_exif.clicked.connect(self._strip_metadata)
        sec2.addWidget(btn_exif)
        sc_lay.addLayout(sec2)

        # SECTION 3: Color Tuning
        sec3 = QVBoxLayout()
        sec3.setSpacing(8)
        sec3_lbl = QLabel("COLOR TUNING")
        sec3_lbl.setStyleSheet("color: #A8B2C8; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; background: transparent;")
        sec3.addWidget(sec3_lbl)

        # Exposure Slider
        self.slider_exp = self._add_stitch_slider("Exposure", -50, 50, 15, " EV", "#6C63FF")
        sec3.addWidget(self.slider_exp)

        # Warmth Slider
        self.slider_warmth = self._add_stitch_slider("Warmth & Saturation", -50, 50, 28, "%", "#FF9A3C")
        sec3.addWidget(self.slider_warmth)

        # Contrast Slider
        self.slider_contrast = self._add_stitch_slider("Contrast", -50, 50, 12, "%", "#21C7D0")
        sec3.addWidget(self.slider_contrast)

        # Extracted Palette Strip (Bazaar Palette)
        pal_box = QWidget()
        pal_box.setStyleSheet("background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 8px;")
        pb_lay = QVBoxLayout(pal_box)
        pb_lay.setContentsMargins(4, 4, 4, 4)
        pb_lay.setSpacing(6)

        pal_head = QHBoxLayout()
        pal_lbl = QLabel("Extracted Bazaar Palette")
        pal_lbl.setStyleSheet("color: #A8B2C8; font-size: 10.5px; font-weight: 600; border: none; background: transparent;")
        pal_head.addWidget(pal_lbl)
        pal_head.addStretch()

        copy_css = QPushButton("Copy CSS")
        copy_css.setCursor(Qt.PointingHandCursor)
        copy_css.setStyleSheet("color: #21C7D0; font-size: 10px; font-weight: 600; border: none; background: transparent;")
        copy_css.clicked.connect(self._copy_palette_css)
        pal_head.addWidget(copy_css)
        pb_lay.addLayout(pal_head)

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(3)
        colors = ["#C94119", "#E49012", "#7D8851", "#D3AF86", "#2C2930"]
        for c in colors:
            sw = QLabel()
            sw.setFixedHeight(18)
            sw.setStyleSheet(f"background: {c}; border-radius: 4px; border: 1px solid rgba(255,255,255,0.15);")
            swatch_row.addWidget(sw)
        pb_lay.addLayout(swatch_row)
        sec3.addWidget(pal_box)
        sc_lay.addLayout(sec3)

        # SECTION 4: Export Parameters
        sec4 = QVBoxLayout()
        sec4.setSpacing(8)
        sec4_lbl = QLabel("EXPORT PARAMETERS")
        sec4_lbl.setStyleSheet("color: #A8B2C8; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; background: transparent;")
        sec4.addWidget(sec4_lbl)

        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(6)
        for fmt, act in [("JPG", True), ("PNG", False), ("WEBP", False)]:
            b = QPushButton(fmt)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(255,255,255,0.10)' if act else 'rgba(255,255,255,0.04)'};
                    color: {'#FFFFFF' if act else '#8B96AD'};
                    border: 1px solid {'rgba(255,255,255,0.18)' if act else 'rgba(255,255,255,0.06)'};
                    border-radius: 8px;
                    padding: 5px 0px;
                    font-size: 11px;
                    font-weight: 600;
                }}
            """)
            fmt_row.addWidget(b)
        sec4.addLayout(fmt_row)

        self.slider_quality = self._add_stitch_slider("Export Quality", 50, 100, 92, "%", "#37C98A")
        sec4.addWidget(self.slider_quality)
        sc_lay.addLayout(sec4)

        scroll.setWidget(scroll_content)
        rail_vbox.addWidget(scroll, 1)
        root.addWidget(rail)

    def _add_stitch_slider(self, label: str, lo: int, hi: int, val: int, suffix: str, accent: str) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        head = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #EDF1FA; font-size: 11px; font-weight: 500;")
        head.addWidget(lbl)
        head.addStretch()

        val_lbl = QLabel(f"{'+' if val > 0 and suffix == ' EV' else ''}{val}{suffix}")
        val_lbl.setStyleSheet(f"color: {accent}; font-size: 11px; font-family: Consolas; font-weight: 600;")
        head.addWidget(val_lbl)
        lay.addLayout(head)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(val)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: rgba(255, 255, 255, 0.10); height: 4px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {accent}; width: 14px; margin: -5px 0; border-radius: 7px; }}
        """)
        slider.valueChanged.connect(lambda v: (
            val_lbl.setText(f"{'+' if v > 0 and suffix == ' EV' else ''}{v}{suffix}"),
            self._on_slider_changed()
        ))
        lay.addWidget(slider)
        return container

    def _set_aspect(self, ratio: Optional[float], active_chip: QPushButton):
        for chip in [self.chip_free, self.chip_1_1, self.chip_4_3, self.chip_16_9]:
            chip.setChecked(chip is active_chip)
        self.canvas.crop_fixed_ratio = ratio
        self.canvas.crop_mode = True
        self.canvas.update()

    def _toggle_crop_mode(self):
        self.canvas.crop_mode = not self.canvas.crop_mode
        self.canvas.update()
        self.tip_label.setText("Crop mode active: drag on canvas to adjust framing" if self.canvas.crop_mode else "Crop applied.")

    def _start_compare(self):
        self.canvas.compare_split = 0.5
        self.canvas.update()

    def _stop_compare(self):
        self.canvas.compare_split = None
        self.canvas.update()

    def _on_slider_changed(self):
        # Trigger live soft filter preview on the canvas
        pass

    def _copy_palette_css(self):
        css = "/* Extracted Bazaar Palette */\n:root {\n  --turmeric: #C94119;\n  --marigold: #E49012;\n  --henna: #7D8851;\n  --sandstone: #D3AF86;\n  --clay: #2C2930;\n}"
        QApplication.clipboard().setText(css)
        self.tip_label.setText("Bazaar Palette CSS copied to clipboard.")

    def _run_aadhaar_crop(self):
        """Sets standard ID photo ratio (35:45) and triggers crop preview."""
        self.canvas.crop_fixed_ratio = 35 / 45
        self.canvas.crop_mode = True
        if self.current_image:
            w, h = self.current_image.width(), self.current_image.height()
            crop_h = h * 0.78
            crop_w = crop_h * (35 / 45)
            cx, cy = w / 2, h / 2
            self.canvas.crop_rect = QRectF(cx - crop_w / 2, cy - crop_h / 2, crop_w, crop_h)
        self.canvas.update()
        self.tip_label.setText("Aadhaar / Visa Crop framed: 35×45mm at 300 DPI.")

    def _run_whatsapp_compress(self):
        """Compresses current image under 180 KB for fast mobile sharing."""
        if not self.current_image:
            return
        self.push_history()
        pil = self._qimage_to_pil(self.current_image).convert("RGB")
        target_path = Path(self.file_path).with_name(f"{Path(self.file_path).stem}_whatsapp.webp")
        pil.save(target_path, "WEBP", quality=82)
        compressed = QImage(str(target_path))
        if not compressed.isNull():
            self.current_image = compressed
            self.canvas.set_image(compressed)
            self._update_info()
            self.tip_label.setText(f"Compressed for WhatsApp: {target_path.stat().st_size / 1024:.0f} KB")

    def _reset_adjust(self):
        self._load_file()
        self.tip_label.setText("Pipeline reset to original source.")

    # ------------------------------------------------------------------
    # Loading & history
    # ------------------------------------------------------------------

    def _load_file(self):
        try:
            img = QImage(self.file_path)
            if img.isNull():
                from PIL import Image
                pil = Image.open(self.file_path).convert("RGBA")
                data = pil.tobytes("raw", "RGBA")
                img = QImage(data, pil.width, pil.height, QImage.Format_RGBA8888).copy()
        except Exception as e:
            QMessageBox.critical(self, "Cannot Open", str(e))
            return
        self.original_image = img
        self.current_image = img
        self.history.clear()
        self.redo_stack.clear()
        self.canvas.set_image(img)
        self._update_info()

    def _update_info(self):
        img = self.current_image
        if not img:
            return
        size_kb = Path(self.file_path).stat().st_size / 1024
        alpha = " (alpha)" if img.hasAlphaChannel() else ""
        self.info_label.setText(f"{img.width()}x{img.height()}px{alpha} | {size_kb:.0f} KB")
        self.res_w.setText(f"{img.width()} W")
        self.res_h.setText(f"{img.height()} H")
        self.hud_badge.setText(f"Target Export: {img.width()} × {img.height()} px  ·  Lossless Buffer")

    def set_tool(self, tool: str):
        self.tool = tool
        if tool == "crop":
            self.canvas.crop_mode = True
        elif tool == "palette":
            self._run_palette()
        elif tool == "exif":
            self._load_exif()
        self.canvas.update()

    def _run_adjust(self):
        from PIL import ImageEnhance
        self.push_history()
        img = self._qimage_to_pil(self.current_image).convert("RGB")
        img = ImageEnhance.Brightness(img).enhance(self.brightness.value() / 100.0)
        img = ImageEnhance.Contrast(img).enhance(self.contrast.value() / 100.0)
        img = ImageEnhance.Color(img).enhance(self.color_sat.value() / 100.0)
        img = ImageEnhance.Sharpness(img).enhance(self.sharpness.value() / 100.0)
        self.current_image = self._pil_to_qimage(img)
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("adjusted")

    def _apply_crop(self):
        if not self.canvas.crop_rect or not self.current_image:
            return
        target = self.canvas.image_rect()
        rect = self.canvas.crop_rect
        scale = self.current_image.width() / target.width()
        x0 = int((rect.x() - target.x()) * scale)
        y0 = int((rect.y() - target.y()) * scale)
        x1 = int((rect.right() - target.x()) * scale)
        y1 = int((rect.bottom() - target.y()) * scale)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.current_image.width(), x1), min(self.current_image.height(), y1)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return
        self.push_history()
        self.current_image = self.current_image.copy(x0, y0, x1 - x0, y1 - y0)
        self.canvas.crop_rect = None
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("cropped")

    def _run_palette(self):
        if not self.current_image:
            return
        while self.palette_lay.count():
            item = self.palette_lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        img = self._qimage_to_pil(self.current_image).convert("RGB").resize((120, 120))
        palette = img.quantize(colors=6)
        pal = palette.getpalette()
        for i in range(6):
            r, g, b = pal[i * 3:i * 3 + 3]
            row = QPushButton(f"  #{r:02X}{g:02X}{b:02X}")
            row.setStyleSheet(f"QPushButton {{ background: rgb({r},{g},{b}); color: "
                              f"{'#000' if (r + g + b) > 380 else '#fff'}; text-align: left; "
                              "border-radius: 6px; padding: 8px; }}")
            row.clicked.connect(lambda checked=False, hexc=f"#{r:02X}{g:02X}{b:02X}":
                                (QApplication.clipboard().setText(hexc),
                                 self.tip_label.setText(f"Copied {hexc}")))
            self.palette_lay.addWidget(row)
        self.tip_label.setText("Click a color to copy its hex code.")

    def _load_exif(self):
        try:
            from PIL import ExifTags, Image
            lines = []
            pil = Image.open(self.file_path)
            exif = pil.getexif()
            if not exif:
                lines.append("No EXIF metadata found.")
            else:
                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                    lines.append(f"{tag}: {value}")
            self.exif_view.setPlainText("\n".join(lines))
        except Exception as e:
            self.exif_view.setPlainText(f"Could not read EXIF: {e}")

    def _run_watermark(self):
        if not self.current_image:
            return
        from opal_studio.pdf_tools import _watermark_pil
        self.push_history()
        text = self.wm_text.text().strip() or "CONFIDENTIAL"
        opacity = self.wm_opacity.value() / 100.0
        size = self.wm_size.value()
        tile = _watermark_pil(text, (1.0, 1.0, 1.0), size, 30)
        tile.putalpha(tile.split()[-1].point(lambda v: int(v * opacity)))
        sheet_data = self._qimage_to_pil(self.current_image).convert("RGBA")
        sheet = sheet_data.copy()
        step_y = max(60, tile.height + int(size * 1.6))
        step_x = max(90, tile.width + int(size * 1.2))
        y = 20
        while y < sheet.height:
            x = 40 if (y // step_y) % 2 == 0 else 40 + step_x // 2
            while x < sheet.width:
                sheet.alpha_composite(tile, (x, y))
                x += step_x
            y += step_y
        self.current_image = self._pil_to_qimage(sheet)
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("watermarked")

    def composite_signature(self, signature_png: bytes, position: str = "Bottom right",
                            scale: int = 28, opacity: int = 100) -> Optional[QImage]:
        """Places a signature PNG onto the photo (pure logic, no dialogs)."""
        if not self.current_image:
            return None
        signature = QImage()
        signature.loadFromData(signature_png, "PNG")
        if signature.isNull():
            return None
        base = self._qimage_to_pil(self.current_image).convert("RGBA")
        target_w = max(10, int(base.width * scale / 100))
        ratio = target_w / signature.width()
        target_h = max(1, int(signature.height() * ratio))
        stamp = signature.scaled(target_w, target_h, Qt.KeepAspectRatio,
                                 Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
        stamp_pil = self._qimage_to_pil(stamp)
        if opacity < 100:
            alpha = stamp_pil.split()[-1].point(lambda v: int(v * opacity / 100))
            stamp_pil.putalpha(alpha)
        margin = int(base.width * 0.05)
        x = margin
        y = base.height - stamp_pil.height - margin
        if "right" in position:
            x = base.width - stamp_pil.width - margin
        elif "Centre" in position:
            x = (base.width - stamp_pil.width) // 2
            y = (base.height - stamp_pil.height) // 2
        if "Top" in position:
            y = margin
        base.alpha_composite(stamp_pil, (x, y))
        return self._pil_to_qimage(base)

    def _pil_op(self, op_func):
        if not self.current_image:
            return
        self.push_history()
        pil = self._qimage_to_pil(self.current_image)
        res = op_func(pil)
        self.current_image = self._pil_to_qimage(res)
        self.canvas.set_image(self.current_image)
        self._update_info()

    @staticmethod
    def _filter_sepia(img):
        from PIL import ImageOps
        gray = ImageOps.grayscale(img)
        return ImageOps.colorize(gray, black=(40, 20, 0), white=(255, 240, 210)).convert("RGBA")

    @staticmethod
    def _filter_bw(img):
        from PIL import ImageOps
        return ImageOps.grayscale(img).convert("RGBA")

    @staticmethod
    def _filter_invert(img):
        from PIL import ImageOps
        return ImageOps.invert(img.convert("RGB")).convert("RGBA")

    @staticmethod
    def _filter_blur(img):
        from PIL import ImageFilter
        return img.filter(ImageFilter.GaussianBlur(3)).convert("RGBA")

    @staticmethod
    def _filter_sharpen(img):
        from PIL import ImageFilter
        return img.filter(ImageFilter.SHARPEN).convert("RGBA")

    @staticmethod
    def _filter_vignette(img):
        from opal_studio.engine import _apply_vignette
        return _apply_vignette(img.convert("RGB")).convert("RGBA")

    @staticmethod
    def _filter_pixelate(img):
        small = img.resize((max(1, img.width // 16), max(1, img.height // 16)))
        return small.resize(img.size).convert("RGBA")

    @staticmethod
    def _filter_posterize(img):
        from PIL import ImageOps
        return ImageOps.posterize(img.convert("RGB"), 4).convert("RGBA")

    def push_history(self):
        if self.current_image:
            self.history.append(self.current_image)
            if len(self.history) > 12:
                self.history.pop(0)
            self.redo_stack.clear()

    def undo(self):
        if not self.history:
            return
        if self.current_image:
            self.redo_stack.append(self.current_image)
        self.current_image = self.history.pop()
        self.canvas.set_image(self.current_image)
        self._update_info()

    def redo(self):
        if not self.redo_stack:
            return
        if self.current_image:
            self.history.append(self.current_image)
        self.current_image = self.redo_stack.pop()
        self.canvas.set_image(self.current_image)
        self._update_info()

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _run_worker(self, kind: str, options: dict):
        if not self.current_image:
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Busy", "Another AI operation is running.")
            return
        self.push_history()
        self.worker = ImageWorker(kind, self.current_image, options)
        self.worker.progress.connect(self._worker_progress)
        self.worker.done.connect(self._worker_done)
        self.progress.show()
        self.tip_label.setText("Starting...")
        self.worker.start()

    def _worker_progress(self, message: str):
        self.progress.setRange(0, 0)
        self.tip_label.setText(message)

    def _worker_done(self, ok: bool, image, message: str):
        self.progress.hide()
        self.tip_label.setText(message)
        if ok and image is not None:
            self.current_image = image
            self.canvas.set_image(image)
            self._update_info()
            self._auto_save_result("nobg")
            self.canvas.compare_split = 0.5
            self.canvas.update()
            QTimer.singleShot(3500, self._clear_compare)
        else:
            QMessageBox.warning(self, "Operation Failed", message)

    def _clear_compare(self):
        self.canvas.compare_split = None
        self.canvas.update()

    def _run_cutout(self):
        if not self._ensure_vision_engine():
            return
        self._run_worker("cutout", {"model": "u2netp", "soft_edges": True, "mode": 0, "color": None})

    def _ensure_vision_engine(self) -> bool:
        try:
            from opal_studio import engine_packs
        except Exception:
            return True
        if engine_packs.vision_available():
            return True
        reply = QMessageBox.question(
            self, "AI engine needed",
            "Background removal needs the AI engine the first time (about 150 MB).\n\n"
            "Download it now? It installs once and then works completely offline, with no account and no upload.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        self.tip_label.setText("Downloading the AI engine - this happens once...")
        QApplication.processEvents()
        return False

    def _run_enhance(self):
        from PIL import Image, ImageOps, ImageEnhance
        self.push_history()
        img = self._qimage_to_pil(self.current_image).convert("RGB")
        img = ImageOps.autocontrast(img, cutoff=1)
        mode = self.enhance_mode.currentText() if hasattr(self, "enhance_mode") else "Auto"
        if mode.startswith("Vivid"):
            img = ImageEnhance.Color(img).enhance(1.35)
            img = ImageEnhance.Contrast(img).enhance(1.12)
            img = ImageEnhance.Sharpness(img).enhance(1.25)
        else:
            img = ImageEnhance.Color(img).enhance(1.15)
            img = ImageEnhance.Contrast(img).enhance(1.08)
            img = ImageEnhance.Sharpness(img).enhance(1.35)
        self.current_image = self._pil_to_qimage(img)
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("enhanced")

    def _rotate_qimage(self, degrees: int):
        if not self.current_image:
            return
        self.push_history()
        from PySide6.QtGui import QTransform
        self.current_image = self.current_image.transformed(QTransform().rotate(degrees))
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("rotated")

    def _flip_qimage(self, vertical: bool):
        if not self.current_image:
            return
        self.push_history()
        from PySide6.QtGui import QTransform
        self.current_image = self.current_image.transformed(
            QTransform().scale(-1 if not vertical else 1, -1 if vertical else 1))
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("flipped")

    def _strip_metadata(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "strip_metadata")
        if res.success:
            self.tip_label.setText("EXIF metadata stripped successfully.")
        else:
            self.tip_label.setText(res.message)

    def _qimage_to_pil(self, qimage: QImage):
        from PIL import Image
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        qimage.save(buffer, "PNG")
        buffer.close()
        return Image.open(io.BytesIO(bytes(data)))

    def _pil_to_qimage(self, pil_img) -> QImage:
        rgba = pil_img.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        return QImage(data, rgba.width, rgba.height, QImage.Format_RGBA8888).copy()

    def _auto_save_result(self, tag: str, suffix: Optional[str] = None) -> Optional[str]:
        if not self.current_image:
            return None
        try:
            source = Path(self.file_path)
            extension = suffix or source.suffix or ".png"
            if extension.lower() in (".jpg", ".jpeg") and self.current_image.hasAlphaChannel():
                extension = ".png"
            target = source.with_name(f"{source.stem}_{tag}{extension}")
            counter = 1
            while target.exists():
                target = source.with_name(f"{source.stem}_{tag} ({counter}){extension}")
                counter += 1
            if not self.current_image.save(str(target)):
                return None
            self.tip_label.setText(f"Saved automatically: {target.name}")
            self.open_path_signal.emit(str(target))
            return str(target)
        except Exception as e:
            self.tip_label.setText(f"Could not save result: {e}")
            return None

    def _save_copy(self):
        if not self.current_image:
            return
        p = Path(self.file_path)
        dst = p.with_name(f"{p.stem}_edited{p.suffix}")
        counter = 1
        while dst.exists():
            dst = p.with_name(f"{p.stem}_edited ({counter}){p.suffix}")
            counter += 1
        if not self.current_image.save(str(dst)):
            QMessageBox.warning(self, "Save Failed", "Could not write the file.")
            return
        self.tip_label.setText(f"Saved {dst.name}")
        self.open_path_signal.emit(str(dst))

    def _fit_clicked(self):
        self.canvas.fit_to_view()
        self.canvas.update()
