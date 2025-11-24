import sys
import os
import csv
from datetime import datetime, timedelta
from notes_viewer import NotesPreview
from PyQt6.QtSql import QSqlQuery
from draw_dialog import DrawDialog

from PyQt6.QtCore import (
    Qt,
    QDate,
    QTimer,
    QSettings,
    QUrl,
    QSize,
)
from PyQt6.QtGui import (
    QAction,
    QDesktopServices,
    QFont,
    QTextDocument,
    QIcon,
)
from PyQt6.QtSql import QSqlQuery, QSqlTableModel
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QToolBar,
    QLineEdit,
    QLabel,
    QPushButton,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QDialog,
    QFormLayout,
    QTextEdit,
    QDateEdit,
    QSpinBox,
    QDialogButtonBox,
    QCheckBox,
    QGroupBox,
    QStatusBar,
    QListWidget,
    QListWidgetItem,
    QSystemTrayIcon,
    QStyle,
    QMenu,
    QStackedWidget,
    QScrollArea,
    QAbstractItemView,
    QSplitter,
    QFrame,
    QTabWidget,
    QInputDialog,
)

from style import DARK_QSS
from db import connect_db, init_schema
from delegates import (
    PriorityDelegate,
    ArchiveDelegate,
    TimeSpentDelegate,
    DurationDelegate,
    DescriptionDelegate,
    DeadlineDelegate,
    ProjectDelegate,
    TitleDelegate,
)
from panels import SubtasksPanel, AttachmentsPanel, RichTextEdit, KanbanListWidget
from dialogs import (
    LoginDialog,
    HistoryDialog,
    TemplatesDialog,
    DashboardDialog,
    SettingsDialog,
)


class TodoManager(QMainWindow):
    STATUSES = ["План", "В работе", "Готово", "Отложено"]
    PRIORITY_LABELS = {1: "Низкий", 2: "Средний", 3: "Высокий", 4: "Критический"}
    PRIORITY_VALUES = [1, 2, 3, 4]
    RECURRENCE_LABELS = ["Нет", "Каждый день", "Каждую неделю", "Каждый месяц", "По будням"]
    RECURRENCE_CODES = ["none", "daily", "weekly", "monthly", "weekdays"]

    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("To-Do Manager")
        self.resize(1300, 800)

        self.settings = QSettings("TodoManagerCompany", "TodoManager")

        connect_db()
        init_schema()

        self.current_user_id = None
        self.today_mode = False

        if not self._authenticate():
            sys.exit(0)

        self.model = QSqlTableModel(self)
        self.model.setTable("tasks")
        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
        self._setup_headers()

        self._build_main_ui()
        self.setStyleSheet(DARK_QSS)
        self._install_hotkeys()

        self.refresh_view()

        self.stat_timer = QTimer(self)
        self.stat_timer.timeout.connect(self._update_statusbar_stats)
        self.stat_timer.start(2000)

        self.work_timer = QTimer(self)
        self.work_timer.setInterval(1000)
        self.work_timer.timeout.connect(self._tick_work_timer)
        self.timer_task_id = None
        self.timer_elapsed = 0

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton)
        )
        m = QMenu()
        ma = m.addAction("Показать")
        mq = m.addAction("Выход")
        ma.triggered.connect(self.showNormal)
        mq.triggered.connect(QApplication.instance().quit)
        self.tray.setContextMenu(m)
        self.tray.show()

        self.notify_timer = QTimer(self)
        self.notify_timer.setInterval(60000)
        self.notify_timer.timeout.connect(self._check_deadlines)
        self.notify_timer.start()
        self.notified_ids = set()

        if self.settings.value("behavior/auto_today", False, bool):
            self.today_mode = True
            self.btn_today_toggle.setChecked(True)
        if self.settings.value("behavior/auto_kanban", False, bool):
            self._show_kanban_page()
        else:
            self._show_main_page()

    def _authenticate(self) -> bool:
        dlg = LoginDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.current_user_id = int(dlg.user_id)
            return True
        return False

    def _hide_internal_columns(self):
        visible = {1, 3, 4, 5, 8}
        for col in range(self.model.columnCount()):
            self.table.setColumnHidden(col, col not in visible)

    def _setup_headers(self):
        headers = [
            "ID",
            "Название",
            "Описание",
            "Статус",
            "Приоритет",
            "Дедлайн",
            "Мягкий срок",
            "Теги",
            "Проект",
            "Оценка, мин",
            "Архив",
            "Создано",
            "Обновлено",
            "user_id",
            "Время",
            "Повтор",
        ]
        for i, h in enumerate(headers):
            self.model.setHeaderData(i, Qt.Orientation.Horizontal, h)

    def _build_main_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_today_panel(root)

        main_h = QHBoxLayout()
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(0)
        root.addLayout(main_h, 1)

        self.stack = QStackedWidget()
        self.page_main = QWidget()
        self.page_kanban = QWidget()
        self.page_dummy_stats = QWidget()

        self.stack.addWidget(self.page_main)
        self.stack.addWidget(self.page_kanban)
        self.stack.addWidget(self.page_dummy_stats)

        self.left_nav = self._build_left_nav()

        main_h.addWidget(self.left_nav)
        main_h.addWidget(self.stack, 1)

        self._build_main_page()

        self._build_kanban_page()

        self._build_toolbar()

        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self._build_timer_panel(root)

        self._update_left_nav_buttons()

    def _build_today_panel(self, parent_layout: QVBoxLayout):
        grp = QGroupBox()
        grp.setTitle("")
        hl = QHBoxLayout(grp)
        hl.setContentsMargins(12, 6, 12, 6)
        hl.setSpacing(12)

        self.lbl_today_title = QLabel()
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        self.lbl_today_title.setFont(f)

        self.lbl_today_stats = QLabel()
        self.btn_focus = QPushButton("Начать фокус-сессию")
        self.btn_today_toggle = QPushButton("Сегодня")
        self.btn_today_toggle.setCheckable(True)

        hl.addWidget(self.lbl_today_title)
        hl.addSpacing(16)
        hl.addWidget(self.lbl_today_stats)
        hl.addStretch(1)
        hl.addWidget(self.btn_focus)
        hl.addWidget(self.btn_today_toggle)

        parent_layout.addWidget(grp)

        self.btn_today_toggle.toggled.connect(self._toggle_today_view)
        self.btn_focus.clicked.connect(self._start_focus_session)
        self._update_today_panel()

    def _build_left_nav(self):
        frame = QFrame()
        frame.setObjectName("LeftNav")
        frame.setMinimumWidth(220)
        v = QVBoxLayout(frame)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        def mk_btn(text: str, checkable: bool = True):
            b = QPushButton(text)
            b.setCheckable(checkable)
            b.setProperty("LeftNavButton", True)
            return b

        self.btn_nav_list = mk_btn("Список задач")
        self.btn_nav_kanban = mk_btn("Канбан")
        self.btn_nav_today = mk_btn("Сегодня (фильтр)")
        self.btn_nav_stats = mk_btn("Статистика", checkable=False)
        self.btn_nav_archive = mk_btn("Архив")

        v.addWidget(self.btn_nav_list)
        v.addWidget(self.btn_nav_kanban)
        v.addWidget(self.btn_nav_today)
        v.addWidget(self.btn_nav_stats)
        v.addWidget(self.btn_nav_archive)

        v.addSpacing(10)
        v.addWidget(QLabel("Проекты"))
        self.projects_list = QListWidget()
        v.addWidget(self.projects_list, 1)

        self.btn_nav_list.clicked.connect(self._show_main_page)
        self.btn_nav_kanban.clicked.connect(self._show_kanban_page)
        self.btn_nav_today.toggled.connect(self._left_today_toggled)
        self.btn_nav_stats.clicked.connect(self._open_dashboard)
        self.btn_nav_archive.toggled.connect(self._left_archive_toggled)
        self.projects_list.itemClicked.connect(self._left_project_clicked)

        self._reload_projects_left()
        return frame

    def _build_main_page(self):
        layout = QVBoxLayout(self.page_main)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal, self.page_main)
        layout.addWidget(splitter, 1)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        search_line = QLineEdit()
        search_line.setPlaceholderText(
            "Поиск: текст, @тег, status:Готово priority:3 project:Общее >2025-01-10"
        )
        self.search = search_line
        left_layout.addWidget(self.search)

        filters_grp = QGroupBox("Фильтры")
        fl = QHBoxLayout(filters_grp)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(10)

        self.status_cb = QComboBox()
        self.status_cb.addItems(["Все"] + self.STATUSES)
        self.project_cb = QComboBox()
        self.project_cb.addItem("—", -1)
        self._reload_projects_combo(self.project_cb)
        self.hide_arch = QCheckBox("Скрывать архив")
        self.hide_arch.setChecked(True)

        fl.addWidget(QLabel("Статус:"))
        fl.addWidget(self.status_cb)
        fl.addWidget(QLabel("Проект:"))
        fl.addWidget(self.project_cb)
        fl.addStretch(1)
        fl.addWidget(self.hide_arch)

        left_layout.addWidget(filters_grp)

        mode_h = QHBoxLayout()
        self.view_mode_cb = QComboBox()
        self.view_mode_cb.addItems(["Таблица", "Карточки"])
        mode_h.addWidget(QLabel("Вид:"))
        mode_h.addWidget(self.view_mode_cb)
        mode_h.addStretch(1)
        left_layout.addLayout(mode_h)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.open_detail_current)

        self.table.setItemDelegateForColumn(1, TitleDelegate(self.table))
        self.table.setItemDelegateForColumn(2, DescriptionDelegate(self.table))
        self.table.setItemDelegateForColumn(4, PriorityDelegate(self.table))
        self.table.setItemDelegateForColumn(5, DeadlineDelegate(self.table))
        self.table.setItemDelegateForColumn(8, ProjectDelegate(self.table))
        self.table.setItemDelegateForColumn(9, DurationDelegate(self.table))
        self.table.setItemDelegateForColumn(10, ArchiveDelegate(self.table))
        self.table.setItemDelegateForColumn(14, TimeSpentDelegate(self.table))

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)

        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.gallery.setMovement(QListWidget.Movement.Static)
        self.gallery.setIconSize(QSize(0, 0))
        self.gallery.itemDoubleClicked.connect(self._open_detail_from_gallery)
        self.gallery.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.gallery.customContextMenuRequested.connect(self._gallery_context_menu)

        left_layout.addWidget(self.table, 1)
        left_layout.addWidget(self.gallery, 1)
        self.gallery.hide()

        splitter.addWidget(left_container)

        right_container = QWidget()
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        self._build_detail_panel(right_container)

        self.search.returnPressed.connect(self.apply_filter)
        self.search.textChanged.connect(self.apply_filter)
        self.status_cb.currentTextChanged.connect(self.apply_filter)
        self.project_cb.currentIndexChanged.connect(self.apply_filter)
        self.hide_arch.toggled.connect(self.apply_filter)
        self.view_mode_cb.currentIndexChanged.connect(self._switch_view_mode)

        self.table.selectionModel().selectionChanged.connect(
            self._table_selection_changed
        )

        self._hide_internal_columns()

    def _build_detail_panel(self, container: QWidget):
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        hb = QHBoxLayout()
        self.btn_history = QPushButton("История")
        self.btn_full = QPushButton("Доп. параметры…")
        self.btn_save = QPushButton("Сохранить")
        self.btn_expand = QPushButton("Развернуть деталь")
        hb.addWidget(self.btn_expand)
        hb.addStretch(1)
        hb.addWidget(self.btn_history)
        hb.addWidget(self.btn_full)
        hb.addWidget(self.btn_save)
        v.addLayout(hb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        v.addWidget(scroll, 1)

        container_inner = QWidget()
        scroll.setWidget(container_inner)
        lay = QVBoxLayout(container_inner)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        self.detail_title = QLineEdit()
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        self.detail_title.setFont(f)
        lay.addWidget(self.detail_title)

        self.lbl_status = QLabel()
        self.lbl_priority = QLabel()
        self.lbl_deadline = QLabel()
        self.lbl_soft = QLabel()
        self.lbl_tags = QLabel()
        self.lbl_project = QLabel()
        self.lbl_duration = QLabel()
        self.lbl_arch = QLabel()
        self.lbl_spent = QLabel()

        for lab in [
            self.lbl_status,
            self.lbl_priority,
            self.lbl_deadline,
            self.lbl_soft,
            self.lbl_tags,
            self.lbl_project,
            self.lbl_duration,
            self.lbl_arch,
            self.lbl_spent,
        ]:
            h = QHBoxLayout()
            h.addWidget(lab)
            h.addStretch(1)
            lay.addLayout(h)

        self.detail_desc = RichTextEdit()
        self.detail_desc.setPlaceholderText("Описание задачи, ссылки, чек-листы…")
        self.detail_desc.setMinimumHeight(200)
        self.detail_desc.linkClicked.connect(self._handle_desc_link_clicked)
        lay.addWidget(self.detail_desc, 1)

        self.attach_panel = AttachmentsPanel()
        lay.addWidget(self.attach_panel)

        self.sub_panel = SubtasksPanel()
        lay.addWidget(self.sub_panel)
        self.notes_preview = NotesPreview()
        lay.addWidget(self.notes_preview)

        self.btn_draw = QPushButton("Рисунок")
        lay.addWidget(self.btn_draw)
        self.btn_draw.clicked.connect(self._detail_add_drawing)

        self.btn_save.clicked.connect(self._save_detail)
        self.btn_full.clicked.connect(self._open_full_editor_from_detail)
        self.btn_history.clicked.connect(self._open_history_for_current)
        self.btn_expand.clicked.connect(self._toggle_expand_detail)

        self.attach_panel.add_b.clicked.connect(self._detail_add_attachment)
        self.attach_panel.del_b.clicked.connect(self._detail_del_attachment)
        self.attach_panel.list.itemDoubleClicked.connect(self._detail_open_attachment)

        self.sub_panel.add_b.clicked.connect(self._detail_add_subtask)
        self.sub_panel.del_b.clicked.connect(self._detail_del_subtask)
        self.sub_panel.toggle_b.clicked.connect(self._detail_toggle_subtask)

        self.current_detail_task = None
        self.detail_expanded = False

    def _detail_add_drawing(self):
        if not self.current_detail_task:
            return
        dlg = DrawDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.saved_path:
            import os
            from PyQt6.QtSql import QSqlQuery
            name = os.path.basename(dlg.saved_path)
            q = QSqlQuery()
            q.prepare("INSERT INTO attachments(task_id, name, path) VALUES(?,?,?)")
            q.addBindValue(int(self.current_detail_task))
            q.addBindValue(name)
            q.addBindValue(dlg.saved_path)
            q.exec()
            aid = self._last_insert_rowid()
            cursor = self.detail_desc.textCursor()
            cursor.insertHtml(f' <a href="attach://{aid}">{name}</a> ')
            self._detail_reload_attachments()

    def _build_kanban_page(self):
        w = self.page_kanban
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        top = QHBoxLayout()
        self.btn_kanban_refresh = QPushButton("Обновить")
        top.addStretch(1)
        top.addWidget(self.btn_kanban_refresh)
        v.addLayout(top)

        cols = QHBoxLayout()
        cols.setSpacing(10)
        v.addLayout(cols, 1)

        self.kanban_lists = {}
        for st in self.STATUSES:
            col_w = QFrame()
            col_w.setObjectName("KanbanColumn")
            col_l = QVBoxLayout(col_w)
            col_l.setContentsMargins(8, 8, 8, 8)
            col_l.setSpacing(6)

            lbl = QLabel(st)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lst = KanbanListWidget(st, self)
            lst.setObjectName("KanbanList")

            col_l.addWidget(lbl)
            col_l.addWidget(lst, 1)
            cols.addWidget(col_w)
            self.kanban_lists[st] = lst

            lst.itemDoubleClicked.connect(self._open_detail_from_kanban)
            lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lst.customContextMenuRequested.connect(
                lambda pos, l=lst: self._kanban_context_menu(l, pos)
            )

        self.btn_kanban_refresh.clicked.connect(self._reload_kanban)

    def _build_toolbar(self):
        tb = QToolBar("Главная")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_add = QAction("Добавить", self)
        self.act_add.triggered.connect(self.add_task)

        self.act_edit_full = QAction("Изменить…", self)
        self.act_edit_full.triggered.connect(self._open_full_editor_from_list)

        self.act_export = QAction("Экспорт CSV", self)
        self.act_export.triggered.connect(self.export_csv)

        self.act_import = QAction("Импорт CSV", self)
        self.act_import.triggered.connect(self.import_csv)

        self.act_proj = QAction("Проекты", self)
        self.act_proj.triggered.connect(self.manage_projects)

        self.act_tpl = QAction("Шаблоны", self)
        self.act_tpl.triggered.connect(self.open_templates)

        self.act_dash = QAction("Статистика", self)
        self.act_dash.triggered.connect(self._open_dashboard)

        self.act_timer = QAction("Старт таймера", self)
        self.act_timer.triggered.connect(self.toggle_timer)

        self.act_logout = QAction("Сменить пользователя", self)
        self.act_logout.triggered.connect(self.logout)

        self.act_settings = QAction("Настройки", self)
        self.act_settings.triggered.connect(self._open_settings)

        for a in [
            self.act_add,
            self.act_edit_full,
            self.act_export,
            self.act_import,
            self.act_proj,
            self.act_tpl,
            self.act_dash,
            self.act_timer,
            self.act_settings,
            self.act_logout,
        ]:
            tb.addAction(a)

    def _build_timer_panel(self, root: QVBoxLayout):
        panel = QFrame()
        panel.setObjectName("TimerPanel")
        hl = QHBoxLayout(panel)
        hl.setContentsMargins(10, 4, 10, 4)
        hl.setSpacing(8)

        self.lbl_timer = QLabel("Таймер: не запущен")
        self.btn_timer_stop = QPushButton("Стоп")
        self.btn_timer_open = QPushButton("Открыть задачу")

        hl.addWidget(self.lbl_timer)
        hl.addStretch(1)
        hl.addWidget(self.btn_timer_open)
        hl.addWidget(self.btn_timer_stop)

        self.btn_timer_stop.clicked.connect(self._stop_timer_from_panel)
        self.btn_timer_open.clicked.connect(self._open_timer_task_from_panel)

        self.timer_panel = panel
        self.timer_panel.setVisible(False)
        root.addWidget(panel)

    def _reload_projects_left(self):
        self.projects_list.clear()
        it_all = QListWidgetItem("Все проекты")
        it_all.setData(Qt.ItemDataRole.UserRole, -1)
        self.projects_list.addItem(it_all)
        q = QSqlQuery("SELECT id, name FROM projects ORDER BY name")
        if q.exec():
            while q.next():
                it = QListWidgetItem(q.value(1))
                it.setData(Qt.ItemDataRole.UserRole, int(q.value(0)))
                self.projects_list.addItem(it)

    def _update_left_nav_buttons(self):
        self.btn_nav_list.setChecked(self.stack.currentWidget() == self.page_main)
        self.btn_nav_kanban.setChecked(self.stack.currentWidget() == self.page_kanban)
        self.btn_nav_archive.setChecked(
            not self.hide_arch.isChecked()
        )

    def _show_main_page(self):
        self.today_mode = False
        self.btn_today_toggle.setChecked(False)
        self.btn_nav_today.setChecked(False)

        self.stack.setCurrentWidget(self.page_main)
        self.apply_filter()
        self._update_left_nav_buttons()

    def _show_kanban_page(self):
        self.stack.setCurrentWidget(self.page_kanban)
        self._reload_kanban()
        self._update_left_nav_buttons()

    def _left_today_toggled(self, checked: bool):
        self.today_mode = checked
        self.btn_today_toggle.setChecked(checked)
        self.apply_filter()

    def _left_archive_toggled(self, checked: bool):
        self.hide_arch.setChecked(not checked)
        self.apply_filter()
        self._update_left_nav_buttons()

    def _left_project_clicked(self, item: QListWidgetItem):
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid == -1:
            self.project_cb.setCurrentIndex(0)
        else:
            idx = self.project_cb.findData(int(pid))
            if idx != -1:
                self.project_cb.setCurrentIndex(idx)
        self.apply_filter()

    def _update_today_panel(self):
        today_str = datetime.now().strftime("%d %B %Y")
        self.lbl_today_title.setText(f"Сегодня, {today_str}")

        today = datetime.now().strftime("%Y-%m-%d")

        q_total = QSqlQuery(
            f"""
            SELECT COUNT(*) FROM tasks
            WHERE user_id={int(self.current_user_id)} AND archived=0
              AND deadline = '{today}'
        """
        )
        today_count = 0
        if q_total.exec() and q_total.next():
            today_count = int(q_total.value(0) or 0)

        q_over = QSqlQuery(
            f"""
            SELECT COUNT(*) FROM tasks
            WHERE user_id={int(self.current_user_id)} AND archived=0
              AND status!='Готово' AND deadline IS NOT NULL AND deadline < '{today}'
        """
        )
        over = 0
        if q_over.exec() and q_over.next():
            over = int(q_over.value(0) or 0)

        q_time = QSqlQuery(
            f"SELECT COALESCE(SUM(time_spent),0) FROM tasks WHERE user_id={int(self.current_user_id)}"
        )
        total_sec = 0
        if q_time.exec() and q_time.next():
            total_sec = int(q_time.value(0) or 0)
        h = total_sec // 3600
        m = (total_sec % 3600) // 60

        self.lbl_today_stats.setText(
            f"На сегодня задач: {today_count} | Просрочено: {over} | Всего времени: {h} ч {m} мин"
        )

    def _toggle_today_view(self, checked: bool):
        self.today_mode = bool(checked)
        self.btn_nav_today.setChecked(checked)
        self.apply_filter()

    def _start_focus_session(self):
        self.today_mode = True
        self.btn_today_toggle.setChecked(True)
        self.btn_nav_today.setChecked(True)
        self.apply_filter()

    def _reload_projects_combo(self, combo: QComboBox):
        combo.blockSignals(True)
        current = combo.currentData() if combo.count() else -1

        for i in range(combo.count() - 1, -1, -1):
            if combo.itemData(i) != -1:
                combo.removeItem(i)

        q = QSqlQuery("SELECT id, name FROM projects ORDER BY name")
        if q.exec():
            while q.next():
                combo.addItem(q.value(1), int(q.value(0)))

        if current is not None:
            idx = combo.findData(current)
            combo.setCurrentIndex(idx if idx != -1 else 0)

        combo.blockSignals(False)

    def refresh_view(self):
        self._reload_projects_combo(self.project_cb)
        self._reload_projects_left()
        self.apply_filter()
        self._hide_internal_columns()
        self._reload_gallery()
        self._reload_kanban()
        self._update_today_panel()

    def _escape_like(self, s: str) -> str:
        return s.replace("'", "''")

    def _parse_smart_search(self, text: str):
        text = text.strip()
        clauses = []
        free_tokens = []
        if not text:
            return clauses, ""
        tokens = text.split()
        for t in tokens:
            if ":" in t:
                key, val = t.split(":", 1)
                key = key.lower()
                val = self._escape_like(val)
                if key == "status":
                    clauses.append(f"status = '{val}'")
                elif key == "priority":
                    try:
                        clauses.append(f"priority = {int(val)}")
                    except Exception:
                        pass
                elif key == "project":
                    sub = QSqlQuery()
                    sub.prepare("SELECT id FROM projects WHERE name=?")
                    sub.addBindValue(val)
                    pid = None
                    if sub.exec() and sub.next():
                        pid = int(sub.value(0))
                    if pid is not None:
                        clauses.append(f"project_id = {pid}")
                elif key in ("deadline", "soft_deadline"):
                    clauses.append(f"{key} LIKE '%{val}%'")
                else:
                    free_tokens.append(t)
            elif t.startswith("@"):
                tag = self._escape_like(t[1:])
                clauses.append(f"tags LIKE '%{tag}%'")
            elif t.startswith(">"):
                d = t[1:]
                clauses.append(f"deadline >= '{self._escape_like(d)}'")
            else:
                free_tokens.append(t)
        return clauses, " ".join(free_tokens)

    def apply_filter(self):
        clauses = [f"user_id = {int(self.current_user_id)}"]
        if self.hide_arch.isChecked():
            clauses.append("archived = 0")

        status = self.status_cb.currentText()
        if status and status != "Все":
            clauses.append(f"status = '{self._escape_like(status)}'")

        pid = self.project_cb.currentData()
        if pid is not None and pid != -1:
            clauses.append(f"project_id = {int(pid)}")

        smart, leftover = self._parse_smart_search(self.search.text())
        clauses.extend(smart)
        if leftover:
            t = self._escape_like(leftover)
            like = f"'%{t}%'"
            clauses.append(
                f"(title LIKE {like} OR description LIKE {like} OR tags LIKE {like} "
                f"OR deadline LIKE {like} OR soft_deadline LIKE {like})"
            )

        if self.today_mode:
            today = datetime.now().strftime("%Y-%m-%d")
            clauses.append(
                "("
                f"(deadline IS NOT NULL AND deadline <= '{today}') "
                f"OR status = 'В работе'"
                ")"
            )

        self.model.setFilter(" AND ".join(clauses))
        self.model.select()
        self.table.resizeColumnsToContents()
        self._hide_internal_columns()
        self._reload_gallery()
        self._reload_kanban()
        self._update_left_nav_buttons()
        self._update_today_panel()

    def _reload_gallery(self):
        self.gallery.clear()
        filter_sql = self.model.filter()
        if filter_sql:
            sql = (
                "SELECT id, title, description, priority, status, deadline "
                "FROM tasks WHERE " + filter_sql
            )
        else:
            sql = (
                "SELECT id, title, description, priority, status, deadline "
                "FROM tasks"
            )
        q = QSqlQuery(sql)
        if q.exec():
            while q.next():
                tid = int(q.value(0))
                title = q.value(1) or ""
                desc_html = q.value(2) or ""
                pr = int(q.value(3) or 2)
                status = q.value(4) or ""
                dl = q.value(5)

                doc = QTextDocument()
                doc.setHtml(desc_html)
                plain = doc.toPlainText()
                desc = plain.strip().splitlines()[0] if plain else ""
                if len(desc) > 80:
                    desc = desc[:77] + "..."

                pr_text = PriorityDelegate.MAP.get(pr, "")
                line1 = title
                line2 = f"{status} • {pr_text}"
                if dl:
                    line2 += f" • {dl}"
                if self._task_has_attachments(tid):
                    line2 += " • 📎"


                text = f"{line1}\n{line2}\n{desc}"
                it = QListWidgetItem(text)
                it.setData(Qt.ItemDataRole.UserRole, tid)
                it.setSizeHint(QSize(240, 80))
                self.gallery.addItem(it)

    def _switch_view_mode(self, idx: int):
        if idx == 0:
            self.table.show()
            self.gallery.hide()
        else:
            self.gallery.show()
            self.table.hide()

    def _current_task_id(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        row = idx.row()
        val = self.model.data(self.model.index(row, 0))
        return int(val) if val is not None else None

    def _display_number_for_task(self, tid: int):
        try:
            tid = int(tid)
        except Exception:
            return tid
        for row in range(self.model.rowCount()):
            val = self.model.data(self.model.index(row, 0))
            try:
                if int(val or 0) == tid:
                    return row + 1
            except Exception:
                continue
        return tid

    def _table_selection_changed(self, *_):
        tid = self._current_task_id()
        if tid:
            self._open_detail(tid)

    def open_detail_current(self):
        tid = self._current_task_id()
        if not tid:
            return
        self._open_detail(tid)

    def _format_minutes(self, minutes):
        try:
            m = int(minutes or 0)
            if m >= 60:
                h = m // 60
                mm = m % 60
                return f"{h} ч {mm} мин" if mm else f"{h} ч"
            return f"{m} мин"
        except Exception:
            return "0 мин"

    def _format_seconds(self, secs):
        try:
            s = int(secs or 0)
            if s >= 3600:
                h = s // 3600
                m = (s % 3600) // 60
                return f"{h} ч {m} мин" if m else f"{h} ч"
            return f"{s // 60} мин"
        except Exception:
            return "0 мин"

    def _open_detail(self, task_id):
        self.current_detail_task = int(task_id)
        q = QSqlQuery()
        q.prepare(
            "SELECT title, description, status, priority, deadline, soft_deadline, "
            "tags, project_id, duration_estimate, archived, time_spent "
            "FROM tasks WHERE id=? AND user_id=?"
        )
        q.addBindValue(int(task_id))
        q.addBindValue(int(self.current_user_id))
        title = ""
        desc = ""
        st = "План"
        pr = 2
        dl = None
        sdl = None
        tags = ""
        pid = None
        dur = 0
        arch = 0
        spent = 0
        if q.exec() and q.next():
            title = q.value(0) or ""
            desc = q.value(1) or ""
            st = q.value(2) or "План"
            pr = int(q.value(3) or 2)
            dl = q.value(4)
            sdl = q.value(5)
            tags = q.value(6) or ""
            pid = q.value(7)
            dur = int(q.value(8) or 0)
            arch = int(q.value(9) or 0)
            spent = int(q.value(10) or 0)

        pname = "—"
        if pid:
            qp = QSqlQuery()
            qp.prepare("SELECT name FROM projects WHERE id=?")
            qp.addBindValue(int(pid))
            if qp.exec() and qp.next():
                pname = qp.value(0) or "—"

        self.detail_title.setText(title)
        self.lbl_status.setText(f"Статус — {st}")
        self.lbl_priority.setText(f"Приоритет — {PriorityDelegate.MAP.get(pr, '')}")
        self.lbl_deadline.setText(f"Дедлайн — {dl or '—'}")
        self.lbl_soft.setText(f"Мягкий срок — {sdl or '—'}")
        self.lbl_tags.setText(f"Теги — {tags or '—'}")
        self.lbl_project.setText(f"Проект — {pname}")
        self.lbl_duration.setText(
            f"Оценка длительности — {self._format_minutes(dur)}"
        )
        self.lbl_arch.setText(f"Архив — {'+' if arch else '-'}")
        self.lbl_spent.setText(f"Время — {self._format_seconds(spent)}")

        self.detail_desc.blockSignals(True)
        self.detail_desc.setHtml(desc if desc else "")
        self.detail_desc.blockSignals(False)

        self._detail_reload_attachments()
        self._detail_reload_subtasks()
        self.notes_preview.load_for_task(int(task_id))

    def _save_detail(self):
        if not self.current_detail_task:
            return
        tid = int(self.current_detail_task)
        title = self.detail_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Ошибка", "Название обязательно")
            return
        desc_html = self.detail_desc.toHtml()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        q = QSqlQuery()
        q.prepare(
            "UPDATE tasks SET title=?, description=?, updated_at=? WHERE id=? AND user_id=?"
        )
        q.addBindValue(title)
        q.addBindValue(desc_html)
        q.addBindValue(now)
        q.addBindValue(tid)
        q.addBindValue(int(self.current_user_id))
        if not q.exec():
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить")
        self.refresh_view()

    def _toggle_expand_detail(self):
        self.detail_expanded = not self.detail_expanded

    def _handle_desc_link_clicked(self, href: str):
        try:
            url = QUrl(href)
            if url.scheme() == "attach":
                aid = int(url.path().lstrip("/"))
                q = QSqlQuery()
                q.prepare("SELECT path FROM attachments WHERE id=?")
                q.addBindValue(aid)
                if q.exec() and q.next():
                    p = q.value(0)
                    if p and os.path.exists(p):
                        QDesktopServices.openUrl(QUrl.fromLocalFile(p))
                    else:
                        QMessageBox.warning(self, "Файл", "Файл не найден")
        except Exception:
            pass

    def _task_has_attachments(self, tid: int) -> bool:
        q = QSqlQuery()
        q.prepare("SELECT 1 FROM attachments WHERE task_id=? LIMIT 1")
        q.addBindValue(int(tid))
        return q.exec() and q.next()


    def _detail_reload_attachments(self):
        self.attach_panel.list.clear()
        if not self.current_detail_task:
            return
        q = QSqlQuery()
        q.prepare(
            "SELECT id, name, path FROM attachments WHERE task_id=? ORDER BY id"
        )
        q.addBindValue(int(self.current_detail_task))
        if q.exec():
            while q.next():
                aid = int(q.value(0))
                name = q.value(1) or os.path.basename(q.value(2) or "")
                it = QListWidgetItem(name)
                it.setData(Qt.ItemDataRole.UserRole, aid)
                self.attach_panel.list.addItem(it)

    def _detail_add_attachment(self):
        if not self.current_detail_task:
            return
        name, ok = QInputDialog.getText(self, "Название файла", "Название:")
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбор файла", "", "Все файлы (*)"
        )
        if not path:
            return
        q = QSqlQuery()
        q.prepare("INSERT INTO attachments(task_id, name, path) VALUES(?,?,?)")
        q.addBindValue(int(self.current_detail_task))
        q.addBindValue(name.strip())
        q.addBindValue(path)
        q.exec()
        aid = self._last_insert_rowid()
        cursor = self.detail_desc.textCursor()
        cursor.insertHtml(f' <a href="attach://{aid}">{name.strip()}</a> ')
        self._detail_reload_attachments()

    def _detail_del_attachment(self):
        it = self.attach_panel.list.currentItem()
        if not it:
            return
        aid = int(it.data(Qt.ItemDataRole.UserRole))
        q = QSqlQuery()
        q.prepare("DELETE FROM attachments WHERE id=?")
        q.addBindValue(aid)
        q.exec()
        self._detail_reload_attachments()

    def _detail_open_attachment(self, item: QListWidgetItem):
        aid = int(item.data(Qt.ItemDataRole.UserRole))
        q = QSqlQuery()
        q.prepare("SELECT path FROM attachments WHERE id=?")
        q.addBindValue(aid)
        if q.exec() and q.next():
            p = q.value(0)
            if p and os.path.exists(p):
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
            else:
                QMessageBox.warning(self, "Файл", "Файл не найден")

    def _detail_reload_subtasks(self):
        self.sub_panel.list.clear()
        if not self.current_detail_task:
            return
        q = QSqlQuery()
        q.prepare(
            "SELECT id, title, done FROM subtasks WHERE task_id=? ORDER BY id"
        )
        q.addBindValue(int(self.current_detail_task))
        if q.exec():
            while q.next():
                it = QListWidgetItem(q.value(1))
                it.setData(Qt.ItemDataRole.UserRole, int(q.value(0)))
                it.setCheckState(
                    Qt.CheckState.Checked
                    if int(q.value(2) or 0)
                    else Qt.CheckState.Unchecked
                )
                self.sub_panel.list.addItem(it)

    def _detail_add_subtask(self):
        if not self.current_detail_task:
            return
        text, ok = QInputDialog.getText(self, "Новая подзадача", "Название:")
        if ok and text.strip():
            q = QSqlQuery()
            q.prepare(
                "INSERT INTO subtasks(task_id, title, done) VALUES(?,?,0)"
            )
            q.addBindValue(int(self.current_detail_task))
            q.addBindValue(text.strip())
            q.exec()
            self._detail_reload_subtasks()
            self._auto_progress_from_subtasks(self.current_detail_task)

    def _detail_del_subtask(self):
        it = self.sub_panel.list.currentItem()
        if not it:
            return
        sid = int(it.data(Qt.ItemDataRole.UserRole))
        q = QSqlQuery()
        q.prepare("DELETE FROM subtasks WHERE id=?")
        q.addBindValue(sid)
        q.exec()
        self._detail_reload_subtasks()
        if self.current_detail_task:
            self._auto_progress_from_subtasks(self.current_detail_task)

    def _detail_toggle_subtask(self):
        it = self.sub_panel.list.currentItem()
        if not it:
            return
        sid = int(it.data(Qt.ItemDataRole.UserRole))
        done = (
            1
            if it.checkState() != Qt.CheckState.Checked
            else 0
        )
        q = QSqlQuery()
        q.prepare("UPDATE subtasks SET done=? WHERE id=?")
        q.addBindValue(done)
        q.addBindValue(sid)
        q.exec()
        self._detail_reload_subtasks()
        if self.current_detail_task:
            self._auto_progress_from_subtasks(self.current_detail_task)

    def _last_insert_rowid(self):
        q = QSqlQuery("SELECT last_insert_rowid()")
        if q.exec() and q.next():
            return int(q.value(0))
        return None

    def add_task(self, from_template_id=None):
        title = ""
        if from_template_id:
            title = self._get_template_name(from_template_id)
        self._open_full_editor(preset_title=title)

    def _open_full_editor_from_list(self):
        tid = self._current_task_id()
        if not tid:
            return
        self._open_full_editor(task_id=tid)

    def _open_full_editor_from_detail(self):
        if not self.current_detail_task:
            return
        self._open_full_editor(task_id=int(self.current_detail_task))

    def _open_full_editor(self, task_id=None, preset_title=""):
        dlg = QDialog(self)
        dlg.setWindowTitle("Задача — параметры")
        form = QFormLayout(dlg)

        e_title = QLineEdit()
        e_title.setText(preset_title)
        e_desc = QTextEdit()
        cb_status = QComboBox()
        cb_status.addItems(self.STATUSES)
        cb_pr = QComboBox()
        cb_pr.addItems(
            [self.PRIORITY_LABELS[p] for p in self.PRIORITY_VALUES]
        )
        d1 = QDateEdit()
        d1.setCalendarPopup(True)
        d1.setDate(QDate.currentDate())
        d2 = QDateEdit()
        d2.setCalendarPopup(True)
        d2.setDate(QDate.currentDate())
        e_tags = QLineEdit()
        cb_proj = QComboBox()
        cb_proj.setEditable(True)
        cb_proj.addItem("—", -1)
        self._reload_projects_combo(cb_proj)
        sp_dur = QSpinBox()
        sp_dur.setRange(0, 100000)
        sp_dur.setSuffix(" мин")
        cb_recur = QComboBox()
        cb_recur.addItems(self.RECURRENCE_LABELS)
        ch_arch = QCheckBox("Архивировать")

        if task_id:
            q = QSqlQuery()
            q.prepare(
                "SELECT title, description, status, priority, deadline, soft_deadline, "
                "tags, project_id, duration_estimate, archived, recurrence "
                "FROM tasks WHERE id=? AND user_id=?"
            )
            q.addBindValue(int(task_id))
            q.addBindValue(int(self.current_user_id))
            if q.exec() and q.next():
                e_title.setText(q.value(0) or "")
                e_desc.setHtml(q.value(1) or "")
                st = q.value(2) or self.STATUSES[0]
                cb_status.setCurrentIndex(max(0, self.STATUSES.index(st)))
                pr = int(q.value(3) or 2)
                cb_pr.setCurrentIndex(self.PRIORITY_VALUES.index(pr))
                if q.value(4):
                    d = QDate.fromString(q.value(4), "yyyy-MM-dd")
                    if d.isValid():
                        d1.setDate(d)
                if q.value(5):
                    sd = QDate.fromString(q.value(5), "yyyy-MM-dd")
                    if sd.isValid():
                        d2.setDate(sd)
                e_tags.setText(q.value(6) or "")
                pid = q.value(7) if q.value(7) is not None else -1
                self._reload_projects_combo(cb_proj)
                idx = cb_proj.findData(pid)
                cb_proj.setCurrentIndex(idx if idx != -1 else 0)
                sp_dur.setValue(int(q.value(8) or 0))
                ch_arch.setChecked(bool(q.value(9)))
                rec = q.value(10) or "none"
                try:
                    rec_idx = self.RECURRENCE_CODES.index(rec)
                except ValueError:
                    rec_idx = 0
                cb_recur.setCurrentIndex(rec_idx)

        form.addRow("Название", e_title)
        form.addRow("Описание", e_desc)
        form.addRow("Статус", cb_status)
        form.addRow("Приоритет", cb_pr)
        form.addRow("Дедлайн", d1)
        form.addRow("Мягкий срок", d2)
        form.addRow("Теги", e_tags)
        form.addRow("Проект", cb_proj)
        form.addRow("Оценка длительности", sp_dur)
        form.addRow("Повторение", cb_recur)
        form.addRow("Архив", ch_arch)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dlg,
        )
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        t = e_title.text().strip()
        if not t:
            QMessageBox.warning(self, "Ошибка", "Название обязательно")
            return

        pid = cb_proj.currentData()
        text_name = cb_proj.currentText().strip()
        if (pid is None or pid == -1) and text_name:
            qq = QSqlQuery()
            qq.prepare("INSERT OR IGNORE INTO projects(name) VALUES(?)")
            qq.addBindValue(text_name)
            qq.exec()
            qq2 = QSqlQuery()
            qq2.prepare("SELECT id FROM projects WHERE name=?")
            qq2.addBindValue(text_name)
            if qq2.exec() and qq2.next():
                pid = int(qq2.value(0))

        rec_idx = cb_recur.currentIndex()
        recurrence = (
            "none" if rec_idx <= 0 else self.RECURRENCE_CODES[rec_idx]
        )

        data = {
            "title": t,
            "description": e_desc.toHtml(),
            "status": cb_status.currentText(),
            "priority": self.PRIORITY_VALUES[cb_pr.currentIndex()],
            "deadline": d1.date().toString("yyyy-MM-dd")
            if d1.date().isValid()
            else None,
            "soft_deadline": d2.date().toString("yyyy-MM-dd")
            if d2.date().isValid()
            else None,
            "tags": e_tags.text().strip(),
            "project_id": None if (pid is None or pid == -1) else int(pid),
            "duration_estimate": int(sp_dur.value()),
            "archived": 1 if ch_arch.isChecked() else 0,
            "recurrence": recurrence,
        }

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if task_id:
            old = self._get_task_row(task_id)
            q = QSqlQuery()
            q.prepare(
                """
                UPDATE tasks
                SET title=?, description=?, status=?, priority=?, deadline=?, soft_deadline=?,
                    tags=?, project_id=?, duration_estimate=?, archived=?, recurrence=?, updated_at=?
                WHERE id=? AND user_id=?
                """
            )
            q.addBindValue(data["title"])
            q.addBindValue(data["description"])
            q.addBindValue(data["status"])
            q.addBindValue(int(data["priority"]))
            q.addBindValue(data["deadline"])
            q.addBindValue(data["soft_deadline"])
            q.addBindValue(data["tags"])
            if data["project_id"] is None:
                q.addBindValue(None)
            else:
                q.addBindValue(int(data["project_id"]))
            q.addBindValue(int(data["duration_estimate"]))
            q.addBindValue(int(data["archived"]))
            q.addBindValue(data["recurrence"])
            q.addBindValue(now)
            q.addBindValue(int(task_id))
            q.addBindValue(int(self.current_user_id))
            if not q.exec():
                QMessageBox.critical(self, "Ошибка", "Не удалось обновить задачу")
            else:
                self._log_diff(task_id, old, data)
                if data["status"] == "В работе" and self.settings.value(
                    "behavior/auto_timer_on_inprogress", False, bool
                ):
                    self._start_timer_for_task(task_id)
                if data["status"] == "Готово":
                    self._spawn_recurring_if_needed(task_id)
        else:
            q = QSqlQuery()
            q.prepare(
                """
                INSERT INTO tasks(
                    title, description, status, priority, deadline, soft_deadline,
                    tags, project_id, duration_estimate, archived,
                    created_at, updated_at, user_id, time_spent, recurrence
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """
            )
            q.addBindValue(data["title"])
            q.addBindValue(data["description"])
            q.addBindValue(data["status"])
            q.addBindValue(int(data["priority"]))
            q.addBindValue(data["deadline"])
            q.addBindValue(data["soft_deadline"])
            q.addBindValue(data["tags"])
            if data["project_id"] is None:
                q.addBindValue(None)
            else:
                q.addBindValue(int(data["project_id"]))
            q.addBindValue(int(data["duration_estimate"]))
            q.addBindValue(int(data["archived"]))
            q.addBindValue(now)
            q.addBindValue(now)
            q.addBindValue(int(self.current_user_id))
            q.addBindValue(0)
            q.addBindValue(data["recurrence"])
            if not q.exec():
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить задачу")
            else:
                self._log_history(self._last_insert_rowid(), "create", "", data["title"])
        self.refresh_view()
        if task_id:
            self._open_detail(task_id)

    def _get_template_name(self, tid):
        q = QSqlQuery()
        q.prepare("SELECT name FROM templates WHERE id=?")
        q.addBindValue(int(tid))
        if q.exec() and q.next():
            return q.value(0) or ""
        return ""

    def _select_task_in_table(self, tid: int):
        for row in range(self.model.rowCount()):
            idx = self.model.index(row, 0)
            val = self.model.data(idx)
            try:
                if int(val or 0) == int(tid):
                    self.table.selectRow(row)
                    self.table.setCurrentIndex(self.model.index(row, 1))
                    break
            except Exception:
                continue

    def _table_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.selectRow(index.row())

        menu = QMenu(self)
        menu.addAction("Открыть", self.open_detail_current)
        menu.addAction(self.act_edit_full)
        menu.addAction("История", self._open_history_for_current)
        menu.addSeparator()
        menu.addAction("Выполнено", self.mark_done)
        menu.addAction("В архив", self.archive_task)
        menu.addSeparator()
        menu.addAction(self.act_timer)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _gallery_context_menu(self, pos):
        item = self.gallery.itemAt(pos)
        if not item:
            return
        tid = item.data(Qt.ItemDataRole.UserRole)
        if not tid:
            return
        self._select_task_in_table(int(tid))
        menu = QMenu(self)
        menu.addAction("Открыть", self.open_detail_current)
        menu.addAction(self.act_edit_full)
        menu.addAction("История", self._open_history_for_current)
        menu.addSeparator()
        menu.addAction("Выполнено", self.mark_done)
        menu.addAction("В архив", self.archive_task)
        menu.addSeparator()
        menu.addAction(self.act_timer)
        menu.exec(self.gallery.viewport().mapToGlobal(pos))

    def _kanban_context_menu(self, lst: QListWidget, pos):
        item = lst.itemAt(pos)
        if not item:
            return
        lst.setCurrentItem(item)
        tid = item.data(Qt.ItemDataRole.UserRole)
        if not tid:
            return
        self._select_task_in_table(int(tid))
        menu = QMenu(self)
        menu.addAction("Открыть", self.open_detail_current)
        menu.addAction(self.act_edit_full)
        menu.addAction("История", self._open_history_for_current)
        menu.addSeparator()
        menu.addAction("Выполнено", self.mark_done)
        menu.addAction("В архив", self.archive_task)
        menu.addSeparator()
        menu.addAction(self.act_timer)
        menu.exec(lst.viewport().mapToGlobal(pos))

    def delete_task(self):
        tid = self._current_task_id()
        if not tid:
            return
        if (
            QMessageBox.question(
                self, "Подтверждение", "Удалить выбранную задачу?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._log_history(
            tid, "delete", self._get_task_row(tid).get("title", ""), ""
        )
        q = QSqlQuery()
        q.prepare("DELETE FROM tasks WHERE id=? AND user_id=?")
        q.addBindValue(int(tid))
        q.addBindValue(int(self.current_user_id))
        if not q.exec():
            QMessageBox.critical(self, "Ошибка", "Не удалось удалить задачу")
        q = QSqlQuery()
        q.prepare("DELETE FROM subtasks WHERE task_id=?")
        q.addBindValue(int(tid))
        q.exec()
        q = QSqlQuery()
        q.prepare("DELETE FROM attachments WHERE task_id=?")
        q.addBindValue(int(tid))
        q.exec()
        self.refresh_view()

    def archive_task(self):
        tid = self._current_task_id()
        if not tid:
            return
        q = QSqlQuery()
        q.prepare(
            "UPDATE tasks SET archived=1, updated_at=? WHERE id=? AND user_id=?"
        )
        q.addBindValue(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        q.addBindValue(int(tid))
        q.addBindValue(int(self.current_user_id))
        if not q.exec():
            QMessageBox.critical(self, "Ошибка", "Не удалось архивировать задачу")
        else:
            self._log_history(tid, "archived", "0", "1")
        self.refresh_view()

    def mark_done(self):
        tid = self._current_task_id()
        if not tid:
            return
        q = QSqlQuery()
        q.prepare(
            "UPDATE tasks SET status='Готово', updated_at=? WHERE id=? AND user_id=?"
        )
        q.addBindValue(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        q.addBindValue(int(tid))
        q.addBindValue(int(self.current_user_id))
        if not q.exec():
            QMessageBox.critical(self, "Ошибка", "Не удалось обновить статус")
        else:
            self._log_history(tid, "status", "", "Готово")
            self._spawn_recurring_if_needed(tid)
        self.refresh_view()

    def open_templates(self):
        dlg = TemplatesDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tid = dlg.selected_template_id()
            if tid:
                self._open_full_editor(preset_title=self._get_template_name(tid))

    def _open_history_for_current(self):
        tid = self.current_detail_task or self._current_task_id()
        if not tid:
            return
        dlg = HistoryDialog(int(tid), self)
        dlg.exec()

    def _open_dashboard(self):
        DashboardDialog(self.current_user_id, self).exec()

    def _reload_kanban(self):
        if not hasattr(self, "kanban_lists") or not self.kanban_lists:
            if hasattr(self, "statusbar"):
                self.statusbar.showMessage("Kanban: нет колонок")
            return

        for lst in self.kanban_lists.values():
            lst.clear()

        filter_sql = self.model.filter()
        if filter_sql:
            sql = (
                "SELECT id, title, status, priority, deadline "
                "FROM tasks WHERE " + filter_sql
            )
        else:
            sql = (
                f"SELECT id, title, status, priority, deadline "
                f"FROM tasks WHERE user_id={int(self.current_user_id)}"
            )

        q = QSqlQuery(sql)

        total = 0
        added = 0

        if q.exec():
            while q.next():
                total += 1
                try:
                    tid = int(q.value(0))
                except Exception:
                    continue

                title = q.value(1) or ""
                raw_status = (q.value(2) or "").strip()
                try:
                    pr = int(q.value(3) or 2)
                except Exception:
                    pr = 2
                dl = q.value(4)

                st = None
                for s in self.STATUSES:
                    if raw_status.lower() == s.lower():
                        st = s
                        break
                if not st:
                    st = "План"

                pr_text = PriorityDelegate.MAP.get(pr, "")
                line1 = title if len(title) <= 20 else title[:17] + "..."
                line2 = pr_text
                if dl:
                    line2 += f" • {dl}"

                if self._task_has_attachments(tid):
                    line2 += " • 📎"

                text = f"{line1}\n{line2}"

                it = QListWidgetItem(text)
                it.setData(Qt.ItemDataRole.UserRole, tid)
                it.setSizeHint(QSize(0, 50))

                lst = self.kanban_lists.get(st)
                if lst is None:
                    lst = self.kanban_lists.get("План")

                if lst is not None:
                    lst.addItem(it)
                    added += 1

        if hasattr(self, "statusbar"):
            self.statusbar.showMessage(
                f"Kanban: всего задач в выборке: {total}, выведено в колонки: {added}"
            )

    def _open_detail_from_kanban(self, item: QListWidgetItem):
        tid = item.data(Qt.ItemDataRole.UserRole)
        if tid:
            self._select_task_in_table(int(tid))
            self._open_detail(int(tid))
            self._show_main_page()

    def _open_detail_from_gallery(self, item: QListWidgetItem):
        tid = item.data(Qt.ItemDataRole.UserRole)
        if not tid:
            return
        self._select_task_in_table(int(tid))
        self._open_detail(int(tid))
        self._show_main_page()

    def _kanban_move_task(self, task_id, new_status):
        q = QSqlQuery()
        q.prepare(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=? AND user_id=?"
        )
        q.addBindValue(new_status)
        q.addBindValue(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        q.addBindValue(int(task_id))
        q.addBindValue(int(self.current_user_id))
        if q.exec():
            self._log_history(task_id, "status", "", new_status)
            if new_status == "Готово":
                self._spawn_recurring_if_needed(task_id)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт CSV", "tasks.csv", "CSV (*.csv)"
        )
        if not path:
            return
        headers = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "deadline",
            "soft_deadline",
            "tags",
            "project_id",
            "duration_estimate",
            "archived",
            "created_at",
            "updated_at",
            "user_id",
            "time_spent",
            "recurrence",
        ]
        q = QSqlQuery(
            f"SELECT {','.join(headers)} FROM tasks WHERE user_id={int(self.current_user_id)}"
        )
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(headers)
                if q.exec():
                    while q.next():
                        w.writerow([q.value(i) for i in range(len(headers))])
            QMessageBox.information(self, "Готово", "Экспорт завершён")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {e}")

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт CSV", "", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    QMessageBox.warning(self, "Ошибка", "Пустой CSV")
                    return
                required = {"title"}
                lower = set(map(str.lower, reader.fieldnames))
                if not required.issubset(lower):
                    QMessageBox.warning(
                        self, "Ошибка", "В CSV должна быть колонка 'title'"
                    )
                    return
                count = 0

                def getv(row, k):
                    for key in row.keys():
                        if key.lower() == k:
                            return row[key]
                    return None

                for row in reader:
                    title = (getv(row, "title") or "").strip()
                    if not title:
                        continue
                    description = getv(row, "description")
                    st = getv(row, "status")
                    status = st if st in self.STATUSES else "План"
                    try:
                        priority = int(getv(row, "priority") or 2)
                        if priority not in self.PRIORITY_VALUES:
                            priority = 2
                    except Exception:
                        priority = 2
                    deadline = getv(row, "deadline") or None
                    soft_deadline = getv(row, "soft_deadline") or None
                    tags = getv(row, "tags") or None
                    rec = getv(row, "recurrence") or "none"
                    if rec not in self.RECURRENCE_CODES:
                        rec = "none"
                    project_name = (
                        getv(row, "project") or getv(row, "project_name") or ""
                    ).strip()
                    project_id = None
                    if project_name:
                        q = QSqlQuery()
                        q.prepare(
                            "INSERT OR IGNORE INTO projects(name) VALUES(?)"
                        )
                        q.addBindValue(project_name)
                        q.exec()
                        q2 = QSqlQuery()
                        q2.prepare("SELECT id FROM projects WHERE name=?")
                        q2.addBindValue(project_name)
                        if q2.exec() and q2.next():
                            project_id = int(q2.value(0))
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    q = QSqlQuery()
                    q.prepare(
                        """
                        INSERT INTO tasks(
                            title, description, status, priority, deadline, soft_deadline,
                            tags, project_id, duration_estimate, archived,
                            created_at, updated_at, user_id, time_spent, recurrence
                        )
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """
                    )
                    q.addBindValue(title)
                    q.addBindValue(description)
                    q.addBindValue(status)
                    q.addBindValue(priority)
                    q.addBindValue(deadline)
                    q.addBindValue(soft_deadline)
                    q.addBindValue(tags)
                    if project_id is None:
                        q.addBindValue(None)
                    else:
                        q.addBindValue(int(project_id))
                    q.addBindValue(int(getv(row, "duration_estimate") or 0))
                    q.addBindValue(int(getv(row, "archived") or 0))
                    q.addBindValue(now)
                    q.addBindValue(now)
                    q.addBindValue(int(self.current_user_id))
                    q.addBindValue(int(getv(row, "time_spent") or 0))
                    q.addBindValue(rec)
                    q.exec()
                    count += 1
                QMessageBox.information(self, "Готово", f"Импортировано: {count}")
                self.refresh_view()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать файл: {e}")

    def manage_projects(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Проекты")
        v = QVBoxLayout(dlg)
        table = QTableView(dlg)
        pmodel = QSqlTableModel(dlg)
        pmodel.setTable("projects")
        pmodel.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
        pmodel.select()
        pmodel.setHeaderData(0, Qt.Orientation.Horizontal, "ID")
        pmodel.setHeaderData(1, Qt.Orientation.Horizontal, "Название")
        pmodel.setHeaderData(2, Qt.Orientation.Horizontal, "Описание")
        table.setModel(pmodel)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        v.addWidget(table)

        h = QHBoxLayout()
        add_b = QPushButton("Добавить")
        del_b = QPushButton("Удалить")
        h.addWidget(add_b)
        h.addWidget(del_b)
        h.addStretch(1)
        v.addLayout(h)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dlg)
        v.addWidget(bb)
        bb.accepted.connect(dlg.accept)

        def add_project():
            name, ok = QInputDialog.getText(dlg, "Новый проект", "Название:")
            if ok and name.strip():
                q = QSqlQuery()
                q.prepare("INSERT OR IGNORE INTO projects(name) VALUES(?)")
                q.addBindValue(name.strip())
                q.exec()
                pmodel.select()

        def del_project():
            idx = table.currentIndex()
            if not idx.isValid():
                return
            row = idx.row()
            pid = int(pmodel.data(pmodel.index(row, 0)))
            if (
                QMessageBox.question(
                    dlg,
                    "Подтверждение",
                    "Удалить проект? Задачи останутся без проекта.",
                )
                == QMessageBox.StandardButton.Yes
            ):
                q = QSqlQuery()
                q.prepare("DELETE FROM projects WHERE id=?")
                q.addBindValue(pid)
                q.exec()
                q2 = QSqlQuery()
                q2.prepare(
                    "UPDATE tasks SET project_id=NULL WHERE project_id=? AND user_id=?"
                )
                q2.addBindValue(pid)
                q2.addBindValue(int(self.current_user_id))
                q2.exec()
                pmodel.select()

        add_b.clicked.connect(add_project)
        del_b.clicked.connect(del_project)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_view()

    def _get_task_row(self, tid):
        q = QSqlQuery()
        q.prepare(
            "SELECT title, description, status, priority, deadline, soft_deadline, "
            "tags, project_id, duration_estimate, archived, recurrence "
            "FROM tasks WHERE id=?"
        )
        q.addBindValue(int(tid))
        row = {}
        if q.exec() and q.next():
            row = {
                "title": q.value(0) or "",
                "description": q.value(1) or "",
                "status": q.value(2) or "",
                "priority": int(q.value(3) or 2),
                "deadline": q.value(4),
                "soft_deadline": q.value(5),
                "tags": q.value(6) or "",
                "project_id": q.value(7),
                "duration_estimate": int(q.value(8) or 0),
                "archived": int(q.value(9) or 0),
                "recurrence": q.value(10) or "none",
            }
        return row

    def _log_history(self, task_id, field, old, new):
        q = QSqlQuery()
        q.prepare(
            "INSERT INTO history(task_id, field, old_value, new_value, changed_at) "
            "VALUES(?,?,?,?,?)"
        )
        q.addBindValue(int(task_id))
        q.addBindValue(field)
        q.addBindValue("" if old is None else str(old))
        q.addBindValue("" if new is None else str(new))
        q.addBindValue(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        q.exec()

    def _log_diff(self, tid, old, new):
        mapping = [
            "title",
            "description",
            "status",
            "priority",
            "deadline",
            "soft_deadline",
            "tags",
            "project_id",
            "duration_estimate",
            "archived",
            "recurrence",
        ]
        for k in mapping:
            ov = old.get(k) if old else None
            nv = new.get(k)
            if str(ov) != str(nv):
                self._log_history(tid, k, ov, nv)

    def _install_hotkeys(self):
        a_add = QAction(self)
        a_add.setShortcut("Ctrl+N")
        a_add.triggered.connect(self.add_task)
        self.addAction(a_add)

        a_open = QAction(self)
        a_open.setShortcut("Enter")
        a_open.triggered.connect(self.open_detail_current)
        self.addAction(a_open)

        a_done = QAction(self)
        a_done.setShortcut("Space")
        a_done.triggered.connect(self.mark_done)
        self.addAction(a_done)

        a_del = QAction(self)
        a_del.setShortcut("Delete")
        a_del.triggered.connect(self.delete_task)
        self.addAction(a_del)

        a_timer = QAction(self)
        a_timer.setShortcut("Ctrl+T")
        a_timer.triggered.connect(self.toggle_timer)
        self.addAction(a_timer)

        a_dash = QAction(self)
        a_dash.setShortcut("Ctrl+D")
        a_dash.triggered.connect(self._open_dashboard)
        self.addAction(a_dash)

        a_kanban = QAction(self)
        a_kanban.setShortcut("Ctrl+B")
        a_kanban.triggered.connect(self._show_kanban_page)
        self.addAction(a_kanban)

    def _start_timer_for_task(self, tid):
        if self.timer_task_id is not None:
            return
        self.timer_task_id = int(tid)
        self.timer_elapsed = 0
        self.work_timer.start()
        self.act_timer.setText("Стоп таймера")
        if self.timer_panel:
            self.timer_panel.setVisible(True)
        num = self._display_number_for_task(self.timer_task_id)
        self.lbl_timer.setText(f"Сейчас выполняется задача {num} — 00:00:00")

    def toggle_timer(self):
        if self.stack.currentWidget() in (self.page_main, self.page_kanban):
            tid = self._current_task_id()
        else:
            tid = self.current_detail_task
        if not tid:
            return
        tid = int(tid)
        if self.timer_task_id is None:
            self._start_timer_for_task(tid)
        elif self.timer_task_id == tid:
            self._stop_timer()
        else:
            QMessageBox.information(
                self, "Таймер", "Сначала остановите текущий таймер"
            )

    def _stop_timer(self):
        if self.timer_task_id is None:
            return
        tid = int(self.timer_task_id)
        self.work_timer.stop()
        secs = self.timer_elapsed
        q = QSqlQuery()
        q.prepare(
            "UPDATE tasks SET time_spent = COALESCE(time_spent,0)+?, updated_at=? WHERE id=?"
        )
        q.addBindValue(int(secs))
        q.addBindValue(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        q.addBindValue(int(tid))
        q.exec()
        self._log_history(tid, "time_spent+=", "", str(secs))
        self.timer_task_id = None
        self.timer_elapsed = 0
        self.act_timer.setText("Старт таймера")
        self.lbl_timer.setText("Таймер: не запущен")
        if self.timer_panel:
            self.timer_panel.setVisible(False)
        self._update_statusbar_stats()
        self.refresh_view()

    def _tick_work_timer(self):
        if self.timer_task_id is None:
            self.lbl_timer.setText("Таймер: не запущен")
            if self.timer_panel:
                self.timer_panel.setVisible(False)
            return
        self.timer_elapsed += 1
        h = self.timer_elapsed // 3600
        m = (self.timer_elapsed % 3600) // 60
        s = self.timer_elapsed % 60
        num = self._display_number_for_task(self.timer_task_id)
        self.lbl_timer.setText(
            f"Сейчас выполняется задача {num} — {h:02d}:{m:02d}:{s:02d}"
        )

    def _stop_timer_from_panel(self):
        self._stop_timer()

    def _open_timer_task_from_panel(self):
        if not self.timer_task_id:
            return
        self._select_task_in_table(int(self.timer_task_id))
        self._open_detail(int(self.timer_task_id))
        self._show_main_page()

    def _spawn_recurring_if_needed(self, task_id):
        q = QSqlQuery()
        q.prepare(
            "SELECT title, description, status, priority, deadline, soft_deadline, "
            "tags, project_id, duration_estimate, archived, user_id, recurrence "
            "FROM tasks WHERE id=?"
        )
        q.addBindValue(int(task_id))
        if not (q.exec() and q.next()):
            return
        rec = (q.value(11) or "none").strip()
        if rec in ("", "none", None):
            return

        title = q.value(0) or ""
        desc = q.value(1) or ""
        priority = int(q.value(3) or 2)
        deadline = q.value(4)
        soft_deadline = q.value(5)
        tags = q.value(6) or ""
        project_id = q.value(7)
        duration = int(q.value(8) or 0)
        user_id = int(q.value(10) or self.current_user_id)

        def shift_date(dstr):
            if not dstr:
                return None
            try:
                d = datetime.strptime(dstr, "%Y-%m-%d").date()
            except ValueError:
                return dstr
            if rec == "daily":
                nd = d + timedelta(days=1)
            elif rec == "weekly":
                nd = d + timedelta(days=7)
            elif rec == "monthly":
                nd = d + timedelta(days=30)
            elif rec == "weekdays":
                nd = d + timedelta(days=1)
                while nd.weekday() >= 5:
                    nd += timedelta(days=1)
            else:
                nd = d
            return nd.strftime("%Y-%m-%d")

        deadline2 = shift_date(deadline)
        soft_deadline2 = shift_date(soft_deadline)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        iq = QSqlQuery()
        iq.prepare(
            """
            INSERT INTO tasks(
                title, description, status, priority, deadline, soft_deadline,
                tags, project_id, duration_estimate, archived,
                created_at, updated_at, user_id, time_spent, recurrence
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """
        )
        iq.addBindValue(title)
        iq.addBindValue(desc)
        iq.addBindValue("План")
        iq.addBindValue(priority)
        iq.addBindValue(deadline2)
        iq.addBindValue(soft_deadline2)
        iq.addBindValue(tags)
        if project_id is None:
            iq.addBindValue(None)
        else:
            iq.addBindValue(int(project_id))
        iq.addBindValue(duration)
        iq.addBindValue(0)
        iq.addBindValue(now)
        iq.addBindValue(now)
        iq.addBindValue(user_id)
        iq.addBindValue(0)
        iq.addBindValue(rec)
        iq.exec()

    def _auto_progress_from_subtasks(self, tid):
        q = QSqlQuery()
        q.prepare("SELECT COUNT(*), SUM(done) FROM subtasks WHERE task_id=?")
        q.addBindValue(int(tid))
        total = done = 0
        if q.exec() and q.next():
            total = int(q.value(0) or 0)
            done = int(q.value(1) or 0)
        if total > 0 and done == total:
            qq = QSqlQuery()
            qq.prepare(
                "UPDATE tasks SET status='Готово', updated_at=? WHERE id=?"
            )
            qq.addBindValue(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            qq.addBindValue(int(tid))
            qq.exec()
            self._log_history(tid, "status", "", "Готово")
            self._spawn_recurring_if_needed(tid)

    def _check_deadlines(self):
        if not self.current_user_id:
            return

        today = datetime.now().date()
        soon = today + timedelta(days=1)

        q = QSqlQuery(
            """
            SELECT id, title, deadline
            FROM tasks
            WHERE user_id=? AND archived=0 AND (status IS NULL OR status!='Готово')
                  AND deadline IS NOT NULL
            """
        )
        q.addBindValue(int(self.current_user_id))

        if not (q.exec()):
            return

        while q.next():
            try:
                tid = int(q.value(0))
            except Exception:
                continue

            if tid in self.notified_ids:
                continue

            title = q.value(1) or ""
            dstr = q.value(2)
            try:
                d = datetime.strptime(dstr, "%Y-%m-%d").date()
            except Exception:
                continue

            if d < today:
                self.tray.showMessage("Просрочено", f"Дедлайн задачи «{title}» просрочен ({dstr})")
                self.notified_ids.add(tid)
            elif d == today:
                self.tray.showMessage("Сегодня дедлайн", f"Сегодня срок по «{title}»")
                self.notified_ids.add(tid)
            elif d == soon:
                self.tray.showMessage("Скоро дедлайн", f"Завтра срок по «{title}»")
                self.notified_ids.add(tid)

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            fs = self.settings.value("ui/font_size", 14, int)
            f = self.font()
            f.setPointSize(fs)
            QApplication.instance().setFont(f)

            compact = self.settings.value("ui/compact_table", False, bool)
            vh = self.table.verticalHeader()
            vh.setDefaultSectionSize(22 if compact else 28)

            self.refresh_view()

    def _update_statusbar_stats(self):
        if not hasattr(self, "statusbar") or not self.current_user_id:
            return

        total = open_count = over = 0
        today = datetime.now().strftime("%Y-%m-%d")

        q = QSqlQuery(f"SELECT COUNT(*) FROM tasks WHERE user_id={int(self.current_user_id)} AND archived=0")
        if q.exec() and q.next():
            total = int(q.value(0) or 0)

        q = QSqlQuery(
            f"SELECT COUNT(*) FROM tasks WHERE user_id={int(self.current_user_id)} AND archived=0 AND (status IS NULL OR status!='Готово')"
        )
        if q.exec() and q.next():
            open_count = int(q.value(0) or 0)

        q = QSqlQuery(
            f"""
            SELECT COUNT(*) FROM tasks
            WHERE user_id={int(self.current_user_id)} AND archived=0
              AND (status IS NULL OR status!='Готово')
              AND deadline IS NOT NULL AND deadline < '{today}'
            """
        )
        if q.exec() and q.next():
            over = int(q.value(0) or 0)

        self.statusbar.showMessage(f"Всего: {total} | Открыто: {open_count} | Просрочено: {over}")

    def logout(self):
        if self.timer_task_id is not None:
            self._stop_timer()

        self.hide()
        self.current_user_id = None
        if not self._authenticate():
            QApplication.instance().quit()
            return

        self.refresh_view()
        self.showNormal()

    def closeEvent(self, event):
        try:
            if self.timer_task_id is not None:
                self._stop_timer()
        except Exception:
            pass
        super().closeEvent(event)
