"""
Opal - Conversion History Dialog
Plain English: This window displays a history of files you converted with Opal,
allowing you to quickly open past files or reveal them in File Explorer.
"""

import os
import time
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QMessageBox
)

from opal_studio.config import ConfigManager


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opal Conversion History")
        self.resize(650, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._apply_theme()
        self._setup_ui()
        self.load_history()

    def _apply_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #101625;
                color: #EDF1FA;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #A8B2C8;
            }
            QTableWidget {
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 12px;
                gridline-color: rgba(255,255,255,0.09);
                color: #EDF1FA;
                selection-background-color: #6C63FF;
                selection-color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: rgba(108,99,255,0.18);
                color: #A79FFF;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-right: 1px solid rgba(255,255,255,0.09);
            }
            QPushButton {
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.16);
                border-radius: 10px;
                padding: 6px 14px;
                color: #EDF1FA;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(108,99,255,0.18);
                border: 1px solid #6C63FF;
                color: #C9C4FF;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header
        top_row = QHBoxLayout()
        title_label = QLabel("Conversion History")
        title_label.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title_label.setStyleSheet("color: #A79FFF;")
        top_row.addWidget(title_label)
        top_row.addStretch()

        self.btn_clear = QPushButton("Clear History")
        self.btn_clear.clicked.connect(self._clear_history)
        top_row.addWidget(self.btn_clear)

        layout.addLayout(top_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Original File", "Output File", "Action", "Saved", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self._open_selected_file)
        layout.addWidget(self.table)

        # Footer Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_open = QPushButton("Open Selected File")
        self.btn_open.clicked.connect(self._open_selected_file)
        btn_row.addWidget(self.btn_open)

        self.btn_reveal = QPushButton("Show in Folder")
        self.btn_reveal.clicked.connect(self._reveal_selected_file)
        btn_row.addWidget(self.btn_reveal)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

    def load_history(self):
        history = ConfigManager.load_history()
        self.table.setRowCount(len(history))
        for row, item in enumerate(history):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("source_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("target_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("action", "").upper()))

            saved = item.get("saved_bytes", 0)
            saved_str = f"{saved // 1024} KB" if saved > 0 else "-"
            self.table.setItem(row, 3, QTableWidgetItem(saved_str))

            ts = item.get("timestamp", 0)
            date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""
            self.table.setItem(row, 4, QTableWidgetItem(date_str))

            # Store full output path in row item data
            self.table.item(row, 1).setData(Qt.UserRole, item.get("output_path", ""))

    def _open_selected_file(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 1)
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                from opal_studio.platform_compat import open_with_default
                open_with_default(path)
            else:
                QMessageBox.warning(self, "Opal", "File no longer exists at that location.")

    def _reveal_selected_file(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 1)
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                from opal_studio.platform_compat import reveal_in_file_manager
                reveal_in_file_manager(path)
            else:
                QMessageBox.warning(self, "Opal", "File no longer exists.")

    def _clear_history(self):
        ConfigManager.clear_history()
        self.load_history()
