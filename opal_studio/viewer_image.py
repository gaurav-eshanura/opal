"""
Opal - AI Image Lab (Floating Studio)
Plain English: A pin-on-top photo studio. Remove or replace backgrounds with
local AI, upscale old photos 2x/4x with Real-ESRGAN, enhance, adjust, crop,
filter, watermark, extract palettes, inspect EXIF and save share-ready copies.
Everything runs on your machine; files are never uploaded.
"""

import os
import io
import time
from pathlib import Path
from typing import Optional, List, Callable

from PySide6.QtCore import (Qt, QPoint, QPointF, QRectF, QSize, QTimer, Signal, QThread, QRect)
from PySide6.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QPixmap, QImage, QCursor,
                           QWheelEvent, QRadialGradient)
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

CITRUS = QColor(255, 122, 24)
INK_STYLE = """
    QDialog, QWidget { background-color: rgba(255,255,255,0.05); color: #EDF1FA; }
    QPushButton { background-color: rgba(255,255,255,0.05); color: #EDF1FA; border: 1px solid rgba(255,255,255,0.16);
                  border-radius: 10px; padding: 6px 14px; font-weight: 600; }
    QPushButton:hover { background-color: #6C63FF; color: #FFFFFF; border-color: #8A83FF; }
    QPushButton:disabled { background-color: #101625; color: rgba(237,241,250,0.28); border-color: rgba(255,255,255,0.09); }
    QLineEdit, QComboBox, QSpinBox { background: rgba(255,255,255,0.05); color: #EDF1FA;
                  border: 1px solid rgba(255,255,255,0.16); border-radius: 10px; padding: 5px; }
    QLabel { color: #EDF1FA; }
    QGroupBox { border: 1px solid rgba(255,255,255,0.10); border-radius: 12px; margin-top: 10px;
                padding-top: 10px; font-weight: 600; color: #A79FFF; }
    QSlider::groove:horizontal { background: rgba(255,255,255,0.05); height: 4px; border-radius: 2px; }
    QSlider::handle:horizontal { background: #6C63FF; width: 14px; margin: -5px 0; border-radius: 7px; }
"""


def _tool_btn(text: str, tooltip: str = "", checkable: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setToolTip(tooltip or text)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setMinimumHeight(32)
    btn.setStyleSheet("""
        QPushButton { background: transparent; color: #A8B2C8; border: 1px solid transparent;
                      border-radius: 10px; padding: 7px 12px; font-size: 12px; font-weight: 500;
                      text-align: left; }
        QPushButton:hover { background: rgba(40,43,41,0.05); color: #EDF1FA; }
        QPushButton:checked { background: rgba(108,99,255,0.18); color: #C9C4FF;
                              border-color: rgba(255, 82, 0, 0.35); font-weight: 700; }
        QPushButton:disabled { color: #AEB4AC; }
    """)
    return btn


def _chip_btn(text: str, tooltip: str = "") -> QPushButton:
    """Compact, centred button used in the header rows."""
    btn = QPushButton(text)
    btn.setToolTip(tooltip or text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setMinimumHeight(28)
    btn.setStyleSheet("""
        QPushButton { background: rgba(255,255,255,0.05); color: #EDF1FA; border: 1px solid rgba(255,255,255,0.13);
                      border-radius: 10px; padding: 5px 12px; font-size: 11.5px; font-weight: 600; }
        QPushButton:hover { background: rgba(255,255,255,0.05); color: #C9C4FF; border-color: rgba(255,82,0,0.5); }
        QPushButton:pressed { background: rgba(255,255,255,0.05); }
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
    """Zoomable, pannable image canvas with checkerboard alpha and crop rubber band."""

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
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setStyleSheet("background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); "
                           "border-radius: 14px;")

    def set_image(self, image: QImage):
        self.image = image
        self.zoom = 1.0
        self.offset = QPointF(0, 0)
        self.fit_to_view()
        self.update()

    def fit_to_view(self):
        if not self.image:
            return
        vw, vh = self.width() - 40, self.height() - 40
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

        # A soft stage so the photo feels lit, not pasted on a black rectangle.
        stage = QRadialGradient(self.rect().center(), max(self.width(), self.height()) * 0.75)
        stage.setColorAt(0.0, QColor(38, 44, 64))
        stage.setColorAt(0.55, QColor(22, 27, 42))
        stage.setColorAt(1.0, QColor(11, 14, 24))
        painter.fillRect(self.rect(), stage)
        painter.setPen(QPen(QColor(255, 255, 255, 26)))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)

        if not self.image:
            painter.setPen(QPen(QColor(140, 144, 164)))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image")
            return

        target = self.image_rect()
        if self.image.hasAlphaChannel():
            tile = 14
            painter.save()
            painter.setClipRect(target)
            x0, y0 = int(target.x()), int(target.y())
            for x in range(x0, x0 + int(target.width()), tile):
                for y in range(y0, y0 + int(target.height()), tile):
                    if ((x - x0) // tile + (y - y0) // tile) % 2 == 0:
                        painter.fillRect(QRectF(x, y, tile, tile), QColor(214, 215, 211))
                    else:
                        painter.fillRect(QRectF(x, y, tile, tile), QColor(236, 237, 234))
            painter.restore()
        painter.drawImage(target, self.image)

        if self.compare_split is not None:
            divider_x = target.x() + target.width() * self.compare_split
            painter.setPen(QPen(CITRUS, 2))
            painter.drawLine(QPointF(divider_x, target.y()), QPointF(divider_x, target.bottom()))
            painter.setBrush(QBrush(QColor(255, 122, 24, 200)))
            handle = QRectF(divider_x - 6, target.center().y() - 6, 12, 12)
            painter.drawEllipse(handle)
            painter.setPen(QPen(Qt.white, 1))
            painter.restore()
            painter.save()
            painter.setClipping(False)
            painter.setPen(QPen(QColor(255, 255, 255, 200)))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(QRectF(target.x(), target.y() - 22, 90, 18), "BEFORE")
            painter.drawText(QRectF(divider_x + 8, target.y() - 22, 90, 18), "AFTER")
            painter.restore()

        if self.crop_rect:
            overlay = QColor(0, 0, 0, 120)
            top = QRectF(target.x(), target.y(), target.width(), self.crop_rect.y() - target.y())
            bottom = QRectF(target.x(), self.crop_rect.bottom(), target.width(),
                            target.bottom() - self.crop_rect.bottom())
            left = QRectF(target.x(), self.crop_rect.y(),
                          self.crop_rect.x() - target.x(), self.crop_rect.height())
            right = QRectF(self.crop_rect.right(), self.crop_rect.y(),
                           target.right() - self.crop_rect.right(), self.crop_rect.height())
            painter.fillRect(top, overlay)
            painter.fillRect(bottom, overlay)
            painter.fillRect(left, overlay)
            painter.fillRect(right, overlay)
            painter.setPen(QPen(CITRUS, 1.5, Qt.DashLine))
            painter.drawRect(self.crop_rect)

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
    """The complete floating image studio."""

    open_path_signal = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        from opal_studio.theme import apply_field
        apply_field(self)
        self.file_path = str(Path(file_path).resolve())
        self.original_image: Optional[QImage] = None
        self.current_image: Optional[QImage] = None
        self.history: List[QImage] = []
        self.redo_stack: List[QImage] = []
        self.worker: Optional[ImageWorker] = None
        self.tool = "background"

        self._build_ui()
        self._load_file()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        rail = QWidget()
        rail.setObjectName("toolRail")
        rail.setFixedWidth(186)
        rail.setStyleSheet("QWidget#toolRail { background: rgba(255,255,255,0.05); "
                           "border: 1px solid rgba(255,255,255,0.10); border-radius: 18px; }")
        rail_lay = QVBoxLayout(rail)
        rail_lay.setSpacing(3)
        rail_lay.setContentsMargins(12, 14, 12, 14)

        brand = QLabel("OPAL  ·  IMAGE LAB")
        brand.setStyleSheet("color: #A79FFF; font-size: 10px; font-weight: 700; "
                            "letter-spacing: 2px; background: transparent;")
        rail_lay.addWidget(brand)
        rail_lay.addSpacing(10)

        # The headline feature: one click, background gone, file saved by itself.
        self.quick_remove = QPushButton("Remove Background")
        self.quick_remove.setToolTip("Remove the background now — the result saves "
                                      "next to your photo automatically")
        self.quick_remove.setMinimumHeight(64)
        self.quick_remove.setProperty("accent", "true")
        self.quick_remove.setCursor(Qt.PointingHandCursor)
        self.quick_remove.setStyleSheet("""
            QPushButton { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                    stop: 0 #8A5CF6, stop: 0.55 #EE4E8A, stop: 1 #FF9A3C);
                          color: #FFFFFF; border: none;
                          border-radius: 14px; font-size: 12.5px; font-weight: 800;
                          line-height: 118%; padding: 8px 6px; }
            QPushButton:hover { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                          stop: 0 #9B7BFF, stop: 0.55 #FF6BA0, stop: 1 #FFB35C); }
            QPushButton:disabled { background: rgba(0,0,0,0.22); color: #AEB4AC; }
        """)
        self.quick_remove.clicked.connect(self._quick_remove_background)
        rail_lay.addWidget(self.quick_remove)
        rail_lay.addSpacing(12)

        self.tool_buttons = {}
        for key, label in [
            ("replace_bg", "Replace Background"),
            ("upscale", "AI Upscale"),
            ("enhance", "Auto-Enhance"),
            ("adjust", "Adjust"),
            ("crop", "Crop"),
            ("rotate", "Rotate & Flip"),
            ("filters", "Filters"),
            ("watermark", "Watermark"),
            ("signature", "Signature"),
            ("privacy", "Blur Faces"),
            ("meme", "Meme Caption"),
            ("palette", "Colour Palette"),
            ("exif", "EXIF & Privacy"),
            ("wallpaper", "Wallpaper"),
        ]:
            btn = _tool_btn(label, checkable=True)
            btn.clicked.connect(lambda checked=False, t=key: self.set_tool(t))
            self.tool_buttons[key] = btn
            rail_lay.addWidget(btn)
        rail_lay.addStretch()
        undo = _tool_btn("Undo")
        undo.clicked.connect(self.undo)
        rail_lay.addWidget(undo)
        redo = _tool_btn("Redo")
        redo.clicked.connect(self.redo)
        rail_lay.addWidget(redo)
        root.addWidget(rail)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)

        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        self.name_label = QLabel(Path(self.file_path).name)
        self.name_label.setStyleSheet("color: #EDF1FA; font-size: 13px; font-weight: 700;")
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #727E96; font-size: 11px;")
        info_row.addWidget(self.name_label)
        info_row.addWidget(self.info_label)
        info_row.addStretch()
        for text, tip, slot in [
            ("Fit", "Fit image to view", self._fit_clicked),
            ("1:1", "Actual size", self._actual_size),
            ("Copy", "Copy image with alpha", self._copy_image),
            ("Save Copy", "Save the edited copy", self._save_copy),
            ("Save As", "Save with a chosen name & format", self._save_as),
        ]:
            btn = _chip_btn(text, tip)
            btn.clicked.connect(slot)
            info_row.addWidget(btn)
        center_lay.addLayout(info_row)

        self.canvas = ImageCanvas()
        center_lay.addWidget(self.canvas, 1)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        center_lay.addWidget(self.progress)

        self.tip_label = QLabel("")
        self.tip_label.setStyleSheet("color: #727E96; font-size: 10px;")
        center_lay.addWidget(self.tip_label)
        root.addWidget(center, 1)

        self.options_panel = QWidget()
        self.options_panel.setObjectName("optionsPanel")
        self.options_panel.setFixedWidth(286)
        self.options_panel.setStyleSheet("QWidget#optionsPanel { background: rgba(255,255,255,0.05); "
                                         "border: 1px solid rgba(255,255,255,0.10); "
                                         "border-radius: 18px; }")
        self.options_lay = QVBoxLayout(self.options_panel)
        self.options_lay.setAlignment(Qt.AlignTop)
        self.options_lay.setContentsMargins(14, 14, 14, 14)
        self.options_lay.setSpacing(10)
        root.addWidget(self.options_panel)

        self.set_tool("background")

    def set_tool(self, tool: str):
        self.tool = tool
        for key, btn in self.tool_buttons.items():
            btn.setChecked(key == tool)
        self._rebuild_options()
        self.canvas.crop_mode = tool == "crop"
        self.canvas.compare_split = None
        self.canvas.update()

    def _rebuild_options(self):
        # clear
        while self.options_lay.count():
            item = self.options_lay.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        heading = QLabel(self.tool.replace("_", " ").title())
        heading.setStyleSheet("color: #EDF1FA; font-size: 14px; font-weight: 700; "
                              "background: transparent;")
        self.options_lay.addWidget(heading)
        sub = QLabel(self._tool_hint())
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #727E96; font-size: 11px; background: transparent;")
        self.options_lay.addWidget(sub)
        self.options_lay.addSpacing(4)
        getattr(self, f"_opts_{self.tool}", lambda: None)()

    def _tool_hint(self) -> str:
        return {
            "background": "AI removes the background and saves a transparent PNG next to "
                          "your original.",
            "replace_bg": "Keep the subject, change what is behind it.",
            "upscale": "Restore detail with Real-ESRGAN. The model downloads once.",
            "enhance": "One tap for contrast, colour and clarity.",
            "adjust": "Fine-tune by hand, then save a copy.",
            "crop": "Drag on the image, or pick a ratio.",
            "rotate": "Turn the photo or flip it.",
            "filters": "Give the photo a new look.",
            "watermark": "Stamp text across the photo.",
            "signature": "Draw or type a signature onto the photo.",
            "palette": "Find the colours that make this photo work.",
            "exif": "See what the camera recorded — and remove it.",
            "wallpaper": "Fit the photo to your screen.",
        }.get(self.tool, "")

    def _add_group(self, title: str) -> QFormLayout:
        group = QGroupBox(title)
        lay = QFormLayout(group)
        self.options_lay.addWidget(group)
        return lay

    def _add_run_button(self, text: str, slot: Callable, accent: bool = True):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        if accent:
            btn.setStyleSheet(
                "QPushButton { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,"
                " stop: 0 #8A5CF6, stop: 0.55 #EE4E8A, stop: 1 #FF9A3C);"
                " color: #fff; border: none;"
                " border-radius: 10px; padding: 8px 16px; font-weight: 700; }"
                "QPushButton:hover { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,"
                " stop: 0 #9B7BFF, stop: 0.55 #FF6BA0, stop: 1 #FFB35C); }"
                "QPushButton:disabled { background: rgba(255,255,255,0.05); color: rgba(237,241,250,0.28); }")
        else:
            btn.setStyleSheet(INK_STYLE.replace("QPushButton {", "QPushButton {"))
        btn.clicked.connect(slot)
        self.options_lay.addWidget(btn)
        return btn

    def _add_slider_row(self, form: QFormLayout, label: str, lo: int, hi: int,
                        value: int, suffix: str = "") -> QSlider:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        value_lbl = QLabel(f"{value}{suffix}")
        slider.valueChanged.connect(lambda v: value_lbl.setText(f"{v}{suffix}"))
        lay.addWidget(slider, 1)
        lay.addWidget(value_lbl)
        form.addRow(label, row)
        return slider

    # ------------------------------------------------------------------
    # Tool option panels
    # ------------------------------------------------------------------

    def _opts_background(self):
        form = self._add_group("AI Background Remover")
        self.bg_model = QComboBox()
        from opal_studio.engines import CUTOUT_MODELS, EngineManager
        cached = {m for m, _, s in EngineManager.available_cutout_models() if s == "cached"}
        for mid, (label, _size) in CUTOUT_MODELS.items():
            self.bg_model.addItem(f"{label} {'✓' if mid in cached else '☁'}", mid)
        if "u2netp" in cached:
            self.bg_model.setCurrentIndex(list(CUTOUT_MODELS).index("u2netp"))
        form.addRow("AI model", self.bg_model)
        self.soft_edges = QCheckBox("Soften edges (feather)")
        form.addRow("", self.soft_edges)
        self._add_run_button("Remove Background", self._run_cutout)

    def _opts_replace_bg(self):
        form = self._add_group("Replace Background")
        self.bg_mode = QComboBox()
        self.bg_mode.addItems(["Transparent PNG", "Solid white", "Solid black",
                               "Blurred original", "Custom color"])
        self.bg_mode.currentIndexChanged.connect(self._toggle_color_row)
        form.addRow("New background", self.bg_mode)
        self.bg_color_row = QWidget()
        color_lay = QHBoxLayout(self.bg_color_row)
        color_lay.setContentsMargins(0, 0, 0, 0)
        self.bg_color_btn = _tool_btn("#FFFFFF")
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        color_lay.addWidget(self.bg_color_btn)
        self._bg_color = QColor(255, 255, 255)
        form.addRow("Color", self.bg_color_row)
        self.bg_model2 = QComboBox()
        from opal_studio.engines import CUTOUT_MODELS
        for mid, (label, _size) in CUTOUT_MODELS.items():
            self.bg_model2.addItem(label, mid)
        form.addRow("AI model", self.bg_model2)
        self._add_run_button("Remove & Replace", self._run_replace_bg)

    def _toggle_color_row(self):
        self.bg_color_row.setVisible(self.bg_mode.currentIndex() == 4)

    def _pick_bg_color(self):
        color = QColorDialog.getColor(self._bg_color, self, "Background Color")
        if color.isValid():
            self._bg_color = color
            self.bg_color_btn.setText(color.name())

    def _opts_upscale(self):
        form = self._add_group("AI Upscaling")
        self.upscale_model = QComboBox()
        self.upscale_model.addItem("Real-ESRGAN x4+ (best quality, 64MB)", "realesrgan-x4plus")
        self.upscale_model.addItem("Real-ESRGAN x2+ (faster, 68MB)", "realesrgan-x2plus")
        form.addRow("Engine", self.upscale_model)
        self._add_run_button("Upscale Now", self._run_upscale)
        hint = QLabel("Model downloads once, then works offline.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #727E96; font-size: 10px;")
        self.options_lay.addWidget(hint)

    def _opts_enhance(self):
        form = self._add_group("Auto Enhance")
        self.enhance_mode = QComboBox()
        self.enhance_mode.addItems(["Auto (balanced)", "Vivid (punchy)"])
        form.addRow("Preset", self.enhance_mode)
        self._add_run_button("Enhance", self._run_enhance)

    def _opts_adjust(self):
        form = self._add_group("Adjustments")
        self.brightness = self._add_slider_row(form, "Brightness", 50, 200, 100, "%")
        self.contrast = self._add_slider_row(form, "Contrast", 50, 200, 100, "%")
        self.color_sat = self._add_slider_row(form, "Color", 0, 200, 100, "%")
        self.sharpness = self._add_slider_row(form, "Sharpness", 0, 250, 100, "%")
        reset = _tool_btn("Reset Sliders")
        reset.clicked.connect(self._reset_adjust)
        self.options_lay.addWidget(reset)
        self._add_run_button("Apply Adjustments", self._run_adjust)

    def _reset_adjust(self):
        for s in (self.brightness, self.contrast, self.color_sat, self.sharpness):
            s.setValue(100)

    def _opts_crop(self):
        form = self._add_group("Crop")
        self.crop_ratio = QComboBox()
        self.crop_ratio.addItems(["Free", "1:1 Square", "4:5 Portrait", "9:16 Vertical",
                                  "16:9 Wide", "3:2 Photo"])
        self.crop_ratio.currentIndexChanged.connect(self._update_crop_ratio)
        form.addRow("Aspect", self.crop_ratio)
        apply_btn = _tool_btn("✂️ Apply Crop")
        apply_btn.clicked.connect(self._apply_crop)
        self.options_lay.addWidget(apply_btn)
        clear_btn = _tool_btn("Clear Selection")
        clear_btn.clicked.connect(lambda: (setattr(self.canvas, "crop_rect", None),
                                            self.canvas.update()))
        self.options_lay.addWidget(clear_btn)
        hint = QLabel("Drag on the image to select the crop area.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #727E96; font-size: 10px;")
        self.options_lay.addWidget(hint)

    def _update_crop_ratio(self):
        ratios = [None, 1.0, 4 / 5, 9 / 16, 16 / 9, 3 / 2]
        self.canvas.crop_fixed_ratio = ratios[self.crop_ratio.currentIndex()]

    def _opts_rotate(self):
        form = self._add_group("Rotate & Flip")
        for label, slot in [
            ("↺ Rotate Left", lambda: self._rotate_qimage(-90)),
            ("↻ Rotate Right", lambda: self._rotate_qimage(90)),
            ("↕ Flip Vertical", lambda: self._flip_qimage(True)),
            ("↔ Flip Horizontal", lambda: self._flip_qimage(False)),
        ]:
            self.options_lay.addWidget(_tool_btn(label))

    def _opts_filters(self):
        form = self._add_group("Filters")
        for label, slot in [
            ("Sepia", lambda: self._pil_op(self._filter_sepia)),
            ("Black & White", lambda: self._pil_op(self._filter_bw)),
            ("Invert", lambda: self._pil_op(self._filter_invert)),
            ("Blur", lambda: self._pil_op(self._filter_blur)),
            ("Sharpen", lambda: self._pil_op(self._filter_sharpen)),
            ("Vignette", lambda: self._pil_op(self._filter_vignette)),
            ("Pixelate", lambda: self._pil_op(self._filter_pixelate)),
            ("Posterize", lambda: self._pil_op(self._filter_posterize)),
        ]:
            self.options_lay.addWidget(_tool_btn(label))

    def _opts_watermark(self):
        form = self._add_group("Text Watermark")
        self.wm_text = QLineEdit("CONFIDENTIAL")
        form.addRow("Text", self.wm_text)
        self.wm_opacity = self._add_slider_row(form, "Opacity", 5, 100, 30, "%")
        self.wm_size = self._add_slider_row(form, "Size", 16, 120, 48, "px")
        self._add_run_button("Add Watermark", self._run_watermark)

    def _opts_signature(self):
        form = self._add_group("Signature on Photo")
        self.sig_position = QComboBox()
        self.sig_position.addItems(["Bottom right", "Bottom left", "Top right", "Top left",
                                    "Centre"])
        form.addRow("Position", self.sig_position)
        self.sig_scale = self._add_slider_row(form, "Width", 10, 60, 28, "% of photo")
        self.sig_opacity = self._add_slider_row(form, "Opacity", 20, 100, 100, "%")
        add_btn = _tool_btn("✍️ Draw or type a signature")
        add_btn.clicked.connect(self._add_signature_to_photo)
        self.options_lay.addWidget(add_btn)
        hint = QLabel("Customers often need their signature stamped on a photo "
                      "or a certificate. The result saves automatically.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #727E96; font-size: 10px;")
        self.options_lay.addWidget(hint)

    def _add_signature_to_photo(self):
        """Stamps a drawn or typed signature onto the photo."""
        if not self.current_image:
            return
        try:
            from opal_studio.viewer_pdf import SignatureDialog
        except Exception as e:
            QMessageBox.warning(self, "Signature Unavailable", str(e))
            return
        dialog = SignatureDialog(self)
        if dialog.exec() != QDialog.Accepted or not dialog.signature_png:
            return
        self.push_history()
        result = self.composite_signature(
            dialog.signature_png,
            self.sig_position.currentText(),
            self.sig_scale.value(),
            self.sig_opacity.value())
        if result is None:
            QMessageBox.warning(self, "Signature Failed", "Could not read the signature.")
            return
        self.current_image = result
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("signed")

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

    def _opts_privacy(self):
        form = self._add_group("Privacy")
        note = QLabel("Detects every face in the photo and blurs it — useful before "
                      "sharing a picture online.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #A8B2C8; font-size: 11px; background: transparent;")
        form.addRow(note)
        self._add_run_button("Blur Faces", self._run_face_blur)

    def _run_face_blur(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "face_blur")
        if not res.success:
            QMessageBox.warning(self, "Blur Faces", res.message)
            return
        blurred = QImage(res.output_path)
        if blurred.isNull():
            QMessageBox.warning(self, "Blur Faces", "Could not read the result.")
            return
        self.push_history()
        self.current_image = blurred
        self.canvas.set_image(blurred)
        self._update_info()
        self.tip_label.setText(f"Saved automatically: {Path(res.output_path).name}")

    def _opts_meme(self):
        form = self._add_group("Meme Caption")
        self.meme_top = QLineEdit()
        self.meme_top.setPlaceholderText("Top caption")
        form.addRow("Top", self.meme_top)
        self.meme_bottom = QLineEdit()
        self.meme_bottom.setPlaceholderText("Bottom caption")
        form.addRow("Bottom", self.meme_bottom)
        self._add_run_button("Create Meme", self._run_meme)

    def _run_meme(self):
        from opal_studio.engine import OpalEngine
        options = {"top": self.meme_top.text(), "bottom": self.meme_bottom.text()}
        res = OpalEngine.execute_single(self.file_path, "meme", options)
        if not res.success:
            QMessageBox.warning(self, "Meme", res.message)
            return
        meme = QImage(res.output_path)
        if meme.isNull():
            QMessageBox.warning(self, "Meme", "Could not read the result.")
            return
        self.push_history()
        self.current_image = meme
        self.canvas.set_image(meme)
        self._update_info()
        self.tip_label.setText(f"Saved automatically: {Path(res.output_path).name}")

    def _opts_palette(self):
        self.options_lay.addWidget(QLabel("Dominant colors are extracted when you press Run."))
        self._add_run_button("Extract Palette", self._run_palette)
        self.palette_view = QWidget()
        self.palette_lay = QVBoxLayout(self.palette_view)
        self.options_lay.addWidget(self.palette_view)

    def _opts_exif(self):
        self.options_lay.addWidget(QLabel("Hidden camera, device and GPS data:"))
        self.exif_view = QTextEdit()
        self.exif_view.setReadOnly(True)
        self.exif_view.setStyleSheet("QTextEdit { background:#101625; color:#EDF1FA; "
                                     "border:1px solid rgba(255,255,255,0.10); border-radius:10px; padding:6px; "
                                     "font-family: Consolas; font-size: 10px; }")
        self.options_lay.addWidget(self.exif_view)
        strip = _tool_btn("🧹 Strip All Metadata")
        strip.clicked.connect(self._strip_metadata)
        self.options_lay.addWidget(strip)
        self._load_exif()

    def _opts_wallpaper(self):
        form = self._add_group("Wallpaper Maker")
        self.wall_res = QComboBox()
        try:
            import screeninfo
            monitors = screeninfo.get_monitors()
            for m in monitors[:3]:
                self.wall_res.addItem(f"{m.width}x{m.height}", (m.width, m.height))
        except Exception:
            pass
        self.wall_res.addItem("1920x1080", (1920, 1080))
        self.wall_res.addItem("2560x1440", (2560, 1440))
        form.addRow("Screen", self.wall_res)
        self.wall_mode = QComboBox()
        self.wall_mode.addItems(["Blurred fill", "Plain fill (crop)"])
        form.addRow("Style", self.wall_mode)
        self._add_run_button("Create Wallpaper", self._run_wallpaper)

    # ------------------------------------------------------------------
    # Loading & history
    # ------------------------------------------------------------------

    def _load_file(self):
        try:
            img = QImage(self.file_path)
            if img.isNull():
                # Retry via PIL (handles HEIC/AVIF edge cases)
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

    def _current_qimage(self) -> QImage:
        return self.current_image

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
            # Save the result next to the original automatically.
            tag = "nobg" if self.tool in ("background", "replace_bg") else "upscale"
            self._auto_save_result(tag)
            # Show before/after comparison briefly
            self.canvas.compare_split = 0.5
            self.canvas.update()
            QTimer.singleShot(3500, self._clear_compare)
        else:
            QMessageBox.warning(self, "Operation Failed", message)

    def _clear_compare(self):
        self.canvas.compare_split = None
        self.canvas.update()

    def _quick_remove_background(self):
        """One-click background removal using the chosen model."""
        model = "u2netp"
        if getattr(self, "bg_model", None) is not None:
            model = self.bg_model.currentData() or model
        self.set_tool("background")
        if not self._ensure_vision_engine():
            return
        self._run_worker("cutout", {"model": model, "mode": 0, "soft_edges": False})

    def _run_cutout(self):
        model = self.bg_model.currentData()
        mode = self.bg_mode.currentIndex() if hasattr(self, "bg_mode") else 0
        if not self._ensure_vision_engine():
            return
        self._run_worker("cutout", {"model": model, "soft_edges": self.soft_edges.isChecked(),
                                    "mode": mode, "color": getattr(self, "_bg_color", None)})

    def _ensure_vision_engine(self) -> bool:
        """Offers the one-time AI engine download when it is not installed yet."""
        try:
            from opal_studio import engine_packs
        except Exception:
            return True
        if engine_packs.vision_available():
            return True
        reply = QMessageBox.question(
            self, "AI engine needed",
            "Background removal needs the AI engine the first time "
            "(about 150 MB).\n\nDownload it now? It installs once and then works "
            "completely offline, with no account and no upload.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return False
        self.tip_label.setText("Downloading the AI engine - this happens once...")
        QApplication.processEvents()

        class _Worker(QThread):
            done = Signal(bool, str)

            def run(self):
                ok = engine_packs.install_vision_engine()
                self.done.emit(bool(ok), "AI engine ready." if ok else "Engine install failed.")

        worker = _Worker()
        worker.done.connect(self._engine_ready)
        worker.start()
        self._engine_worker = worker
        return False

    def _engine_ready(self, ok: bool, message: str):
        self.tip_label.setText(message)
        if ok:
            QMessageBox.information(self, "AI engine ready",
                                    "The engine is installed. Background removal now "
                                    "works offline, forever.")

    def _run_replace_bg(self):
        model = self.bg_model2.currentData()
        mode_idx = self.bg_mode.currentIndex()
        color = self._bg_color if mode_idx == 4 else None
        self._run_worker("cutout", {"model": model, "mode": mode_idx, "color": color})

    def _run_upscale(self):
        self._run_worker("upscale", {"model": self.upscale_model.currentData()})

    def _run_enhance(self):
        from PIL import Image, ImageOps, ImageEnhance
        mode = self.enhance_mode.currentText()
        self.push_history()
        img = self._qimage_to_pil(self.current_image).convert("RGB")
        img = ImageOps.autocontrast(img, cutoff=1)
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

    def _run_adjust(self):
        from PIL import Image, ImageEnhance
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
            QMessageBox.information(self, "Crop", "Drag a crop rectangle on the image first.")
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

    def _rotate_qimage(self, degrees: int):
        if not self.current_image:
            return
        self.push_history()
        transform = {90: Qt.FastTransformation, -90: Qt.FastTransformation}.get(degrees)
        from PySide6.QtGui import QTransform
        self.current_image = self.current_image.transformed(QTransform().rotate(degrees))
        self.canvas.set_image(self.current_image)
        self._update_info()

    def _flip_qimage(self, vertical: bool):
        if not self.current_image:
            return
        self.push_history()
        from PySide6.QtGui import QTransform
        self.current_image = self.current_image.transformed(
            QTransform().scale(-1 if not vertical else 1, -1 if vertical else 1))
        self.canvas.set_image(self.current_image)
        self._update_info()

    # -- PIL filter helpers --
    def _pil_op(self, func):
        self.push_history()
        img = func(self._qimage_to_pil(self.current_image))
        self.current_image = self._pil_to_qimage(img)
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("filtered")

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

    def _run_watermark(self):
        if not self.current_image:
            return
        from opal_studio.pdf_tools import _watermark_pil
        self.push_history()
        text = self.wm_text.text().strip() or "CONFIDENTIAL"
        opacity = self.wm_opacity.value() / 100.0
        size = self.wm_size.value()
        base = self._qimage_to_pil(self.current_image).convert("RGBA")
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

    def _run_palette(self):
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
            from PIL import ExifTags
            lines = []
            from PIL import Image
            pil = Image.open(self.file_path)
            exif = pil.getexif()
            if not exif:
                lines.append("No EXIF metadata found.")
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                lines.append(f"{tag}: {value}")
            self.exif_view.setPlainText("\n".join(lines))
        except Exception as e:
            self.exif_view.setPlainText(f"Could not read EXIF: {e}")

    def _strip_metadata(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "strip_metadata")
        if res.success:
            QMessageBox.information(self, "Metadata Stripped", res.message)
            self._load_exif()
        else:
            QMessageBox.warning(self, "Strip Failed", res.message)

    def _run_wallpaper(self):
        if not self.current_image:
            return
        from PIL import Image, ImageFilter
        w, h = self.wall_res.currentData()
        self.push_history()
        pil = self._qimage_to_pil(self.current_image).convert("RGB")
        style = self.wall_mode.currentText()
        scale = max(w / pil.width, h / pil.height)
        cover = pil.resize((max(w, int(pil.width * scale)), max(h, int(pil.height * scale))),
                           Image.Resampling.LANCZOS)
        left, top = (cover.width - w) // 2, (cover.height - h) // 2
        cover = cover.crop((left, top, left + w, top + h))
        if style.startswith("Blurred"):
            blurred = cover.filter(ImageFilter.GaussianBlur(28))
        else:
            blurred = cover
        self.current_image = self._pil_to_qimage(blurred)
        self.canvas.set_image(self.current_image)
        self._update_info()
        self._auto_save_result("wallpaper", suffix=".jpg")
        self.tip_label.setText(f"Wallpaper ready ({w}x{h}) - saved next to the original.")

    # ------------------------------------------------------------------
    # Save / copy
    # ------------------------------------------------------------------

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
        """
        Saves the processed image next to the original straight away - no dialog,
        no "where do you want it" question. The customer just picks up the file.
        """
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
            self.tip_label.setText(f"Could not save the result: {e}")
            return None

    def _copy_image(self):
        if not self.current_image:
            return
        QApplication.clipboard().setImage(self.current_image)
        self.tip_label.setText("Image copied to clipboard (alpha preserved).")

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

    def _save_as(self):
        if not self.current_image:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Image As", str(Path(self.file_path).parent),
                                              "PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;BMP (*.bmp)")
        if not path:
            return
        self.current_image.save(path)
        self.tip_label.setText(f"Saved {Path(path).name}")

    def _fit_clicked(self):
        self.canvas.fit_to_view()
        self.canvas.update()

    def _actual_size(self):
        self.canvas.zoom = 1.0
        self.canvas.offset = QPointF(0, 0)
        self.canvas.update()
