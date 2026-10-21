"""
Opal - Universal Document Viewer
Plain English: Opens what other apps refuse to: code, logs, markdown, HTML,
spreadsheets, JSON, EPUB books, fonts and archives. Each type gets a purpose
built view - rendered markdown, sortable CSV grid, collapsible JSON tree,
chapters for ebooks, a real specimen sheet for fonts, and a browsable archive
tree that can extract or open files straight into the Studio.
"""

import io
import json
import os
import re
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import (QColor, QFont, QTextCursor, QTextCharFormat, QFontDatabase, QPixmap,
                           QImage, QPainter, QTextDocument)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QTextEdit, QPlainTextEdit, QLineEdit, QSplitter, QMessageBox,
                               QFileDialog, QTabWidget, QTreeWidget, QTreeWidgetItem, QTableWidget,
                               QTableWidgetItem, QHeaderView, QApplication, QCheckBox, QComboBox,
                               QListWidget, QListWidgetItem, QStackedWidget, QTextBrowser)

from opal_studio.safepath import safe_path

CITRUS = QColor(255, 122, 24)

CODE_EXT = {".txt", ".log", ".py", ".dart", ".js", ".ts", ".json", ".yaml", ".yml", ".ini",
            ".cfg", ".conf", ".xml", ".sql", ".sh", ".bat", ".ps1", ".html", ".htm", ".css",
            ".toml", ".env", ".csv", ".tsv", ".srt", ".vtt"}
MARKDOWN_EXT = {".md", ".markdown", ".mdown"}
HTML_EXT = {".html", ".htm"}
DATA_EXT = {".json", ".csv", ".tsv"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
ARCHIVE_EXT = {".zip", ".tar", ".gz", ".tgz"}


def _btn(text: str, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setToolTip(tip or text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("""
        QPushButton { background: rgba(255,255,255,0.05); color: #EDF1FA; border: 1px solid rgba(255,255,255,0.16);
                      border-radius: 10px; padding: 5px 11px; font-size: 11px; font-weight: 600; }
        QPushButton:hover { background: #6C63FF; color: #FFFFFF; border-color: #8A83FF; }
        QPushButton:pressed { background: #D55223; color: #FFFFFF; }
        QPushButton:disabled { background: #101625; color: rgba(237,241,250,0.28); border-color: rgba(255,255,255,0.09); }
    """)
    return b


class DocStudio(QWidget):
    """Universal document workspace. Routes by file type to the right view."""

    open_path_signal = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        from opal_studio.theme import apply_field
        apply_field(self)
        self.file_path = str(Path(file_path).resolve())
        self.kind = "text"
        self._build_ui()
        self._route()

    # ------------------------------------------------------------------
    # Shell
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(Path(self.file_path).name)
        self.title_label.setStyleSheet("color: #EDF1FA; font-size: 12px; font-weight: 700;")
        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #727E96; font-size: 10px;")
        header.addWidget(self.title_label)
        header.addWidget(self.meta_label)
        header.addStretch()

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("🔍 Find in document...")
        self.find_edit.setFixedWidth(240)
        self.find_edit.setStyleSheet("QLineEdit { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                     "border:1px solid rgba(255,255,255,0.16); border-radius:10px; padding:4px 8px; }"
                                     "QLineEdit::placeholder { color:#727E96; }")
        self.find_edit.textChanged.connect(self._find)
        header.addWidget(self.find_edit)

        for text, tip, slot in [
            ("📋 Copy", "Copy the whole document", self._copy_all),
            ("📄 → PDF", "Export this document to PDF", self._export_pdf),
            ("🔤 → TXT", "Export the text of this document", self._export_txt),
            ("📁 Folder", "Show in Explorer", self._reveal),
        ]:
            b = _btn(text, tip)
            b.clicked.connect(slot)
            header.addWidget(b)
        root.addLayout(header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self._build_text_view()
        self._build_html_view()
        self._build_table_view()
        self._build_tree_view()
        self._build_epub_view()
        self._build_font_view()
        self._build_archive_view()

    def _build_text_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.wrap_check = QCheckBox("Wrap lines")
        self.wrap_check.setChecked(True)
        self.wrap_check.stateChanged.connect(self._toggle_wrap)
        bar.addWidget(self.wrap_check)
        self.font_combo = QComboBox()
        for fam in ("Consolas", "Cascadia Code", "Courier New", "Segoe UI"):
            self.font_combo.addItem(fam)
        self.font_combo.currentTextChanged.connect(self._set_font)
        bar.addWidget(self.font_combo)
        bar.addStretch()
        self.text_stats = QLabel("")
        self.text_stats.setStyleSheet("color: #727E96; font-size: 10px;")
        bar.addWidget(self.text_stats)
        lay.addLayout(bar)
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.text_view.setStyleSheet("QPlainTextEdit { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                     "border:1px solid rgba(255,255,255,0.10); border-radius:12px; "
                                     "font-family: Consolas, monospace; font-size: 12px; padding:10px; }")
        lay.addWidget(self.text_view, 1)
        self.stack.addWidget(w)

    def _build_html_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.html_view = QTextBrowser()
        self.html_view.setOpenExternalLinks(True)
        self.html_view.setStyleSheet("QTextBrowser { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                     "border:1px solid rgba(255,255,255,0.10); border-radius:12px; padding:10px; }")
        lay.addWidget(self.html_view)
        self.stack.addWidget(w)

    def _build_table_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                  "border:1px solid rgba(255,255,255,0.10); gridline-color:rgba(255,255,255,0.10); "
                                  "alternate-background-color:#FAFAF8; }"
                                  "QHeaderView::section { background:rgba(108,99,255,0.18); color:#A79FFF; "
                                  "border:none; border-bottom:1px solid rgba(255,255,255,0.10); padding:6px; }"
                                  "QTableWidget::item { padding:4px; }")
        lay.addWidget(self.table, 1)
        self.stack.addWidget(w)

    def _build_tree_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Key", "Value"])
        self.tree.setStyleSheet("QTreeWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                "border:1px solid rgba(255,255,255,0.10); border-radius:12px; }"
                                "QHeaderView::section { background:rgba(108,99,255,0.18); color:#A79FFF; "
                                "border:none; border-bottom:1px solid rgba(255,255,255,0.10); padding:6px; }")
        split.addWidget(self.tree)
        self.tree_json = QTextEdit()
        self.tree_json.setReadOnly(True)
        self.tree_json.setStyleSheet("QTextEdit { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                      "border:1px solid rgba(255,255,255,0.10); font-family:Consolas; }")
        split.addWidget(self.tree_json)
        split.setSizes([420, 420])
        lay.addWidget(split)
        self.stack.addWidget(w)

    def _build_epub_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal)
        self.epub_chapters = QListWidget()
        self.epub_chapters.setStyleSheet("QListWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                         "border:1px solid rgba(255,255,255,0.10); border-radius:12px; padding:4px; }"
                                         "QListWidget::item { padding:5px 8px; border-radius:8px; }"
                                         "QListWidget::item:selected { background:rgba(108,99,255,0.18); color:#A79FFF; }")
        self.epub_chapters.currentRowChanged.connect(self._epub_select)
        split.addWidget(self.epub_chapters)
        self.epub_view = QTextBrowser()
        self.epub_view.setStyleSheet("QTextBrowser { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                     "border:1px solid rgba(255,255,255,0.10); border-radius:12px; padding:10px; }")
        split.addWidget(self.epub_view)
        split.setSizes([220, 700])
        lay.addWidget(split)
        self.stack.addWidget(w)

    def _build_font_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.font_specimen = QTextEdit()
        self.font_specimen.setStyleSheet("QTextEdit { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                         "border:1px solid rgba(255,255,255,0.10); border-radius:12px; }")
        lay.addWidget(self.font_specimen, 1)
        self.font_meta = QTextEdit()
        self.font_meta.setReadOnly(True)
        self.font_meta.setMaximumHeight(160)
        self.font_meta.setStyleSheet("QTextEdit { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                      "border:1px solid rgba(255,255,255,0.10); font-family:Consolas; }")
        lay.addWidget(self.font_meta)
        self.stack.addWidget(w)

    def _build_archive_view(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.archive_info = QLabel("")
        self.archive_info.setStyleSheet("color: #727E96; font-size: 10px;")
        bar.addWidget(self.archive_info)
        bar.addStretch()
        extract_btn = _btn("📦 Extract All", "Extract the archive next to the original file")
        extract_btn.clicked.connect(self._extract_archive)
        bar.addWidget(extract_btn)
        open_btn = _btn("📂 Open Selected", "Open the selected file inside the archive")
        open_btn.clicked.connect(self._open_archive_item)
        bar.addWidget(open_btn)
        lay.addLayout(bar)
        self.archive_tree = QTreeWidget()
        self.archive_tree.setHeaderLabels(["Name", "Size"])
        self.archive_tree.setStyleSheet("QTreeWidget { background:rgba(255,255,255,0.05); color:#EDF1FA; "
                                        "border:1px solid rgba(255,255,255,0.10); border-radius:12px; }"
                                        "QHeaderView::section { background:rgba(108,99,255,0.18); color:#A79FFF; "
                                        "border:none; border-bottom:1px solid rgba(255,255,255,0.10); padding:6px; }")
        lay.addWidget(self.archive_tree, 1)
        self.stack.addWidget(w)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route(self):
        p = Path(self.file_path)
        ext = p.suffix.lower()
        size_kb = p.stat().st_size / 1024
        self.meta_label.setText(f"{ext or 'file'} | {size_kb:.0f} KB | "
                                f"modified {p.stat().st_mtime and 'recently' or ''}")

        if ext in FONT_EXT:
            self.kind = "font"
            self.stack.setCurrentWidget(self.font_meta.parentWidget())
            self._load_font()
        elif ext in ARCHIVE_EXT:
            self.kind = "archive"
            self.stack.setCurrentWidget(self.archive_tree.parentWidget())
            self._load_archive()
        elif ext == ".epub":
            self.kind = "epub"
            self.stack.setCurrentWidget(self.epub_view.parentWidget())
            self._load_epub()
        elif ext == ".json":
            self.kind = "json"
            self.stack.setCurrentWidget(self.tree_json.parentWidget())
            self._load_json()
        elif ext in (".csv", ".tsv"):
            self.kind = "table"
            self.stack.setCurrentWidget(self.table.parentWidget())
            self._load_table()
        elif ext in MARKDOWN_EXT or ext in HTML_EXT:
            self.kind = "html"
            self.stack.setCurrentWidget(self.html_view.parentWidget())
            self._load_markdown_or_html()
        else:
            self.kind = "text"
            self.stack.setCurrentWidget(self.text_view.parentWidget())
            self._load_text()

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def _read_text(self) -> str:
        ext = Path(self.file_path).suffix.lower()
        if ext == ".docx":
            text = self._read_docx()
            if text is not None:
                return text
        if ext in (".xlsx", ".xls"):
            text = self._read_xlsx()
            if text is not None:
                return text
        if ext in (".pptx", ".ppt"):
            text = self._read_pptx()
            if text is not None:
                return text
        try:
            return Path(self.file_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            try:
                return Path(self.file_path).read_text(encoding="cp1252", errors="replace")
            except Exception as e:
                return f"Could not read file: {e}"

    def _read_docx(self) -> Optional[str]:
        try:
            import docx
            d = docx.Document(str(self.file_path))
            lines = [p.text for p in d.paragraphs if p.text.strip()]
            for table in d.tables:
                for row in table.rows:
                    lines.append("  |  ".join(c.text for c in row.cells))
            return "\n".join(lines)
        except Exception:
            return None

    def _read_xlsx(self) -> Optional[str]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(self.file_path), data_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"--- Sheet: {ws.title} ---")
                for row in ws.iter_rows(values_only=True):
                    lines.append("  |  ".join("" if c is None else str(c) for c in row))
            return "\n".join(lines)
        except Exception:
            return None

    def _read_pptx(self) -> Optional[str]:
        try:
            from pptx import Presentation
            prs = Presentation(str(self.file_path))
            lines = []
            for i, slide in enumerate(prs.slides, 1):
                lines.append(f"--- Slide {i} ---")
                for shape in slide.shapes:
                    if shape.has_text_frame and shape.text_frame.text.strip():
                        lines.append(shape.text_frame.text.strip())
            return "\n".join(lines)
        except Exception:
            return None

    def _load_text(self):
        content = self._read_text()
        self.text_view.setPlainText(content)
        words = len(content.split())
        lines = content.count("\n") + 1
        self.text_stats.setText(f"{lines} lines | {words} words | {len(content)} chars")

    def _load_markdown_or_html(self):
        ext = Path(self.file_path).suffix.lower()
        content = self._read_text()
        if ext in MARKDOWN_EXT:
            try:
                import markdown as md_lib
                body = md_lib.markdown(content, extensions=["extra", "tables", "fenced_code",
                                                           "toc", "sane_lists"])
            except Exception:
                body = f"<pre>{content}</pre>"
            css = ("body{font-family:'Segoe UI',sans-serif;line-height:1.6;color:#EDF1FA;"
                   "background:#FFFFFF;max-width:820px;margin:0 auto;padding:18px;}"
                   "h1{color:#8A83FF;} h2{border-bottom:1px solid #E7E8E4;padding-bottom:4px;}"
                   "code,pre{background:#101625;} pre{padding:10px;border-radius:10px;"
                   "font-family:Consolas,monospace;} table{border-collapse:collapse;}"
                   "td,th{border:1px solid #DDE3EF;padding:6px;} blockquote{border-left:4px solid #6C63FF;"
                   "margin:0;padding-left:12px;color:#A8B2C8;}")
            self.html_view.setHtml(f"<style>{css}</style>{body}")
            self.text_stats.setText(f"{len(content.split())} words")
        else:
            cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", content,
                             flags=re.S | re.I)
            self.html_view.setHtml(cleaned)

    def _load_table(self):
        import csv
        ext = Path(self.file_path).suffix.lower()
        delim = "\t" if ext == ".tsv" else ","
        try:
            with open(self.file_path, "r", newline="", encoding="utf-8",
                      errors="replace") as f:
                rows = list(csv.reader(f, delimiter=delim))
        except Exception as e:
            QMessageBox.warning(self, "Cannot Read", str(e))
            return
        if not rows:
            return
        header, body = rows[0], rows[1:]
        self.table.setColumnCount(len(header))
        self.table.setHorizontalHeaderLabels([h or f"Column {i + 1}" for i, h in enumerate(header)])
        limit = 5000
        for r, row in enumerate(body[:limit]):
            self.table.insertRow(r)
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        self.meta_label.setText(f"{len(body)} rows x {len(header)} columns"
                                 + (f" (showing first {limit})" if len(body) > limit else ""))

    def _load_json(self):
        content = self._read_text()
        try:
            data = json.loads(content)
        except Exception as e:
            self.tree_json.setPlainText(f"Invalid JSON: {e}\n\n{content[:4000]}")
            return
        self.tree_json.setPlainText(json.dumps(data, indent=2, ensure_ascii=False)[:200000])
        self.tree.clear()
        self._fill_tree(self.tree, data)
        self.tree.expandToDepth(1)

    def _fill_tree(self, parent, data, depth: int = 0):
        if depth > 12:
            return
        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem(parent, [str(key), _short_repr(value)])
                if isinstance(value, (dict, list)):
                    self._fill_tree(item, value, depth + 1)
        elif isinstance(data, list):
            for i, value in enumerate(data):
                item = QTreeWidgetItem(parent, [f"[{i}]", _short_repr(value)])
                if isinstance(value, (dict, list)):
                    self._fill_tree(item, value, depth + 1)
        else:
            QTreeWidgetItem(parent, ["value", str(data)])

    def _load_epub(self):
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
            book = epub.read_epub(self.file_path)
            self.epub_chapters.clear()
            self._epub_items = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                soup = BeautifulSoup(item.get_content(), "lxml")
                title = (soup.title.string if soup.title and soup.title.string
                         else item.file_name)
                self.epub_chapters.addItem(str(title))
                self._epub_items.append(str(item.get_content()))
            if self.epub_chapters.count():
                self.epub_chapters.setCurrentRow(0)
            meta = f"{len(self._epub_items)} chapters"
            try:
                meta += f" | {book.get_metadata('DC', 'title')[0][3]}"
            except Exception:
                pass
            self.meta_label.setText(meta)
        except Exception as e:
            QMessageBox.warning(self, "Cannot Read EPUB", str(e))

    def _epub_select(self, row: int):
        if not hasattr(self, "_epub_items") or row < 0 or row >= len(self._epub_items):
            return
        content = self._epub_items[row]
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "lxml")
            for tag in soup(["script", "style"]):
                tag.decompose()
            self.epub_view.setHtml(str(soup))
        except Exception:
            self.epub_view.setPlainText(content)

    def _load_font(self):
        path = self.file_path
        try:
            from fontTools.ttLib import TTFont
            font = TTFont(path)
            meta_lines = []
            for label, nid in [("Family", 1), ("Subfamily", 2), ("Full name", 4),
                               ("PostScript", 6), ("Version", 5), ("Designer", 9),
                               ("Manufacturer", 8), ("License", 13), ("License URL", 14)]:
                value = font["name"].getDebugName(nid)
                if value:
                    meta_lines.append(f"{label}: {value}")
            meta_lines.append(f"Glyphs: {len(font.getGlyphOrder())}")
            self.font_meta.setPlainText("\n".join(meta_lines))
        except Exception as e:
            self.font_meta.setPlainText(f"fontTools could not read this file: {e}")

        pangram = ("The quick brown fox jumps over the lazy dog. 0123456789 "
                   "Sphinx of black quartz, judge my vow!")
        html = ["<html><body style='background:#FFFFFF;color:#282B29;padding:18px;'>"]
        try:
            from PySide6.QtGui import QFontDatabase as _db
            families = set(_db.families())
            family = Path(path).stem
            for size in (12, 18, 28, 44, 68):
                html.append(f"<div style=\"font-family:'{family}';font-size:{size}px;"
                            f"margin:10px 0;\">{pangram}</div>")
            if family not in families:
                html.append("<p style='color:#727E96'>Installing this font system-wide lets "
                            "you use it in the specimen; the preview below uses a fallback.</p>")
        except Exception:
            pass
        html.append("</body></html>")
        self.font_specimen.setHtml("".join(html))

    def _load_archive(self):
        self.archive_tree.clear()
        path = Path(self.file_path)
        total = 0
        count = 0
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        node = QTreeWidgetItem([info.filename, _human_size(info.file_size)])
                        node.setData(0, Qt.UserRole, info.filename)
                        self.archive_tree.addTopLevelItem(node)
                        total += info.file_size
                        count += 1
            elif path.suffix.lower() in (".tar", ".tgz") or path.name.lower().endswith(".tar.gz"):
                with tarfile.open(path) as t:
                    for member in t.getmembers():
                        node = QTreeWidgetItem([member.name, _human_size(member.size)])
                        node.setData(0, Qt.UserRole, member.name)
                        self.archive_tree.addTopLevelItem(node)
                        total += member.size
                        count += 1
            else:
                self.archive_info.setText("Archive type not supported for browsing.")
                return
        except Exception as e:
            self.archive_info.setText(f"Cannot read archive: {e}")
            return
        self.archive_info.setText(f"{count} entries | {_human_size(total)} uncompressed")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_wrap(self):
        if self.wrap_check.isChecked():
            self.text_view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        else:
            self.text_view.setLineWrapMode(QPlainTextEdit.NoWrap)

    def _set_font(self, family: str):
        font = QFont(family, 12)
        font.setStyleHint(QFont.Monospace)
        self.text_view.setFont(font)

    def _find(self, needle: str):
        if not needle:
            return
        if self.kind == "text":
            self.text_view.setFocus()
            cursor = self.text_view.find(needle)
            if cursor is not None:
                self.text_view.setTextCursor(cursor)
                self.text_view.ensureCursorVisible()
        elif self.kind == "html":
            self.html_view.setFocus()
            self.html_view.find(needle)
        elif self.kind == "epub":
            self.epub_view.setFocus()
            self.epub_view.find(needle)

    def _copy_all(self):
        if self.kind == "text":
            QApplication.clipboard().setText(self.text_view.toPlainText())
        elif self.kind == "html":
            QApplication.clipboard().setText(self.html_view.toPlainText())
        elif self.kind == "epub":
            QApplication.clipboard().setText(self.epub_view.toPlainText())
        else:
            try:
                QApplication.clipboard().setText(Path(self.file_path).read_text(
                    encoding="utf-8", errors="replace"))
            except Exception:
                pass

    def _export_pdf(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "pdf")
        if res.success:
            QMessageBox.information(self, "PDF Created", f"Saved to:\n{res.output_path}")
        else:
            QMessageBox.warning(self, "Export Failed", res.message)

    def _export_txt(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "extract_text")
        if res.success:
            QMessageBox.information(self, "Text Saved", f"Saved to:\n{res.output_path}")
        else:
            QMessageBox.warning(self, "Export Failed", res.message)

    def _reveal(self):
        try:
            from opal_studio.platform_compat import reveal_in_file_manager
            reveal_in_file_manager(self.file_path)
        except Exception:
            pass

    def _extract_archive(self):
        from opal_studio.engine import OpalEngine
        res = OpalEngine.execute_single(self.file_path, "extract_archive")
        if res.success:
            QMessageBox.information(self, "Extracted", f"Saved to:\n{res.output_path}")
        else:
            QMessageBox.warning(self, "Extract Failed", res.message)

    def _open_archive_item(self):
        item = self.archive_tree.currentItem()
        if not item:
            return
        name = item.data(0, Qt.UserRole)
        if not name:
            return
        try:
            out_dir = Path(self.file_path).parent / f"{Path(self.file_path).stem}_extracted"
            out_dir.mkdir(parents=True, exist_ok=True)
            target = safe_path(out_dir, Path(name).name)
            if self.file_path.lower().endswith(".zip"):
                with zipfile.ZipFile(self.file_path) as z:
                    target.write_bytes(z.read(name))
            else:
                with tarfile.open(self.file_path) as t:
                    member = t.getmember(name)
                    if member.isfile():
                        extracted = t.extractfile(member)
                        if extracted is not None:
                            target.write_bytes(extracted.read())
            self.open_path_signal.emit(str(target))
        except Exception as e:
            QMessageBox.warning(self, "Cannot Open", str(e))


def _short_repr(value) -> str:
    if isinstance(value, (dict, list)):
        return f"{type(value).__name__}({len(value)})"
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _human_size(num: int) -> str:
    if num >= 1024 ** 2:
        return f"{num / 1024 ** 2:.1f} MB"
    if num >= 1024:
        return f"{num / 1024:.0f} KB"
    return f"{num} B"
