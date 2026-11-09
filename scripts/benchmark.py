"""Repeat a controlled catalog comparison and save measured JSON + Markdown evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
from statistics import mean, median
from time import perf_counter
from urllib.request import urlopen


def positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def read(url):
    start = perf_counter()
    with urlopen(url, timeout=20) as response:
        payload = response.read()
    return (perf_counter() - start) * 1000, json.loads(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--rounds", type=positive, default=5)
    parser.add_argument("--requests", type=positive, default=100)
    parser.add_argument("--concurrency", type=positive, default=5)
    parser.add_argument("--warmup", type=positive, default=10)
    parser.add_argument("--output", default="reports/benchmark.json")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    _, health = read(base + "/health")
    strategies = ["n_plus_one", "batch"]
    urls = {name: f"{base}/api/demo/catalog?strategy={name}" for name in strategies}
    _, expected = read(urls["batch"])
    for _ in range(args.warmup):
        for name in strategies:
            _, data = read(urls[name])
            if data != expected:
                raise RuntimeError("Catalog output mismatch during warm-up")
    rounds = []
    for iteration in range(args.rounds):
        order = strategies if iteration % 2 == 0 else list(reversed(strategies))
        for name in order:
            def visit(_):
                duration, data = read(urls[name])
                if data != expected:
                    raise RuntimeError("Catalog output mismatch")
                return duration
            start = perf_counter()
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                durations = sorted(executor.map(visit, range(args.requests)))
            elapsed = perf_counter() - start
            rounds.append({"round": iteration + 1, "strategy": name, "requests": len(durations),
                           "avg_ms": mean(durations), "p95_ms": durations[math.ceil(len(durations) * .95) - 1],
                           "requests_per_second": len(durations) / elapsed, "elapsed_seconds": elapsed})
            print(f"Round {iteration + 1}: {name}, mean {mean(durations):.2f} ms", flush=True)
    summary = {name: {key: median(row[key] for row in rounds if row["strategy"] == name)
                      for key in ["avg_ms", "p95_ms", "requests_per_second"]} for name in strategies}
    reduction = 100 * (1 - summary["batch"]["avg_ms"] / summary["n_plus_one"]["avg_ms"])
    root = Path(__file__).resolve().parents[1]
    source = hashlib.sha256()
    for path in sorted((root / "app").glob("*.py")):
        source.update(path.name.encode()); source.update(path.read_bytes())
    result = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "platform": platform.platform(), "database": health["database"], "source_sha256": source.hexdigest(),
              "workload": vars(args), "products": len(expected["items"]), "all_responses_equal": True,
              "measured_requests": args.rounds * args.requests * 2,
              "median_round_results": summary, "mean_latency_reduction_pct": reduction, "rounds": rounds}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# Controlled benchmark results", "", f"Recorded (UTC): {result['recorded_at_utc']}",
             f"Database: {health['database']}; Python: {result['python']}; OS: {result['platform']}", "",
             f"{args.rounds} rounds × {args.requests} requests per strategy; concurrency {args.concurrency}.",
             f"{args.warmup} warm-up requests per strategy, plus one initial output check. Alternating strategy order.",
             f"All {result['measured_requests']} measured responses succeeded and matched the same {result['products']}-product catalog.", "",
             "| Strategy | Median round mean | Median round p95 | Median throughput |",
             "| --- | ---: | ---: | ---: |"]
    for name in strategies:
        values = summary[name]
        lines.append(f"| {name} | {values['avg_ms']:.2f} ms | {values['p95_ms']:.2f} ms | {values['requests_per_second']:.2f} req/s |")
    lines += ["", f"Observed reduction in median round mean latency: **{reduction:.1f}%**.", "",
              "## Interpretation and limits", "",
              "These are local HTTP measurements, not production capacity claims. Timings include connection setup and response transfer; JSON validation happens after the latency timer. Throughput includes validation and client scheduling.",
              "The SQL optimization is verified separately by integration tests: 101 queries become one with identical output. No artificial sleep is used in this comparison.",
              "Connections are opened per request. Persistent metric writes happen after the response body but can affect subsequent requests under load. The benchmark includes that monitoring overhead.",
              "The dashboard's rolling history includes warm-ups and previous traffic. These results use separate client measurements for each round. No confidence interval is claimed; repeat on the target hardware before generalizing.",
              "", "## Per-round results", "", "| Round | Strategy | Mean ms | p95 ms | req/s |", "| --- | --- | ---: | ---: | ---: |"]
    for row in rounds:
        lines.append(f"| {row['round']} | {row['strategy']} | {row['avg_ms']:.2f} | {row['p95_ms']:.2f} | {row['requests_per_second']:.2f} |")
    lines += ["", f"Backend source SHA-256: `{result['source_sha256']}`", ""]
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {output} and {output.with_suffix('.md')}")


if __name__ == "__main__":
    main()
