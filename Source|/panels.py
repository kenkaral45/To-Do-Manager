from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QHBoxLayout,
    QAbstractItemView,
)

from delegates import SubtaskDelegate


class SubtasksPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Подзадачи"))

        self.list = QListWidget(self)
        self.list.setObjectName("SubtaskList")
        self.list.setItemDelegate(SubtaskDelegate(self.list))
        v.addWidget(self.list)

        hb = QHBoxLayout()
        self.add_b = QPushButton("Добавить")
        self.del_b = QPushButton("Удалить")
        self.toggle_b = QPushButton("Переключить")
        hb.addWidget(self.add_b)
        hb.addWidget(self.del_b)
        hb.addWidget(self.toggle_b)
        hb.addStretch(1)
        v.addLayout(hb)


class AttachmentsPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Вложения"))

        self.list = QListWidget(self)
        v.addWidget(self.list)

        hb = QHBoxLayout()
        self.add_b = QPushButton("Добавить вложение")
        self.del_b = QPushButton("Удалить")
        hb.addWidget(self.add_b)
        hb.addWidget(self.del_b)
        hb.addStretch(1)
        v.addLayout(hb)


class RichTextEdit(QWidget):

    linkClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        from PyQt6.QtWidgets import QTextEdit, QVBoxLayout

        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.editor = QTextEdit(self)
        self.editor.setObjectName("DetailDesc")
        self.editor.setAcceptRichText(True)
        layout.addWidget(self.editor)

        self.editor.mouseReleaseEvent = self._mouse_release_wrapper(self.editor.mouseReleaseEvent)

    def _mouse_release_wrapper(self, original):

        def wrapper(event):
            from PyQt6.QtGui import QTextCursor

            original(event)
            cursor = self.editor.cursorForPosition(event.position().toPoint())
            fmt = cursor.charFormat()
            try:
                if fmt.isAnchor():
                    href = fmt.anchorHref()
                    if href:
                        self.linkClicked.emit(href)
            except Exception:
                pass

        return wrapper

    def setHtml(self, html: str):
        self.editor.setHtml(html)

    def toHtml(self) -> str:
        return self.editor.toHtml()

    def setPlaceholderText(self, text: str):
        self.editor.setPlaceholderText(text)

    def setMinimumHeight(self, h: int):
        self.editor.setMinimumHeight(h)

    def blockSignals(self, block: bool):
        self.editor.blockSignals(block)

    def textCursor(self):
        return self.editor.textCursor()


class KanbanListWidget(QListWidget):

    def __init__(self, status: str, manager, parent=None):
        super().__init__(parent)
        self.status = status
        self.manager = manager

        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def dropEvent(self, event):
        super().dropEvent(event)

        for it in self.selectedItems():
            tid = it.data(Qt.ItemDataRole.UserRole)
            if tid:
                self.manager._kanban_move_task(int(tid), self.status)

        self.manager._reload_kanban()
        self.manager.refresh_view()
