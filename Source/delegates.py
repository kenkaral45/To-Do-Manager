from datetime import datetime

from PyQt6.QtCore import QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter, QPen, QTextDocument
from PyQt6.QtWidgets import (
    QStyledItemDelegate,
    QApplication,
    QStyle,
    QStyleOptionViewItem,
)
from PyQt6.QtSql import QSqlQuery
from style import COLORS, PRIORITY_TONES, STATUS_TONES, icon


def _draw_item_background(delegate, painter, option, index):
    opt = QStyleOptionViewItem(option)
    delegate.initStyleOption(opt, index)
    opt.text = ""
    style = opt.widget.style() if opt.widget else QApplication.style()
    style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)


def _draw_chip(delegate, painter, option, index, text, tone):
    painter.save()
    _draw_item_background(delegate, painter, option, index)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(option.font)
    width = min(option.rect.width() - 12, option.fontMetrics.horizontalAdvance(text) + 15)
    height = min(option.rect.height() - 6, option.fontMetrics.height() + 7)
    if width > 0 and height > 0:
        rect = QRect(option.rect.x() + 6, option.rect.center().y() - height // 2, width, height)
        color = QColor(COLORS[tone])
        fill = QColor(color)
        fill.setAlpha(31)
        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(color)
        text = option.fontMetrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, width - 9))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


class SubtaskDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        state = index.data(Qt.ItemDataRole.CheckStateRole)
        is_checked = state == Qt.CheckState.Checked

        if is_checked:
            bg = QColor(COLORS["teal"])
            bg.setAlpha(30)
            opt.backgroundBrush = QBrush(bg)

        style = opt.widget.style() if opt.widget else QApplication.style()
        painter.save()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        painter.restore()


class StatusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        status = str(index.data() or "")
        _draw_chip(self, painter, option, index, status, STATUS_TONES.get(status, "muted"))


class PriorityDelegate(QStyledItemDelegate):
    MAP = {1: "Низкий", 2: "Средний", 3: "Высокий", 4: "Критический"}

    def displayText(self, value, locale):
        try:
            return self.MAP.get(int(value), str(value))
        except Exception:
            return str(value)

    def paint(self, painter, option, index):
        try:
            val = int(index.data() or 0)
        except (ValueError, TypeError):
            val = 0
        if val in self.MAP:
            _draw_chip(self, painter, option, index, self.MAP[val], PRIORITY_TONES[val])
        else:
            super().paint(painter, option, index)


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
            _draw_item_background(self, painter, opt, index)
            painter.setPen(QColor(COLORS["rose"]))
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

        symbols = []
        if dur > 0:
            symbols.append("clock")
        if rec != "none":
            symbols.append("repeat")

        painter.save()
        _draw_item_background(self, painter, option, index)
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS[STATUS_TONES.get(status, "muted")]))
        middle = option.rect.center().y()
        painter.drawEllipse(QRectF(option.rect.x() + 9, middle - 3.5, 7, 7))

        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        text_rect = option.rect.adjusted(24, 0, -6 - 17 * len(symbols), 0)
        text = painter.fontMetrics().elidedText(str(text), Qt.TextElideMode.ElideRight, max(0, text_rect.width()))
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        for offset, symbol in enumerate(symbols):
            glyph = icon(symbol).pixmap(QSize(13, 13))
            painter.drawPixmap(text_rect.right() + 4 + offset * 17, middle - 6, glyph)
        painter.restore()


class TaskCardDelegate(QStyledItemDelegate):
    CONTENT = Qt.ItemDataRole.UserRole + 1

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.data(self.CONTENT):
            size.setHeight(max(size.height(), option.fontMetrics.height() * 3 + 25))
        return size

    def paint(self, painter, option, index):
        content = index.data(self.CONTENT)
        if not content:
            super().paint(painter, option, index)
            return

        title, meta, description, tone = content
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        body = option.rect.adjusted(1, 1, -1, -2)
        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(COLORS["selection" if selected else "layer" if hovered else "surface"]))
        painter.setPen(QPen(QColor(COLORS["accent" if focused else "border"]), 1))
        painter.drawRoundedRect(body, 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS[tone]))
        painter.drawEllipse(QRectF(body.x() + 10, body.y() + 15, 6, 6))

        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        height = painter.fontMetrics().height()
        first = body.adjusted(23, 10, -9, 0)
        first.setHeight(height)
        self._draw_line(painter, first, title, "text")
        painter.setFont(option.font)
        next_line = QRect(body.x() + 10, first.bottom() + 5, body.width() - 20, height)
        self._draw_line(painter, next_line, meta, tone)
        if description:
            next_line.translate(0, height + 3)
            self._draw_line(painter, next_line, description, "muted")
        painter.restore()

    @staticmethod
    def _draw_line(painter, rect, text, tone):
        painter.setPen(QColor(COLORS[tone]))
        text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(0, rect.width()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, text)
