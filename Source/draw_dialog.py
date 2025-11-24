import os, tempfile, time
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QToolBar, QColorDialog, QSpinBox, QLabel, QPushButton
from draw_canvas import DrawCanvas

class DrawDialog(QDialog):
    def __init__(self, parent=None, init_color=QColor(255,255,255), init_width=3):
        super().__init__(parent)
        self.setWindowTitle("Рукописная заметка")
        self.resize(1000, 650)

        v_lay = QVBoxLayout(self)
        tb = QToolBar(self)
        v_lay.addWidget(tb)

        self.canvas = DrawCanvas(self, 1920, 1080)
        v_lay.addWidget(self.canvas, 1)

        a_pen = QAction("Кисть", self)
        a_eraser = QAction("Ластик", self)
        a_eraser.setCheckable(True)
        a_color = QAction("Цвет…", self)
        a_undo = QAction("Отменить", self)
        a_redo = QAction("Повторить", self)
        a_clear = QAction("Очистить", self)

        tb.addAction(a_pen)
        tb.addAction(a_eraser)
        tb.addSeparator()
        tb.addAction(a_color)
        tb.addSeparator()
        tb.addAction(a_undo)
        tb.addAction(a_redo)
        tb.addSeparator()
        tb.addAction(a_clear)

        tb.addSeparator()
        tb.addWidget(QLabel("Толщина:"))
        self.sp = QSpinBox(self)
        self.sp.setRange(1, 64)
        self.sp.setValue(init_width)
        tb.addWidget(self.sp)

        bottom = QHBoxLayout()
        v_lay.addLayout(bottom)
        bottom.addStretch(1)
        self.btn_ok = QPushButton("Сохранить")
        self.btn_cancel = QPushButton("Отмена")
        bottom.addWidget(self.btn_ok)
        bottom.addWidget(self.btn_cancel)

        self.canvas.set_pen_color(init_color)
        self.canvas.set_pen_width(init_width)

        a_pen.triggered.connect(lambda: (a_eraser.setChecked(False), self.canvas.set_eraser(False)))
        a_eraser.toggled.connect(self.canvas.set_eraser)
        a_color.triggered.connect(self._pick_color)
        a_undo.triggered.connect(self.canvas.undo)
        a_redo.triggered.connect(self.canvas.redo)
        a_clear.triggered.connect(self.canvas.clear)
        self.sp.valueChanged.connect(self.canvas.set_pen_width)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._save)

        self.saved_path = None

    def _pick_color(self):
        c = QColorDialog.getColor(parent=self, title="Выбор цвета")
        if c.isValid():
            self.canvas.set_pen_color(c)

    def _save(self):
        base = tempfile.gettempdir()
        name = f"drawing_{int(time.time())}.png"
        path = os.path.join(base, name)
        if self.canvas.export_png(path):
            self.saved_path = path
            self.accept()
        else:
            self.saved_path = None
            self.reject()
