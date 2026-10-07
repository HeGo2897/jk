"""Business layer: validates input, calls the DAO and records activity.

It contains no HTTP code and no SQL, so it is easy to explain and to test.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from errors import ApiError

PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
STATUSES = {"PENDING", "IN_PROGRESS", "COMPLETED"}
ACTIVITY_LIMIT = 15
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def sample_drafts() -> list[dict]:
    """Demo tasks (dates are relative to today)."""
    today = date.today()

    def make(title, description, category, priority, offset, status):
        return {"title": title, "description": description, "category": category, "priority": priority,
                "deadline": (today + timedelta(days=offset)).isoformat(), "status": status}

    return [
        make("Complete Java Assignment", "Implement JDBC CRUD operations for the student module.",
             "Academics", "HIGH", 2, "IN_PROGRESS"),
        make("Prepare DS Seminar", "Slides on balanced trees and hashing.", "Academics", "MEDIUM", 5, "PENDING"),
        make("Submit VAC Project", "Final report, source code and demo video.", "Project", "HIGH", -1, "PENDING"),
        make("Revise Sorting Algorithms", "Quick, merge and heap sort complexity notes.",
             "Academics", "LOW", 7, "COMPLETED"),
        make("Build Portfolio Landing Page", "Responsive hero section using CSS Grid.",
             "Development", "MEDIUM", 10, "PENDING"),
    ]


class TaskService:
    def __init__(self, dao):
        self.dao = dao

    def storage_name(self) -> str:
        return self.dao.name

    def list_tasks(self) -> list[dict]:
        return self.dao.find_all()

    def get(self, task_id: int) -> dict:
        task = self.dao.find_by_id(task_id)
        if task is None:
            raise ApiError(404, f"Task {task_id} not found")
        return task

    def create(self, body: dict) -> dict:
        blank = {"title": "", "description": "", "category": "General", "priority": "MEDIUM",
                 "deadline": None, "status": "PENDING"}
        created = self.dao.insert(_merge(blank, body))
        self.dao.add_activity("New task created", created["title"])
        return created

    def update(self, task_id: int, body: dict) -> dict:
        """Partial update: only the fields present in the JSON body are changed."""
        before = self.get(task_id)
        current = {k: before[k] for k in ("title", "description", "category", "priority", "deadline", "status")}
        nxt = _merge(current, body)
        self.dao.update(task_id, nxt)

        if nxt["status"] == "COMPLETED" and before["status"] != "COMPLETED":
            self.dao.add_activity("Task completed", nxt["title"])
        elif nxt["priority"] != before["priority"]:
            self.dao.add_activity("Task priority changed", f"{nxt['title']} \u2192 {nxt['priority']}")
        else:
            self.dao.add_activity("Task updated", nxt["title"])
        return self.get(task_id)

    def delete(self, task_id: int) -> None:
        task = self.get(task_id)
        if not self.dao.delete(task_id):
            raise ApiError(404, f"Task {task_id} not found")
        self.dao.add_activity("Task deleted", task["title"])

    def delete_all(self) -> int:
        count = self.dao.delete_all()
        self.dao.clear_activity()
        return count

    def load_samples(self) -> int:
        drafts = sample_drafts()
        for d in drafts:
            self.dao.insert(d)
        self.dao.add_activity("Sample data loaded", f"{len(drafts)} tasks")
        return len(drafts)

    def seed_initial_data(self) -> None:
        """Seeds demo data without an activity entry (used once, on a brand-new database)."""
        for d in sample_drafts():
            self.dao.insert(d)

    def activity(self) -> list[dict]:
        return self.dao.recent_activity(ACTIVITY_LIMIT)


# --------------------------------------------------------------- validation
def _merge(base: dict, body: dict) -> dict:
    title = _text(body, "title", base["title"], 255)
    if not title:
        raise ApiError(400, "Task title is required.")
    category = _text(body, "category", base["category"], 100) or "General"
    return {
        "title": title,
        "description": _text(body, "description", base["description"], 5000),
        "category": category,
        "priority": _choice(body, "priority", base["priority"], PRIORITIES),
        "deadline": _date(body, "deadline", base["deadline"]),
        "status": _choice(body, "status", base["status"], STATUSES),
    }


def _text(body: dict, key: str, current: str, max_len: int) -> str:
    if key not in body:
        return current
    value = body[key]
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ApiError(400, f"{key} must be text")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(400, f"{key} must be at most {max_len} characters")
    return value


def _choice(body: dict, key: str, current: str, allowed: set) -> str:
    if key not in body:
        return current
    value = body[key]
    value = value.strip().upper() if isinstance(value, str) else None
    if value not in allowed:
        raise ApiError(400, f"{key} must be one of [{', '.join(sorted(allowed))}]")
    return value


def _date(body: dict, key: str, current):
    if key not in body:
        return current
    value = body[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(400, f"{key} must be a date in YYYY-MM-DD format")
    value = value.strip()
    if not value:
        return None
    try:
        if not _DATE_RE.fullmatch(value):
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(400, f"{key} must be a valid date in YYYY-MM-DD format") from None
