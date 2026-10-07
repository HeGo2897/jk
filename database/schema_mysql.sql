-- NEXA TASK: MySQL 8 schema (optional database, set database.type = mysql in backend/config.ini).
-- The Python server creates these automatically when the MySQL user may CREATE DATABASE,
-- so running this file is OPTIONAL.   Run:  mysql -u root -p < database/schema_mysql.sql

CREATE DATABASE IF NOT EXISTS todo_database
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE todo_database;

CREATE TABLE IF NOT EXISTS tasks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    category    VARCHAR(100),
    priority    VARCHAR(20),                       -- HIGH | MEDIUM | LOW
    deadline    DATE,
    status      VARCHAR(20) DEFAULT 'PENDING',     -- PENDING | IN_PROGRESS | COMPLETED
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_deadline (deadline)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS activity_log (          -- feeds the "Recent Activity" panel
    id          INT AUTO_INCREMENT PRIMARY KEY,
    message     VARCHAR(100) NOT NULL,
    detail      VARCHAR(500),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Handy queries for your demonstration:
--   SELECT * FROM tasks;
--   SELECT status, COUNT(*) FROM tasks GROUP BY status;
--   SELECT title, deadline FROM tasks WHERE status <> 'COMPLETED' AND deadline < CURDATE();   -- overdue
