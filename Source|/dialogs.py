from hashlib import sha256
from datetime import datetime

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtSql import QSqlQuery
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QInputDialog,
    QSpinBox,
    QCheckBox,
    QWidget,
    QTabWidget,
)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход / Регистрация")

        lay = QVBoxLayout(self)

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        lay.addWidget(QLabel("Логин"))
        lay.addWidget(self.username)
        lay.addWidget(QLabel("Пароль"))
        lay.addWidget(self.password)

        b1 = QPushButton("Вход")
        b2 = QPushButton("Регистрация")
        h = QHBoxLayout()
        h.addWidget(b1)
        h.addWidget(b2)
        lay.addLayout(h)

        b1.clicked.connect(self.handle_login)
        b2.clicked.connect(self.handle_register)

        self.user_id = None

    def hash_pass(self, pw: str) -> str:
        return sha256(pw.encode("utf-8")).hexdigest()

    def handle_login(self):
        u = self.username.text().strip()
        p = self.password.text()
        q = QSqlQuery()
        q.prepare("SELECT id, password_hash FROM users WHERE username=?")
        q.addBindValue(u)
        if q.exec() and q.next():
            uid, ph = int(q.value(0)), q.value(1)
            if self.hash_pass(p) == ph:
                self.user_id = uid
                self.accept()
                return
        QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль")

    def handle_register(self):
        u = self.username.text().strip()
        p = self.password.text()
        if not u or not p:
            QMessageBox.warning(self, "Ошибка", "Укажи логин и пароль")
            return
        q = QSqlQuery()
        q.prepare("INSERT INTO users(username, password_hash) VALUES(?,?)")
        q.addBindValue(u)
        q.addBindValue(self.hash_pass(p))
        if not q.exec():
            QMessageBox.warning(self, "Ошибка", "Пользователь уже существует")
            return
        self.handle_login()


class HistoryDialog(QDialog):
    def __init__(self, task_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История изменений")
        self.resize(650, 420)

        v = QVBoxLayout(self)
        self.list = QListWidget(self)
        v.addWidget(self.list)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        v.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        self._load(task_id)

    def _load(self, task_id: int):
        q = QSqlQuery()
        q.prepare(
            "SELECT field, old_value, new_value, changed_at "
            "FROM history WHERE task_id=? ORDER BY id DESC"
        )
        q.addBindValue(int(task_id))
        if q.exec():
            while q.next():
                field = q.value(0) or ""
                old = q.value(1) or ""
                new = q.value(2) or ""
                ts = q.value(3) or ""
                text = f"[{ts}] {field}: '{old}' → '{new}'"
                self.list.addItem(text)


class TemplatesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Шаблоны задач")

        v = QVBoxLayout(self)
        self.list = QListWidget(self)
        v.addWidget(self.list)

        hb = QHBoxLayout()
        self.add_b = QPushButton("Добавить")
        self.apply_b = QPushButton("Применить")
        self.del_b = QPushButton("Удалить")
        hb.addWidget(self.add_b)
        hb.addWidget(self.apply_b)
        hb.addWidget(self.del_b)
        hb.addStretch(1)
        v.addLayout(hb)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        v.addWidget(bb)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)

        self.add_b.clicked.connect(self.add_tpl)
        self.apply_b.clicked.connect(self.accept)
        self.del_b.clicked.connect(self.del_tpl)

        self.reload()

    def reload(self):
        self.list.clear()
        q = QSqlQuery("SELECT id, name FROM templates ORDER BY id")
        if q.exec():
            while q.next():
                it = QListWidgetItem(q.value(1))
                it.setData(Qt.ItemDataRole.UserRole, int(q.value(0)))
                self.list.addItem(it)

    def add_tpl(self):
        name, ok = QInputDialog.getText(self, "Новый шаблон", "Название шаблона:")
        if not ok or not name.strip():
            return
        q = QSqlQuery()
        q.prepare("INSERT INTO templates(name) VALUES(?)")
        q.addBindValue(name.strip())
        q.exec()
        self.reload()

    def del_tpl(self):
        it = self.list.currentItem()
        if not it:
            return
        tid = int(it.data(Qt.ItemDataRole.UserRole))
        q = QSqlQuery()
        q.prepare("DELETE FROM templates WHERE id=?")
        q.addBindValue(tid)
        q.exec()
        self.reload()

    def selected_template_id(self):
        it = self.list.currentItem()
        return int(it.data(Qt.ItemDataRole.UserRole)) if it else None


class DashboardDialog(QDialog):
    def __init__(self, user_id, parent=None):
        super().__init__(parent)
        self.user_id = int(user_id)
        self.setWindowTitle("Статистика")

        v = QVBoxLayout(self)
        self.l_total = QLabel()
        self.l_done = QLabel()
        self.l_over = QLabel()
        self.l_time = QLabel()
        self.l_by_proj = QLabel()
        v.addWidget(self.l_total)
        v.addWidget(self.l_done)
        v.addWidget(self.l_over)
        v.addWidget(self.l_time)
        v.addWidget(QLabel("По проектам:"))
        v.addWidget(self.l_by_proj)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=self)
        v.addWidget(bb)
        bb.accepted.connect(self.accept)

        self.refresh()

    def refresh(self):
        q = QSqlQuery(
            f"SELECT COUNT(*) FROM tasks WHERE user_id={self.user_id} AND archived=0"
        )
        total = 0
        if q.exec() and q.next():
            total = int(q.value(0) or 0)

        q = QSqlQuery(
            f"SELECT COUNT(*) FROM tasks WHERE user_id={self.user_id} AND archived=0 AND status='Готово'"
        )
        done = 0
        if q.exec() and q.next():
            done = int(q.value(0) or 0)

        today = datetime.now().strftime("%Y-%m-%d")
        q = QSqlQuery(
            f"""
            SELECT COUNT(*) FROM tasks
            WHERE user_id={self.user_id} AND archived=0 AND status!='Готово'
              AND deadline IS NOT NULL AND deadline < '{today}'
        """
        )
        over = 0
        if q.exec() and q.next():
            over = int(q.value(0) or 0)

        q = QSqlQuery(
            f"SELECT COALESCE(SUM(time_spent),0) FROM tasks WHERE user_id={self.user_id}"
        )
        tsum = 0
        if q.exec() and q.next():
            tsum = int(q.value(0) or 0)
        hours = tsum // 3600
        mins = (tsum % 3600) // 60

        by_proj = []
        q = QSqlQuery(
            f"""
            SELECT COALESCE(p.name,'—') as pname, COUNT(t.id)
            FROM tasks t LEFT JOIN projects p ON p.id=t.project_id
            WHERE t.user_id={self.user_id} AND t.archived=0
            GROUP BY pname ORDER BY COUNT(t.id) DESC
        """
        )
        if q.exec():
            while q.next():
                by_proj.append(f"{q.value(0)}: {q.value(1)}")

        self.l_total.setText(f"Открытых задач: {total}")
        self.l_done.setText(f"Выполнено: {done}")
        self.l_over.setText(f"Просрочено: {over}")
        self.l_time.setText(f"Накопленное время: {hours} ч {mins} мин")
        self.l_by_proj.setText("\n".join(by_proj) if by_proj else "—")


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.settings = settings
        self.resize(500, 400)

        v = QVBoxLayout(self)
        tabs = QTabWidget(self)
        v.addWidget(tabs)

        view_page = QWidget()
        vl = QVBoxLayout(view_page)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 24)
        self.font_size_spin.setValue(self.settings.value("ui/font_size", 14, int))
        vl.addWidget(QLabel("Размер шрифта интерфейса"))
        vl.addWidget(self.font_size_spin)

        self.compact_table = QCheckBox("Компактная таблица")
        self.compact_table.setChecked(
            self.settings.value("ui/compact_table", False, bool)
        )
        vl.addWidget(self.compact_table)
        vl.addStretch(1)
        tabs.addTab(view_page, "Вид")

        beh_page = QWidget()
        bl = QVBoxLayout(beh_page)

        self.auto_kanban = QCheckBox("Открывать Канбан при запуске")
        self.auto_kanban.setChecked(
            self.settings.value("behavior/auto_kanban", False, bool)
        )
        self.auto_today = QCheckBox("Включать режим 'Сегодня' при запуске")
        self.auto_today.setChecked(
            self.settings.value("behavior/auto_today", False, bool)
        )
        self.auto_timer = QCheckBox("Авто-запуск таймера при статусе 'В работе'")
        self.auto_timer.setChecked(
            self.settings.value("behavior/auto_timer_on_inprogress", False, bool)
        )
        bl.addWidget(self.auto_kanban)
        bl.addWidget(self.auto_today)
        bl.addWidget(self.auto_timer)
        bl.addStretch(1)
        tabs.addTab(beh_page, "Поведение")

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        v.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

    def accept(self):
        self.settings.setValue("ui/font_size", self.font_size_spin.value())
        self.settings.setValue("ui/compact_table", self.compact_table.isChecked())
        self.settings.setValue("behavior/auto_kanban", self.auto_kanban.isChecked())
        self.settings.setValue("behavior/auto_today", self.auto_today.isChecked())
        self.settings.setValue(
            "behavior/auto_timer_on_inprogress", self.auto_timer.isChecked()
        )
        super().accept()
