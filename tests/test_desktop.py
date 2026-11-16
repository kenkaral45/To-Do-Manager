import csv
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QDropEvent, QPixmap
from PyQt6.QtSql import QSqlQuery
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QPushButton

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Source"))

import db
from dialogs import DashboardDialog, HistoryDialog, LoginDialog, SettingsDialog, TemplatesDialog
from mainwindow import TodoManager
from style import apply_theme


def query(statement, *values):
    result = QSqlQuery()
    assert result.prepare(statement), result.lastError().text()
    for value in values:
        result.addBindValue(value)
    assert result.exec(), result.lastError().text()
    return result


def scalar(statement, *values):
    result = query(statement, *values)
    assert result.next()
    return result.value(0)


class DesktopTest(unittest.TestCase):
    def test_task_workflows(self):
        app = QApplication([])
        apply_theme(app)
        app.setQuitOnLastWindowClosed(False)

        def dialog_action(trigger, expected, interact):
            errors = []
            opened = []

            def on_dialog():
                dialog = app.activeModalWidget()
                try:
                    self.assertIsInstance(dialog, expected)
                    opened.append(dialog)
                    interact(dialog)
                except Exception as error:
                    errors.append(error)
                    if isinstance(dialog, QDialog):
                        dialog.reject()

            QTimer.singleShot(0, on_dialog)
            result = trigger()
            app.processEvents()
            if errors:
                raise errors[0]
            self.assertTrue(opened, "The action must open its dialog")
            return result

        def register(login, account="desktop-test"):
            login.username.setText(account)
            login.password.setText("local-test-password")
            next(b for b in login.findChildren(QPushButton) if b.text() == "Создать аккаунт").click()

        with TemporaryDirectory() as tmp, patch.object(db, "DB_NAME", ":memory:"):
            settings = QSettings(str(Path(tmp) / "settings.ini"), QSettings.Format.IniFormat)
            with patch("mainwindow.QSettings", return_value=settings):
                window = dialog_action(TodoManager, LoginDialog, register)
            try:
                window.resize(1440, 860)
                window.show()
                app.processEvents()
                self.assertIs(window.task_views.currentWidget(), window.empty_tasks)
                self.assertIs(window.detail_views.currentWidget(), window.detail_empty)

                def create(dialog):
                    fields = {label.text(): label.buddy() for label in dialog.findChildren(QLabel)}
                    fields["Название"].setText("Тестовая задача")
                    fields["Описание"].setPlainText("Тестовое описание")
                    fields["Теги"].setText("дизайн")
                    fields["Статус"].setCurrentText("В работе")
                    fields["Приоритет"].setCurrentText("Высокий")
                    buttons = dialog.findChild(QDialogButtonBox)
                    buttons.button(QDialogButtonBox.StandardButton.Ok).click()

                dialog_action(window.findChild(QPushButton, "AddTask").click, QDialog, create)
                task = scalar("SELECT id FROM tasks WHERE title=?", "Тестовая задача")
                self.assertEqual(scalar("SELECT priority FROM tasks WHERE id=?", task), 3)
                self.assertEqual(window.model.rowCount(), 1)
                self.assertTrue(window._select_task_in_table(task))
                self.assertIs(window.detail_views.currentWidget(), window.detail_content)

                window.detail_title.setText("Изменённая задача")
                window.btn_expand.click()
                self.assertTrue(window.task_list_panel.isHidden())
                window.btn_expand.click()
                self.assertFalse(window.task_list_panel.isHidden())
                self.assertEqual(window.detail_title.text(), "Изменённая задача")
                window.btn_save.click()
                self.assertEqual(scalar("SELECT title FROM tasks WHERE id=?", task), "Изменённая задача")

                window.search.setText("@дизайн priority:3")
                self.assertEqual(window.model.rowCount(), 1)
                window.search.setText("несуществующая задача")
                self.assertIs(window.task_views.currentWidget(), window.empty_tasks)
                window.search.clear()
                window.view_mode_cb.setCurrentIndex(1)
                self.assertIs(window.task_views.currentWidget(), window.gallery)
                window.gallery.setCurrentRow(0)
                self.assertEqual(window._current_task_id(), task)

                window.btn_nav_kanban.click()
                work = window.kanban_lists["В работе"]
                self.assertEqual(work.count(), 1)
                planned = window.kanban_lists["План"]
                work.setCurrentRow(0)
                mime = work.mimeData([work.currentItem()])

                class BoardDrop(QDropEvent):
                    def source(self):
                        return work

                drop = BoardDrop(
                    QPointF(10, 10), Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
                    mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                )
                planned.dropEvent(drop)
                app.processEvents()
                self.assertTrue(drop.isAccepted())
                self.assertEqual(work.count(), 0)
                self.assertEqual(planned.count(), 1)
                self.assertEqual(scalar("SELECT status FROM tasks WHERE id=?", task), "План")
                planned.setCurrentRow(0)
                window.activateWindow()
                planned.setFocus()
                app.processEvents()
                QTest.keyClick(planned, Qt.Key.Key_Return)
                self.assertIs(window.stack.currentWidget(), window.page_main)
                self.assertEqual(window.current_detail_task, task)

                window.act_timer.trigger()
                self.assertTrue(window.work_timer.isActive())
                window._tick_work_timer()
                window.btn_timer_stop.click()
                self.assertEqual(scalar("SELECT time_spent FROM tasks WHERE id=?", task), 1)
                self.assertFalse(window.timer_panel.isVisible())

                window.btn_focus.click()
                self.assertTrue(window.today_mode)
                self.assertEqual(window.model.rowCount(), 1)
                window.btn_nav_list.click()
                self.assertFalse(window.today_mode)
                window._select_task_in_table(task)

                png = Path(tmp) / "drawing.png"
                image = QPixmap(QSize(30, 20))
                image.fill(QColor("#89E3CC"))
                self.assertTrue(image.save(str(png)))
                with patch("mainwindow.QInputDialog.getText", return_value=("Рисунок", True)):
                    with patch("mainwindow.QFileDialog.getOpenFileName", return_value=(str(png), "")):
                        window.attach_panel.add_b.click()
                self.assertEqual(window.notes_preview.list.count(), 1)
                self.assertFalse(window.notes_preview.preview_png.pixmap().isNull())

                svg = Path(tmp) / "drawing.svg"
                svg.write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                    '<rect width="20" height="20" fill="red"/></svg>', encoding="utf-8",
                )
                query("INSERT INTO attachments(task_id,name,path) VALUES (?,?,?)", task, "SVG", str(svg))
                window._detail_reload_attachments()
                window.notes_preview.list.setCurrentRow(1)
                self.assertTrue(window.notes_preview.preview_svg.renderer().isValid())
                window.attach_panel.list.setCurrentRow(1)
                window.attach_panel.del_b.click()
                self.assertEqual(window.notes_preview.list.count(), 1)

                with patch("mainwindow.QInputDialog.getText", return_value=("Подзадача", True)):
                    window.sub_panel.add_b.click()
                item = window.sub_panel.list.item(0)
                item.setCheckState(Qt.CheckState.Checked)
                self.assertEqual(scalar("SELECT done FROM subtasks WHERE task_id=?", task), 1)
                window.sub_panel.list.setCurrentItem(item)
                window.sub_panel.toggle_b.click()
                self.assertEqual(scalar("SELECT done FROM subtasks WHERE task_id=?", task), 0)

                def check_history(dialog):
                    self.assertGreaterEqual(dialog.list.count(), 2)
                    dialog.reject()

                dialog_action(window.btn_history.click, HistoryDialog, check_history)
                dialog_action(window.act_tpl.trigger, TemplatesDialog, lambda dialog: dialog.reject())
                dialog_action(window.act_dash.trigger, DashboardDialog, lambda dialog: dialog.reject())

                def compact(dialog):
                    dialog.compact_table.setChecked(True)
                    dialog.accept()

                normal_height = window.table.verticalHeader().defaultSectionSize()
                dialog_action(window.act_settings.trigger, SettingsDialog, compact)
                self.assertLess(window.table.verticalHeader().defaultSectionSize(), normal_height)

                def enlarge(dialog):
                    dialog.font_size_spin.setValue(18)
                    dialog.accept()

                dialog_action(window.act_settings.trigger, SettingsDialog, enlarge)
                self.assertEqual(window.search.font().pixelSize(), 18)
                self.assertEqual(window.table.font().pixelSize(), 18)
                settings.setValue("ui/font_size", 14)
                window._apply_view_settings()

                csv_path = Path(tmp) / "tasks.csv"
                with patch("mainwindow.QFileDialog.getSaveFileName", return_value=(str(csv_path), "")):
                    with patch("mainwindow.QMessageBox.information"):
                        window.act_export.trigger()
                with csv_path.open(encoding="utf-8", newline="") as stream:
                    self.assertEqual(next(csv.DictReader(stream))["title"], "Изменённая задача")
                csv_path.write_text("title,tags\nИмпортированная задача,импорт\n", encoding="utf-8")
                with patch("mainwindow.QFileDialog.getOpenFileName", return_value=(str(csv_path), "")):
                    with patch("mainwindow.QMessageBox.information"):
                        window.act_import.trigger()
                self.assertEqual(window.model.rowCount(), 2)

                window.view_mode_cb.setCurrentIndex(1)
                window.gallery.setCurrentRow(0)
                window.activateWindow()
                window.gallery.setFocus()
                app.processEvents()
                first = window._current_task_id()
                QTest.keyClick(window.gallery, Qt.Key.Key_Right)
                second = window._current_task_id()
                self.assertNotEqual(first, second)
                self.assertEqual(window.current_detail_task, second)
                query("UPDATE tasks SET status='План' WHERE id=?", first)
                QTest.keyClick(window.gallery, Qt.Key.Key_Space)
                self.assertEqual(scalar("SELECT status FROM tasks WHERE id=?", first), "План")
                self.assertEqual(scalar("SELECT status FROM tasks WHERE id=?", second), "Готово")
                window.detail_title.setText("Изменено с клавиатуры")
                window.btn_save.setFocus()
                QTest.keyClick(window.btn_save, Qt.Key.Key_Space)
                self.assertEqual(
                    scalar("SELECT title FROM tasks WHERE id=?", second),
                    "Изменено с клавиатуры",
                )

                window.view_mode_cb.setCurrentIndex(0)
                window._select_task_in_table(task)
                window.archive_task()
                self.assertEqual(window.model.rowCount(), 1)
                window.btn_nav_archive.click()
                self.assertEqual(window.model.rowCount(), 2)

                dialog_action(window.act_logout.trigger, LoginDialog, lambda form: register(form, "second-test"))
                self.assertIsNone(window.current_detail_task)
                self.assertIs(window.detail_views.currentWidget(), window.detail_empty)
                self.assertEqual(window.model.rowCount(), 0)
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
