"""Real HTTP roles, actual worker, persisted payer timeout/retry/reconciliation and audit safety."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request(path, body=None, token="local-review"):
    req = urllib.request.Request(
        "http://127.0.0.1:18102" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_real_worker_roles_claim_rejection_and_payer_recovery(tmp_path):
    from docket import store
    from docket.documents import fixture

    store.initialize()
    with store.connection() as c:
        c.execute("TRUNCATE audit,outbox,mock_payer,jobs,documents RESTART IDENTITY CASCADE")
    log = tmp_path / "server.log"
    with log.open("w") as out:
        child = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "docket.server"],
            cwd=ROOT,
            env={**os.environ, "PORT": "18102"},
            stdout=out,
            stderr=out,
        )
        try:
            for _ in range(300):
                try:
                    if request("/api/documents")[0] == 200:
                        break
                except OSError:
                    time.sleep(0.05)
            assert request("/api/documents", token="wrong")[0] == 401
            assert request("/api/ingest", {"fixture": 15}, token="local-view")[0] == 403
            assert request("/api/ingest", {"fixture": True})[0] == 400
            code, evidence = request("/api/evidence", token="local-view")
            assert code == 200 and "rows" not in evidence
            assert evidence["model"]["total_fields"] > 0 and "rows" not in evidence["model"]
            assert "synthetic@example.invalid" not in json.dumps(evidence)
            assert "source_text" not in json.dumps(evidence)
            for _ in range(500):
                row = request("/api/document?id=doc-0002")[1]
                if row["state"] in ["auto", "review"]:
                    break
                time.sleep(0.05)
            assert row["result"] is not None
            code, redacted = request("/api/document?id=doc-0002", token="local-view")
            assert code == 200 and redacted["result"]["redacted"]
            assert request("/api/image?id=doc-0002", token="local-view")[0] == 403
            assert (
                request("/api/check-claim", {"id": row["id"], "claim": "urgent action is stated."})[
                    1
                ]["supported"]
                is False
            )
            review = {
                "id": row["id"],
                "revision": row["revision"],
                "values": fixture(2)["truth"],
                "attested": True,
                "note": "Scripted synthetic source correction",
            }
            assert request("/api/review", review)[0] == 200
            assert request("/api/review", review)[0] == 409
            assert request("/api/payer", {"id": row["id"]})[0] == 200
            for _ in range(200):
                updated = request("/api/document?id=doc-0002")[1]
                if updated["payer"] and updated["payer"]["state"] in [
                    "accepted",
                    "denied",
                    "error",
                ]:
                    break
                time.sleep(0.05)
            assert updated["payer"]["state"] == "accepted", updated["payer"]
            assert updated["payer"]["attempts"] >= 2  # real timeout after mock committed
            assert any(a["event"] == "payer_retry" for a in updated["audit"])
            with store.connection() as c:
                assert (
                    c.execute(
                        "SELECT count(*) AS n FROM mock_payer WHERE document='doc-0002'"
                    ).fetchone()["n"]
                    == 1
                )
            from docket.worker import image_path

            source = image_path("doc-0002")
            original = source.read_bytes()
            try:
                source.write_bytes(original + b"synthetic corruption control")
                assert request("/api/image?id=doc-0002")[0] == 409
            finally:
                source.write_bytes(original)
            # Restart the actual server while Postgres remains; decisions/outbox must survive.
            child.terminate()
            child.wait(timeout=25)
            child = subprocess.Popen(
                [str(ROOT / ".venv/bin/python"), "-m", "docket.server"],
                cwd=ROOT,
                env={**os.environ, "PORT": "18102"},
                stdout=out,
                stderr=out,
            )
            for _ in range(200):
                try:
                    restored = request("/api/document?id=doc-0002")[1]
                    if restored.get("payer", {}).get("state") == "accepted":
                        break
                except (OSError, AttributeError):
                    pass
                time.sleep(0.05)
            assert restored["state"] == "reviewed" and restored["payer"]["state"] == "accepted"
            assert restored["review"]["fields"]["amount"]["value"] == fixture(2)["truth"]["amount"]
            print(
                json.dumps(
                    {
                        "mock_payer": "actual post-commit HTTP timeout reconciled",
                        "attempts": updated["payer"]["attempts"],
                        "duplicate_claims": 0,
                    }
                )
            )
        finally:
            child.terminate()
            child.wait(timeout=25)
    text = log.read_text()
    assert (
        "DEMO710002" not in text
        and "synthetic@example.invalid" not in text
        and "local-review" not in text
    )
