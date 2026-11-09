import asyncio
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.monitoring import Metrics, Sample


class ProfilerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = create_app(str(Path(self.folder.name) / "test.db"))
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.folder.cleanup()

    def test_monitoring_does_not_measure_itself(self):
        self.client.get("/health")
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/static/dashboard.js").status_code, 200)
        self.client.get("/monitoring/requests")
        self.assertEqual(self.client.get("/monitoring/summary").json()["requests"], 0)

    def test_route_grouping_and_error_classification(self):
        for product in [1, 2, 999]:
            self.client.get(f"/api/products/{product}")
        row = self.client.get("/monitoring/summary").json()["endpoints"][0]
        self.assertEqual(row["route"], "/api/products/{product_id}")
        self.assertEqual(row["requests"], 3)
        self.assertEqual(row["client_errors"], 1)
        self.assertEqual(row["server_errors"], 0)
        self.assertEqual(row["avg_query_count"], 1)

    def test_optimization_preserves_data_and_reduces_queries(self):
        before = self.client.get("/api/demo/catalog?strategy=n_plus_one")
        after = self.client.get("/api/demo/catalog?strategy=batch")
        self.assertEqual(before.json(), after.json())
        samples = self.client.get("/monitoring/requests").json()["items"]
        self.assertEqual([s["query_count"] for s in samples], [1, 101])
        self.assertTrue(all(s["query_ms"] > 0 for s in samples))
        rows = self.client.get("/monitoring/summary").json()["endpoints"]
        self.assertEqual({r["variant"]: r["avg_query_count"] for r in rows}, {"batch": 1, "n_plus_one": 101})
        self.assertTrue(all(s["timestamp"] > 0 for s in samples))

    def test_delay_and_handled_server_error(self):
        self.client.get("/api/demo/slow?delay_ms=40")
        self.assertEqual(self.client.get("/api/demo/error").status_code, 503)
        rows = self.client.get("/monitoring/summary").json()["endpoints"]
        slow = next(r for r in rows if r["route"].endswith("slow"))
        error = next(r for r in rows if r["route"].endswith("error"))
        self.assertGreaterEqual(slow["p95_ms"], 35)
        self.assertEqual(error["server_errors"], 1)

    def test_unhandled_exception_is_recorded(self):
        @self.app.get("/api/crash")
        def crash():
            raise RuntimeError("test exception")
        self.assertEqual(self.client.get("/api/crash").status_code, 500)
        self.assertEqual(self.app.state.metrics.snapshot()[-1].status, 500)

    def test_concurrent_requests_keep_separate_sql_counts(self):
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
                replies = await asyncio.gather(*[
                    client.get("/api/demo/catalog", params={"strategy": "batch" if n % 2 else "n_plus_one"})
                    for n in range(12)
                ])
                self.assertTrue(all(r.status_code == 200 for r in replies))
        asyncio.run(exercise())
        counts = [s.query_count for s in self.app.state.metrics.snapshot()]
        self.assertEqual(sorted(counts), [1] * 6 + [101] * 6)

    def test_validation_and_unknown_routes(self):
        self.assertEqual(self.client.get("/api/demo/slow?delay_ms=-1").status_code, 422)
        self.client.get("/api/missing/123")
        self.assertEqual(self.app.state.metrics.snapshot()[-1].route, "<unmatched>")


class AggregationTests(unittest.TestCase):
    def test_bounded_window_and_nearest_rank_percentile(self):
        metrics = Metrics(capacity=20)
        for duration in range(21):
            metrics.record(Sample("GET", "/test", 200, duration, 0, 0))
        report = metrics.report()
        self.assertEqual(report["requests"], 20)
        self.assertEqual(report["endpoints"][0]["p95_ms"], 19)
        self.assertEqual(report["endpoints"][0]["avg_ms"], 10.5)


if __name__ == "__main__":
    unittest.main()
