FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    METRICS_PATH=/app/data/metrics.db
WORKDIR /app

COPY requirements.txt requirements-postgres.txt ./
RUN python -m pip install --no-cache-dir -r requirements-postgres.txt \
    && groupadd --gid 10001 profiler \
    && useradd --uid 10001 --gid profiler --no-create-home profiler \
    && mkdir -p /app/data \
    && chown profiler:profiler /app/data

COPY app ./app
COPY tests ./tests
USER profiler
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
