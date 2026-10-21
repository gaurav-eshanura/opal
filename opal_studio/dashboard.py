"""
Opal - Main Dashboard & Command Center
Plain English: This is the visible main window that opens when you launch Opal.
It shows that Opal is running, lets you drop files, paste clipboard screenshots,
and test the radial wheel directly.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QPoint, QRectF, QSize
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QPainterPath, QCursor, QDragEnterEvent, QDropEvent, QIcon, QPixmap
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QApplication, QCheckBox
)

from opal_studio.config import ConfigManager
from opal_studio.tray import create_opal_icon


class DashboardDropZone(QFrame):
    """Large interactive drop zone in the center of the dashboard."""
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(190)
        self.is_drag_over = False
        self.is_hovered = False
        self.setCursor(Qt.PointingHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.is_drag_over = True
            self.update()

    def dragLeaveEvent(self, event):
        self.is_drag_over = False
        self.update()

    def dropEvent(self, event: QDropEvent):
        self.is_drag_over = False
        self.update()
        urls = event.mimeData().urls()
        valid = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if valid:
            self.files_dropped.emit(valid)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select File(s) for Opal",
                "",
                "All Files (*.*)"
            )
            if files:
                self.files_dropped.emit(files)

    def paintEvent(self, event):
        from opal_studio.glass import paint_glass_sheet, caustic_glow, spectral_brush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w, h = self.width(), self.height()
        rect = QRectF(4, 4, w - 8, h - 8)

        if self.is_drag_over:
            # Lit: the fire shows through the glass.
            glow = QLinearGradient(0, 0, w, h)
            glow.setColorAt(0, QColor(138, 92, 246, 70))
            glow.setColorAt(1, QColor(255, 154, 60, 40))
            painter.setBrush(QBrush(glow))
            painter.setPen(QPen(QColor(160, 140, 255, 230), 2.2, Qt.DashLine))
            painter.drawRoundedRect(rect, 18, 18)
            caustic_glow(painter, rect, 18, strength=1.6)
        else:
            paint_glass_sheet(painter, rect, 18,
                              fill_top=34 if self.is_hovered else 20,
                              fill_bottom=12, edge=True, shadow=True)
            if self.is_hovered:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(140, 131, 255, 190), 1.6,
                                    Qt.SolidLine if self.is_hovered else Qt.DashLine))
                painter.drawRoundedRect(rect, 18, 18)
            else:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255, 40), 1.4, Qt.DashLine))
                painter.drawRoundedRect(rect, 18, 18)

        # The Opal mark, floating in the middle of the drop area.
        cx = w / 2.0
        cy = h / 2.0 - 24
        from opal_studio.icons import mark_icon
        emblem = mark_icon(72).pixmap(72, 72)
        if self.is_hovered or self.is_drag_over:
            painter.setOpacity(1.0)
        else:
            painter.setOpacity(0.88)
        painter.drawPixmap(QPoint(int(cx - 36), int(cy - 36)), emblem)
        painter.setOpacity(1.0)

        # Labels
        painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
        painter.setPen(QPen(QColor("#EDF1FA")))
        label_text = "Drop a file to convert it" if not self.is_drag_over else "Release to open the wheel"
        painter.drawText(QRectF(0, cy + 34, w, 24), Qt.AlignCenter, label_text)

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QPen(QColor("#727E96")))
        sub_text = ("Hold Shift to convert  •  Alt for tools  •  Ctrl for actions")
        painter.drawText(QRectF(0, cy + 60, w, 20), Qt.AlignCenter, sub_text)


class OpalDashboard(QWidget):
    """The visible Command Center for Opal."""
    files_selected = Signal(list)
    radial_test_requested = Signal()
    settings_requested = Signal()
    history_requested = Signal()
    toggle_orb_requested = Signal()
    studio_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opal — Every file, in every light")
        self.setWindowIcon(create_opal_icon(64))
        self.resize(680, 560)
        self.setMinimumSize(620, 520)

        self.setStyleSheet("""
            QWidget {
                background-color: #101625;
                color: #EDF1FA;
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.05);
                color: #EDF1FA;
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.05);
                border-color: #6C63FF;
                color: #C9C4FF;
            }
            QPushButton#primaryBtn {
                background-color: #6C63FF;
                border: 1px solid #6C63FF;
                color: #FFFFFF;
                font-size: 12px;
                padding: 12px 22px;
            }
            QPushButton#primaryBtn:hover {
                background-color: #8A83FF;
            }
            QCheckBox {
                font-size: 11px;
                color: #A8B2C8;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(40,43,41,0.20);
                background-color: rgba(255,255,255,0.05);
            }
            QCheckBox::indicator:checked {
                background-color: #6C63FF;
                border-color: #6C63FF;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # 1. Header Bar
        header = QHBoxLayout()
        header.setSpacing(14)

        # App Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        from opal_studio.icons import mark_icon
        brand_mark = QLabel()
        brand_mark.setPixmap(mark_icon(30).pixmap(30, 30))
        title_row.addWidget(brand_mark)

        title_label = QLabel("Opal")
        title_label.setFont(QFont("Segoe UI", 17, QFont.Bold))
        title_label.setStyleSheet("color: #EDF1FA;")
        title_row.addWidget(title_label)

        status_pill = QLabel("Active & Running")
        status_pill.setFont(QFont("Segoe UI", 8, QFont.Bold))
        status_pill.setStyleSheet("""
            background-color: rgba(47, 158, 99, 0.10);
            color: #2F7D52;
            border: 1px solid rgba(47, 158, 99, 0.30);
            border-radius: 10px;
            padding: 3px 10px;
        """)
        title_row.addWidget(status_pill)
        title_row.addStretch()
        title_box.addLayout(title_row)

        sub_label = QLabel("Convert, edit and sign files on your own computer — nothing is ever uploaded.")
        sub_label.setFont(QFont("Segoe UI", 9))
        sub_label.setStyleSheet("color: #727E96;")
        title_box.addWidget(sub_label)

        header.addLayout(title_box)

        # Settings & History Buttons in header
        hist_btn = QPushButton("History")
        hist_btn.clicked.connect(self.history_requested.emit)
        header.addWidget(hist_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.settings_requested.emit)
        header.addWidget(settings_btn)

        main_layout.addLayout(header)

        # 2. Central Big Drop Zone
        self.drop_zone = DashboardDropZone(self)
        self.drop_zone.files_dropped.connect(self.files_selected.emit)
        main_layout.addWidget(self.drop_zone)

        # 3. Action Buttons Row (File Picker + Clipboard Screenshot + Test Wheel)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        choose_file_btn = QPushButton("Select files…")
        choose_file_btn.clicked.connect(self._on_choose_files)
        btn_row.addWidget(choose_file_btn)

        clipboard_btn = QPushButton("Convert clipboard screenshot")
        clipboard_btn.setToolTip("Windows + Shift + S")
        clipboard_btn.clicked.connect(self._on_clipboard_clicked)
        btn_row.addWidget(clipboard_btn)

        test_wheel_btn = QPushButton("See how it works")
        test_wheel_btn.setToolTip("Shows the key-press wheel with a sample file")
        test_wheel_btn.clicked.connect(self.radial_test_requested.emit)
        btn_row.addWidget(test_wheel_btn)

        studio_btn = QPushButton("Open Floating Studio")
        studio_btn.setToolTip("PDF editor, AI image lab, media player and document viewer")
        studio_btn.setProperty("accent", "true")
        studio_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                    stop: 0 #8A5CF6, stop: 0.55 #EE4E8A, stop: 1 #FF9A3C);
                          color: #FFFFFF; border: none;
                          border-radius: 12px; padding: 9px 20px;
                          font-size: 12px; font-weight: 700; }
            QPushButton:hover { background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                          stop: 0 #9B7BFF, stop: 0.55 #FF6BA0, stop: 1 #FFB35C); }
        """)
        studio_btn.clicked.connect(self.studio_requested.emit)
        btn_row.addWidget(studio_btn)

        main_layout.addLayout(btn_row)

        # 4. Feature Cards Banner
        cards_frame = QFrame()
        cards_frame.setObjectName("cardsFrame")
        cards_frame.setStyleSheet("""
            QFrame#cardsFrame {
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 18px;
            }
            QFrame#cardsFrame QFrame#featureCard {
                background-color: #0B0E18;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 14px;
            }
            QFrame#cardsFrame QLabel { background: transparent; border: none; }
        """)
        cards_layout = QHBoxLayout(cards_frame)
        cards_layout.setSpacing(12)
        cards_layout.setContentsMargins(12, 12, 12, 12)

        card1 = self._create_feature_card("Remove Background", "Local AI cutout, transparent PNG",
                                         "Saved next to your photo")
        card2 = self._create_feature_card("PDF Studio", "Sign, search, redact, export",
                                         "A full PDF editor, not a viewer")
        card3 = self._create_feature_card("WhatsApp Ready", "Shrink photos and PDFs to share",
                                          "Hold Alt while dragging")
        card4 = self._create_feature_card("Auto Watch Folder", "Dropped files convert themselves",
                                          "Downloads / Opal_Auto")

        for card in (card1, card2, card3, card4):
            cards_layout.addWidget(card, 1)

        main_layout.addWidget(cards_frame)

        # 5. Bottom Status / Options Bar
        bottom_row = QHBoxLayout()
        hotkey_lbl = QLabel("Global Hotkey: <b style='color:#A79FFF;'>Ctrl + Alt + T</b>")
        hotkey_lbl.setFont(QFont("Segoe UI", 9))
        hotkey_lbl.setStyleSheet("color: #727E96;")
        bottom_row.addWidget(hotkey_lbl)

        bottom_row.addStretch()

        self.orb_checkbox = QCheckBox("Show the drop target on the desktop edge")
        config = ConfigManager.load_config()
        self.orb_checkbox.setChecked(config.get("show_drop_dock", True))
        self.orb_checkbox.toggled.connect(self._on_orb_toggle)
        bottom_row.addWidget(self.orb_checkbox)

        main_layout.addLayout(bottom_row)

    def _create_feature_card(self, title: str, desc: str, hint: str) -> QFrame:
        """One bordered card: title, one line of detail, and a quiet hint."""
        card = QFrame()
        card.setObjectName("featureCard")
        card.setStyleSheet("""
            QFrame#featureCard {
                background-color: #0B0E18;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 14px;
            }
            QFrame#featureCard:hover { border-color: rgba(255,82,0,0.45); }
            QFrame#featureCard QLabel { background: transparent; border: none; }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(3)
        layout.setContentsMargins(16, 14, 16, 14)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        t_lbl.setStyleSheet("color: #A79FFF; background: transparent;")
        layout.addWidget(t_lbl)

        d_lbl = QLabel(desc)
        d_lbl.setFont(QFont("Segoe UI", 9))
        d_lbl.setStyleSheet("color: #A8B2C8; background: transparent;")
        d_lbl.setWordWrap(True)
        layout.addWidget(d_lbl)

        h_lbl = QLabel(hint)
        h_lbl.setFont(QFont("Segoe UI", 8))
        h_lbl.setStyleSheet("color: #727E96; background: transparent;")
        h_lbl.setWordWrap(True)
        layout.addWidget(h_lbl)

        return card

    def _on_choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select File(s) to Convert with Opal",
            "",
            "All Files (*.*)"
        )
        if files:
            self.files_selected.emit(files)

    def _on_clipboard_clicked(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasUrls():
            valid = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if valid:
                self.files_selected.emit(valid)
                return
        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                import time
                target_dir = Path.home() / "Downloads"
                target_dir.mkdir(parents=True, exist_ok=True)
                temp_file = target_dir / f"Screenshot_{int(time.time())}.png"
                image.save(str(temp_file), "PNG")
                self.files_selected.emit([str(temp_file)])
                return

        # If nothing on clipboard
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "No Image on Clipboard",
            "Take a screenshot using Win+Shift+S first, then click this button to convert it instantly!"
        )

    def _on_orb_toggle(self, checked: bool):
        config = ConfigManager.load_config()
        config["show_drop_dock"] = checked
        ConfigManager.save_config(config)
        self.toggle_orb_requested.emit()

    def closeEvent(self, event):
        # Minimize to system tray instead of exiting the entire background engine
        event.ignore()
        self.hide()
