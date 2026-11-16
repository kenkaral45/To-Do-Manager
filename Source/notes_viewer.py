# notes_viewer.py
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

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

        title = QLabel("Рисунки и изображения")
        title.setObjectName("SectionTitle")
        v.addWidget(title)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setAccessibleName(title.text())
        self.list.setMaximumHeight(76)
        v.addWidget(self.list)

        self.views = QStackedWidget()
        self.views.setFixedHeight(160)
        self.preview_png = QLabel()
        self.preview_png.setObjectName("DrawingPreview")
        self.preview_png.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview_png.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.views.addWidget(self.preview_png)
        self.preview_svg = QSvgWidget() if QSvgWidget is not None else None
        if self.preview_svg is not None:
            self.views.addWidget(self.preview_svg)
        v.addWidget(self.views)

        self.list.currentItemChanged.connect(self._on_item)
        self.hide()

    def load_for_task(self, task_id: int):
        from PyQt6.QtSql import QSqlQuery
        self.list.clear()
        self._clear_preview()

        q = QSqlQuery()
        q.prepare("SELECT id, name, path FROM attachments WHERE task_id=? ORDER BY id")
        q.addBindValue(int(task_id))
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
        self.setVisible(self.list.count() > 0)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _on_item(self, it: QListWidgetItem, _prev):
        if not it:
            self._clear_preview()
            return
        _, path = it.data(Qt.ItemDataRole.UserRole)
        self._render(path)

    def _clear_preview(self):
        self.views.setCurrentWidget(self.preview_png)
        self.preview_png.clear()

    def _render(self, path: str):
        low = path.lower()
        if low.endswith(".png"):
            pm = QPixmap(path)
            self.views.setCurrentWidget(self.preview_png)
            if not pm.isNull():
                target = QSize(self.width(), self.views.height()) - QSize(16, 16)
                self.preview_png.setPixmap(pm.scaled(
                    target if target.width() > 0 and target.height() > 0 else pm.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self.preview_png.setText("Изображение недоступно")
            return

        if low.endswith(".svg") and self.preview_svg is not None:
            self.preview_svg.load(path)
            if self.preview_svg.renderer().isValid():
                self.views.setCurrentWidget(self.preview_svg)
                return

        if low.endswith(".svg") and self.preview_svg is None and QSvgRenderer is not None:
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
                return

        self.views.setCurrentWidget(self.preview_png)
        self.preview_png.setText("Изображение недоступно")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width() and self.list.currentItem():
            self._on_item(self.list.currentItem(), None)
