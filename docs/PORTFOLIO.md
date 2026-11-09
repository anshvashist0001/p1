# Portfolio and interview notes

## Project description

**API Performance Profiler & Bottleneck Analyzer** is a FastAPI application that
instruments request latency, errors, and database queries, presents live metrics,
and demonstrates a measured SQL optimization. PostgreSQL stores the product
catalog; a separate SQLite database retains the latest 10,000 request samples.

## Resume-ready bullets

- Built a FastAPI performance profiler with a live dashboard for endpoint latency,
  error rates, query counts, and database execution timings.
- Analyzed and eliminated an N+1 query pattern, reducing catalog queries from
  101 to 1 while preserving identical output; measured a 20.6% reduction in median
  round-average latency across a local PostgreSQL benchmark of 1,000 requests.
- Implemented bounded persistent monitoring history and validated restart recovery,
  concurrent request isolation, error handling, and PostgreSQL behavior with 12 tests.
- Containerized the API and dashboard with PostgreSQL using Docker Compose,
  healthchecks, an unprivileged app user, and persistent data volumes; verified
  all 12 tests inside Docker and history recovery after container recreation.

The latency figure is specific to the workload and machine in
[the benchmark report](../reports/benchmark.md). Do not describe it as a production
improvement or claim 1,000 concurrent users: concurrency was five.

## Five-minute demonstration

1. Open the dashboard and explain request latency, p95, errors, and SQL timings.
2. Generate traffic. Point out that the slow route and 503 are deliberate test cases.
3. Compare query strategies. Filter the table to `catalog` and show 101 versus 1 query.
4. Explain why identical output matters when optimizing a query pattern.
5. Restart the API and show that the request history is restored.
6. Open the benchmark report, describe warm-up and alternating order, and discuss
   the variation between rounds instead of claiming a universal speedup.

## Interview discussion

**What does analysis mean here?** Investigating software behavior: tracing where
time is spent, identifying repeated queries, proposing a change, and validating
both correctness and performance with a controlled workload.

**Why isn't query time the same as request latency?** Request time also includes
connection setup, Python work, scheduling, serialization, and response transmission
through the application. SQL time covers only execute/fetch calls.

**Why retain a bounded window?** It limits memory and stored rows while keeping
recent evidence. It is deliberately not an indefinite audit log.

**Why separate monitoring storage?** Measurements remain available independently
of the product database and can be restored quickly. The trade-off is a
single-process architecture with extra disk-write overhead.

**What would come next in a production system?** Authentication, connection pools,
centralized telemetry, distributed tracing, robust queuing, and retention policies.
These are extensions, not implemented capabilities.

## Source and results

The repository includes source code, tests, a dashboard screenshot, and the saved
benchmark reports. Local databases and Python environments are excluded from Git.
The benchmark is a historical run from 1 November 2026; its source fingerprint
identifies that version, before later readability edits.
