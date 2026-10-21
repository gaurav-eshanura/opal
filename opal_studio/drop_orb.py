"""
Opal - Production Floating Drop Target (Drop Orb)
Plain English: A sleek desktop target that accepts dragged files or batches from File Explorer.
When you drop files onto it, it opens the Radial Wheel right under your cursor.
"""

from pathlib import Path
from typing import List
from PySide6.QtCore import Qt, QPoint, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QCursor
from PySide6.QtWidgets import QWidget, QFileDialog, QMenu


class DropOrbWidget(QWidget):
    # Emits (file_paths, screen_pos)
    files_dropped = Signal(list, QPoint)
    settings_requested = Signal()
    history_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        self.orb_width = 168
        self.orb_height = 54
        self.resize(self.orb_width, self.orb_height)

        self.is_hovered = False
        self.is_drag_over = False
        self.drag_position = QPoint()

        # The opal's fire
        self.fire = QColor("#8A5CF6")
        self.fire_glow = QColor("#FF9A3C")
        self.bg_dark = QColor(24, 29, 45, 245)
        self.border_normal = QColor(255, 255, 255, 46)
        self.border_active = QColor(255, 154, 60, 255)

    # --- DRAG & DROP HANDLING ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if valid:
                event.acceptProposedAction()
                self.is_drag_over = True
                self.update()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.is_drag_over = False
        self.update()

    def dropEvent(self, event):
        self.is_drag_over = False
        self.update()
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid_paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if valid_paths:
                event.acceptProposedAction()
                cursor_pos = QCursor.pos()
                self.files_dropped.emit(valid_paths, cursor_pos)

    # --- MOUSE INTERACTIONS (MOVING THE DOCK) ---

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._trigger_clipboard_or_dialog()

    def _trigger_clipboard_or_dialog(self):
        from PySide6.QtWidgets import QApplication
        from pathlib import Path
        import time
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasUrls():
            valid = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if valid:
                self.files_dropped.emit(valid, QCursor.pos())
                return
        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                target_dir = Path.home() / "Downloads"
                target_dir.mkdir(parents=True, exist_ok=True)
                temp_file = target_dir / f"Screenshot_{int(time.time())}.png"
                image.save(str(temp_file), "PNG")
                self.files_dropped.emit([str(temp_file)], QCursor.pos())
                return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select File(s) to Convert with Opal",
            "",
            "All Files (*.*)"
        )
        if files:
            self.files_dropped.emit(files, QCursor.pos())

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
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

        paste_action = menu.addAction("Convert from Clipboard")
        choose_action = menu.addAction("Convert File(s)...")
        history_action = menu.addAction("Conversion History")
        settings_action = menu.addAction("Preferences...")
        menu.addSeparator()
        hide_action = menu.addAction("Hide Drop Target")
        menu.addSeparator()
        exit_action = menu.addAction("Quit Opal")

        action = menu.exec(pos)
        if action == paste_action:
            self._trigger_clipboard_or_dialog()
        elif action == choose_action:
            files, _ = QFileDialog.getOpenFileNames(self, "Choose File(s)", "", "All Files (*.*)")
            if files:
                self.files_dropped.emit(files, QCursor.pos())
        elif action == history_action:
            self.history_requested.emit()
        elif action == settings_action:
            self.settings_requested.emit()
        elif action == hide_action:
            self.hide()
        elif action == exit_action:
            from PySide6.QtWidgets import QApplication
            QApplication.quit()

    # --- RENDERING ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w, h = self.width(), self.height()
        rect = QRectF(2, 2, w - 4, h - 4)

        if self.is_drag_over:
            bg_gradient = QLinearGradient(0, 0, w, h)
            bg_gradient.setColorAt(0, QColor("#EE4E8A"))
            bg_gradient.setColorAt(1, QColor("#8A5CF6"))
            painter.setBrush(QBrush(bg_gradient))
            painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
        else:
            painter.setBrush(QBrush(self.bg_dark))
            border_col = self.border_active if self.is_hovered else self.border_normal
            painter.setPen(QPen(border_col, 1.8 if self.is_hovered else 1.2))

        painter.drawRoundedRect(rect, h / 2.0, h / 2.0)

        # The opal
        icon_cx = 28
        icon_cy = h // 2
        painter.setBrush(QBrush(self.fire if not self.is_drag_over else Qt.white))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(icon_cx, icon_cy), 11, 11)

        painter.setBrush(QBrush(QColor(255, 255, 255, 225) if not self.is_drag_over else QColor(255, 255, 255)))
        painter.drawEllipse(QPoint(icon_cx, icon_cy), 4, 4)

        # Typography
        text_x = 48
        text_rect = QRectF(text_x, 6, w - text_x - 10, h - 12)

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QPen(QColor("#EDF1FA")))

        if self.is_drag_over:
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, "Drop to Convert!")
        else:
            painter.drawText(QRectF(text_x, 10, 110, 18), Qt.AlignLeft, "Opal")
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QPen(QColor("#8A9189")))
            painter.drawText(QRectF(text_x, 26, 110, 16), Qt.AlignLeft, "Drop file(s) here")
