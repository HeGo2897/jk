-- NEXA TASK: SQLite schema (default database).
-- The Python server creates these tables automatically on first start, so running this file is OPTIONAL.
-- Inspect your data any time with:   sqlite3 backend/nexa_tasks.db     (or "DB Browser for SQLite")

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    category    TEXT,
    priority    TEXT,                          -- HIGH | MEDIUM | LOW
    deadline    TEXT,                          -- 'YYYY-MM-DD' (SQLite has no DATE type)
    status      TEXT DEFAULT 'PENDING',        -- PENDING | IN_PROGRESS | COMPLETED
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP -- UTC
);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks (deadline);

CREATE TABLE IF NOT EXISTS activity_log (      -- feeds the "Recent Activity" panel
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message     TEXT NOT NULL,
    detail      TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Handy queries for your demonstration:
--   SELECT * FROM tasks;
--   SELECT status, COUNT(*) FROM tasks GROUP BY status;
--   SELECT title, deadline FROM tasks WHERE status <> 'COMPLETED' AND deadline < date('now');   -- overdue
