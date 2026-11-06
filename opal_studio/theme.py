"""
Opal - Brand theme for the desktop app
Plain English: One place that defines every colour, font and spacing rule the
app uses, plus the global stylesheet.

The whole app is built from one idea: a polished opal. The stone is milky and
almost white, and the colour inside it - teal, blue, violet, rose, amber - is
not painted on but comes from light refracting within. So the app is a deep,
cool, inky field, and every surface on it is a pane of glass: translucent,
lit from above, with a bright edge where the light bends.
"""

from typing import Optional

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QLabel, QWidget

# ---------------------------------------------------------------- palette ---
# The fire inside the stone. These are the brand's colours, in the order the
# light travels through the opal.
FIRE_TEAL = "#21C7D0"
FIRE_BLUE = "#3C7BF2"
FIRE_VIOLET = "#8A5CF6"
FIRE_ROSE = "#EE4E8A"
FIRE_AMBER = "#FF9A3C"
FIRE_GREEN = "#37C98A"
FIRE = [FIRE_TEAL, FIRE_BLUE, FIRE_VIOLET, FIRE_ROSE, FIRE_AMBER, FIRE_GREEN]

# The one colour the user should ever have to notice.
ACCENT = "#6C63FF"
ACCENT_HI = "#8A83FF"
ACCENT_DEEP = "#4E45D6"
ACCENT_DEEPER = "#3A32A8"
ACCENT_SOFT = "rgba(108, 99, 255, 0.20)"
ACCENT_WASH = "rgba(108, 99, 255, 0.12)"

# The deep field the glass sits on.
BG = "#0B0E18"
BG_RAISED = "#141A2B"
BG_SUNK = "#080B13"

# Glass itself. Everything translucent is built from these.
SURFACE = "rgba(255, 255, 255, 0.07)"
SURFACE_ALT = "rgba(255, 255, 255, 0.11)"
SURFACE_SUNK = "rgba(0, 0, 0, 0.24)"
PAPER = "#FFFFFF"              # a sheet of paper, for documents and photos

TEXT = "#EDF1FA"
TEXT_DIM = "#A8B2C8"
TEXT_FAINT = "#8B96AD"
TEXT_INVERSE = "#0B0E18"

INK = "#05070D"
SAND = "#E4D6C6"
LEAF = FIRE_GREEN
LEAF_SOFT = "rgba(55, 201, 138, 0.16)"

# The edges. Light bends where glass meets air.
LINE = "rgba(255, 255, 255, 0.10)"
LINE_STRONG = "rgba(255, 255, 255, 0.18)"
GLASS_SPECULAR = "rgba(255, 255, 255, 0.55)"     # the lit top edge
GLASS_SHADE = "rgba(0, 0, 0, 0.32)"              # the shadowed bottom edge

RADIUS = 12
RADIUS_LARGE = 18
RADIUS_SMALL = 8      # tab corners, tiny sub-elements

# --- Stitch Liquid Glass canonical tokens (captured 2026-11-06 from the
# "Opal Liquid Glass" design system, assets/3539134380188353237; see
# design/stitch/DESIGN.md). Exact values the Stitch screens were built with.
GROUND = "#0B0E18"
GROUND_RAISED = "#141A2B"
GROUND_SUNK = "#080B13"
GLASS_TOP = "rgba(255,255,255,0.18)"    # specular-edge inner top line
GLASS_EDGE = "rgba(255,255,255,0.10)"   # subtle top line
WHEEL_ACTIVE_GRAD = ("#EE4E8A", "#8A5CF6", "#6C63FF")   # rose->violet->violet
SCROLLBAR_THUMB = "rgba(255,255,255,0.12)"
SCROLLBAR_THUMB_HOVER = "rgba(255,255,255,0.22)"

# The field behind the glass: a cool pool of light falling from the top of
# the window, so no surface ever sits on a flat black rectangle.
FIELD = ("qradialgradient(cx: 0.5, cy: -0.1, radius: 1.6, fx: 0.5, fy: -0.1, "
         "stop: 0 #161C30, stop: 0.55 #0E1220, stop: 1 #0B0E18)")

# One type ladder for the whole app, as (px, weight) pairs.
TYPE_TITLE = (22, 700)    # window headlines
TYPE_HEAD = (15, 600)     # dialog and panel titles
TYPE_BODY = (12, 400)     # reading text
TYPE_CAP = (11, 600)      # buttons, tab labels, card titles
TYPE_HINT = (10, 400)     # secondary and helper text

# One glass panel recipe, reused by every card, rail and side pane.
PANEL_CSS = (f"background: {SURFACE}; border: 1px solid {LINE}; "
             f"border-radius: {RADIUS_LARGE}px;")

# ------------------------------------------------------------------ fonts ---
UI_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter",
                "Helvetica Neue", "system-ui", "sans-serif"]
DISPLAY_FAMILIES = ["Segoe UI Variable Display", "Segoe UI", "Inter",
                    "Helvetica Neue", "system-ui", "sans-serif"]
HAND_FAMILIES = ["Segoe Script", "Brush Script MT", "Lucida Handwriting",
                 "Caveat", "cursive"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "monospace"]


def display_font(size: int = 16, weight: int = 600) -> QFont:
    font = QFont(DISPLAY_FAMILIES[0], size)
    font.setWeight(QFont.Weight(weight))
    font.setStyleStrategy(QFont.PreferQuality)
    return font


def text_font(size: int = 10, weight: int = 400) -> QFont:
    font = QFont(UI_FAMILIES[0], size)
    font.setWeight(QFont.Weight(weight))
    return font


def hand_font(size: int = 24) -> QFont:
    font = QFont(HAND_FAMILIES[0], size)
    font.setStyleStrategy(QFont.PreferQuality)
    return font


def mono_font(size: int = 10, weight: int = 400) -> QFont:
    font = QFont(MONO_FAMILIES[0], size)
    font.setWeight(QFont.Weight(weight))
    return font


def apply_field(widget: QWidget, base: Optional[str] = None) -> None:
    """Puts a widget on the deep field.

    Every pane of glass needs something behind it. By default the window gets
    the radial pool of light (FIELD); pass a flat colour to override it. The
    rule is scoped to this one widget, so it never leaks onto the children.
    """
    from PySide6.QtCore import Qt

    name = widget.objectName() or f"opalField{id(widget)}"
    widget.setObjectName(name)
    widget.setAttribute(Qt.WA_StyledBackground, True)
    widget.setStyleSheet(f"#{name} {{ background: {base or FIELD}; }}")


# ------------------------------------------------------------ label helpers ---
# Every headline in the app is made with these, so the type ladder never
# drifts: one call, one look.

def _label(text: str, size: int, weight: int, color: str,
           letter_spacing: float = 0.0, display: bool = False) -> QLabel:
    lbl = QLabel(text)
    font = display_font(size, weight) if display else text_font(size, weight)
    if letter_spacing:
        font.setLetterSpacing(QFont.AbsoluteSpacing, letter_spacing)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def title_label(text: str) -> QLabel:
    """A window headline: 22px semibold display type."""
    return _label(text, *TYPE_TITLE, TEXT, display=True)


def head_label(text: str) -> QLabel:
    """A dialog or panel title: 15px semibold."""
    return _label(text, *TYPE_HEAD, TEXT)


def section_label(text: str) -> QLabel:
    """A small uppercase section header, letterspaced in accent."""
    return _label(text.upper(), TYPE_CAP[0], 700, ACCENT_HI, letter_spacing=1.2)


def body_label(text: str, dim: bool = False) -> QLabel:
    return _label(text, *TYPE_BODY, TEXT_DIM if dim else TEXT)


def hint_label(text: str) -> QLabel:
    return _label(text, *TYPE_HINT, TEXT_FAINT)


# -------------------------------------------------------------- stylesheet ---
def build_stylesheet() -> str:
    """The global look: a deep field, panes of glass, and one lit accent."""
    return f"""
    /* ---------- base ---------- */
    QWidget {{
        color: {TEXT};
        font-family: "{UI_FAMILIES[0]}";
        font-size: 12px;
        background: transparent;
    }}
    QMainWindow, QDialog {{
        background: {FIELD};
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {BG}; }}
    QTabWidget::pane {{ background: {SURFACE}; }}
    QStatusBar {{ background: transparent; }}
    QLabel, QCheckBox, QRadioButton {{
        background: transparent;
        border: none;
    }}

    /* ---------- glass buttons ---------- */
    QPushButton {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {LINE_STRONG};
        border-radius: {RADIUS}px;
        padding: 7px 14px;
        font-size: 11px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {SURFACE_ALT};
        border-color: rgba(255, 255, 255, 0.30);
        color: #FFFFFF;
    }}
    QPushButton:pressed {{ background: rgba(255, 255, 255, 0.04); }}
    QPushButton:disabled {{
        background: rgba(255, 255, 255, 0.03);
        color: rgba(237, 241, 250, 0.28);
        border-color: rgba(255, 255, 255, 0.06);
    }}
    QPushButton[accent="true"] {{
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 {FIRE_VIOLET}, stop: 0.55 {FIRE_ROSE}, stop: 1 {FIRE_AMBER});
        color: #FFFFFF;
        border: none;
        font-weight: 700;
    }}
    QPushButton[accent="true"]:hover {{
        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                        stop: 0 #9B7BFF, stop: 0.55 #FF6BA0, stop: 1 #FFB35C);
    }}
    QPushButton[accent="true"]:disabled {{
        background: rgba(255, 255, 255, 0.05);
        color: rgba(237, 241, 250, 0.28);
    }}
    QPushButton[flat="true"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {TEXT_DIM};
    }}
    QPushButton[flat="true"]:hover {{
        background: {SURFACE};
        color: {TEXT};
        border-color: {LINE};
    }}

    /* ---------- tool buttons & segmented rows ---------- */
    QToolButton {{
        background: {SURFACE};
        color: {TEXT_DIM};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
        padding: 6px 10px;
        font-size: 11px;
        font-weight: 600;
    }}
    QToolButton:hover {{
        background: {SURFACE_ALT};
        color: #FFFFFF;
        border-color: {LINE_STRONG};
    }}
    QToolButton:checked {{
        background: {ACCENT_SOFT};
        color: #FFFFFF;
        border-color: {ACCENT_HI};
    }}
    QToolButton:disabled {{ color: rgba(237,241,250,0.28); }}
    QStackedWidget {{ background: transparent; border: none; padding: 0; }}

    /* ---------- inputs ---------- */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: rgba(255, 255, 255, 0.05);
        color: {TEXT};
        border: 1px solid {LINE_STRONG};
        border-radius: {RADIUS}px;
        padding: 6px 10px;
        selection-background-color: {ACCENT};
        selection-color: {TEXT_INVERSE};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QSpinBox:focus, QComboBox:focus {{
        border-color: {ACCENT_HI};
        background: rgba(255, 255, 255, 0.08);
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: #171D2E;
        border: 1px solid {LINE_STRONG};
        border-radius: {RADIUS}px;
        selection-background-color: {ACCENT};
        selection-color: {TEXT_INVERSE};
        padding: 4px;
    }}
    QCheckBox, QRadioButton {{ color: {TEXT_DIM}; spacing: 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 15px; height: 15px;
        border: 1px solid {LINE_STRONG};
        background: rgba(255, 255, 255, 0.06);
    }}
    QCheckBox::indicator {{ border-radius: 4px; }}
    QRadioButton::indicator {{ border-radius: 8px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {ACCENT}; border-color: {ACCENT};
    }}

    /* ---------- sliders ---------- */
    QSlider::groove:horizontal {{
        background: rgba(255, 255, 255, 0.10); height: 4px; border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: #FFFFFF;
        border: 2px solid {ACCENT};
        width: 12px; height: 12px;
        margin: -5px 0; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ border-color: {ACCENT_HI}; }}

    /* ---------- lists & trees ---------- */
    QListWidget, QTreeWidget, QTableWidget {{
        background: rgba(255, 255, 255, 0.04);
        color: {TEXT};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
        outline: none;
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: 6px 8px; border-radius: 8px;
    }}
    QListWidget::item:hover, QTreeWidget::item:hover {{ background: rgba(255, 255, 255, 0.06); }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background: {ACCENT_SOFT};
        color: #FFFFFF;
    }}
    QHeaderView::section {{
        background: rgba(255, 255, 255, 0.05);
        color: {TEXT_DIM};
        border: none;
        border-bottom: 1px solid {LINE};
        padding: 7px 10px;
        font-size: 11px;
        font-weight: 600;
    }}

    /* ---------- tabs ---------- */
    QTabWidget {{
        background: transparent;
    }}
    QTabBar {{
        background: transparent;
    }}
    QTabWidget::tab-bar {{
        background: transparent;
    }}
    QTabWidget::pane {{
        border: 1px solid {LINE};
        border-radius: {RADIUS_LARGE}px;
        background: {SURFACE};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_DIM};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-size: 12px;
    }}
    QTabBar::tab:hover {{ color: {TEXT}; }}
    QTabBar::tab:selected {{
        background: {SURFACE_ALT};
        color: #FFFFFF;
        font-weight: 600;
    }}

    /* ---------- groups & frames ---------- */
    QGroupBox {{
        border: 1px solid {LINE};
        border-radius: {RADIUS_LARGE}px;
        margin-top: 20px;
        padding: 16px 12px 12px 12px;
        background: {SURFACE};
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 14px; top: 0px;
        padding: 0 6px;
        color: {ACCENT_HI};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.6px;
    }}
    QFrame[card="true"] {{
        background: {SURFACE};
        border: 1px solid {LINE};
        border-radius: {RADIUS_LARGE}px;
    }}

    /* ---------- scrollbars ---------- */
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {SCROLLBAR_THUMB}; border-radius: 9999px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {SCROLLBAR_THUMB_HOVER}; }}
    QScrollBar:horizontal {{
        background: transparent; height: 6px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {SCROLLBAR_THUMB}; border-radius: 9999px; min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {SCROLLBAR_THUMB_HOVER}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ---------- misc ---------- */
    QProgressBar {{
        background: rgba(255, 255, 255, 0.08);
        border: none; border-radius: 3px;
        height: 5px; text-align: center; color: transparent;
    }}
    QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
    QStatusBar {{ background: transparent; color: {TEXT_FAINT}; }}
    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:horizontal {{ width: 6px; }}
    QSplitter::handle:vertical {{ height: 6px; }}
    QMenu {{
        background: #171D2E; color: {TEXT};
        border: 1px solid {LINE_STRONG}; border-radius: 12px; padding: 6px;
    }}
    QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 8px; }}
    QMenu::item:selected {{ background: {ACCENT}; color: {TEXT_INVERSE}; }}
    QMenu::separator {{ height: 1px; background: {LINE}; margin: 6px 10px; }}
    QToolTip {{
        background: #1B2233;
        color: #EDF1FA;
        border: 1px solid {LINE_STRONG};
        padding: 6px 10px;
        border-radius: 8px;
    }}
    """
