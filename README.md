# NEXA TASK (Python edition): Smart Task Management System

Full-stack To-Do application for a college Value Added Course.

| Layer | Technology |
|---|---|
| Front end | HTML5, CSS3, vanilla JavaScript (no frameworks) |
| API | REST + JSON over HTTP |
| Back end | Python 3.10+ with **Flask** |
| Database | **SQLite** (default, built into Python, nothing to install) or **MySQL 8** (optional) |

```
Browser (HTML/CSS/JS)  --fetch JSON-->  Flask  -->  TaskService  -->  SqlTaskDao  -->  SQLite / MySQL
   js/api.js                            app.py      service.py        dao.py            tasks, activity_log
```

```
nexa-task-py/
├── database/                 schema_sqlite.sql, schema_mysql.sql (tables are also auto-created)
├── backend/
│   ├── app.py                Flask routes (HTTP layer) + serves the website
│   ├── service.py            validation, business rules, activity log
│   ├── dao.py                ALL SQL lives here (SQLite and MySQL)
│   ├── config.py, config.ini settings
│   ├── errors.py
│   ├── requirements.txt      Flask   (requirements-mysql.txt adds PyMySQL)
│   ├── setup.bat/.sh         one-time: create venv + install Flask
│   ├── run.bat/.sh           start the server
│   └── tests/test_api.py     21 automated tests
└── frontend/                 index.html, css/style.css, js/api.js, js/script.js
```

## 1. Install Python
Python **3.10 or newer** (tested on 3.12). Check: `python --version` (Windows) or `python3 --version`.
On Windows, tick **"Add python.exe to PATH"** in the installer.

## 2. One-time setup
**Windows** (Command Prompt, inside the project):
```
cd nexa-task-py\backend
setup.bat
```
**Linux / macOS**
```
cd nexa-task-py/backend
./setup.sh
```
This creates a private `venv` folder and installs Flask (needs internet once).

## 3. Run
```
run.bat          (Windows)
./run.sh         (Linux / macOS)
```
When you see `NEXA TASK is running`, open **http://localhost:8080/**. Keep the window open; closing it stops the server. The first start creates `backend/nexa_tasks.db` with 5 sample tasks.

## 4. Prove that data is stored permanently (for your demonstration)
1. Add a task on the website.
2. Open the database file and query it, for example with Python (no extra tools needed):
   ```
   python -c "import sqlite3; [print(r) for r in sqlite3.connect('nexa_tasks.db').execute('SELECT id,title,priority,status FROM tasks')]"
   ```
   (or open `nexa_tasks.db` with the free *DB Browser for SQLite*).
3. Stop the server (Ctrl+C), run it again, refresh the page. The task is still there.

## 5. Run the automated tests
```
python -m unittest discover -s tests -v          (use venv\Scripts\python on Windows if you did setup)
```
They use temporary databases, so your real data is untouched.

## 6. Using MySQL instead of SQLite (optional, matches a "SQL/MySQL" syllabus)
1. Install MySQL 8 and make sure it is running.
2. Install the driver: `setup.bat mysql` (or `./setup.sh --mysql`).
3. Edit `backend/config.ini`:
   ```
   [database]
   type = mysql
   [mysql]
   user = root
   password = your_mysql_password
   ```
   (or set the environment variable `NEXA_MYSQL_PASSWORD`).
4. Start the server. It creates `todo_database` and the tables itself. Then check: `USE todo_database; SELECT * FROM tasks;`
The front end and the API do not change at all. Only `dao.py` knows which database is used.

## 7. REST API
Base URL `http://localhost:8080`. All bodies are JSON. Errors look like `{"error":"message"}`.

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/api/health` | server and storage status | 200 |
| GET | `/api/tasks` | list all tasks | 200 |
| POST | `/api/tasks` | create a task | 201 |
| GET | `/api/tasks/<id>` | read one task | 200 |
| PUT / PATCH | `/api/tasks/<id>` | update (send only the changed fields) | 200 |
| DELETE | `/api/tasks/<id>` | delete one task | 204 |
| DELETE | `/api/tasks` | delete all tasks | 200 |
| POST | `/api/tasks/sample` | add the demo tasks | 201 |
| GET | `/api/activity` | recent activity feed | 200 |

Example (Linux/macOS/Git Bash):
```
curl -X POST http://localhost:8080/api/tasks -H "Content-Type: application/json" \
     -d '{"title":"Submit VAC project","priority":"HIGH","deadline":"2026-10-20"}'
```
Validation: `title` required (max 255), `priority` HIGH/MEDIUM/LOW, `status` PENDING/IN_PROGRESS/COMPLETED, `deadline` as `YYYY-MM-DD`. Invalid input returns HTTP 400.

## 8. Design decisions (useful for viva questions)
- **Why layers?** `app.py` (HTTP) -> `service.py` (rules) -> `dao.py` (SQL). Each file has one job, so the database can be swapped without touching the website or the API.
- **SQL injection:** every query uses placeholders (`?` for SQLite, `%s` for MySQL). User text is never pasted into SQL. A test stores `x'); DROP TABLE tasks; --` and proves the table survives.
- **XSS:** the front end escapes all task text before inserting it into the page.
- **Overdue** is computed from `deadline` and `status` when displayed, never stored, so it cannot become out of date.
- **Why SQLite by default?** It is a real SQL database that lives in one file and ships with Python, so the project runs anywhere with no server to install. MySQL is supported for multi-user setups.
- **Search, filter and sort** run in the browser on the list loaded from the database, which is instant for a personal task list. For thousands of rows you would move them into SQL (`WHERE ... LIKE`, `ORDER BY`).
- **One connection per operation** keeps the code simple. A production system would use a connection pool.
- **Flask's built-in server** is for development and demos. A real deployment would use a production server such as Waitress or Gunicorn.

## 9. Troubleshooting
| Message | Fix |
|---|---|
| `'python' is not recognized` | Python is not installed or not on PATH. Reinstall and tick "Add to PATH". Try `py` instead of `python`. |
| `ModuleNotFoundError: No module named 'flask'` | Run `setup.bat` / `./setup.sh` first, then start with `run.bat` / `./run.sh` (they use the venv). |
| `The MySQL driver is missing` | Run `setup.bat mysql` (installs PyMySQL). |
| `Access denied for user` | Wrong `mysql.user` / `mysql.password` in `config.ini`. |
| `Can't connect to MySQL server` | MySQL is not running, or `mysql.port` is wrong. |
| `Address already in use` | Another program uses port 8080. Change `port` in `config.ini` and use the new URL. |
| Red "Cannot reach the NEXA server" banner | The Python window was closed. Run it again, then click Retry. |
| Opening `index.html` by double-click | Works if the server runs on port 8080 (CORS is enabled), but prefer http://localhost:8080/. |
