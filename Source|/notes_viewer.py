# notes_viewer.py
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLabel

try:
    from PyQt6.QtSvgWidgets import QSvgWidget
except Exception:
    QSvgWidget = None

try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:
    QSvgRenderer = None


class NotesPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        h = QHBoxLayout()
        self.list = QListWidget(self)
        self.list.setMinimumWidth(220)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        h.addWidget(self.list)

        self.preview_svg = QSvgWidget() if QSvgWidget is not None else None
        if self.preview_svg is not None:
            self.preview_svg.setMinimumHeight(180)
            self.preview_svg.setStyleSheet("border:1px solid #333;border-radius:10px;")
            h.addWidget(self.preview_svg, 1)
            self.preview_png = None
        else:
            self.preview_png = QLabel(self)
            self.preview_png.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_png.setMinimumHeight(180)
            self.preview_png.setStyleSheet("border:1px solid #333;border-radius:10px;")
            h.addWidget(self.preview_png, 1)
            self.preview_svg = None

        v.addLayout(h, 1)

        self.list.currentItemChanged.connect(self._on_item)

        self._task_id = None
        self._items = []

    def load_for_task(self, task_id: int):
        from PyQt6.QtSql import QSqlQuery
        self._task_id = int(task_id)
        self.list.clear()
        self._clear_preview()
        self._items.clear()

        q = QSqlQuery()
        q.prepare("SELECT id, name, path FROM attachments WHERE task_id=? ORDER BY id")
        q.addBindValue(self._task_id)
        if q.exec():
            while q.next():
                aid = int(q.value(0))
                name = q.value(1) or ""
                path = q.value(2) or ""
                low = path.lower()
                if low.endswith(".png") or (low.endswith(".svg") and (QSvgWidget or QSvgRenderer)):
                    it = QListWidgetItem(name or path)
                    it.setData(Qt.ItemDataRole.UserRole, (aid, path))
                    it.setSizeHint(QSize(0, 28))
                    self.list.addItem(it)
                    self._items.append((aid, path))

        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _on_item(self, it: QListWidgetItem, _prev):
        if not it:
            self._clear_preview()
            return
        _, path = it.data(Qt.ItemDataRole.UserRole)
        self._render(path)

    def _clear_preview(self):
        if self.preview_svg is not None:
            self.preview_svg.load(b"")
        if self.preview_png is not None:
            self.preview_png.clear()

    def _render(self, path: str):
        low = path.lower()
        if low.endswith(".png"):
            if self.preview_png is None:
                pass
            pm = QPixmap(path)
            if not pm.isNull() and self.preview_png is not None:
                target = self.preview_png.size() - QSize(16, 16)
                self.preview_png.setPixmap(pm.scaled(
                    target if target.width() > 0 and target.height() > 0 else pm.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            return

        if low.endswith(".svg") and self.preview_svg is not None:
            self.preview_svg.load(path)
            return

        if low.endswith(".svg") and QSvgRenderer is not None and self.preview_png is not None:
            svg = QSvgRenderer(path)
            if svg.isValid():
                w = max(800, self.width())
                h = max(500, self.height())
                img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
                img.fill(0x00121212)
                p = QPainter(img)
                svg.render(p)
                p.end()
                pm = QPixmap.fromImage(img)
                target = self.preview_png.size() - QSize(16, 16)
                self.preview_png.setPixmap(pm.scaled(
                    target if target.width() > 0 and target.height() > 0 else pm.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
