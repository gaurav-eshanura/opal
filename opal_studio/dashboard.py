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
from opal_studio.icons import ICONS, mark_icon
from opal_studio.theme import (BG, BG_SUNK, FIELD, SURFACE, TEXT, TEXT_DIM, TEXT_FAINT,
                              ACCENT_HI, ACCENT_WASH, LEAF, LEAF_SOFT, LINE,
                              RADIUS, RADIUS_LARGE, PANEL_CSS,
                              title_label, head_label, section_label, body_label, hint_label)
from opal_studio.tray import create_opal_icon


class DashboardDropZone(QFrame):
    """Large interactive drop zone in the center of the dashboard."""
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(216)
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
        cy = h / 2.0 - 28
        from opal_studio.icons import mark_icon
        emblem = mark_icon(84).pixmap(84, 84)
        if self.is_hovered or self.is_drag_over:
            painter.setOpacity(1.0)
        else:
            painter.setOpacity(0.88)
        painter.drawPixmap(QPoint(int(cx - 42), int(cy - 42)), emblem)
        painter.setOpacity(1.0)

        # Labels
        painter.setFont(QFont("Segoe UI", 15, QFont.Bold))
        painter.setPen(QPen(QColor("#EDF1FA")))
        label_text = "Drop a file to convert it" if not self.is_drag_over else "Release to open the wheel"
        painter.drawText(QRectF(0, cy + 42, w, 26), Qt.AlignCenter, label_text)

        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(QPen(QColor(TEXT_DIM)))
        sub_text = ("Hold Shift to convert  •  Alt for tools  •  Ctrl for actions")
        painter.drawText(QRectF(0, cy + 72, w, 22), Qt.AlignCenter, sub_text)


class OpalDashboard(QWidget):
    """The visible Command Center for Opal."""
    files_selected = Signal(list)
    radial_test_requested = Signal()
    settings_requested = Signal()
    history_requested = Signal()
    toggle_orb_requested = Signal()
    studio_requested = Signal()
    feature_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opal — Every file, in every light")
        self.setWindowIcon(create_opal_icon(64))
        self.resize(680, 560)
        self.setMinimumSize(620, 520)

        self.setStyleSheet(f"""
            QWidget {{
                background: {FIELD};
                color: {TEXT};
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
            }}
            QPushButton {{
                background-color: rgba(255,255,255,0.05);
                color: #EDF1FA;
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: {RADIUS}px;
                padding: 8px 16px;
                min-height: 32px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.08);
                border-color: {ACCENT_HI};
                color: #C9C4FF;
            }}
            QPushButton#primaryBtn {{
                background-color: #6C63FF;
                border: 1px solid #6C63FF;
                color: #FFFFFF;
                font-size: 11px;
                padding: 8px 18px;
                min-height: 32px;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: #8A83FF;
            }}
            QCheckBox {{
                font-size: 11px;
                color: {TEXT_DIM};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.16);
                background-color: rgba(255,255,255,0.05);
            }}
            QCheckBox::indicator:checked {{
                background-color: #6C63FF;
                border-color: #6C63FF;
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 1. Header Bar
        header = QHBoxLayout()
        header.setSpacing(12)

        # App Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        brand_mark = QLabel()
        brand_mark.setPixmap(mark_icon(32).pixmap(32, 32))
        title_row.addWidget(brand_mark)

        title_lbl = head_label("Opal")
        title_row.addWidget(title_lbl)

        self.status_pill = QLabel("Active & Running")
        self.status_pill.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.status_pill.setStyleSheet(f"""
            background-color: {LEAF_SOFT};
            color: {LEAF};
            border: 1px solid rgba(55, 201, 138, 0.35);
            border-radius: 999px;
            padding: 3px 10px;
        """)
        title_row.addWidget(self.status_pill)
        title_row.addStretch()
        title_box.addLayout(title_row)

        title_box.addWidget(body_label(
            "Convert, edit and sign files on your own computer — nothing is ever uploaded.", dim=True))

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
        btn_row.setSpacing(8)

        def _icon_btn(text, icon_key, tip, slot, accent=False):
            btn = QPushButton(text)
            btn.setIcon(ICONS[icon_key](15))
            btn.setIconSize(QSize(15, 15))
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            if accent:
                btn.setProperty("accent", "true")
            return btn

        btn_row.addWidget(_icon_btn("Select files…", "folder",
                                    "Pick files from disk", self._on_choose_files))
        btn_row.addWidget(_icon_btn("Clipboard screenshot", "clip",
                                    "Convert a Win+Shift+S screenshot", self._on_clipboard_clicked))
        btn_row.addWidget(_icon_btn("See the wheel", "cursor",
                                    "Shows the key-press wheel with a sample file",
                                    self.radial_test_requested.emit))
        btn_row.addStretch()

        studio_btn = _icon_btn("Open Floating Studio", "layers",
                               "PDF editor, AI image lab, media player and document viewer",
                               self.studio_requested.emit, accent=True)
        btn_row.addWidget(studio_btn)

        main_layout.addLayout(btn_row)

        # 4. Feature Cards
        main_layout.addWidget(section_label("Popular right now"))
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        card1 = self._create_feature_card("Remove Background", "Local AI cutout, transparent PNG",
                                         "Saved next to your photo", "layers", feature_key="remove_bg")
        card2 = self._create_feature_card("PDF Studio", "Sign, search, redact, export",
                                         "A full PDF editor, not a viewer", "doc", feature_key="pdf_studio")
        card3 = self._create_feature_card("WhatsApp Ready", "Shrink photos and PDFs to share",
                                          "Hold Alt while dragging", "compress", feature_key="whatsapp")
        card4 = self._create_feature_card("Auto Watch Folder", "Dropped files convert themselves",
                                          "Downloads / Opal_Auto", "folder", feature_key="watch_folder")

        for card in (card1, card2, card3, card4):
            cards_layout.addWidget(card, 1)

        main_layout.addLayout(cards_layout)

        # 5. Bottom Status / Options Bar
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(hint_label("Global hotkey"))
        kbd = QLabel("Ctrl + Alt + T")
        kbd.setStyleSheet(f"""
            background: {SURFACE}; border: 1px solid rgba(255,255,255,0.16);
            border-bottom-width: 2px; border-radius: 6px; padding: 2px 8px;
            color: {ACCENT_HI}; font-size: 10px; font-weight: 700;
        """)
        bottom_row.addWidget(kbd)

        bottom_row.addStretch()

        self.orb_checkbox = QCheckBox("Show the drop target on the desktop edge")
        config = ConfigManager.load_config()
        self.orb_checkbox.setChecked(config.get("show_drop_dock", True))
        self.orb_checkbox.toggled.connect(self._on_orb_toggle)
        bottom_row.addWidget(self.orb_checkbox)

        main_layout.addLayout(bottom_row)

    def _make_feature_click(self, card: QFrame, feature_key: str):
        """Build a mouse handler that asks the app to run the card's feature."""
        def handler(event):
            if event.button() == Qt.LeftButton:
                self.feature_requested.emit(feature_key)
            QFrame.mouseReleaseEvent(card, event)
        return handler

    def _create_feature_card(self, title: str, desc: str, hint: str, icon_key: str,
                             feature_key: str = "") -> QFrame:
        """One glass card: an icon tile, a white title, detail, and a hint.

        A card with a feature key is clickable and asks the app to run that
        feature; a card without one is a plain caption.
        """
        card = QFrame()
        card.setObjectName("featureCard")
        card.setStyleSheet(f"""
            QFrame#featureCard {{
                background: rgba(255,255,255,0.04);
                border: 1px solid {LINE};
                border-radius: {RADIUS}px;
            }}
            QFrame#featureCard:hover {{ border-color: {ACCENT_HI}; background: rgba(255,255,255,0.06); }}
            QFrame#featureCard QLabel {{ background: transparent; border: none; }}
            QFrame#featureCard QFrame#iconTile {{
                background: {ACCENT_WASH};
                border: 1px solid rgba(138,131,255,0.35);
                border-radius: 10px;
            }}
        """)
        if feature_key:
            card.setCursor(Qt.PointingHandCursor)
            card.setToolTip(f"Open {title}")
            card.mouseReleaseEvent = self._make_feature_click(card, feature_key)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        tile = QFrame()
        tile.setObjectName("iconTile")
        tile.setFixedSize(34, 34)
        tile_lay = QHBoxLayout(tile)
        tile_lay.setContentsMargins(0, 0, 0, 0)
        tile_icon = QLabel()
        tile_icon.setPixmap(ICONS[icon_key](18).pixmap(18, 18))
        tile_lay.addWidget(tile_icon, 0, Qt.AlignCenter)
        layout.addWidget(tile)

        layout.addWidget(body_label(title))

        d_lbl = body_label(desc, dim=True)
        d_lbl.setWordWrap(True)
        layout.addWidget(d_lbl)

        h_lbl = hint_label(hint)
        h_lbl.setWordWrap(True)
        layout.addWidget(h_lbl)
        layout.addStretch()

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

    def set_queue_status(self, running: bool, queued: int):
        """The header pill says what the app is doing right now: one job
        running, and how many more are waiting their turn."""
        if running:
            text = f"Working · {queued} queued" if queued else "Working…"
            self.status_pill.setText(text)
            self.status_pill.setStyleSheet(f"""
                background-color: {ACCENT_WASH};
                color: {ACCENT_HI};
                border: 1px solid rgba(108, 99, 255, 0.40);
                border-radius: 999px;
                padding: 3px 10px;
            """)
        else:
            self.status_pill.setText("Active & Running")
            self.status_pill.setStyleSheet(f"""
                background-color: {LEAF_SOFT};
                color: {LEAF};
                border: 1px solid rgba(55, 201, 138, 0.35);
                border-radius: 999px;
                padding: 3px 10px;
            """)

    def closeEvent(self, event):
        # Minimize to system tray instead of exiting the entire background engine
        event.ignore()
        self.hide()
