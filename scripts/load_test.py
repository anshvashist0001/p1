"""Run repeatable HTTP traffic; reports actual client-observed measurements."""

import argparse
import json
import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/products")
    parser.add_argument("--requests", type=positive, default=100)
    parser.add_argument("--concurrency", type=positive, default=10)
    args = parser.parse_args()

    def visit(_):
        start = time.perf_counter()
        try:
            with urlopen(args.url, timeout=10) as response:
                response.read()
                status = str(response.status)
        except HTTPError as error:
            status = str(error.code)
            error.close()
        except (URLError, TimeoutError, OSError):
            status = "connection_error"
        return status, (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(visit, range(args.requests)))
    elapsed = time.perf_counter() - start
    timings = sorted(duration for _, duration in results)
    print(json.dumps({
        "url": args.url, "requests": args.requests, "concurrency": args.concurrency,
        "status_counts": dict(Counter(status for status, _ in results)),
        "elapsed_seconds": round(elapsed, 3),
        "requests_per_second": round(args.requests / elapsed, 2),
        "avg_ms": round(sum(timings) / len(timings), 3),
        "p95_ms": round(timings[math.ceil(len(timings) * .95) - 1], 3),
        "max_ms": round(timings[-1], 3),
    }, indent=2))


if __name__ == "__main__":
    main()
