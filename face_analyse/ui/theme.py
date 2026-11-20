"""Identité visuelle : noir profond, blanc lumineux, typographie fine."""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase

BG = "#030303"
PANEL = "#0a0a0a"
PANEL_2 = "#111111"
LINE = "#1f1f1f"
LINE_2 = "#2c2c2c"
FG = "#ececec"
MUTED = "#7d7d7d"
WHITE = "#ffffff"
OK = "#d9ffe6"
WARN = "#ffe9b0"
DANGER = "#ff9a9a"

QC_WHITE = QColor(WHITE)
QC_UNKNOWN = QColor("#ffb4b4")
QC_KNOWN = QColor("#ffffff")


def ui_font_family() -> str:
    families = set(QFontDatabase.families())
    for name in ("Segoe UI Variable Display", "Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans"):
        if name in families:
            return name
    return QFont().defaultFamily()


def mono_font_family() -> str:
    families = set(QFontDatabase.families())
    for name in ("Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"):
        if name in families:
            return name
    return "monospace"


def title_font(size: int = 30, weight: QFont.Weight = QFont.Weight.ExtraLight) -> QFont:
    f = QFont(ui_font_family(), size)
    f.setWeight(weight)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, size * 0.35)
    return f


def apply_fonts(app) -> None:
    """Espacement des lettres via QFont (pris en compte dans le calcul des
    tailles, contrairement à « letter-spacing » des feuilles de style)."""
    from PySide6.QtWidgets import QPushButton, QTabBar

    for cls, spacing in ((QPushButton, 1.6), (QTabBar, 1.6)):
        f = QFont(app.font())
        f.setFamily(ui_font_family())
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        app.setFont(f, cls.__name__)


def stylesheet() -> str:
    family = ui_font_family()
    mono = mono_font_family()
    base_size = 10 if sys.platform.startswith("win") else 11
    return f"""
* {{ font-family: "{family}"; font-size: {base_size}pt; color: {FG}; }}
QMainWindow, QDialog, QWidget#Root {{ background: {BG}; }}
QWidget#Page {{ background: transparent; }}
QToolTip {{ background: {PANEL_2}; color: {FG}; border: 1px solid {LINE_2}; padding: 4px; }}

QLabel#H1 {{ font-size: {base_size + 9}pt; font-weight: 200; letter-spacing: 6px; color: {WHITE}; }}
QLabel#H2 {{ font-size: {base_size + 1}pt; font-weight: 300; letter-spacing: 4px; color: {MUTED}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Mono {{ font-family: "{mono}"; color: {FG}; }}
QLabel#Warn {{ color: {WARN}; }}
QLabel#Danger {{ color: {DANGER}; }}

QFrame#Card {{ background: rgba(14,14,14,0.92); border: 1px solid {LINE}; border-radius: 6px; }}
QFrame#Sidebar {{ background: rgba(6,6,6,0.96); border-right: 1px solid {LINE}; }}

QPushButton {{
    background: transparent; border: 1px solid {LINE_2}; border-radius: 4px;
    padding: 7px 16px; color: {FG};
}}
QPushButton:hover {{ border-color: {WHITE}; color: {WHITE}; background: rgba(255,255,255,0.04); }}
QPushButton:pressed {{ background: rgba(255,255,255,0.10); }}
QPushButton:disabled {{ color: #444; border-color: #1a1a1a; }}
QPushButton#Primary {{ border-color: {WHITE}; color: {WHITE}; }}
QPushButton#Primary:hover {{ background: {WHITE}; color: {BG}; }}
QPushButton#Danger {{ border-color: #5a2a2a; color: {DANGER}; }}
QPushButton#Danger:hover {{ background: #2a0f0f; }}

QPushButton#NavButton {{
    border: none; border-left: 2px solid transparent; border-radius: 0;
    text-align: left; padding: 12px 22px; color: {MUTED};
}}
QPushButton#NavButton:hover {{ color: {WHITE}; background: rgba(255,255,255,0.03); }}
QPushButton#NavButton:checked {{ color: {WHITE}; border-left: 2px solid {WHITE}; background: rgba(255,255,255,0.05); }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {PANEL}; border: 1px solid {LINE_2}; border-radius: 4px; padding: 6px 8px;
    selection-background-color: #333;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {WHITE}; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {LINE_2}; selection-background-color: #222; }}

QTableWidget, QTreeWidget, QListWidget {{
    background: {PANEL}; border: 1px solid {LINE}; gridline-color: {LINE}; alternate-background-color: #0d0d0d;
}}
QHeaderView::section {{ background: {PANEL_2}; color: {MUTED}; border: none; border-bottom: 1px solid {LINE};
    padding: 6px; letter-spacing: 1px; }}
QTableWidget::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{ background: #1e1e1e; color: {WHITE}; }}

QProgressBar {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 2px; height: 4px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {WHITE}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: #2a2a2a; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: #2a2a2a; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}

QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {LINE_2}; background: {PANEL}; }}
QCheckBox::indicator:checked {{ background: {WHITE}; border-color: {WHITE}; }}
QSlider::groove:horizontal {{ height: 2px; background: {LINE_2}; }}
QSlider::handle:horizontal {{ background: {WHITE}; width: 12px; margin: -6px 0; border-radius: 6px; }}
QTabWidget::pane {{ border: 1px solid {LINE}; }}
QTabBar::tab {{ background: transparent; padding: 8px 18px; color: {MUTED}; letter-spacing: 2px; border-bottom: 1px solid transparent; }}
QTabBar::tab:selected {{ color: {WHITE}; border-bottom: 1px solid {WHITE}; }}
QStatusBar {{ background: {BG}; color: {MUTED}; border-top: 1px solid {LINE}; }}
QMessageBox {{ background: {PANEL}; }}
"""
