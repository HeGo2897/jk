"""NEXA TASK: Flask web server.

This file is the HTTP layer (controller). It turns requests into TaskService calls and
returns JSON. It also serves the HTML/CSS/JS front end so the whole site runs from one URL.

    Browser --fetch JSON--> Flask routes (app.py) --> TaskService (service.py)
                                                  --> SqlTaskDao (dao.py) --> SQLite / MySQL

    GET    /api/health            server + storage status
    GET    /api/tasks             list all tasks
    POST   /api/tasks             create a task              -> 201
    GET    /api/tasks/<id>        read one task
    PUT    /api/tasks/<id>        update (partial allowed)
    PATCH  /api/tasks/<id>        same as PUT
    DELETE /api/tasks/<id>        delete one task            -> 204
    DELETE /api/tasks             delete every task
    POST   /api/tasks/sample      add the demo tasks         -> 201
    GET    /api/activity          recent activity feed
"""
from __future__ import annotations

import json
import re
import sys

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from config import Config
from dao import create_dao
from errors import ApiError, DataAccessError
from service import TaskService

MAX_BODY_BYTES = 1_000_000


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config()

    dao = create_dao(cfg)
    fresh = dao.init()                                   # creates tables if needed
    service = TaskService(dao)
    if fresh and cfg.get_bool("app", "seed_sample_data", True):
        service.seed_initial_data()

    frontend_dir = cfg.get_path("app", "frontend_dir", "../frontend")

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    app.json.sort_keys = False                           # keep field order as written
    app.extensions["nexa_dao"] = dao
    app.extensions["nexa_frontend_dir"] = frontend_dir

    # ------------------------------------------------------------ helpers
    def is_api() -> bool:
        return request.path == "/api" or request.path.startswith("/api/")

    def read_body() -> dict:
        raw = request.get_data(cache=False)              # > 1 MB raises 413 automatically
        if not raw:
            raise ApiError(400, "Request body is empty")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ApiError(400, f"Invalid JSON: {exc}") from None
        if not isinstance(parsed, dict):
            raise ApiError(400, "A JSON object was expected")
        return parsed

    def parse_id(raw: str) -> int:
        if not re.fullmatch(r"[0-9]{1,18}", raw) or int(raw) < 1:
            raise ApiError(400, "Task id must be a positive number")
        return int(raw)

    # ------------------------------------------------------------- routes
    @app.get("/api/health")
    def health():
        return jsonify(status="ok", storage=service.storage_name())

    @app.get("/api/activity")
    def activity():
        return jsonify(service.activity())

    @app.route("/api/tasks", methods=["GET", "POST", "DELETE"], strict_slashes=False)
    def tasks():
        if request.method == "GET":
            return jsonify(service.list_tasks())
        if request.method == "POST":
            return jsonify(service.create(read_body())), 201
        return jsonify(deleted=service.delete_all())

    @app.post("/api/tasks/sample")
    def sample():
        return jsonify(created=service.load_samples()), 201

    @app.route("/api/tasks/<task_id>", methods=["GET", "PUT", "PATCH", "DELETE"], strict_slashes=False)
    def one_task(task_id: str):
        tid = parse_id(task_id)
        if request.method == "GET":
            return jsonify(service.get(tid))
        if request.method == "DELETE":
            service.delete(tid)
            return "", 204
        return jsonify(service.update(tid, read_body()))

    # Everything else is the static front end (index.html, css/, js/ ...).
    # send_from_directory refuses ../ path traversal.
    @app.route("/", defaults={"filename": "index.html"})
    @app.route("/<path:filename>")
    def frontend(filename: str):
        return send_from_directory(frontend_dir, filename)

    # ----------------------------------------------------- error handling
    @app.errorhandler(ApiError)
    def on_api_error(err: ApiError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(DataAccessError)
    def on_data_error(err: DataAccessError):
        print(f"[ERROR] {err}", file=sys.stderr)
        return jsonify(error="The database is unavailable or returned an error. Check the server console."), 503

    @app.errorhandler(HTTPException)
    def on_http_error(err: HTTPException):
        if not is_api():
            return err                                    # plain HTML page for the front end
        messages = {404: "Unknown API endpoint", 405: "Method not allowed", 413: "Request body too large"}
        return jsonify(error=messages.get(err.code, err.description)), err.code

    @app.errorhandler(Exception)
    def on_unexpected(err: Exception):
        app.logger.exception("Unexpected error")
        return jsonify(error="Internal server error"), 500

    @app.after_request
    def add_headers(resp):
        if is_api():                                      # CORS (lets index.html opened from disk call the API)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Cache-Control"] = "no-store"
        else:
            resp.headers["Cache-Control"] = "no-cache"
            resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    return app


def main() -> None:
    cfg = Config()
    try:
        app = create_app(cfg)
    except DataAccessError as exc:
        print("\nCould not start the database layer:\n  " + str(exc) + "\n")
        print("Checklist:")
        print("  1. SQLite: is the folder of database.sqlite_path writable?")
        print("  2. MySQL : is MySQL running, and are mysql.user / mysql.password in backend/config.ini correct?")
        print("  3. MySQL : did you run  pip install pymysql  ?")
        sys.exit(1)
    except ValueError as exc:
        print(f"\nConfiguration problem: {exc}\n")
        sys.exit(1)

    host = cfg.get("server", "host", "127.0.0.1")
    port = cfg.get_int("server", "port", 8080)
    dao = app.extensions["nexa_dao"]
    print()
    print("  NEXA TASK is running")
    print(f"  Website : http://localhost:{port}/")
    print(f"  API     : http://localhost:{port}/api/tasks")
    print(f"  Storage : {dao.name}  ({dao.location})")
    print("  Press Ctrl+C to stop.")
    print()
    app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
