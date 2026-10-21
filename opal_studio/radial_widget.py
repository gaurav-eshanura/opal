"""
Opal - Production Radial Wheel Overlay
Plain English: This creates the smooth circular pie menu that opens under your cursor.
It handles single files, multiple files at once, and switches instantly between Convert, Tools, and Actions.
"""

import math
from pathlib import Path
from typing import List, Dict, Optional
from PySide6.QtCore import Qt, QPoint, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath, QLinearGradient, QCursor
from PySide6.QtWidgets import QWidget

from opal_studio.engine import OpalEngine


class RadialMenuWidget(QWidget):
    # Emits (file_paths, action_id)
    action_selected = Signal(list, str)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMouseTracking(True)

        self.size_px = 400
        self.resize(self.size_px, self.size_px)

        self.center_radius = 62
        self.outer_radius = 175
        self.center_pt = QPoint(self.size_px // 2, self.size_px // 2)

        self.file_paths: List[str] = []
        self.mode = "convert"  # 'convert' (Shift), 'tools' (Alt), 'actions' (Ctrl)
        self.options: List[Dict[str, str]] = []
        self.hovered_index = -1

        # Brand colours: warm off-white wheel, one tangerine accent
        self.color_fire = QColor("#8A5CF6")
        self.color_fire_glow = QColor("#EE4E8A")
        self.color_dark_bg = QColor(22, 27, 42, 238)
        self.color_inner = QColor(30, 36, 54, 248)
        self.color_border = QColor(255, 255, 255, 40)
        self.color_text = QColor("#EDF1FA")
        self.color_text_dim = QColor("#A8B2C8")

    def show_for_files(self, file_paths: List[str], screen_pos: Optional[QPoint] = None, initial_mode: str = "convert"):
        self.file_paths = file_paths
        self.mode = initial_mode
        self.load_options()

        if screen_pos is None:
            screen_pos = QCursor.pos()

        # Center radial menu directly on mouse
        x = screen_pos.x() - self.size_px // 2
        y = screen_pos.y() - self.size_px // 2
        self.move(x, y)
        self.hovered_index = -1
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.update()

    def show_for_file(self, file_path: str, screen_pos: Optional[QPoint] = None, initial_mode: str = "convert"):
        self.show_for_files([file_path], screen_pos, initial_mode)

    def load_options(self):
        if not self.file_paths:
            self.options = []
            return
        self.options = OpalEngine.get_options_for_files(self.file_paths, self.mode)
        self.update()

    def set_mode(self, mode: str):
        if self.mode != mode:
            self.mode = mode
            self.load_options()
            self.hovered_index = -1
            self.update()

    # --- EVENTS ---

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Shift,):
            self.set_mode("convert")
        elif key in (Qt.Key_Alt, Qt.Key_Meta):
            self.set_mode("tools")
        elif key in (Qt.Key_Control,):
            self.set_mode("actions")
        elif key == Qt.Key_Escape:
            self.close()
            self.cancelled.emit()
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if 0 <= self.hovered_index < len(self.options):
                self._trigger_current()
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        dx = pos.x() - self.center_pt.x()
        dy = pos.y() - self.center_pt.y()
        dist = math.hypot(dx, dy)

        if dist < self.center_radius or dist > self.outer_radius + 40:
            new_hover = -1
        else:
            if not self.options:
                new_hover = -1
            else:
                n = len(self.options)
                slice_deg = 360.0 / n
                # Angle in degrees where top is 0, clockwise
                angle = (math.degrees(math.atan2(dy, dx)) + 90.0) % 360.0
                new_hover = int(angle // slice_deg) % n

        if new_hover != self.hovered_index:
            self.hovered_index = new_hover
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if 0 <= self.hovered_index < len(self.options):
                self._trigger_current()
            else:
                self.close()
                self.cancelled.emit()
        super().mouseReleaseEvent(event)

    def _trigger_current(self):
        if 0 <= self.hovered_index < len(self.options):
            selected = self.options[self.hovered_index]
            self.close()
            self.action_selected.emit(self.file_paths, selected["id"])

    # --- DRAWING RADIAL WHEEL ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        cx, cy = self.center_pt.x(), self.center_pt.y()
        n = len(self.options)

        # 1. Outer Wedges
        if n > 0:
            slice_deg = 360.0 / n
            for i, opt in enumerate(self.options):
                start_angle = -90.0 + (i * slice_deg)
                span_angle = slice_deg

                is_active = (i == self.hovered_index)
                wedge_path = self._build_wedge_path(cx, cy, self.center_radius, self.outer_radius, start_angle, span_angle)

                if is_active:
                    gradient = QLinearGradient(cx, cy - self.outer_radius, cx, cy + self.outer_radius)
                    gradient.setColorAt(0, self.color_fire_glow)
                    gradient.setColorAt(1, self.color_fire)
                    painter.setBrush(QBrush(gradient))
                    painter.setPen(QPen(QColor(255, 255, 255, 235), 2))
                else:
                    painter.setBrush(QBrush(self.color_dark_bg))
                    painter.setPen(QPen(self.color_border, 1.2))

                painter.drawPath(wedge_path)

                # Label placement - with many slices only the hovered one is
                # labelled, otherwise the wheel turns into unreadable soup.
                show_label = (n <= 10) or (i == self.hovered_index)
                if show_label:
                    mid_angle_deg = start_angle + (span_angle / 2.0)
                    mid_angle_rad = math.radians(mid_angle_deg)
                    label_radius = (self.center_radius + self.outer_radius) / 2.0

                    lx = cx + label_radius * math.cos(mid_angle_rad)
                    ly = cy + label_radius * math.sin(mid_angle_rad)

                    painter.save()
                    painter.translate(lx, ly)

                    label_font = QFont("Segoe UI", 11, QFont.Bold if is_active else QFont.DemiBold)
                    painter.setFont(label_font)
                    if n > 10:
                        painter.setPen(QPen(QColor(255, 255, 255)))
                        label_rect = QRectF(-70, -13, 140, 26)
                        painter.drawText(label_rect, Qt.AlignCenter, opt["label"])
                    else:
                        painter.setPen(QPen(Qt.white if is_active else self.color_text))
                        label_rect = QRectF(-65, -12, 130, 24)
                        painter.drawText(label_rect, Qt.AlignCenter, opt["label"])

                    painter.restore()

        # 2. Center Hub
        center_path = QPainterPath()
        center_path.addEllipse(QPoint(cx, cy), self.center_radius, self.center_radius)
        painter.setBrush(QBrush(self.color_inner))
        painter.setPen(QPen(QColor(255, 154, 60, 220), 2.5))
        painter.drawPath(center_path)

        # Center Content
        if self.file_paths:
            if len(self.file_paths) == 1:
                p = Path(self.file_paths[0])
                header_text = p.name
                if len(header_text) > 13:
                    header_text = header_text[:11] + "…"
            else:
                category = OpalEngine.get_file_category(self.file_paths)
                header_text = f"{len(self.file_paths)} {category.capitalize()}s"

            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(self.color_text))
            painter.drawText(QRectF(cx - 55, cy - 34, 110, 20), Qt.AlignCenter, header_text)

            # Active Mode Pill
            mode_text = {
                "convert": "⇧ Convert",
                "tools": "⌥ Tools",
                "actions": "⌃ Actions",
            }.get(self.mode, "Opal")

            pill_rect = QRectF(cx - 44, cy - 9, 88, 20)
            painter.setBrush(QBrush(QColor(255, 154, 60, 0.16)))
            painter.setPen(QPen(self.color_fire, 1))
            painter.drawRoundedRect(pill_rect, 10, 10)

            painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            painter.setPen(QPen(self.color_fire))
            painter.drawText(pill_rect, Qt.AlignCenter, mode_text)

            # Shortcut Tip
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QPen(self.color_text_dim))
            painter.drawText(QRectF(cx - 55, cy + 16, 110, 16), Qt.AlignCenter, "Shift / Alt / Ctrl")

        # 3. Active Description Banner
        if 0 <= self.hovered_index < len(self.options):
            active_opt = self.options[self.hovered_index]
            banner_rect = QRectF(cx - 120, self.size_px - 34, 240, 26)
            painter.setBrush(QBrush(QColor(30, 36, 54, 240)))
            painter.setPen(QPen(QColor(255, 154, 60, 150), 1.2))
            painter.drawRoundedRect(banner_rect, 13, 13)

            painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            painter.setPen(QPen(self.color_text))
            painter.drawText(banner_rect, Qt.AlignCenter, active_opt.get("desc", active_opt["label"]))

    def _build_wedge_path(self, cx: float, cy: float, r_in: float, r_out: float, start_deg: float, span_deg: float) -> QPainterPath:
        path = QPainterPath()
        outer_rect = QRectF(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
        inner_rect = QRectF(cx - r_in, cy - r_in, r_in * 2, r_in * 2)

        path.arcMoveTo(outer_rect, -start_deg)
        path.arcTo(outer_rect, -start_deg, -span_deg)

        end_deg = start_deg + span_deg
        path.arcTo(inner_rect, -end_deg, span_deg)
        path.closeSubpath()
        return path
