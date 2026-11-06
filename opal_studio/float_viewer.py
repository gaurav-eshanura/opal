"""
Opal - Floating Studio Shell
Plain English: The window that floats above everything else. It holds tabs for
every open document (PDF Studio, AI Image Lab, Media Studio, Document viewer),
stays on top, can fade or become click-through ("ghost mode" so you can trace
over other windows), snaps to screen edges, accepts dropped files, and opens on
a home screen that lists everything Opal can do.
"""

import os
import sys
import ctypes
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QSize, Signal, QTimer
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QBrush, QPixmap, QIcon, QKeySequence,
                           QShortcut, QLinearGradient)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
                               QWidget, QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
                               QGridLayout, QScrollArea, QFrame, QApplication, QSizePolicy)

from opal_studio.icons import ICONS
from opal_studio.theme import (BG_RAISED, RADIUS, RADIUS_SMALL, ACCENT, ACCENT_HI, ACCENT_WASH,
                              TEXT, TEXT_DIM, TEXT_FAINT, LINE,
                              title_label, section_label, body_label, hint_label)
from opal_studio.viewer_pdf import PdfStudio
from opal_studio.viewer_image import ImageLab
from opal_studio.viewer_doc import DocStudio

CITRUS = QColor(255, 122, 24)
CITRUS_GLOW = QColor(255, 160, 67)

PDF_EXT = {".pdf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".ico", ".gif",
             ".avif", ".heic", ".heif", ".svg"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aiff", ".wma", ".aac"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
ARCHIVE_EXT = {".zip", ".tar", ".gz", ".tgz"}


def _chrome_btn(text: str, tip: str = "", size: int = 26) -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip or text)
    b.setFixedSize(size, size)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none;
                       border-radius: {size // 2}px; font-size: 12px; font-weight: 700; }}
        QPushButton:hover {{ background: rgba(108,99,255,0.16); color: {ACCENT_HI}; }}
    """)
    return b


# Catalog action -> icon, so every tile on the home screen has a face.
CATALOG_ICONS = {
    "remove_bg": "layers", "replace_bg": "image", "upscale_2x": "arrow", "enhance": "star",
    "adjust": "contrast", "crop": "scissors", "rotate": "rotate_right", "filters": "palette",
    "watermark": "text_t", "signature": "pen", "blur_faces": "lock", "meme": "note",
    "exif": "search", "wallpaper": "image", "id_photo": "camera", "print_photo": "printer",
    "whatsapp_photo": "compress", "whatsapp_pdf": "compress", "border": "box", "bg_blur": "drop",
    "pdf_to_word": "doc", "pdf_to_ppt": "presentation", "pdf_to_epub": "book",
    "pdf_to_images": "image", "merge_pdf": "merge", "split_pdf": "split", "reorder_pdf": "layers",
    "compress_pdf": "compress", "pdf_ocr": "scan", "protect_pdf": "lock", "unlock_pdf": "unlock",
    "repair_pdf": "wrench", "pdf_watermark": "marker", "page_numbers": "hash", "flatten_pdf": "layers",
    "pdf_summary": "text", "extract_attachments": "clip", "sign_pdf": "pen", "verify_signature": "search",
    "qr_code": "hash", "social_presets": "palette", "to_pdf": "doc", "hash_file": "hash",
    "trim_video": "scissors", "video_to_gif": "film", "extract_audio": "music", "to_720p": "film",
    "burn_subtitles": "text", "normalize_audio": "speaker",
}


class HomeTab(QWidget):
    """The welcome screen: drop zone, everything Opal can do, recent files."""

    run_action = Signal(str, list)  # action id, file paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        lay.addWidget(title_label("Opal Studio"))
        lay.addWidget(body_label("Drop any file here, or pick a tool below. Everything runs locally on your PC.",
                                 dim=True))

        # Tool grid
        lay.addWidget(section_label("Everything Opal can do"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # 4-col grid never needs it
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        from opal_studio.engine import OpalEngine
        for i, item in enumerate(OpalEngine.get_catalog()):
            grid.addWidget(self._catalog_card(item), i // 4, i % 4)
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

        # Recent files
        lay.addWidget(section_label("Recent"))
        self.recent = QListWidget()
        self.recent.setMaximumHeight(130)
        self.recent.setStyleSheet("QListWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                  "border:1px solid rgba(255,255,255,0.10); border-radius:12px; }"
                                  "QListWidget::item { padding:4px 8px; border-radius:8px; }"
                                  "QListWidget::item:selected { background:rgba(108,99,255,0.18); color:#C9C4FF; }")
        self.recent.itemDoubleClicked.connect(self._open_recent)
        lay.addWidget(self.recent)
        self.reload_recent()

    def _pick_and_run(self, action_id: str):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files for this tool", "",
                                                "All Files (*.*)")
        if paths:
            self.run_action.emit(action_id, paths)

    def _catalog_card(self, item: dict) -> QFrame:
        """One tile of the home grid: icon tile, label, one-line description."""
        card = QFrame()
        card.setObjectName("toolCard")
        card.setMinimumHeight(64)
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip(item["desc"])
        card.setStyleSheet(f"""
            QFrame#toolCard {{
                background: rgba(255,255,255,0.04);
                border: 1px solid {LINE};
                border-radius: {RADIUS}px;
            }}
            QFrame#toolCard:hover {{
                background: rgba(255,255,255,0.07);
                border-color: {ACCENT_HI};
            }}
            QFrame#toolCard QLabel {{ background: transparent; border: none; }}
            QFrame#toolCard QFrame#iconTile {{
                background: {ACCENT_WASH};
                border: 1px solid rgba(138,131,255,0.30);
                border-radius: 8px;
            }}
        """)

        def handler(event):
            if event.button() == Qt.LeftButton:
                self._pick_and_run(item["id"])
            QFrame.mouseReleaseEvent(card, event)
        card.mouseReleaseEvent = handler

        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        tile = QFrame()
        tile.setObjectName("iconTile")
        tile.setFixedSize(30, 30)
        tile_lay = QHBoxLayout(tile)
        tile_lay.setContentsMargins(0, 0, 0, 0)
        icon = QLabel()
        icon.setPixmap(ICONS[CATALOG_ICONS.get(item["id"], "star")](16).pixmap(16, 16))
        tile_lay.addWidget(icon, 0, Qt.AlignCenter)
        lay.addWidget(tile)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        t = body_label(item["label"])
        text_box.addWidget(t)
        d = hint_label(item["desc"])
        d.setWordWrap(True)
        text_box.addWidget(d)
        lay.addLayout(text_box, 1)
        return card

    def _open_recent(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path and Path(path).exists():
            self.run_action.emit("float", [path])

    def reload_recent(self):
        self.recent.clear()
        try:
            from opal_studio.config import ConfigManager
            for entry in ConfigManager.load_history()[:20]:
                path = entry.get("output_path") or ""
                if path and Path(path).exists():
                    item = QListWidgetItem(f"{Path(path).name}   ({entry.get('action', '')})")
                    item.setData(Qt.UserRole, path)
                    self.recent.addItem(item)
        except Exception:
            pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.run_action.emit("float", paths)
            event.acceptProposedAction()


class FloatStudio(QWidget):
    """
    The floating window: tabs for every open file, always-on-top, opacity,
    ghost (click-through) mode, edge snapping and drag & drop.
    """

    # Argument order must match main.OpalApp.on_action_selected(file_paths, action_id)
    # and radial_widget.RadialMenuWidget.action_selected = Signal(list, str).
    file_action = Signal(list, str)   # file paths, action id (handled by the app)

    def __init__(self, file_paths: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.resize(1080, 760)
        self.setMinimumSize(640, 480)

        self.is_pinned = True
        self.opacity_level = 1.0
        self.ghost_mode = False
        self.drag_position = QPoint()
        self._dragging = False

        self._build_ui()
        for path in (file_paths or []):
            self.open_file(path)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(8)

        # Title bar
        bar = QHBoxLayout()
        bar.setSpacing(8)
        from opal_studio.icons import (mark_icon, pin_icon, opacity_icon,
                                            ghost_icon, maximize_icon, restore_icon,
                                            close_icon)
        icon = QLabel()
        icon.setPixmap(mark_icon(28).pixmap(28, 28))
        bar.addWidget(icon)
        self.title_label = QLabel("Opal")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #EDF1FA;")
        bar.addWidget(self.title_label)
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Segoe UI", 8))
        self.info_label.setStyleSheet("color: #8B96AD;")
        bar.addWidget(self.info_label)
        bar.addStretch()

        self.btn_pin = _chrome_btn("", "Keep the studio on top of other windows", 30)
        self.btn_pin.setIcon(pin_icon(18))
        self.btn_pin.clicked.connect(self._toggle_pin)
        bar.addWidget(self.btn_pin)
        self.btn_opacity = _chrome_btn("100%", "Fade the window", 52)
        self.btn_opacity.setIcon(opacity_icon(18))
        self.btn_opacity.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none;
                          border-radius: {RADIUS}px; font-size: 11px; font-weight: 700; padding-right: 10px; }}
            QPushButton:hover {{ background: rgba(108,99,255,0.16); color: {ACCENT_HI}; }}
        """)
        self.btn_opacity.clicked.connect(self._toggle_opacity)
        bar.addWidget(self.btn_opacity)
        self.btn_ghost = _chrome_btn("", "Ghost mode: clicks pass through to the window below", 30)
        self.btn_ghost.setIcon(ghost_icon(18))
        self.btn_ghost.clicked.connect(self._toggle_ghost)
        bar.addWidget(self.btn_ghost)
        self.btn_max = _chrome_btn("", "Maximize / restore", 30)
        self.btn_max.setIcon(maximize_icon(18))
        self.btn_max.clicked.connect(self._toggle_maximize)
        bar.addWidget(self.btn_max)
        self.btn_close = _chrome_btn("", "Close the studio", 30)
        self.btn_close.setIcon(close_icon(18, "#EDF1FA"))
        self.btn_close.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; border-radius: {RADIUS}px; }}
            QPushButton:hover {{ background: #E5484D; }}
        """)
        self.btn_close.clicked.connect(self.close)
        bar.addWidget(self.btn_close)
        root.addLayout(bar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid rgba(255,255,255,0.10); border-radius: {RADIUS}px; background: {BG_RAISED}; }}
            QTabBar::tab {{ background: rgba(255,255,255,0.05); color: {TEXT_DIM}; padding: 7px 14px; margin-right: 2px;
                           border-top-left-radius: {RADIUS_SMALL}px; border-top-right-radius: {RADIUS_SMALL}px; font-size: 11px; }}
            QTabBar::tab:selected {{ background: rgba(255,255,255,0.16); color: #FFFFFF; font-weight: 600; }}
            QTabBar::tab:hover {{ color: #EDF1FA; }}
            QTabBar::close-button {{ subcontrol-position: right; }}
        """)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)

        self.home = HomeTab()
        self.home.run_action.connect(self._on_home_action)
        from opal_studio.icons import home_icon
        self.tabs.addTab(self.home, home_icon(16), "Home")

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+Tab"), self, self._next_tab)
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_files)
        QShortcut(QKeySequence("Ctrl+T"), self, self._toggle_ghost)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, self._toggle_opacity)

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def open_file(self, file_path: str) -> bool:
        """Opens a file in the right studio tab. Returns True on success."""
        path = Path(file_path)
        if not path.exists():
            return False
        ext = path.suffix.lower()

        if ext in PDF_EXT:
            widget = PdfStudio(str(path))
        elif ext in IMAGE_EXT:
            widget = ImageLab(str(path))
        elif ext in VIDEO_EXT or ext in AUDIO_EXT:
            from opal_studio.viewer_media import MediaStudio
            widget = MediaStudio(str(path))
        elif ext in FONT_EXT or ext in ARCHIVE_EXT or ext in (
                ".txt", ".md", ".json", ".csv", ".tsv", ".html", ".htm", ".epub", ".log",
                ".py", ".dart", ".js", ".ts", ".xml", ".yml", ".yaml", ".srt", ".vtt", ".docx"):
            widget = DocStudio(str(path))
        else:
            widget = DocStudio(str(path))

        index = self.tabs.addTab(widget, path.name)
        self.tabs.setCurrentIndex(index)
        self.tabs.setTabToolTip(index, str(path))
        if hasattr(widget, "open_path_signal"):
            widget.open_path_signal.connect(self.open_file)
        return True

    def open_pdf_tab(self, file_path: str):
        """Hook used by the PDF studio to open a file in a new tab."""
        self.open_file(file_path)

    def _close_tab(self, index: int):
        widget = self.tabs.widget(index)
        if widget is self.home:
            return
        if hasattr(widget, "close_document"):
            if not widget.close_document():
                return
        self.tabs.removeTab(index)
        widget.deleteLater()
        self._update_title()

    def _close_current_tab(self):
        self._close_tab(self.tabs.currentIndex())

    def _next_tab(self):
        count = self.tabs.count()
        if count > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % count)

    def _tab_changed(self, index: int):
        widget = self.tabs.widget(index)
        name = self.tabs.tabText(index)
        self.title_label.setText(name if name != "Home" else "Opal Studio")
        if isinstance(widget, PdfStudio):
            self.info_label.setText(f"PDF Studio | {len(widget.doc) if widget.doc else 0} pages")
        elif isinstance(widget, ImageLab):
            self.info_label.setText("AI Image Lab")
        else:
            self.info_label.setText("")

    def _update_title(self):
        self._tab_changed(self.tabs.currentIndex())

    def _on_home_action(self, action_id: str, paths: List[str]):
        if action_id == "float":
            for p in paths:
                self.open_file(p)
        else:
            self.file_action.emit(paths, action_id)

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Open in Opal Studio", "",
                                                "All Files (*.*)")
        for p in paths:
            self.open_file(p)

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------

    def _toggle_pin(self):
        from opal_studio.icons import pin_icon
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.btn_pin.setIcon(pin_icon(18, ACCENT_HI if self.is_pinned else TEXT_DIM))
        self.show()
        self._apply_ghost()

    def _toggle_opacity(self):
        if self.opacity_level >= 1.0:
            self.opacity_level = 0.85
        elif self.opacity_level >= 0.85:
            self.opacity_level = 0.65
        else:
            self.opacity_level = 1.0
        self.setWindowOpacity(self.opacity_level)
        self.btn_opacity.setText(f"{int(self.opacity_level * 100)}%")

    def _toggle_ghost(self):
        """Click-through mode: mouse clicks reach the window underneath."""
        from opal_studio.icons import ghost_icon
        self.ghost_mode = not self.ghost_mode
        self.btn_ghost.setIcon(ghost_icon(18, ACCENT_HI if self.ghost_mode else TEXT_DIM))
        self._apply_ghost()
        self.info_label.setText("Ghost mode: clicks pass through" if self.ghost_mode else "")

    def _apply_ghost(self):
        """Click-through mode. Qt's own flag does this on every platform, so
        there is no system-specific code here at all."""
        flags = self.windowFlags()
        if self.ghost_mode:
            flags |= Qt.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.show()

    def _toggle_maximize(self):
        from opal_studio.icons import maximize_icon, restore_icon
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setIcon(maximize_icon(18))
        else:
            self.showMaximized()
            self.btn_max.setIcon(restore_icon(18))

    # -- dragging & snapping --

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 44:
            self._dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = False
            self._snap_to_edge()
            event.accept()

    def _snap_to_edge(self):
        try:
            screen = self.screen() or QApplication.primaryScreen()
            if not screen:
                return
            area = screen.availableGeometry()
            margin = 26
            pos = self.frameGeometry()
            x, y = pos.x(), pos.y()
            changed = False
            if abs(x - area.left()) < margin:
                x, changed = area.left(), True
            elif abs(area.right() - pos.right()) < margin:
                x, changed = area.right() - pos.width() + 1, True
            if abs(y - area.top()) < margin:
                y, changed = area.top(), True
            elif abs(area.bottom() - pos.bottom()) < margin:
                y, changed = area.bottom() - pos.height() + 1, True
            if changed:
                self.move(x, y)
        except Exception:
            pass

    def paintEvent(self, event):
        """The window is a slab of glass: a deep field of colour, lit from
        above, with the light bending along its edge."""
        from opal_studio.glass import paint_frosted_backdrop, caustic_glow

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = 18.0

        # The field the glass sits in.
        paint_frosted_backdrop(painter, rect, radius, strength=0.85)

        # The colour the glass throws onto itself.
        caustic_glow(painter, rect, radius, strength=1.15)

        # The edge: white where the light bends through the top, gathering
        # shadow at the bottom.
        edge = QLinearGradient(0, 0, 0, self.height())
        edge.setColorAt(0.0, QColor(255, 255, 255, 190))
        edge.setColorAt(0.30, QColor(255, 255, 255, 46))
        edge.setColorAt(0.78, QColor(0, 0, 0, 40))
        edge.setColorAt(1.0, QColor(0, 0, 0, 90))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QBrush(edge), 1.4))
        painter.drawRoundedRect(rect, radius, radius)

        # A bright sliver along the top lip.
        lip = QLinearGradient(0, 0, self.width(), 0)
        lip.setColorAt(0.0, QColor(255, 255, 255, 0))
        lip.setColorAt(0.18, QColor(255, 255, 255, 150))
        lip.setColorAt(0.72, QColor(255, 255, 255, 40))
        lip.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(QBrush(lip), 1.6))
        painter.drawLine(QPointF(rect.left() + 18, rect.top() + 1.0),
                         QPointF(rect.right() - 18, rect.top() + 1.0))


    # -- drag & drop --

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        for p in paths:
            self.open_file(p)
        event.acceptProposedAction()

    def closeEvent(self, event):
        for index in range(self.tabs.count() - 1, -1, -1):
            widget = self.tabs.widget(index)
            if widget is self.home:
                continue
            if hasattr(widget, "close_document") and not widget.close_document():
                event.ignore()
                return
        event.accept()


# Backwards compatible alias for older imports
FloatViewerWidget = FloatStudio
