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

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QWidget

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
TEXT_FAINT = "#727E96"
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


def apply_field(widget: QWidget, base: str = BG) -> None:
    """Puts a widget on the deep field.

    Every pane of glass needs something behind it. The window paints the
    colour; this gives the plain widgets the same job, so nothing is left
    sitting on the light default. The rule is scoped to this one widget, so
    it never leaks onto the children.
    """
    from PySide6.QtCore import Qt

    name = widget.objectName() or f"opalField{id(widget)}"
    widget.setObjectName(name)
    widget.setAttribute(Qt.WA_StyledBackground, True)
    widget.setStyleSheet(f"#{name} {{ background: {base}; }}")


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
        background: {BG};
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {BG}; }}
    QTabWidget::pane {{ background: {SURFACE}; }}
    QStatusBar {{ background: transparent; }}
    QLabel, QCheckBox, QRadioButton {{ background: transparent; }}

    /* ---------- glass buttons ---------- */
    QPushButton {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {LINE_STRONG};
        border-radius: {RADIUS}px;
        padding: 7px 14px;
        font-size: 11.5px;
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
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
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
        background: rgba(255, 255, 255, 0.16); border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 0.30); }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(255, 255, 255, 0.16); border-radius: 4px; min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: rgba(255, 255, 255, 0.30); }}
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
