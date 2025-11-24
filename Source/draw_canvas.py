from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QImage, QPainter, QPen, QColor, QMouseEvent, QPaintEvent
from PyQt6.QtWidgets import QWidget

class DrawCanvas(QWidget):
    def __init__(self, parent=None, width=1600, height=900):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        self._img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        self._img.fill(QColor(18, 18, 18, 0))
        self._bg = QColor(18, 18, 18)
        self._pen_color = QColor(255, 255, 255)
        self._pen_width = 3
        self._eraser = False
        self._last = None
        self._undo = []
        self._redo = []
        self._push_undo()

    def sizeHint(self):
        return self._img.size()

    def set_pen_color(self, color: QColor):
        self._pen_color = QColor(color)

    def set_pen_width(self, w: int):
        self._pen_width = max(1, int(w))

    def set_eraser(self, enabled: bool):
        self._eraser = bool(enabled)

    def clear(self):
        self._push_undo()
        self._img.fill(QColor(18, 18, 18, 0))
        self.update()

    def _push_undo(self):
        self._undo.append(self._img.copy())
        if len(self._undo) > 30:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self):
        if len(self._undo) <= 1:
            return
        cur = self._undo.pop()
        self._redo.append(cur)
        self._img = self._undo[-1].copy()
        self.update()

    def redo(self):
        if not self._redo:
            return
        self._undo.append(self._redo[-1].copy())
        self._img = self._redo.pop()
        self.update()

    def export_png(self, path: str) -> bool:
        return self._img.save(path, "PNG")

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        p.fillRect(self.rect(), self._bg)
        p.drawImage(QPoint(0, 0), self._img)
        p.end()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._push_undo()
            self._last = e.position().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent):
        if (e.buttons() & Qt.MouseButton.LeftButton) and self._last is not None:
            cur = e.position().toPoint()
            painter = QPainter(self._img)
            if self._eraser:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen = QPen(QColor(0, 0, 0, 0), self._pen_width, Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(self._pen_color, self._pen_width, Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self._last, cur)
            painter.end()
            dirty = QRect(self._last, cur).normalized().adjusted(-self._pen_width, -self._pen_width, self._pen_width, self._pen_width)
            self.update(dirty)
            self._last = cur

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._last = None
