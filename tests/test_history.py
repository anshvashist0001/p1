from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.monitoring import Metrics, Sample


class HistoryTests(unittest.TestCase):
    def test_restart_restores_bounded_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "metrics.db")
            metrics = Metrics(capacity=3, history_path=path)
            metrics.restore()
            for number in range(5):
                metrics.record(Sample("GET", "/api/test", 200, number, 1, .1))
            restored = Metrics(capacity=3, history_path=path)
            restored.restore()
            self.assertEqual([s.duration_ms for s in restored.snapshot()], [2, 3, 4])
            self.assertEqual(restored.report()["persistence"], "enabled")
            smaller = Metrics(capacity=2, history_path=path)
            smaller.restore()
            self.assertEqual([s.duration_ms for s in smaller.snapshot()], [3, 4])

    def test_application_restart_preserves_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            database = str(Path(folder) / "products.db")
            history = str(Path(folder) / "metrics.db")
            with TestClient(create_app(database, history)) as client:
                client.get("/api/products/1")
            with TestClient(create_app(database, history)) as client:
                report = client.get("/monitoring/summary").json()
                self.assertEqual(report["requests"], 1)
                self.assertEqual(report["endpoints"][0]["avg_query_count"], 1)

    def test_write_failure_is_visible_but_keeps_live_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            metrics = Metrics(history_path=str(Path(folder) / "missing" / "metrics.db"))
            with self.assertLogs("app.monitoring", level="ERROR"):
                metrics.record(Sample("GET", "/api/test", 200, 1, 0, 0))
            self.assertEqual(metrics.report()["persistence"], "degraded")
            self.assertEqual(len(metrics.snapshot()), 1)
