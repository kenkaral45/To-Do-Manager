from PyQt6.QtSql import QSqlDatabase, QSqlQuery

DB_NAME = "todo.db"


def connect_db() -> None:
    if not QSqlDatabase.contains("qt_sql_default_connection"):
        db = QSqlDatabase.addDatabase("QSQLITE")
        db.setDatabaseName(DB_NAME)
    else:
        db = QSqlDatabase.database()

    if not db.open():
        raise RuntimeError("Не удалось открыть базу данных")


def column_exists(table: str, column: str) -> bool:
    q = QSqlQuery()
    q.prepare(f"PRAGMA table_info({table})")
    if q.exec():
        while q.next():
            if str(q.value(1)) == column:
                return True
    return False


def init_schema() -> None:
    q = QSqlQuery()

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
        """
    )

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'План',
            priority INTEGER DEFAULT 2,
            deadline TEXT,
            soft_deadline TEXT,
            tags TEXT,
            project_id INTEGER,
            duration_estimate INTEGER,
            archived INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    if not column_exists("tasks", "user_id"):
        QSqlQuery("ALTER TABLE tasks ADD COLUMN user_id INTEGER")
    if not column_exists("tasks", "time_spent"):
        QSqlQuery("ALTER TABLE tasks ADD COLUMN time_spent INTEGER DEFAULT 0")
    if not column_exists("tasks", "recurrence"):
        QSqlQuery("ALTER TABLE tasks ADD COLUMN recurrence TEXT")

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            title TEXT,
            done INTEGER DEFAULT 0
        )
        """
    )

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            name TEXT,
            path TEXT
        )
        """
    )
    if not column_exists("attachments", "name"):
        QSqlQuery("ALTER TABLE attachments ADD COLUMN name TEXT")

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        """
    )

    q.exec(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_at TEXT NOT NULL
        )
        """
    )

    q.exec("SELECT COUNT(*) FROM projects")
    if q.exec() and q.next() and int(q.value(0) or 0) == 0:
        q2 = QSqlQuery()
        q2.prepare("INSERT INTO projects(name, description) VALUES(?, ?)")
        q2.addBindValue("Общее")
        q2.addBindValue("Проект по умолчанию")
        q2.exec()
