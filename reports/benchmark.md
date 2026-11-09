# Controlled benchmark results

Recorded (UTC): 2026-11-01T09:42:50.957839+00:00
Database: PostgreSQL; Python: 3.12.8; OS: Windows-11-10.0.26300-SP0

5 rounds × 100 requests per strategy; concurrency 5.
10 warm-up requests per strategy, plus one initial output check. Alternating strategy order.
All 1000 measured responses succeeded and matched the same 100-product catalog.

| Strategy | Median round mean | Median round p95 | Median throughput |
| --- | ---: | ---: | ---: |
| n_plus_one | 195.07 ms | 288.19 ms | 25.08 req/s |
| batch | 154.87 ms | 235.14 ms | 31.61 req/s |

Observed reduction in median round mean latency: **20.6%**.

## Interpretation and limits

These are local HTTP measurements, not production capacity claims. Timings include connection setup and response transfer; JSON validation happens after the latency timer. Throughput includes validation and client scheduling.
The SQL optimization is verified separately by integration tests: 101 queries become one with identical output. No artificial sleep is used in this comparison.
Connections are opened per request. Persistent metric writes happen after the response body but can affect subsequent requests under load. The benchmark includes that monitoring overhead.
The dashboard's rolling history includes warm-ups and previous traffic. These results use separate client measurements for each round. No confidence interval is claimed; repeat on the target hardware before generalizing.

## Per-round results

| Round | Strategy | Mean ms | p95 ms | req/s |
| --- | --- | ---: | ---: | ---: |
| 1 | n_plus_one | 155.23 | 225.87 | 31.66 |
| 1 | batch | 129.90 | 228.24 | 37.33 |
| 2 | batch | 116.47 | 200.07 | 41.97 |
| 2 | n_plus_one | 187.05 | 288.19 | 26.34 |
| 3 | n_plus_one | 195.07 | 278.04 | 25.08 |
| 3 | batch | 175.14 | 283.35 | 28.04 |
| 4 | batch | 175.61 | 309.00 | 27.61 |
| 4 | n_plus_one | 238.19 | 317.42 | 20.53 |
| 5 | n_plus_one | 257.76 | 382.64 | 19.17 |
| 5 | batch | 154.87 | 235.14 | 31.61 |

Backend source SHA-256: `ea6e7aafaf755a5a1f6058e91978ab8ca89c5170c9b264679da974a99d3025f7`
