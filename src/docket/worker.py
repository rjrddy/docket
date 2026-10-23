"""Durable OCR jobs and mock payer outbox; no raw source/body in operational logs."""

import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

from . import store
from .extract import ocr
from .privacy import log_record

ROOT = Path(__file__).resolve().parents[2]


def image_path(doc: str) -> Path:
    if not doc.startswith("doc-") or len(doc) != 8 or not doc[4:].isdigit():
        raise ValueError("invalid document identifier")
    return ROOT / ".cache/documents" / f"{doc}.png"


def process_one() -> bool:
    row = store.claim()
    if row is None:
        return False
    doc = row["document"]
    try:
        path = image_path(doc)
        metadata = store.get(doc)
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha"]:
            raise ValueError("immutable image mismatch")
        result = ocr(path)
        published = store.finish(doc, row["lease"], result)
        print(
            log_record(
                event="extraction", document=doc, status="published" if published else "fenced"
            ),
            flush=True,
        )
    except Exception:
        store.failed(doc, row["lease"])
        print(log_record(event="extraction", document=doc, error="processing_failed"), flush=True)
    return True


def payer_one(base: str, token: str) -> bool:
    row = store.payer_claim()
    if row is None:
        return False
    try:
        payload = {"document": row["document"], "amount": row["amount"]}
        req = urllib.request.Request(
            base + "/mock/payer",
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=0.08) as response:
            json.load(response)
        req = urllib.request.Request(
            base + "/mock/payer?document=" + row["document"],
            headers={"Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(req, timeout=0.3) as response:
            result = json.load(response)
        store.payer_finish(row, result)
    except (OSError, ValueError, urllib.error.HTTPError):
        store.payer_finish(row, None)
    return True


def loop(stopped: threading.Event, base: str, token: str) -> None:
    while not stopped.is_set():
        try:
            worked = process_one()
            paid = payer_one(base, token)
            if not worked and not paid:
                stopped.wait(0.15)
        except Exception:
            print(log_record(event="worker", error="dependency_failure"), flush=True)
            stopped.wait(0.5)


def main() -> None:
    store.initialize()
    stop = threading.Event()
    try:
        loop(
            stop,
            os.getenv("DOCKET_URL", "http://127.0.0.1:8096"),
            os.getenv("DOCKET_REVIEW_TOKEN", "local-review"),
        )
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
