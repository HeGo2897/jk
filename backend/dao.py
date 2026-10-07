"""Data Access Object: the only module that contains SQL.

One class (SqlTaskDao) serves both databases. Only the small differences (connection,
placeholder style, CREATE TABLE syntax) are kept in two tiny "dialect" blocks, so almost
all of the code - and all of the tests - are shared.

Every query uses placeholders (?). User input is NEVER joined into the SQL text,
which is what prevents SQL injection.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from config import Config
from errors import DataAccessError

_ISO = "%Y-%m-%dT%H:%M:%SZ"

SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT,
        category    TEXT,
        priority    TEXT,
        deadline    TEXT,
        status      TEXT DEFAULT 'PENDING',
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks (deadline)",
    """CREATE TABLE IF NOT EXISTS activity_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        message     TEXT NOT NULL,
        detail      TEXT,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
]

MYSQL_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS tasks (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        title       VARCHAR(255) NOT NULL,
        description TEXT,
        category    VARCHAR(100),
        priority    VARCHAR(20),
        deadline    DATE,
        status      VARCHAR(20) DEFAULT 'PENDING',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_tasks_status (status),
        INDEX idx_tasks_deadline (deadline)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS activity_log (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        message     VARCHAR(100) NOT NULL,
        detail      VARCHAR(500),
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
]

_SQLITE_HAS_TABLE = "SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
_MYSQL_HAS_TABLE = ("SELECT COUNT(*) AS n FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'tasks'")

_SELECT_TASK = "SELECT id, title, description, category, priority, deadline, status, created_at FROM tasks"


class SqlTaskDao:
    def __init__(self, cfg: Config):
        self.name = cfg.get("database", "type", "sqlite").lower()
        if self.name == "sqlite":
            self._path = cfg.get_path("database", "sqlite_path", "nexa_tasks.db")
            self._placeholder = "?"
            self._schema = SQLITE_SCHEMA
            self._has_table_sql = _SQLITE_HAS_TABLE
            self._errors = (sqlite3.Error, OSError)
        elif self.name == "mysql":
            self._host = cfg.get("mysql", "host", "localhost")
            self._port = cfg.get_int("mysql", "port", 3306)
            self._user = cfg.get("mysql", "user", "root")
            self._password = cfg.get("mysql", "password", "")
            self._db = cfg.get("mysql", "name", "todo_database")
            if not re.fullmatch(r"[A-Za-z0-9_]+", self._db):
                raise ValueError("mysql.name may only contain letters, digits and underscores")
            self._placeholder = "%s"
            self._schema = MYSQL_SCHEMA
            self._has_table_sql = _MYSQL_HAS_TABLE
            self._errors = self._mysql_errors()
        else:
            raise ValueError(f"database.type must be 'sqlite' or 'mysql' (got '{self.name}')")

    @property
    def location(self) -> str:
        """Human-readable place where data is stored (for the start-up banner)."""
        if self.name == "sqlite":
            return str(self._path)
        return f"{self._db} @ {self._host}:{self._port}"

    # ------------------------------------------------------------ connections
    @staticmethod
    def _mysql_errors() -> tuple:
        try:
            import pymysql
        except ImportError:
            return (OSError,)               # the real hint is raised by _connect()
        return (pymysql.MySQLError, OSError)

    def _connect(self, with_db: bool = True):
        if self.name == "sqlite":
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path, timeout=10)
            conn.row_factory = sqlite3.Row
            return conn
        try:
            import pymysql
            import pymysql.cursors
        except ImportError as exc:
            raise DataAccessError("The MySQL driver is missing. Run:  pip install pymysql") from exc
        return pymysql.connect(
            host=self._host, port=self._port, user=self._user, password=self._password,
            database=self._db if with_db else None, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
            init_command="SET time_zone = '+00:00'")      # store/read all timestamps in UTC

    @contextmanager
    def _session(self, with_db: bool = True):
        """Opens a connection, yields a cursor, commits on success, rolls back on error, always closes."""
        try:
            conn = self._connect(with_db)
        except self._errors as exc:
            raise DataAccessError(f"{self.name} error: {exc}") from exc
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except self._errors as exc:
            conn.rollback()
            raise DataAccessError(f"{self.name} error: {exc}") from exc
        finally:
            conn.close()

    def _q(self, sql: str) -> str:
        return sql.replace("?", self._placeholder)

    # ----------------------------------------------------------------- schema
    def init(self) -> bool:
        """Creates the database/tables if needed. Returns True when the tables are brand new."""
        if self.name == "mysql":
            with self._session(with_db=False) as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self._db}` "
                            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        with self._session() as cur:
            cur.execute(self._has_table_sql)
            fresh = cur.fetchone()["n"] == 0
            for statement in self._schema:
                cur.execute(statement)
        return fresh

    # ------------------------------------------------------------------ tasks
    def find_all(self) -> list[dict]:
        with self._session() as cur:
            cur.execute(_SELECT_TASK + " ORDER BY id")
            return [_to_task(r) for r in cur.fetchall()]

    def find_by_id(self, task_id: int) -> dict | None:
        with self._session() as cur:
            cur.execute(self._q(_SELECT_TASK + " WHERE id = ?"), (task_id,))
            row = cur.fetchone()
            return _to_task(row) if row else None

    def insert(self, d: dict) -> dict:
        with self._session() as cur:
            cur.execute(self._q("INSERT INTO tasks (title, description, category, priority, deadline, status) "
                                "VALUES (?, ?, ?, ?, ?, ?)"), _params(d))
            new_id = cur.lastrowid
            cur.execute(self._q(_SELECT_TASK + " WHERE id = ?"), (new_id,))
            return _to_task(cur.fetchone())

    def update(self, task_id: int, d: dict) -> None:
        with self._session() as cur:
            cur.execute(self._q("UPDATE tasks SET title = ?, description = ?, category = ?, priority = ?, "
                                "deadline = ?, status = ? WHERE id = ?"), _params(d) + (task_id,))

    def delete(self, task_id: int) -> bool:
        with self._session() as cur:
            cur.execute(self._q("DELETE FROM tasks WHERE id = ?"), (task_id,))
            return cur.rowcount > 0

    def delete_all(self) -> int:
        with self._session() as cur:
            cur.execute("DELETE FROM tasks")
            return cur.rowcount

    # --------------------------------------------------------------- activity
    def add_activity(self, message: str, detail: str) -> None:
        with self._session() as cur:
            cur.execute(self._q("INSERT INTO activity_log (message, detail) VALUES (?, ?)"), (message, detail))

    def recent_activity(self, limit: int) -> list[dict]:
        with self._session() as cur:
            cur.execute(self._q("SELECT id, message, detail, created_at FROM activity_log "
                                "ORDER BY id DESC LIMIT ?"), (int(limit),))
            return [{"id": r["id"], "message": r["message"], "detail": r["detail"],
                     "at": _epoch_ms(_iso_utc(r["created_at"]))} for r in cur.fetchall()]

    def clear_activity(self) -> None:
        with self._session() as cur:
            cur.execute("DELETE FROM activity_log")


def create_dao(cfg: Config) -> SqlTaskDao:
    return SqlTaskDao(cfg)


# ------------------------------------------------------------------- helpers
def _params(d: dict) -> tuple:
    return (d["title"], d["description"], d["category"], d["priority"], d["deadline"], d["status"])


def _iso_utc(value) -> str:
    """Normalises SQLite text / MySQL datetime into 'YYYY-MM-DDTHH:MM:SSZ' (UTC)."""
    if value is None:
        return datetime.now(timezone.utc).strftime(_ISO)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.strptime(str(value)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(_ISO)


def _epoch_ms(iso: str) -> int:
    return int(datetime.strptime(iso, _ISO).replace(tzinfo=timezone.utc).timestamp() * 1000)


def _to_task(row) -> dict:
    deadline = row["deadline"]
    return {
        "id": int(row["id"]),
        "title": row["title"],
        "description": row["description"] or "",
        "category": row["category"] or "General",
        "priority": row["priority"] or "MEDIUM",
        "deadline": None if deadline is None else str(deadline)[:10],   # text (SQLite) or date (MySQL)
        "status": row["status"] or "PENDING",
        "created_at": _iso_utc(row["created_at"]),
    }
