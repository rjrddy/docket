"""Execute the actual nonroot image with real Postgres, OCR, review and restart."""

import json
import os
import subprocess
import time
import urllib.request
import uuid
from urllib.parse import quote

import psycopg
from psycopg import sql

NAME = "docket-smoke"
TOKEN = "synthetic-container-review-token-12345"


def docker(*args: str, check=True) -> str:
    r = subprocess.run(["docker", *args], check=check, capture_output=True, text=True)
    return (r.stdout + r.stderr if args[0] == "logs" else r.stdout).strip()


def request(path, body=None):
    req = urllib.request.Request(
        "http://127.0.0.1:18105" + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def ready():
    for _ in range(200):
        try:
            row = request("/api/document?id=doc-0002")
            if row.get("result"):
                return row
        except OSError:
            pass
        time.sleep(0.15)
    raise RuntimeError(docker("logs", NAME, check=False))


def main():
    schema = "docket_image_" + uuid.uuid4().hex[:12]
    with psycopg.connect(os.environ["DATABASE_URL"]) as c:
        c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    dsn = (
        "postgresql://postgres:synthetic-local-db-password@127.0.0.1:5432/docket?options="
        + quote("-csearch_path=" + schema, safe="")
    )
    try:
        docker(
            "run",
            "-d",
            "--name",
            NAME,
            "--network",
            "host",
            "-e",
            "PORT=18105",
            "-e",
            "DATABASE_URL=" + dsn,
            "-e",
            "DOCKET_REVIEW_TOKEN=" + TOKEN,
            "-e",
            "DOCKET_VIEW_TOKEN=synthetic-container-view-token-12345",
            "docket:test",
        )
        row = ready()
        assert docker("exec", NAME, "id", "-u") == "10001"
        # Approved values are a scripted synthetic fixture, not independent human review.
        from docket.documents import fixture

        updated = request(
            "/api/review",
            {
                "id": row["id"],
                "revision": row["revision"],
                "values": fixture(2)["truth"],
                "attested": True,
                "note": "Container synthetic fixture correction",
            },
        )
        assert updated["state"] == "reviewed"
        docker("kill", "--signal=KILL", NAME)
        docker("start", NAME)
        restored = ready()
        assert restored["state"] == "reviewed" and restored["review"] == updated["review"]
        print(
            json.dumps(
                {
                    "uid": 10001,
                    "actual_ocr": "pass",
                    "review": "pass",
                    "sigkill_recovery": "review and source persist",
                    "scope": "same actual container writable layer and external Postgres; recreation needs compose source volume",
                }
            )
        )
    finally:
        docker("rm", "-f", NAME, check=False)
        with psycopg.connect(os.environ["DATABASE_URL"]) as c:
            c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


if __name__ == "__main__":
    main()
