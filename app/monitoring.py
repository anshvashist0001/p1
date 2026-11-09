"""Bounded, process-local request measurements and endpoint summaries."""

from collections import defaultdict, deque
from contextlib import closing
from dataclasses import asdict, dataclass, field
import json
import logging
from math import ceil
from pathlib import Path
import sqlite3
from threading import Lock
from time import perf_counter, time
from starlette.concurrency import run_in_threadpool


@dataclass(frozen=True)
class Sample:
    method: str
    route: str
    status: int
    duration_ms: float
    query_count: int
    query_ms: float
    variant: str = "default"
    timestamp: float = field(default_factory=time)


class Metrics:
    def __init__(self, capacity=10000, history_path=None):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.samples = deque(maxlen=capacity)
        self.lock = Lock()
        self.history_path = history_path
        self.persistence_error = False

    def restore(self):
        if self.history_path is None:
            return
        Path(self.history_path).parent.mkdir(parents=True, exist_ok=True)
        with self.lock, closing(sqlite3.connect(self.history_path)) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
            self._prune(connection)
            rows = connection.execute("SELECT payload FROM samples ORDER BY id").fetchall()
            self.samples.clear()
            self.samples.extend(Sample(**json.loads(row[0])) for row in rows)

    def _prune(self, connection):
        connection.execute("DELETE FROM samples WHERE id NOT IN (SELECT id FROM samples ORDER BY id DESC LIMIT ?)", (self.samples.maxlen,))

    def record(self, sample):
        with self.lock:
            self.samples.append(sample)
            if self.history_path is not None:
                try:
                    with closing(sqlite3.connect(self.history_path, timeout=2)) as connection, connection:
                        connection.execute("INSERT INTO samples (payload) VALUES (?)", (json.dumps(asdict(sample)),))
                        self._prune(connection)
                except sqlite3.Error:
                    # Keep live metrics available if the history file cannot be written.
                    self.persistence_error = True
                    logging.getLogger(__name__).exception("Could not persist a monitoring sample")

    def snapshot(self):
        with self.lock:
            return list(self.samples)

    def report(self):
        samples = self.snapshot()
        groups = defaultdict(list)
        for sample in samples:
            groups[(sample.method, sample.route, sample.variant)].append(sample)
        endpoints = []
        for (method, route, variant), rows in groups.items():
            durations = sorted(row.duration_ms for row in rows)
            count = len(rows)
            total_ms = sum(durations)
            query_ms = sum(row.query_ms for row in rows)
            endpoints.append({
                "method": method, "route": route, "variant": variant, "requests": count,
                "avg_ms": round(total_ms / count, 3),
                "p95_ms": round(durations[ceil(count * .95) - 1], 3),
                "max_ms": round(durations[-1], 3),
                "client_errors": sum(400 <= row.status < 500 for row in rows),
                "server_errors": sum(row.status >= 500 for row in rows),
                "error_rate_pct": round(100 * sum(row.status >= 400 for row in rows) / count, 2),
                "avg_query_count": round(sum(row.query_count for row in rows) / count, 2),
                "avg_query_ms": round(query_ms / count, 3),
                "query_share_pct": round(100 * query_ms / total_ms, 2) if total_ms else 0,
            })
        return {
            "window": "most recent requests; restored on restart" if self.history_path else "most recent requests; resets on restart",
            "persistence": "degraded" if self.persistence_error else ("enabled" if self.history_path else "disabled"),
            "capacity": self.samples.maxlen,
            "requests": len(samples),
            "endpoints": sorted(endpoints, key=lambda row: row["p95_ms"], reverse=True),
        }


class MonitorMiddleware:
    """Time API responses without storing bodies, headers, or query parameters."""

    def __init__(self, app, metrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state["query_count"] = 0
        state["query_ms"] = 0.0
        start = perf_counter()
        status = 500
        finished = None

        async def observed_send(message):
            nonlocal status, finished
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                finished = perf_counter()

        try:
            await self.app(scope, receive, observed_send)
        finally:
            route = scope.get("route")
            await run_in_threadpool(self.metrics.record, Sample(
                method=scope["method"],
                route=getattr(route, "path", "<unmatched>"),
                status=status,
                duration_ms=((finished or perf_counter()) - start) * 1000,
                query_count=state["query_count"], query_ms=state["query_ms"],
                variant=state.get("variant", "default"),
            ))


def recent_samples(metrics, limit):
    return [asdict(sample) for sample in reversed(metrics.snapshot()[-limit:])]
