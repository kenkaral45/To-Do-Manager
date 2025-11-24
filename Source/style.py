
DARK_QSS = """
* { font-family: "Segoe UI"; font-size: 14px; }
QMainWindow, QWidget { background: #2b2b2b; color: #e0e0e0; }
QGroupBox { border: 1px solid #3d3d3d; border-radius: 8px; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #a8a8a8; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit {
  background: #3a3a3a; border: 1px solid #555; padding: 6px 8px; border-radius: 8px;
}
QMainWindow#MainWindow {
  background-color: #111111;
}

QWidget {
  background-color: #111111;
  color: #e5e5e5;
  font-family: "Segoe UI", system-ui;
  font-size: 10pt;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus { border: 1px solid #6eaaff; }
QPushButton { background: #4c4c4c; border-radius: 8px; padding: 6px 14px; }
QPushButton:hover { background: #5c5c5c; }
QPushButton:pressed { background: #3d3d3d; }
QToolBar { background: #222; spacing: 8px; padding: 8px; }
QToolButton { background: #3a3a3a; padding: 8px 12px; border-radius: 8px; }
QToolButton:hover { background: #4a4a4a; }
QToolButton:pressed { background: #2d2d2d; }
QTableView { gridline-color: #555; background: #2b2b2b; alternate-background-color: #323232; border: 1px solid #444; }
QHeaderView::section { background: #3a3a3a; border: 1px solid #555; padding: 6px; color: #ddd; }
QTableView::item:selected { background: #5566ff; color: white; }
QTableView::item:hover { background: #3d3d3d; }
QStatusBar { background: #222; color: #bbb; }
QCheckBox { spacing: 8px; }
QScrollArea { border: none; }
QListWidget {
  background: #2b2b2b;
  border: 1px solid #444;
  border-radius: 8px;
}
QListWidget::item {
  margin: 4px;
  padding: 6px;
}
QListWidget::item:selected {
  background: #455a64;
}
QFrame#LeftNav {
  background: #252525;
  border-right: 1px solid #444;
}
QFrame#TimerPanel {
  background: #333;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  border: 1px solid #555;
}
/* текст описания в детальном виде */
QTextEdit#DetailDesc {
  background: #303030;
  border: 1px solid #555;
  border-radius: 10px;
  padding: 8px 10px;
}

/* чекбоксы — чтобы индикатор был виден */
QCheckBox::indicator {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid #777;
  background: #3a3a3a;
}

QCheckBox::indicator:hover {
  border: 1px solid #a0a0a0;
}

QCheckBox::indicator:checked {
  background: #4caf50;
  border: 1px solid #81c784;
}

/* чекаемые айтемы в списке подзадач */
QListWidget::item:selected:!active {
  background: #455a64;
}
QListWidget::item:selected:active {
  background: #455a64;
}
/* канбан-колонки */
QFrame#KanbanColumn {
  background: #333333;
  border-radius: 12px;
  border: 1px solid #444444;
}

/* заголовок колонки */
QFrame#KanbanColumn > QLabel {
  font-weight: 600;
  padding: 4px;
}

/* список карточек внутри канбана */
QListWidget#KanbanList {
  background: transparent;
  border: none;
}

/* сами карточки */
QListWidget#KanbanList::item {
  margin: 4px;
  padding: 6px 8px;
  border-radius: 8px;
  background: #2e2e2e;
  border: 1px solid #454545;
}

QListWidget#KanbanList::item:selected {
  background: #455a64;
  border-color: #607d8b;
}
QFrame#LeftNav {
  background-color: #141414;
  border-right: 1px solid #262626;
}

QFrame#LeftNav QLabel {
  color: #bbbbbb;
  font-weight: 600;
  padding: 4px 10px;
}

QPushButton[LeftNav="true"] {
  background: transparent;
  border-radius: 10px;
  padding: 8px 12px;
  text-align: left;
  border: 1px solid transparent;
}

QPushButton[LeftNav="true"]:hover {
  background: #1f1f1f;
  border-color: #313131;
}

QPushButton[LeftNav="true"]:checked {
  background: #2a2a2a;
  border-color: #3d82f6;
  color: #ffffff;
}
QFrame#DetailCard {
  background-color: #181818;
  border-radius: 16px;
  border: 1px solid #262626;
}

QLineEdit#DetailTitle, QLineEdit#detail_title {
  font-size: 20pt;
  font-weight: 600;
  border: none;
  background: transparent;
  padding: 4px 0 16px 0;
}

QLabel#DetailMeta {
  color: #b0b0b0;
  font-size: 9pt;
}
QTextEdit#DetailDesc {
  background: #202020;
  border: 1px solid #3a3a3a;
  border-radius: 10px;
  padding: 10px 12px;
}
/* подзадачи: зелёный прямоугольник, когда отмечена */
QListWidget#SubtaskList {
  background: #2b2b2b;
  border: 1px solid #444;
  border-radius: 8px;
}
QListWidget#SubtaskList::item {
  margin: 2px;
  padding: 4px 8px;
  border-radius: 6px;
}
"""
