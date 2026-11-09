# Verification record

Verified locally on 1 November 2026 with Python 3.12.8, Windows, and the isolated
PostgreSQL 18 instance on loopback port 5434.

- All 12 unittest checks passed with `TEST_DATABASE_URL` configured, including
  real PostgreSQL seeding, parameterized queries, response equivalence, and SQL counts.
- Persistence tests passed for restart recovery, bounded retention, and visible
  degradation when disk writes fail.
- JavaScript syntax check passed with `node --check app/static/dashboard.js`.
- The five-round benchmark completed 1,000 successful measured requests;
  every response matched the reference catalog. Results are in `reports/`.
- Before restarting the live API: 1,021 samples in memory and 1,021 saved to disk.
  After restart: all 1,021 restored; persistence enabled; database PostgreSQL.
- Browser verification showed PostgreSQL, restored request counts, separate
  strategy statistics, and the updated persistence footer. No browser console
  errors were reported. Screenshot: `dashboard-preview.png`.

## Docker verification — 8 November 2026

- Built the application image successfully using `python:3.12-slim`.
- App and PostgreSQL 17 containers both report healthy in Docker Compose.
- All 12 tests passed inside the Linux app container with PostgreSQL integration enabled.
- Dashboard, CSS, JavaScript, and API docs returned HTTP 200 on loopback port 8001.
- Compared identical catalog output and verified 101 versus 1 recorded SQL queries.
- Recreated both containers with their named volumes retained; all recorded samples
  were restored exactly, including timestamps. PostgreSQL queries passed afterward.
- Confirmed app UID/GID 10001 (unprivileged) and no broken Python requirements.

The native PostgreSQL 18 benchmark remains a native Windows result; it has not
been relabeled as a Docker performance measurement.
These checks describe the local runs on the dates above. Hosted CI results are
available in the repository's Actions tab once the workflow runs.

## Repository cleanup — 9 November 2026

- Simplified the README, clarified comments, and split dense Python and CSS lines.
- Rebuilt the Docker image and passed all 12 tests with PostgreSQL enabled.
- Checked JavaScript syntax with `node --check`.
- Kept the original benchmark results and their source fingerprint unchanged.
