from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPalette, QPen, QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFrame


# Semantic colors are shared by Qt's native widgets, QSS and item delegates.
COLORS = {
    "canvas": "#0E172B",
    "surface": "#182640",
    "field": "#121F37",
    "layer": "#233654",
    "border": "#3C5275",
    "text": "#F1F5FF",
    "muted": "#B0C0DD",
    "disabled": "#8294B3",
    "accent": "#B7C9FF",
    "accent_hover": "#D5DFFF",
    "on_accent": "#142547",
    "selection": "#324C75",
    "teal": "#89E3CC",
    "amber": "#F3CB8D",
    "rose": "#FFACBB",
}

STATUS_TONES = {
    "План": "accent",
    "В работе": "amber",
    "Готово": "teal",
    "Отложено": "muted",
}
PRIORITY_TONES = {1: "teal", 2: "accent", 3: "amber", 4: "rose"}


def apply_theme(app):
    app.setStyle("Fusion")
    family = "Inter" if "Inter" in QFontDatabase.families() else "Segoe UI"
    app.setFont(QFont(family))

    palette = app.palette()
    for role, token in {
        QPalette.ColorRole.Window: "canvas",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "field",
        QPalette.ColorRole.AlternateBase: "surface",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "layer",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "selection",
        QPalette.ColorRole.HighlightedText: "text",
        QPalette.ColorRole.PlaceholderText: "muted",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.ToolTipBase: "layer",
        QPalette.ColorRole.ToolTipText: "text",
    }.items():
        palette.setColor(role, QColor(COLORS[token]))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(COLORS["disabled"]))
    app.setPalette(palette)
    set_interface_size(app, 14)


def set_interface_size(app, size):
    font = app.font()
    font.setPixelSize(size)
    app.setFont(font)
    sheet = GLASS_QSS.replace("@icons@", Path(__file__).resolve().with_name("icons").as_posix())
    for token, color in COLORS.items():
        sheet = sheet.replace(f"@{token}@", color)
    for token, value in {
        "body_size": size,
        "small_size": max(11, size - 2),
        "panel_size": size + 2,
        "detail_size": size + 5,
        "metric_size": size + 10,
        "dialog_size": size + 11,
        "title_size": size + 20,
    }.items():
        sheet = sheet.replace(f"@{token}@", f"{value}px")
    app.setStyleSheet(sheet)


def set_primary(button):
    button.setProperty("variant", "primary")
    button.style().unpolish(button)
    button.style().polish(button)


_ICON_PATHS = {
    "mark": "M6 3.5h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2ZM8 12l2.5 2.5L16 9",
    "list": "M8 6h12M8 12h12M8 18h12M4 6h.1M4 12h.1M4 18h.1",
    "board": "M4 4h16v16H4zM9.3 4v16M14.7 4v16",
    "today": "M4 6h16v14H4zM4 10h16M8 4v4M16 4v4M9 15l2 2 4-4",
    "archive": "M4 4h16v4H4zM6 8v12h12V8M10 12h4",
    "chart": "M4 19h16M7 16v-5M12 16V6M17 16v-8",
    "folder": "M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z",
    "plus": "M12 5v14M5 12h14",
    "search": "M16.5 10a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0ZM15 15l5 5",
    "clock": "M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM12 8v4l3 2",
    "focus": "M9 4H4v5m11-5h5v5m0 6v5h-5m-6 0H4v-5m11-3a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
    "more": "M5 12h.1M12 12h.1M19 12h.1",
    "edit": "M4 20l4.5-1 11-11a2.1 2.1 0 0 0-3-3l-11 11L4 20Zm10-12 3 3",
    "upload": "M12 15V4m-4 4 4-4 4 4M4 15v5h16v-5",
    "download": "M12 4v11m-4-4 4 4 4-4M4 15v5h16v-5",
    "template": "M5 4h14v16H5ZM8 8h8m-8 4h8m-8 4h5",
    "settings": "M4 7h16M4 17h16M8 4v6m8 4v6",
    "user": "M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM5 20v-1a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v1",
    "expand": "M14 4h6v6m0-6-6 6M10 20H4v-6m0 6 6-6",
    "collapse": "M14 4v6h6m-6 0 6-6M10 20v-6H4m6 0-6 6",
    "refresh": "M19 10a7 7 0 1 0-.8 7m-3-7h4V6",
    "repeat": "M4 8h15m-3-3 3 3-3 3M20 16H5m3-3-3 3 3 3",
}


@lru_cache(maxsize=72)
def icon(name, tone="muted"):
    path = _ICON_PATHS[name]
    color = COLORS[tone]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("ascii")))
    result = QIcon()
    for size in (18, 24, 32, 48, 64, 96):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


class GlassOverview(QFrame):
    """Paint the refracted edge inside the overview without raster assets."""

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 16, 16)
        painter.setClipPath(clip)

        width = self.width()
        height = self.height()
        edge = QPainterPath()
        edge.moveTo(width * 0.45, height * 1.36)
        edge.cubicTo(width * 0.62, height * 1.05, width * 0.58, -height * 0.09, width * 0.84, -height * 0.08)
        edge.cubicTo(width * 0.96, -height * 0.06, width * 1.02, height * 0.05, width * 1.05, height * 0.22)
        edge.lineTo(width * 1.05, height * 1.36)
        edge.closeSubpath()

        glass = QLinearGradient(width * 0.46, height, width, 0)
        glass.setColorAt(0, QColor(131, 160, 246, 5))
        glass.setColorAt(0.52, QColor(145, 179, 255, 24))
        glass.setColorAt(1, QColor(160, 197, 255, 68))
        painter.setBrush(glass)
        painter.setPen(QPen(QColor(194, 220, 255, 48), 1.1))
        painter.drawPath(edge)

        reflection = QPainterPath()
        reflection.moveTo(width * 0.57, height * 1.13)
        reflection.cubicTo(width * 0.7, height * 0.66, width * 0.66, -height * 0.06, width * 0.95, -height * 0.13)
        painter.setPen(QPen(QColor(179, 218, 255, 43), 1))
        painter.drawPath(reflection)


GLASS_QSS = """
QWidget { color: @text@; font-size: @body_size@; }
QWidget#Workspace {
    background: qradialgradient(cx:0.86, cy:0.06, fx:0.86, fy:0.06, radius:0.93,
        stop:0 #293C63, stop:0.42 #192949, stop:1 @canvas@);
}
QMainWindow, QDialog { background: @canvas@; }
QDialog#LoginWindow {
    background: qradialgradient(cx:0.92, cy:0, fx:0.92, fy:0, radius:1.18,
        stop:0 #304972, stop:0.53 #192843, stop:1 @canvas@);
}
QFrame#LeftNav {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(62,83,124,143), stop:0.5 rgba(35,53,87,147), stop:1 rgba(17,30,52,219));
    border: 1px solid rgba(172,195,243,56);
    border-top-color: rgba(192,212,255,99);
    border-radius: 17px;
}
QFrame#Overview {
    background: qlineargradient(x1:0,y1:1,x2:1,y2:0,
        stop:0 rgba(30,51,84,217), stop:0.51 rgba(62,90,137,137), stop:1 rgba(93,120,173,141));
    border: 1px solid rgba(182,204,253,80);
    border-top-color: rgba(200,220,255,129);
    border-radius: 17px;
}
QFrame[surface="glass"] {
    background: qlineargradient(x1:0,y1:0,x2:0.82,y2:1,
        stop:0 rgba(58,79,118,141), stop:0.35 rgba(34,53,85,186), stop:1 rgba(18,32,55,201));
    border: 1px solid rgba(160,187,240,60);
    border-top-color: rgba(191,212,252,92);
    border-radius: 16px;
}
QFrame#KanbanColumn {
    background: rgba(24,38,64,183);
    border: 1px solid rgba(166,191,240,57);
    border-radius: 14px;
}
QFrame#TimerPanel {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 12px;
}
QFrame[rule="true"] { border: 0; background: rgba(170,198,255,56); }
QLabel#WorkspaceTitle { font-size: @title_size@; font-weight: 700; }
QLabel#BrandTitle { font-size: @panel_size@; font-weight: 700; }
QLabel#BrandMark, QLabel#EmptyMark {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(190,211,255,68), stop:1 rgba(121,154,222,22));
    border: 1px solid rgba(184,207,255,79);
    border-top-color: rgba(210,226,255,122);
    border-radius: 10px;
}
QLabel#PanelTitle { font-size: @panel_size@; font-weight: 700; }
QLabel#SectionTitle { font-weight: 600; }
QLabel#DialogTitle { font-size: @dialog_size@; font-weight: 700; }
QLabel#MetricValue { font-size: @metric_size@; font-weight: 700; }
QLabel#MetricLabel, QLabel[muted="true"] { color: @muted@; }
QLabel[tone="accent"] { color: @accent@; }
QLabel[tone="amber"] { color: @amber@; }
QLabel[tone="teal"] { color: @teal@; }
QLabel[tone="rose"] { color: @rose@; }
QLabel#ColumnCount {
    background: rgba(172,196,244,24);
    color: @muted@;
    border: 1px solid rgba(182,205,251,45);
    border-radius: 8px;
    padding: 2px 7px;
}

QPushButton, QToolButton {
    background: rgba(169,195,250,19);
    border: 1px solid rgba(182,205,251,45);
    border-radius: 8px;
    padding: 7px 11px;
    min-height: 19px;
    font-weight: 600;
}
QPushButton:hover, QToolButton:hover { background: rgba(169,195,250,40); }
QPushButton:pressed, QToolButton:pressed { background: rgba(137,171,236,62); }
QPushButton:checked, QToolButton:checked {
    background: @selection@;
    border-color: @border@;
}
QPushButton[variant="primary"], QToolButton[variant="primary"] {
    background: qlineargradient(x1:0,y1:0,x2:0.9,y2:1, stop:0 @accent_hover@, stop:1 @accent@);
    border: 1px solid @accent@;
    color: @on_accent@;
}
QPushButton[variant="primary"]:hover, QToolButton[variant="primary"]:hover { background: @accent_hover@; }
QPushButton[variant="primary"]:pressed, QToolButton[variant="primary"]:pressed { background: @accent@; }
QPushButton[variant="nav"], QToolButton[variant="nav"] {
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
}
QPushButton[variant="nav"]:hover, QToolButton[variant="nav"]:hover {
    background: rgba(169,195,250,25);
    border-color: rgba(182,205,251,35);
}
QPushButton[variant="nav"]:checked {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(151,182,252,71), stop:1 rgba(137,171,236,33));
    border-color: rgba(180,202,251,93);
    color: @text@;
}
QPushButton:focus, QToolButton:focus,
QPushButton[variant]:focus, QToolButton[variant]:focus { border-color: @accent_hover@; }
QPushButton:disabled, QToolButton:disabled,
QPushButton[variant]:disabled, QToolButton[variant]:disabled {
    color: @disabled@;
    background: rgba(169,195,250,9);
    border-color: rgba(182,205,251,25);
}
QPushButton::menu-indicator { image: none; }
QToolBar { border: 0; padding: 5px; spacing: 6px; background: transparent; }
QToolBar::separator { background: @border@; width: 1px; margin: 4px 5px; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit {
    background: @field@;
    color: @text@;
    selection-background-color: @selection@;
    selection-color: @text@;
    border: 1px solid @border@;
    border-radius: 8px;
    padding: 6px 9px;
}
QLineEdit, QComboBox, QSpinBox, QDateEdit { min-height: 19px; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDateEdit:focus { border-color: @accent@; }
QLineEdit#TaskSearch { min-height: 23px; }
QLineEdit QToolButton { background: transparent; padding: 0; min-height: 0; border: 0; }
QLineEdit#DetailTitle { font-size: @detail_size@; font-weight: 600; }
QComboBox, QDateEdit, QSpinBox { padding-right: 22px; }
QComboBox::drop-down, QDateEdit::drop-down { border: 0; width: 20px; }
QComboBox::down-arrow, QDateEdit::down-arrow {
    image: url("@icons@/chevron-down.svg");
    width: 12px; height: 12px;
}
QSpinBox::up-button, QSpinBox::down-button { border: 0; width: 20px; }
QSpinBox::up-arrow { image: url("@icons@/chevron-up.svg"); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url("@icons@/chevron-down.svg"); width: 10px; height: 10px; }
QComboBox QLineEdit, QAbstractSpinBox QLineEdit { border: 0; background: transparent; padding: 0; }
QComboBox QAbstractItemView, QCalendarWidget {
    background: @surface@;
    color: @text@;
    border: 1px solid @border@;
    selection-background-color: @selection@;
}
QCheckBox { spacing: 7px; padding: 3px; border: 1px solid transparent; border-radius: 5px; }
QCheckBox:focus { border-color: @accent@; }
QCheckBox::indicator, QListWidget#SubtaskList::indicator {
    width: 14px; height: 14px; border-radius: 4px; border: 1px solid @disabled@;
    background: @field@;
}
QCheckBox::indicator:checked, QListWidget#SubtaskList::indicator:checked {
    image: url("@icons@/check.svg");
    border-color: @accent@;
    background: @accent@;
}
QGroupBox { border: 1px solid @border@; border-radius: 9px; margin-top: 10px; padding-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 5px; color: @muted@; }

QAbstractItemView {
    border: 1px solid rgba(167,193,243,47);
    border-radius: 8px;
    background: @field@;
    selection-background-color: @selection@;
    selection-color: @text@;
    outline: 0;
}
QAbstractItemView:focus { border-color: @accent@; }
QAbstractItemView::item:selected { background: @selection@; color: @text@; }
QListWidget::item { padding: 5px 7px; }
QListWidget::item:hover { background: rgba(135,166,223,30); }
QListWidget#ProjectsList { border: 1px solid transparent; background: transparent; }
QListWidget#ProjectsList:focus { border-color: @accent@; }
QListWidget#ProjectsList::item { margin-bottom: 2px; padding: 5px 6px; border-radius: 7px; }
QListWidget#KanbanList, QListWidget#TaskGallery {
    border: 1px solid transparent;
    background: transparent;
}
QListWidget#KanbanList:focus, QListWidget#TaskGallery:focus { border-color: @accent@; }

QTableView { gridline-color: @border@; alternate-background-color: @surface@; }
QTableView#TaskTable { background: transparent; border: 1px solid transparent; }
QTableView#TaskTable:focus { border-color: @accent@; }
QTableView::item { padding: 0 7px; }
QTableView::item:hover:!selected { background: rgba(151,181,237,21); }
QHeaderView { background: transparent; }
QHeaderView::section {
    color: @muted@;
    background: rgba(15,30,56,161);
    border: 0;
    border-bottom: 1px solid rgba(173,198,247,56);
    padding: 8px 8px;
    font-size: @small_size@;
    font-weight: 600;
}
QHeaderView::section:hover { background: @layer@; }
QTableCornerButton::section { background: @surface@; border: 0; }

QScrollArea { border: 0; background: transparent; }
QWidget#DetailBody { background: transparent; }
QLabel#DrawingPreview { background: @field@; border: 1px solid @border@; border-radius: 8px; }
QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: rgba(175,202,255,41); border-radius: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: transparent; border: 0; margin: 0; }
QScrollBar:vertical { width: 8px; }
QScrollBar:horizontal { height: 8px; }
QScrollBar::handle { background: @border@; border-radius: 4px; min-width: 24px; min-height: 24px; }
QScrollBar::handle:hover { background: @disabled@; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QMenu {
    background: @surface@;
    border: 1px solid @border@;
    padding: 5px;
}
QMenu::item { padding: 7px 24px 7px 30px; border-radius: 6px; }
QMenu::item:selected { background: @selection@; }
QMenu::separator { background: @border@; height: 1px; margin: 4px 7px; }
QToolTip { padding: 4px; }
QStatusBar { background: @canvas@; color: @muted@; font-size: @small_size@; }
QStatusBar::item { border: 0; }
QTabWidget::pane { border: 1px solid @border@; border-radius: 8px; }
QTabBar::tab { padding: 7px 12px; color: @muted@; background: @field@; }
QTabBar::tab:selected { background: @selection@; color: @text@; }
QTabBar::tab:focus { border: 1px solid @accent@; }
"""
