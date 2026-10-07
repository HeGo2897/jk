"""Automated tests. Run from the backend folder:   python -m unittest discover -s tests -v

Each test uses a fresh temporary SQLite file, so your real data is never touched.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app          # noqa: E402
from config import Config           # noqa: E402


def make_app(db_file, seed=True):
    return create_app(Config(overrides={
        ("database", "type"): "sqlite",
        ("database", "sqlite_path"): db_file,
        ("app", "seed_sample_data"): "true" if seed else "false",
    }))


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_file = str(Path(self.tmp.name) / "test.db")
        self.app = make_app(self.db_file)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, body, path="/api/tasks"):
        return self.client.post(path, data=json.dumps(body))

    def put(self, task_id, body):
        return self.client.put(f"/api/tasks/{task_id}", data=json.dumps(body))


class TestReading(ApiTestCase):
    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"status": "ok", "storage": "sqlite"})

    def test_seeded_on_first_run(self):
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 5)
        self.assertEqual(set(tasks[0]), {"id", "title", "description", "category", "priority",
                                         "deadline", "status", "created_at"})

    def test_not_seeded_when_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            app = make_app(str(Path(d) / "x.db"), seed=False)
            self.assertEqual(app.test_client().get("/api/tasks").get_json(), [])

    def test_get_one_and_missing(self):
        self.assertEqual(self.client.get("/api/tasks/1").status_code, 200)
        r = self.client.get("/api/tasks/999")
        self.assertEqual(r.status_code, 404)
        self.assertIn("not found", r.get_json()["error"])


class TestCreate(ApiTestCase):
    def test_create_valid_normalises_input(self):
        r = self.post({"title": "  Learn Flask  ", "description": "Café ☕ & \"quotes\"", "category": "Study",
                       "priority": "high", "deadline": "2026-10-20", "status": "in_progress"})
        self.assertEqual(r.status_code, 201)
        t = r.get_json()
        self.assertEqual((t["title"], t["priority"], t["status"], t["deadline"]),
                         ("Learn Flask", "HIGH", "IN_PROGRESS", "2026-10-20"))
        self.assertEqual(t["description"], 'Café ☕ & "quotes"')
        self.assertTrue(t["created_at"].endswith("Z"))

    def test_defaults(self):
        t = self.post({"title": "Only a title"}).get_json()
        self.assertEqual((t["category"], t["priority"], t["status"], t["deadline"]),
                         ("General", "MEDIUM", "PENDING", None))

    def test_validation_errors(self):
        cases = [
            ({"title": "   "}, "Task title is required."),
            ({"priority": "HIGH"}, "Task title is required."),
            ({"title": "x", "priority": "URGENT"}, "priority must be one of"),
            ({"title": "x", "status": 5}, "status must be one of"),
            ({"title": "x", "deadline": "2026-13-45"}, "valid date"),
            ({"title": "x", "deadline": "20261012"}, "valid date"),
            ({"title": "x", "deadline": 20261012}, "YYYY-MM-DD"),
            ({"title": 123}, "must be text"),
            ({"title": "a" * 256}, "at most 255"),
        ]
        for body, expected in cases:
            with self.subTest(body=str(body)[:40]):
                r = self.post(body)
                self.assertEqual(r.status_code, 400)
                self.assertIn(expected, r.get_json()["error"])

    def test_bad_bodies(self):
        self.assertEqual(self.client.post("/api/tasks").status_code, 400)                       # empty
        self.assertIn("Invalid JSON", self.client.post("/api/tasks", data='{"title":').get_json()["error"])
        self.assertIn("object", self.client.post("/api/tasks", data="[1,2]").get_json()["error"])

    def test_body_too_large(self):
        r = self.client.post("/api/tasks", data=json.dumps({"title": "x", "description": "d" * 1_100_000}))
        self.assertEqual(r.status_code, 413)

    def test_sql_injection_is_stored_as_plain_text(self):
        evil = "x'); DROP TABLE tasks; --"
        self.assertEqual(self.post({"title": evil}).status_code, 201)
        tasks = self.client.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 6)                       # table still exists
        self.assertEqual(tasks[-1]["title"], evil)


class TestUpdateDelete(ApiTestCase):
    def test_partial_update_changes_only_given_fields(self):
        before = self.client.get("/api/tasks/2").get_json()
        after = self.put(2, {"priority": "LOW"}).get_json()
        self.assertEqual(after["priority"], "LOW")
        self.assertEqual({k: v for k, v in after.items() if k != "priority"},
                         {k: v for k, v in before.items() if k != "priority"})

    def test_clear_deadline_and_patch(self):
        r = self.client.patch("/api/tasks/2", data=json.dumps({"deadline": None}))
        self.assertIsNone(r.get_json()["deadline"])

    def test_update_missing_and_invalid(self):
        self.assertEqual(self.put(999, {"title": "a"}).status_code, 404)
        self.assertEqual(self.put(2, {"title": ""}).status_code, 400)
        self.assertEqual(self.client.put("/api/tasks/abc", data="{}").status_code, 400)
        self.assertEqual(self.client.get("/api/tasks/0").status_code, 400)

    def test_delete(self):
        self.assertEqual(self.client.delete("/api/tasks/1").status_code, 204)
        self.assertEqual(self.client.delete("/api/tasks/1").status_code, 404)
        self.assertEqual(len(self.client.get("/api/tasks").get_json()), 4)

    def test_delete_all_clears_activity_and_samples_come_back(self):
        self.post({"title": "temp"})
        self.assertEqual(self.client.delete("/api/tasks").get_json(), {"deleted": 6})
        self.assertEqual(self.client.get("/api/tasks").get_json(), [])
        self.assertEqual(self.client.get("/api/activity").get_json(), [])
        self.assertEqual(self.post({}, "/api/tasks/sample").status_code, 201)
        self.assertEqual(len(self.client.get("/api/tasks").get_json()), 5)


class TestActivity(ApiTestCase):
    def test_activity_messages(self):
        tid = self.post({"title": "Track me"}).get_json()["id"]
        self.put(tid, {"priority": "HIGH"})
        self.put(tid, {"status": "COMPLETED"})
        self.put(tid, {"description": "more"})
        self.client.delete(f"/api/tasks/{tid}")
        messages = [(a["message"], a["detail"]) for a in self.client.get("/api/activity").get_json()]
        self.assertEqual(messages, [
            ("Task deleted", "Track me"),
            ("Task updated", "Track me"),
            ("Task completed", "Track me"),
            ("Task priority changed", "Track me \u2192 HIGH"),
            ("New task created", "Track me"),
        ])

    def test_activity_has_epoch_millis_and_limit(self):
        for i in range(20):
            self.post({"title": f"t{i}"})
        feed = self.client.get("/api/activity").get_json()
        self.assertEqual(len(feed), 15)
        self.assertGreater(feed[0]["at"], 1_600_000_000_000)


class TestPersistenceAndHttp(ApiTestCase):
    def test_data_survives_a_restart_and_is_not_reseeded(self):
        self.post({"title": "Persistent task"})
        second = make_app(self.db_file).test_client()           # "restart": new app, same database file
        tasks = second.get("/api/tasks").get_json()
        self.assertEqual(len(tasks), 6)
        self.assertIn("Persistent task", [t["title"] for t in tasks])

    def test_wrong_method_and_unknown_endpoint_are_json(self):
        r = self.client.post("/api/health")
        self.assertEqual((r.status_code, r.get_json()["error"]), (405, "Method not allowed"))
        r = self.client.get("/api/nope")
        self.assertEqual((r.status_code, r.get_json()["error"]), (404, "Unknown API endpoint"))

    def test_cors_headers(self):
        r = self.client.options("/api/tasks")
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("PUT", r.headers["Access-Control-Allow-Methods"])

    def test_serves_frontend_and_blocks_traversal(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"NEXA TASK", r.data)
        r.close()
        for path, mime in (("/css/style.css", "text/css"), ("/js/api.js", "javascript")):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200)
            self.assertIn(mime, r.headers["Content-Type"])
            r.close()
        for bad in ("/../config.ini", "/%2e%2e/config.ini", "/..%2fconfig.ini", "/missing.html"):
            r = self.client.get(bad)
            self.assertEqual(r.status_code, 404, bad)
            r.close()


if __name__ == "__main__":
    unittest.main()
