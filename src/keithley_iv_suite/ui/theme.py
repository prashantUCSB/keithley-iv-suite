"""Charcoal / amber theme — colours, fonts, and Qt stylesheet."""
from __future__ import annotations

# ── App identity ─────────────────────────────────────────────────────────────
VERSION   = "2.2.0"
DEVELOPER = "Prashant Srinivasan"

GREEN_BRIGHT = "#22c55e"   # version badge
TEXT_CREDIT  = "#94a3b8"   # muted slate for developer name

# ── Palette ─────────────────────────────────────────────────────────────────
BG_DEEP     = "#141414"
BG_BASE     = "#1A1A1A"
BG_PANEL    = "#242424"
BG_WIDGET   = "#2D2D2D"
BG_INPUT    = "#333333"
BORDER      = "#3A3A3A"
BORDER_LITE = "#444444"

AMBER       = "#FFB300"
AMBER_LIGHT = "#FFCA28"
AMBER_DIM   = "#CC8F00"
AMBER_GLOW  = "#FFD54F"

TEXT_PRIMARY   = "#F5F5F5"
TEXT_SECONDARY = "#AAAAAA"
TEXT_MUTED     = "#666666"
TEXT_ON_AMBER  = "#141414"

SUCCESS = "#4CAF50"
ERROR   = "#EF5350"
WARNING = "#FF9800"
INFO    = "#29B6F6"

# ── Plot curve colours (cycled for multi-curve output) ───────────────────────
PLOT_COLORS = [
    "#FFB300",  # amber
    "#29B6F6",  # sky blue
    "#66BB6A",  # green
    "#EF5350",  # red
    "#AB47BC",  # purple
    "#26C6DA",  # cyan
    "#FFA726",  # orange
    "#EC407A",  # pink
]

PLOT_BG     = "#0F0F0F"
PLOT_AXIS   = "#555555"
PLOT_GRID   = "#2A2A2A"

# ── Sizes ────────────────────────────────────────────────────────────────────
FONT_SIZE_BASE  = 11
FONT_SIZE_SMALL = 9
FONT_SIZE_LARGE = 13
FONT_SIZE_TITLE = 15

RADIUS  = 6     # border-radius for widgets
RADIUS_S = 4
PADDING = 6


def stylesheet() -> str:
    """Return the complete Qt application stylesheet."""
    r  = str(RADIUS)
    rs = str(RADIUS_S)
    p  = str(PADDING)
    fs = str(FONT_SIZE_BASE)
    return f"""
/* ── Global ─────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: {fs}pt;
    selection-background-color: {AMBER_DIM};
    selection-color: {TEXT_ON_AMBER};
}}

QMainWindow {{
    background-color: {BG_DEEP};
}}

/* ── Scroll areas ───────────────────────────────────────────────────────── */
QScrollArea {{ border: none; }}
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_LITE}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {AMBER_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_PANEL};
    height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_LITE}; border-radius: 4px; min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {AMBER_DIM}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Frames / Group boxes ───────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {BORDER};
}}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: {r}px;
    margin-top: 18px;
    padding-top: 8px;
    font-size: {FONT_SIZE_SMALL}pt;
    color: {TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {AMBER};
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}

/* ── Labels ─────────────────────────────────────────────────────────────── */
QLabel {{ background: transparent; }}
QLabel[role="title"] {{
    font-size: {FONT_SIZE_TITLE}pt;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel[role="section"] {{
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
    color: {AMBER};
    letter-spacing: 0.06em;
    text-transform: uppercase;
}}
QLabel[role="status-ok"]  {{ color: {SUCCESS}; font-weight: 600; }}
QLabel[role="status-err"] {{ color: {ERROR};   font-weight: 600; }}
QLabel[role="status-warn"]{{ color: {WARNING}; font-weight: 600; }}
QLabel[role="muted"] {{ color: {TEXT_MUTED}; font-size: {FONT_SIZE_SMALL}pt; }}

/* ── Buttons ────────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BG_WIDGET};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LITE};
    border-radius: {rs}px;
    padding: 5px 14px;
    font-size: {fs}pt;
}}
QPushButton:hover {{
    background-color: {BG_INPUT};
    border-color: {AMBER_DIM};
}}
QPushButton:pressed {{
    background-color: {AMBER_DIM};
    color: {TEXT_ON_AMBER};
}}
QPushButton:disabled {{
    background-color: {BG_PANEL};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QPushButton[role="primary"] {{
    background-color: {AMBER};
    color: {TEXT_ON_AMBER};
    font-weight: 700;
    border: none;
    padding: 6px 20px;
}}
QPushButton[role="primary"]:hover {{
    background-color: {AMBER_LIGHT};
}}
QPushButton[role="primary"]:pressed {{
    background-color: {AMBER_DIM};
}}
QPushButton[role="primary"]:disabled {{
    background-color: #5A4500;
    color: #7A6A30;
}}
QPushButton[role="danger"] {{
    background-color: {BG_WIDGET};
    color: {ERROR};
    border: 1px solid {ERROR};
}}
QPushButton[role="danger"]:hover {{
    background-color: {ERROR};
    color: {TEXT_PRIMARY};
}}
QPushButton[role="stop"] {{
    background-color: {ERROR};
    color: {TEXT_PRIMARY};
    font-weight: 700;
    border: none;
    padding: 6px 20px;
}}
QPushButton[role="stop"]:hover {{
    background-color: #FF7043;
}}

/* ── Line edits / Spin boxes / Combo boxes ──────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: {rs}px;
    padding: 3px 7px;
    selection-background-color: {AMBER_DIM};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {AMBER};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background: {BG_WIDGET};
    border-left: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    width: 16px;
    border-top-right-radius: {rs}px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {BG_WIDGET};
    border-left: 1px solid {BORDER};
    width: 16px;
    border-bottom-right-radius: {rs}px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {AMBER_DIM};
}}

QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: {rs}px;
    padding: 3px 7px;
    min-width: 80px;
}}
QComboBox:focus {{ border-color: {AMBER}; }}
QComboBox::drop-down {{
    width: 20px;
    border-left: 1px solid {BORDER};
    subcontrol-origin: padding;
}}
QComboBox::down-arrow {{
    width: 8px; height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {AMBER};
}}
QComboBox QAbstractItemView {{
    background: {BG_WIDGET};
    border: 1px solid {AMBER_DIM};
    selection-background-color: {AMBER_DIM};
    selection-color: {TEXT_ON_AMBER};
    border-radius: {rs}px;
    outline: none;
    padding: 2px;
}}

/* ── Tab widget ─────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: {r}px;
    background: {BG_PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background: {BG_WIDGET};
    color: {TEXT_SECONDARY};
    padding: 6px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: {rs}px;
    border-top-right-radius: {rs}px;
    margin-right: 2px;
    font-size: {FONT_SIZE_SMALL}pt;
}}
QTabBar::tab:selected {{
    background: {BG_PANEL};
    color: {AMBER};
    border-color: {AMBER_DIM};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: {BG_INPUT};
    color: {TEXT_PRIMARY};
}}

/* ── Table / List views ─────────────────────────────────────────────────── */
QTableWidget, QListWidget, QTreeWidget {{
    background-color: {BG_PANEL};
    alternate-background-color: {BG_WIDGET};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: {rs}px;
    outline: none;
}}
QTableWidget::item, QListWidget::item, QTreeWidget::item {{
    padding: 4px 8px;
}}
QTableWidget::item:selected, QListWidget::item:selected,
QTreeWidget::item:selected {{
    background-color: {AMBER_DIM};
    color: {TEXT_ON_AMBER};
}}
QHeaderView::section {{
    background-color: {BG_WIDGET};
    color: {AMBER};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
    letter-spacing: 0.05em;
}}

/* ── Splitter ───────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical   {{ height: 2px; }}
QSplitter::handle:hover {{
    background: {AMBER_DIM};
}}

/* ── Progress bar ───────────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER};
    border-radius: {rs}px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {AMBER_DIM}, stop:1 {AMBER_LIGHT}
    );
    border-radius: {rs}px;
}}

/* ── Status bar ─────────────────────────────────────────────────────────── */
QStatusBar {{
    background: {BG_DEEP};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: {FONT_SIZE_SMALL}pt;
}}
QStatusBar::item {{ border: none; }}

/* ── Menu bar ───────────────────────────────────────────────────────────── */
QMenuBar {{
    background: {BG_DEEP};
    color: {TEXT_SECONDARY};
    border-bottom: 1px solid {BORDER};
    font-size: {FONT_SIZE_SMALL}pt;
    spacing: 4px;
    padding: 2px 4px;
}}
QMenuBar::item {{ padding: 4px 10px; border-radius: {rs}px; }}
QMenuBar::item:selected {{ background: {BG_WIDGET}; color: {TEXT_PRIMARY}; }}
QMenu {{
    background: {BG_WIDGET};
    border: 1px solid {AMBER_DIM};
    border-radius: {rs}px;
    padding: 4px;
}}
QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: {rs}px; }}
QMenu::item:selected {{
    background: {AMBER_DIM};
    color: {TEXT_ON_AMBER};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ── Tooltips ───────────────────────────────────────────────────────────── */
QToolTip {{
    background: {BG_WIDGET};
    color: {TEXT_PRIMARY};
    border: 1px solid {AMBER_DIM};
    border-radius: {rs}px;
    padding: 4px 8px;
    font-size: {FONT_SIZE_SMALL}pt;
}}

/* ── CheckBox / RadioButton ─────────────────────────────────────────────── */
QCheckBox, QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 6px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER_LITE};
    background: {BG_INPUT};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {AMBER};
    border-color: {AMBER};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {AMBER};
}}

/* ── Dock widget ────────────────────────────────────────────────────────── */
QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background: {BG_PANEL};
    padding: 6px 10px;
    border-bottom: 1px solid {BORDER};
    color: {AMBER};
    font-size: {FONT_SIZE_SMALL}pt;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-align: center;
}}
"""
