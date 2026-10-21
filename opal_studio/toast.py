"""
Opal - Floating Notification Toast
Plain English: This displays a clean desktop toast notification at the bottom-right of your screen
when a conversion finishes, giving you one-click buttons to open the new file or reveal it in File Explorer.
"""

import os
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget, QApplication, QPushButton, QHBoxLayout, QVBoxLayout, QLabel


class OpalToast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.SubWindow
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(340, 95)

        self.target_path = None
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.close)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        self.title_label = QLabel("Conversion Complete")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #EDF1FA; background: transparent;")
        layout.addWidget(self.title_label)

        self.detail_label = QLabel("Saved new file.")
        self.detail_label.setFont(QFont("Segoe UI", 8))
        self.detail_label.setStyleSheet("color: #A8B2C8; background: transparent;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_open = QPushButton("Open File")
        self.btn_open.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        self.btn_open.setStyleSheet("""
            QPushButton {
                background-color: #6C63FF;
                color: #FFFFFF;
                border-radius: 10px;
                padding: 5px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #8A83FF;
            }
        """)
        self.btn_open.clicked.connect(self._on_open_clicked)
        btn_layout.addWidget(self.btn_open)

        self.btn_folder = QPushButton("Show in Folder")
        self.btn_folder.setFont(QFont("Segoe UI", 8))
        self.btn_folder.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.05);
                color: #EDF1FA;
                border-radius: 10px;
                padding: 5px 12px;
                border: 1px solid rgba(255,255,255,0.16);
            }
            QPushButton:hover {
                background-color: rgba(108,99,255,0.18);
                color: #C9C4FF;
            }
        """)
        self.btn_folder.clicked.connect(self._on_folder_clicked)
        btn_layout.addWidget(self.btn_folder)

        layout.addLayout(btn_layout)

    def show_message(self, title: str, message: str, target_path: str = None, is_error: bool = False):
        self.target_path = target_path
        self.title_label.setText(title)
        self.detail_label.setText(message)

        if is_error:
            self.title_label.setStyleSheet("color: #C0392B; background: transparent;")
            self.btn_open.hide()
            self.btn_folder.hide()
        else:
            self.title_label.setStyleSheet("color: #A79FFF; background: transparent;")
            self.btn_open.setVisible(bool(target_path and os.path.exists(target_path)))
            self.btn_folder.setVisible(bool(target_path and os.path.exists(target_path)))

        # Position at bottom-right corner of active screen
        screen = QApplication.primaryScreen().geometry()
        margin = 25
        x = screen.width() - self.width() - margin
        y = screen.height() - self.height() - margin - 40  # Above Windows taskbar
        self.move(x, y)

        self.show()
        self.raise_()
        self.auto_close_timer.start(5500)

    def _on_open_clicked(self):
        if self.target_path and os.path.exists(self.target_path):
            from opal_studio.platform_compat import open_with_default
            open_with_default(self.target_path)
            self.close()

    def _on_folder_clicked(self):
        if self.target_path and os.path.exists(self.target_path):
            from opal_studio.platform_compat import reveal_in_file_manager
            reveal_in_file_manager(self.target_path)
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(0, 0, self.width(), self.height())
        painter.setBrush(QBrush(QColor(255, 255, 255, 250)))
        painter.setPen(QPen(QColor(255, 82, 0, 170), 1.4))
        painter.drawRoundedRect(rect, 16, 16)
