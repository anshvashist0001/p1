"""Opt-in integration test; TEST_DATABASE_URL must identify a dedicated demo DB."""

import os
import unittest

from fastapi.testclient import TestClient

from app.database import initialize
from app.main import create_app


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to test PostgreSQL")
class PostgresTests(unittest.TestCase):
    def test_postgres_seed_queries_and_monitoring(self):
        url = os.environ["TEST_DATABASE_URL"]
        initialize(url)
        initialize(url)  # Seeding must be repeatable.
        with TestClient(create_app(url)) as client:
            self.assertEqual(client.get("/health").json()["database"], "PostgreSQL")
            self.assertEqual(client.get("/api/products?limit=3").status_code, 200)
            self.assertEqual(client.get("/api/products/1").json()["id"], 1)
            self.assertEqual(client.get("/api/products/999999").status_code, 404)
            before = client.get("/api/demo/catalog?strategy=n_plus_one")
            after = client.get("/api/demo/catalog?strategy=batch")
            self.assertEqual(before.status_code, 200)
            self.assertEqual(before.json(), after.json())
            self.assertEqual(len(after.json()["items"]), 100)
            samples = client.get("/monitoring/requests").json()["items"][:2]
            self.assertEqual([s["query_count"] for s in samples], [1, 101])
