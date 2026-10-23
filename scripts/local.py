"""Own a local Postgres cluster; persistent for demo, isolated temporary clusters for gates."""

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], env: dict) -> None:
    child = subprocess.Popen(command, cwd=ROOT, env=env)

    def stop(_signum, _frame):
        if child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    code = child.wait()
    if code:
        raise SystemExit(code)


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "serve"
    command = {
        "serve": [sys.executable, "-m", "docket.server"],
        "test": [sys.executable, "-m", "pytest", "-q"],
        "bench": [sys.executable, "scripts/bench.py"],
        "review": [sys.executable, "scripts/review.py", *sys.argv[2:]],
        "seed": [sys.executable, "scripts/seed.py"],
    }[action]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    if env.get("DATABASE_URL"):
        run(command, env)
        return
    pg = shutil.which("pg_ctl")
    if not pg:
        raise SystemExit("Install PostgreSQL server tools or configure DATABASE_URL")
    with tempfile.TemporaryDirectory(prefix="docket-pg-") as temp:
        base = Path(temp)
        data = ROOT / ".cache/postgres-demo" if action == "serve" else base / "data"
        if action != "serve":
            env["DOCKET_SOURCE_DIR"] = str(base / "sources")
        data.parent.mkdir(parents=True, exist_ok=True)
        sock = base / "socket"
        sock.mkdir()
        with socket.socket() as selector:
            selector.bind(("127.0.0.1", 0))
            port = selector.getsockname()[1]
        if not (data / "PG_VERSION").exists():
            subprocess.run(
                ["initdb", "-D", str(data), "-A", "trust", "--no-locale", "-E", "UTF8"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        subprocess.run(
            [
                pg,
                "-D",
                str(data),
                "-l",
                str(base / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {port} -k {sock}",
                "-w",
                "start",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        env["DATABASE_URL"] = (
            f"postgresql://{os.getenv('USER', 'postgres')}@127.0.0.1:{port}/postgres"
        )
        try:
            run(command, env)
        finally:
            subprocess.run(
                [pg, "-D", str(data), "-m", "fast", "-w", "stop"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    main()
