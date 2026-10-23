"""Postgres queue leases, revision-checked review, and transactional value-free audit."""

import os
import uuid
from contextlib import contextmanager
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .documents import FIELDS
from .extract import candidates, route, supported
from .privacy import fingerprint

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
 id text PRIMARY KEY, fixture integer NOT NULL, kind text NOT NULL, template text NOT NULL,
 sha text NOT NULL, state text NOT NULL DEFAULT 'queued', revision integer NOT NULL DEFAULT 0,
 result jsonb, review jsonb, created timestamptz NOT NULL DEFAULT now());
ALTER TABLE documents ADD COLUMN IF NOT EXISTS llm jsonb;
CREATE TABLE IF NOT EXISTS jobs (
 document text PRIMARY KEY REFERENCES documents(id), state text NOT NULL DEFAULT 'ready',
 attempts integer NOT NULL DEFAULT 0, lease uuid, expires timestamptz);
CREATE TABLE IF NOT EXISTS audit (
 seq bigserial PRIMARY KEY, document text NOT NULL, event text NOT NULL, role text NOT NULL,
 detail jsonb NOT NULL DEFAULT '{}', created timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS outbox (
 document text PRIMARY KEY REFERENCES documents(id), amount bigint NOT NULL, state text NOT NULL DEFAULT 'pending',
 attempts integer NOT NULL DEFAULT 0, lease uuid, expires timestamptz, next_at timestamptz NOT NULL DEFAULT now(), result jsonb);
CREATE TABLE IF NOT EXISTS mock_payer (
 document text PRIMARY KEY, amount bigint NOT NULL, status text NOT NULL, delayed boolean NOT NULL DEFAULT false);
"""


@contextmanager
def connection():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as c:
        yield c


def initialize() -> None:
    with connection() as c:
        c.execute(SCHEMA)


def audit(c, doc: str, event: str, role: str, detail: dict) -> None:
    c.execute(
        "INSERT INTO audit(document,event,role,detail) VALUES (%s,%s,%s,%s)",
        (doc, event, role, Jsonb(detail)),
    )


def enqueue(meta: dict) -> str:
    doc = f"doc-{meta['index']:04d}"
    with connection() as c:
        row = c.execute(
            "INSERT INTO documents(id,fixture,kind,template,sha) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
            (doc, meta["index"], meta["kind"], meta["template"], meta["sha256"]),
        ).fetchone()
        if row:
            c.execute("INSERT INTO jobs(document) VALUES (%s)", (doc,))
            audit(c, doc, "ingested", "operator", {"sha256": meta["sha256"]})
        else:
            old = c.execute("SELECT sha FROM documents WHERE id=%s", (doc,)).fetchone()
            if old["sha"] != meta["sha256"]:
                raise ValueError("document identity conflicts with immutable source")
    return doc


def claim() -> dict | None:
    token = uuid.uuid4()
    with connection() as c:
        exhausted = c.execute(
            "UPDATE jobs SET state='error',lease=NULL WHERE state='running' AND expires<now() AND attempts>=3 RETURNING document"
        ).fetchall()
        for item in exhausted:
            c.execute("UPDATE documents SET state='error' WHERE id=%s", (item["document"],))
            audit(c, item["document"], "worker_exhausted", "worker", {"code": "attempt_budget"})
        row = c.execute(
            """WITH picked AS (SELECT document FROM jobs WHERE attempts<3 AND
          (state='ready' OR (state='running' AND expires<now())) ORDER BY document FOR UPDATE SKIP LOCKED LIMIT 1)
          UPDATE jobs j SET state='running',attempts=attempts+1,lease=%s,expires=now()+interval '60 seconds'
          FROM picked WHERE j.document=picked.document RETURNING j.*""",
            (token,),
        ).fetchone()
        if row:
            c.execute("UPDATE documents SET state='processing' WHERE id=%s", (row["document"],))
        return row


def finish(doc: str, token, result: dict) -> bool:
    with connection() as c:
        row = c.execute("SELECT * FROM jobs WHERE document=%s FOR UPDATE", (doc,)).fetchone()
        if not row or str(row["lease"]) != str(token) or row["state"] != "running":
            return False
        # Compare on the database clock; an expired worker cannot publish.
        if not c.execute(
            "SELECT expires>now() AS live FROM jobs WHERE document=%s", (doc,)
        ).fetchone()["live"]:
            return False
        state = route(result)
        c.execute(
            "UPDATE documents SET result=%s,state=%s,revision=revision+1 WHERE id=%s",
            (Jsonb(result), state, doc),
        )
        c.execute("UPDATE jobs SET state='done',lease=NULL,expires=NULL WHERE document=%s", (doc,))
        audit(
            c,
            doc,
            "extracted",
            "worker",
            {"state": state, "fields": list(result["fields"]), "method": "ocr"},
        )
        return True


def failed(doc: str, token) -> None:
    with connection() as c:
        row = c.execute(
            "UPDATE jobs SET state=CASE WHEN attempts>=3 THEN 'error' ELSE 'ready' END,lease=NULL,expires=NULL WHERE document=%s AND lease=%s RETURNING state",
            (doc, token),
        ).fetchone()
        if row:
            c.execute(
                "UPDATE documents SET state=%s WHERE id=%s",
                ("error" if row["state"] == "error" else "queued", doc),
            )
            audit(c, doc, "worker_failed", "worker", {"code": "processing_failed"})


def get(doc: str) -> dict:
    with connection() as c:
        row = c.execute("SELECT * FROM documents WHERE id=%s", (doc,)).fetchone()
        if not row:
            raise KeyError(doc)
        if row["result"]:
            row["matches"] = candidates(row["result"]["fields"])
        row["audit"] = c.execute(
            "SELECT seq,event,role,detail,created FROM audit WHERE document=%s ORDER BY seq", (doc,)
        ).fetchall()
        row["payer"] = c.execute(
            "SELECT document,amount,state,attempts,result FROM outbox WHERE document=%s", (doc,)
        ).fetchone()
        return row


def listing() -> list[dict]:
    with connection() as c:
        return c.execute(
            "SELECT id,fixture,kind,template,state,revision FROM documents ORDER BY id LIMIT 120"
        ).fetchall()


def review(doc: str, revision: int, values: dict, attested: bool, note: str) -> dict:
    if set(values) != set(FIELDS) or any(
        not isinstance(v, str) or not 1 <= len(v) <= 100 for v in values.values()
    ):
        raise ValueError("all field values are required")
    if (
        type(revision) is not int
        or type(attested) is not bool
        or not isinstance(note, str)
        or len(note) > 400
    ):
        raise ValueError("invalid review payload")
    with connection() as c:
        row = c.execute("SELECT * FROM documents WHERE id=%s FOR UPDATE", (doc,)).fetchone()
        if not row:
            raise KeyError(doc)
        if row["state"] not in ("review", "auto", "reviewed") or row["revision"] != revision:
            raise RuntimeError("review revision conflict or extraction not ready")
        result = row["result"]
        changed = []
        evidence = {}
        for key, value in values.items():
            old = result["fields"][key]
            ok = old["start"] is not None and supported(
                result["text"], key, value, old["start"], old["end"]
            )
            if not ok and (not attested or len(note.strip()) < 8):
                raise ValueError(
                    "changed or unsupported OCR values require image attestation and a note"
                )
            if value != old["value"]:
                changed.append(key)
            evidence[key] = {
                "value": value,
                "evidence": "ocr-span" if ok else "reviewer-image-attestation",
                "source_sha256": row["sha"],
            }
        stored = {"fields": evidence, "note_sha256": fingerprint(note), "image_attested": attested}
        c.execute(
            "UPDATE documents SET review=%s,state='reviewed',revision=revision+1 WHERE id=%s",
            (Jsonb(stored), doc),
        )
        audit(
            c,
            doc,
            "reviewed",
            "reviewer",
            {
                "fields": changed,
                "revision": revision + 1,
                "value_hashes": {k: fingerprint(v) for k, v in values.items()},
                "image_attested": attested,
            },
        )
    return get(doc)


def request_payer(doc: str) -> None:
    with connection() as c:
        row = c.execute("SELECT * FROM documents WHERE id=%s FOR UPDATE", (doc,)).fetchone()
        if not row or row["kind"] != "referral" or row["state"] not in ("reviewed", "auto"):
            raise ValueError("only approved synthetic referrals can reach the mock payer")
        values = row["review"]["fields"] if row["review"] else row["result"]["fields"]
        raw = values["amount"]["value"]
        import re

        if not re.fullmatch(r"\d{1,8}\.\d{2}", raw):
            raise ValueError("invalid amount")
        cents = int(Decimal(raw) * 100)
        old = c.execute("SELECT amount FROM outbox WHERE document=%s", (doc,)).fetchone()
        if old and old["amount"] != cents:
            raise RuntimeError("immutable payer idempotency conflict")
        c.execute(
            "INSERT INTO outbox(document,amount) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (doc, cents),
        )
        audit(c, doc, "payer_enqueued", "reviewer", {"mock": True})


def payer_claim() -> dict | None:
    with connection() as c:
        c.execute(
            "UPDATE outbox SET state='error',lease=NULL WHERE state='running' AND expires<now() AND attempts>=4"
        )
        return c.execute(
            """WITH p AS (SELECT document FROM outbox WHERE attempts<4 AND next_at<=now() AND
          (state='pending' OR (state='running' AND expires<now())) ORDER BY document FOR UPDATE SKIP LOCKED LIMIT 1)
          UPDATE outbox o SET state='running',attempts=attempts+1,lease=%s,expires=now()+interval '5 seconds'
          FROM p WHERE o.document=p.document RETURNING o.*""",
            (uuid.uuid4(),),
        ).fetchone()


def payer_finish(row: dict, response: dict | None) -> None:
    with connection() as c:
        old = c.execute(
            "SELECT * FROM outbox WHERE document=%s FOR UPDATE", (row["document"],)
        ).fetchone()
        if (
            str(old["lease"]) != str(row["lease"])
            or old["state"] != "running"
            or not c.execute(
                "SELECT expires>now() AS live FROM outbox WHERE document=%s", (row["document"],)
            ).fetchone()["live"]
        ):
            return
        if response is not None:
            if (
                response.get("amount") != old["amount"]
                or response.get("document") != old["document"]
                or response.get("status") not in ("accepted", "denied")
            ):
                raise ValueError("mock reconciliation mismatch")
            c.execute(
                "UPDATE outbox SET state=%s,result=%s,lease=NULL WHERE document=%s",
                (response["status"], Jsonb(response), row["document"]),
            )
            audit(
                c,
                row["document"],
                "payer_reconciled",
                "worker",
                {"mock": True, "status": response["status"]},
            )
        else:
            state = "error" if old["attempts"] >= 4 else "pending"
            c.execute(
                "UPDATE outbox SET state=%s,lease=NULL,next_at=now()+interval '0.1 seconds' WHERE document=%s",
                (state, row["document"]),
            )
            audit(
                c,
                row["document"],
                "payer_retry",
                "worker",
                {"attempt": old["attempts"], "code": "mock_transport_failure"},
            )


def metrics() -> dict:
    with connection() as c:
        return {
            "states": c.execute(
                "SELECT state,count(*) AS count FROM documents GROUP BY state ORDER BY state"
            ).fetchall(),
            "jobs": c.execute(
                "SELECT state,count(*) AS count FROM jobs GROUP BY state ORDER BY state"
            ).fetchall(),
            "payer": c.execute(
                "SELECT state,count(*) AS count FROM outbox GROUP BY state ORDER BY state"
            ).fetchall(),
        }
