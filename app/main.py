import asyncio
import os
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import connect, initialize, is_postgres, query
from app.monitoring import Metrics, MonitorMiddleware, recent_samples


def create_app(database_path=None, history_path=None):
    data_dir = Path(__file__).resolve().parents[1] / "data"
    path = (
        database_path
        or os.environ.get("DATABASE_URL")
        or os.environ.get("DATABASE_PATH", str(data_dir / "demo.db"))
    )
    # Test apps should not write to the running application's history.
    if history_path is None and database_path is None:
        history_path = os.environ.get("METRICS_PATH", str(data_dir / "metrics.db"))
    metrics = Metrics(history_path=history_path)

    @asynccontextmanager
    async def lifespan(app):
        initialize(path)
        metrics.restore()
        yield

    app = FastAPI(
        title="API Performance Profiler", version="0.3.0",
        description="Track API latency and SQL queries, then compare two ways to load a product catalog.",
        lifespan=lifespan,
    )
    app.state.metrics = metrics
    app.add_middleware(MonitorMiddleware, metrics=metrics)
    static = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static / "index.html")

    @app.get("/health", tags=["Service"])
    def health():
        return {"status": "ok", "database": "PostgreSQL" if is_postgres(path) else "SQLite"}

    @app.get("/api/products", tags=["Sample API"])
    def products(request: Request, limit: int = Query(20, ge=1, le=100)):
        with closing(connect(path)) as connection:
            rows = query(connection, request, "SELECT * FROM products ORDER BY id LIMIT ?", (limit,))
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/products/{product_id}", tags=["Sample API"])
    def product(product_id: int, request: Request):
        with closing(connect(path)) as connection:
            rows = query(connection, request, "SELECT * FROM products WHERE id = ?", (product_id,))
        if not rows:
            raise HTTPException(404, "Product not found")
        return dict(rows[0])

    @app.get("/api/demo/catalog", tags=["Bottleneck examples"])
    def catalog(request: Request, strategy: Literal["n_plus_one", "batch"] = "batch"):
        """Compare identical data fetched with 101 queries versus one query."""
        request.state.variant = strategy
        with closing(connect(path)) as connection:
            if strategy == "n_plus_one":
                ids = query(connection, request, "SELECT id FROM products ORDER BY id")
                rows = [
                    query(connection, request, "SELECT * FROM products WHERE id = ?", (row["id"],))[0]
                    for row in ids
                ]
            else:
                rows = query(connection, request, "SELECT * FROM products ORDER BY id")
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/demo/slow", tags=["Bottleneck examples"])
    async def slow(delay_ms: int = Query(250, ge=0, le=2000)):
        """Artificial wait to validate monitoring, not a real optimization result."""
        await asyncio.sleep(delay_ms / 1000)
        return {"simulated_delay_ms": delay_ms}

    @app.get("/api/demo/error", tags=["Bottleneck examples"])
    def error():
        raise HTTPException(503, "Intentional demo failure")

    @app.get("/monitoring/summary", tags=["Monitoring"])
    def summary():
        return metrics.report()

    @app.get("/monitoring/requests", tags=["Monitoring"])
    def requests(limit: int = Query(50, ge=1, le=200)):
        return {"items": recent_samples(metrics, limit)}

    return app


app = create_app()
