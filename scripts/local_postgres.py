"""Manage an isolated, password-authenticated demo cluster using installed PostgreSQL."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "postgres"
PORT = 5434


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--bin", default="C:/Program Files/PostgreSQL/18/bin")
    args = parser.parse_args()
    binary = Path(args.bin)
    ctl = str(binary / "pg_ctl.exe")
    if not Path(ctl).is_file():
        parser.error("PostgreSQL binaries not found; provide --bin")
    if args.action != "start":
        subprocess.run([ctl, args.action, "-D", str(DATA)], check=True)
        return
    DATA.parent.mkdir(parents=True, exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=DATA.parent) as password:
            password.write("local-profiler-dev\n")
        try:
            subprocess.run([str(binary / "initdb.exe"), "-D", str(DATA), "-U", "profiler",
                            "-A", "scram-sha-256", "--pwfile", password.name,
                            "--encoding=UTF8", "--no-locale"], check=True)
        finally:
            os.unlink(password.name)
    status = subprocess.run([ctl, "status", "-D", str(DATA)], capture_output=True)
    if status.returncode != 0:
        subprocess.run([ctl, "start", "-D", str(DATA), "-l", str(DATA.parent / "postgres.log"),
                        "-o", f"-h 127.0.0.1 -p {PORT}", "-w", "-t", "30"], check=True)
    import psycopg
    with psycopg.connect(host="127.0.0.1", port=PORT, user="profiler", password="local-profiler-dev",
                         dbname="postgres", autocommit=True, connect_timeout=5) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("profiler",)).fetchone():
            connection.execute("CREATE DATABASE profiler")
    print(f"Project PostgreSQL ready on 127.0.0.1:{PORT}; database: profiler")


if __name__ == "__main__":
    main()
