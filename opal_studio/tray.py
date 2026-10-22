"""
Opal - Production System Tray Companion
Plain English: This icon lives in your Windows taskbar near the clock, providing quick access
to settings, history, and the floating drop target.
"""

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (QIcon, QPixmap, QPainter, QColor, QBrush, QPen,
                           QLinearGradient)
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QFileDialog, QApplication, QMessageBox


def create_opal_icon(size: int = 64) -> QIcon:
    """The Opal mark for the system tray."""
    from opal_studio.brand import opal_pixmap

    return QIcon(opal_pixmap(size))


class OpalTray(QSystemTrayIcon):
    open_dashboard_requested = Signal()
    open_studio_requested = Signal()
    toggle_orb_requested = Signal()
    files_selected = Signal(list)
    settings_requested = Signal()
    history_requested = Signal()

    def __init__(self, parent=None):
        icon = create_opal_icon(64)
        super().__init__(icon, parent)
        self.setToolTip("Opal - Every file, in every light")

        self._setup_menu()
        self.activated.connect(self._on_tray_activated)

    def _setup_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(255,255,255,0.05);
                color: #EDF1FA;
                border: 1px solid rgba(255,255,255,0.13);
                border-radius: 12px;
                padding: 6px;
            }
            QMenu::item {
                padding: 7px 22px;
                border-radius: 8px;
            }
            QMenu::item:selected {
                background-color: rgba(108,99,255,0.18);
                color: #C9C4FF;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255,255,255,0.10);
                margin: 5px 10px;
            }
        """)

        dashboard_action = menu.addAction("Open Dashboard")
        dashboard_action.triggered.connect(self.open_dashboard_requested.emit)

        studio_action = menu.addAction("Open Floating Studio")
        studio_action.triggered.connect(self.open_studio_requested.emit)

        convert_action = menu.addAction("Convert File(s)...")
        convert_action.triggered.connect(self._on_convert_clicked)

        toggle_action = menu.addAction("Toggle Drop Target")
        toggle_action.triggered.connect(self.toggle_orb_requested.emit)

        history_action = menu.addAction("Conversion History")
        history_action.triggered.connect(self.history_requested.emit)

        settings_action = menu.addAction("Preferences...")
        settings_action.triggered.connect(self.settings_requested.emit)

        menu.addSeparator()

        about_action = menu.addAction("About Opal")
        about_action.triggered.connect(self._on_about_clicked)

        menu.addSeparator()

        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_dashboard_requested.emit()

    def _on_convert_clicked(self):
        files, _ = QFileDialog.getOpenFileNames(
            None,
            "Select File(s) to Convert with Opal",
            "",
            "All Files (*.*)"
        )
        if files:
            self.files_selected.emit(files)

    def _on_about_clicked(self):
        QMessageBox.information(
            None,
            "About Opal",
            "Opal v2.0.1\n\n"
            "Every file, in every light.\n"
            "• Shift = Convert Formats\n"
            "• Alt = File Tools\n"
            "• Ctrl = File Actions\n\n"
            "Floating Studio: full PDF editor (Acrobat replacement), AI image lab,\n"
            "media player and document viewer - all pinned above your desktop.\n\n"
            "All processing runs 100% locally on your computer.\n"
            "No files are ever uploaded."
        )
