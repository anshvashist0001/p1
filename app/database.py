"""Small demo database; query timing includes execution and fetching rows."""

import sqlite3
from contextlib import closing
from pathlib import Path
from time import perf_counter


def initialize(path):
    if not is_postgres(path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS products ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL)"
        )
        placeholders = "%s, %s, %s" if is_postgres(path) else "?, ?, ?"
        with closing(connection.cursor()) as cursor:
            cursor.executemany(
                f"INSERT INTO products (id, name, price_cents) VALUES ({placeholders}) "
                "ON CONFLICT (id) DO NOTHING",
                [(number, f"Product {number:03d}", number * 125) for number in range(1, 101)],
            )
        connection.commit()


def query(connection, request, sql, parameters=()):
    start = perf_counter()
    try:
        # Only application-owned SQL uses this helper; '?' is our placeholder convention.
        if not isinstance(connection, sqlite3.Connection):
            sql = sql.replace("?", "%s")
        with closing(connection.cursor()) as cursor:
            cursor.execute(sql, parameters)
            return cursor.fetchall()
    finally:
        request.state.query_count += 1
        request.state.query_ms += (perf_counter() - start) * 1000


def connect(path):
    if is_postgres(path):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(path, row_factory=dict_row, connect_timeout=5)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def is_postgres(path):
    return str(path).startswith(("postgresql://", "postgres://"))
