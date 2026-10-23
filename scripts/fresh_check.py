"""Independent tracked-source clone: real gates and actual one-command demo."""

import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/results/fresh-clone"


def request(path: str) -> dict:
    req = urllib.request.Request(
        "http://127.0.0.1:18106" + path,
        headers={"Authorization": "Bearer local-review"},
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory(prefix="docket-fresh-") as temp:
        clone = Path(temp) / "docket"
        subprocess.run(
            ["git", "clone", "--no-hardlinks", str(ROOT), str(clone)],
            check=True,
            capture_output=True,
        )
        assert not (clone / ".venv").exists() and not (clone / ".cache").exists()
        with (OUT / "checks.log").open("w") as log:
            subprocess.run(
                ["make", "setup", "build", "lint", "test", "bench"],
                cwd=clone,
                stdout=log,
                stderr=log,
                check=True,
            )
        for name in ["evaluation.json", "matching-pairs.json"]:
            (OUT / name).write_bytes((clone / "docs/results" / name).read_bytes())
        with (OUT / "demo.log").open("w") as log:
            child = subprocess.Popen(
                ["make", "demo"],
                cwd=clone,
                env={**os.environ, "PORT": "18106"},
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                for _ in range(600):
                    if child.poll() is not None:
                        raise RuntimeError((OUT / "demo.log").read_text())
                    try:
                        row = request("/api/document?id=doc-0002")
                        if row.get("result"):
                            break
                    except OSError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError("make demo readiness timeout")
                with urllib.request.urlopen("http://127.0.0.1:18106/") as response:
                    assert b"Docket" in response.read()
                req = urllib.request.Request(
                    "http://127.0.0.1:18106/api/image?id=doc-0002",
                    headers={"Authorization": "Bearer local-review"},
                )
                with urllib.request.urlopen(req) as response:
                    assert hashlib.sha256(response.read()).hexdigest() == row["sha"]
                tracked = subprocess.check_output(
                    [
                        "git",
                        "ls-files",
                        "src",
                        "scripts",
                        "tests",
                        "apps/web",
                        "data",
                        "Makefile",
                        "pyproject.toml",
                        "requirements-dev.txt",
                    ],
                    cwd=clone,
                    text=True,
                ).splitlines()
                manifest = {
                    name: hashlib.sha256((clone / name).read_bytes()).hexdigest()
                    for name in tracked
                }
                (OUT / "verification.json").write_text(
                    json.dumps(
                        {
                            "head": head,
                            "passed": True,
                            "commands": [
                                "git clone --no-hardlinks",
                                "make setup build lint test bench",
                                "make demo",
                            ],
                            "copied_ignored_artifacts": False,
                            "live_document": {
                                "id": row["id"],
                                "state": row["state"],
                                "source_sha256": row["sha"],
                            },
                            "source_image_sha_verified": True,
                            "source_manifest": manifest,
                        },
                        indent=2,
                    )
                    + "\n"
                )
                print(json.dumps({"head": head, "fresh_clone": "pass", "actual_make_demo": "pass"}))
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=30)


if __name__ == "__main__":
    main()
