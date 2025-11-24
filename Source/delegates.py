from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QColor, QBrush, QPalette
from PyQt6.QtWidgets import (
    QStyledItemDelegate,
    QApplication,
    QStyle,
    QStyleOptionViewItem,
)
from PyQt6.QtSql import QSqlQuery


class SubtaskDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        state = index.data(Qt.ItemDataRole.CheckStateRole)
        is_checked = state == Qt.CheckState.Checked

        if is_checked:
            bg = QColor(76, 175, 80)
            opt.backgroundBrush = QBrush(bg)
            opt.palette.setColor(QPalette.ColorRole.Highlight, bg)
            opt.palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

        style = opt.widget.style() if opt.widget else QApplication.style()
        painter.save()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        painter.restore()


class PriorityDelegate(QStyledItemDelegate):
    MAP = {1: "Низкий", 2: "Средний", 3: "Высокий", 4: "Критический"}
    COLORS = {
        1: QColor(76, 175, 80),
        2: QColor(255, 193, 7),
        3: QColor(255, 152, 0),
        4: QColor(244, 67, 54),
    }

    def displayText(self, value, locale):
        try:
            return self.MAP.get(int(value), str(value))
        except Exception:
            return str(value)

    def paint(self, painter, option, index):
        try:
            val = int(index.data() or 0)
        except Exception:
            val = 0
        text = self.MAP.get(val, str(index.data() or ""))

        painter.save()
        opt = option

        if not (opt.state & QStyle.StateFlag.State_Selected) and val in self.COLORS:
            painter.fillRect(opt.rect, QColor(50, 50, 50))

            rect = opt.rect.adjusted(4, 4, -4, -4)
            painter.setBrush(QBrush(self.COLORS[val]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 8, 8)

            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
        else:
            super().paint(painter, option, index)

        painter.restore()


class ArchiveDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        try:
            return "+" if int(value) else "-"
        except Exception:
            return "-"


class TimeSpentDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        try:
            secs = int(value or 0)
            if secs >= 3600:
                h = secs // 3600
                m = (secs % 3600) // 60
                return f"{h} ч {m} мин" if m else f"{h} ч"
            return f"{secs // 60} мин"
        except Exception:
            return "0 мин"


class DurationDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        try:
            mins = int(value or 0)
            if mins >= 60:
                h = mins // 60
                m = mins % 60
                return f"{h} ч {m} мин" if m else f"{h} ч"
            return f"{mins} мин"
        except Exception:
            return "0 мин"


class DescriptionDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        try:
            doc = QTextDocument()
            doc.setHtml(value or "")
            text = doc.toPlainText()
            if len(text) > 120:
                text = text[:117] + "..."
            return text
        except Exception:
            return ""


class DeadlineDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data() or ""
        painter.save()
        opt = option

        is_overdue = False
        if text:
            try:
                d = datetime.strptime(text, "%Y-%m-%d").date()
                if d < datetime.now().date():
                    is_overdue = True
            except Exception:
                pass

        if is_overdue and not (opt.state & QStyle.StateFlag.State_Selected):
            painter.fillRect(opt.rect, QColor(60, 30, 30))
            painter.setPen(QColor(255, 120, 120))
            painter.drawText(
                opt.rect.adjusted(4, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )
        else:
            super().paint(painter, option, index)

        painter.restore()


class ProjectDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        if not value:
            return "—"
        try:
            pid = int(value)
        except Exception:
            return "—"
        q = QSqlQuery()
        q.prepare("SELECT name FROM projects WHERE id=?")
        q.addBindValue(pid)
        if q.exec() and q.next():
            return q.value(0) or "—"
        return str(pid)


class TitleDelegate(QStyledItemDelegate):
    STATUS_COLORS = {
        "План": QColor(96, 125, 139),
        "В работе": QColor(33, 150, 243),
        "Готово": QColor(76, 175, 80),
        "Отложено": QColor(158, 158, 158),
    }

    def paint(self, painter, option, index):
        model = index.model()
        row = index.row()
        status_idx = model.index(row, 3)
        duration_idx = model.index(row, 9)
        recurrence_idx = model.index(row, 15)

        status = (model.data(status_idx) or "").strip()
        try:
            dur = int(model.data(duration_idx) or 0)
        except Exception:
            dur = 0
        rec = (model.data(recurrence_idx) or "none").strip()
        text = index.data() or ""

        painter.save()
        opt = option

        if opt.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(opt.rect, QColor(85, 102, 255))
        else:
            painter.fillRect(opt.rect, QColor(43, 43, 43))

        color = self.STATUS_COLORS.get(status, QColor(120, 120, 120))
        stripe_rect = opt.rect.adjusted(1, 1, -opt.rect.width() + 6, -1)
        painter.fillRect(stripe_rect, color)

        text_rect = opt.rect.adjusted(8, 0, -4, 0)

        icons = []
        if dur > 0:
            icons.append("⏱")
        if rec != "none":
            icons.append("🔁")
        icon_text = " ".join(icons)

        full_text = text
        if icon_text:
            full_text = f"{text}   {icon_text}"

        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            full_text,
        )
        painter.restore()
