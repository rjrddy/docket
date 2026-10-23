"""Synthetic-only ingestion, reviewer roles, evidence UI, and persisted mock HTTP payer."""

import hashlib
import hmac
import json
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from psycopg.types.json import Jsonb

from . import store
from .documents import render
from .extract import claim_supported
from .privacy import log_record, redact
from .worker import image_path, loop

ROOT = Path(__file__).resolve().parents[2]


def seed(count: int = 12) -> list[str]:
    ids = []
    for n in range(count):
        path = image_path(f"doc-{n:04d}")
        if not path.exists():
            meta = render(n, path)
        else:
            from .documents import fixture

            meta = {**fixture(n), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        ids.append(store.enqueue(meta))
    return ids


def handler(tokens: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            print(
                log_record(event="http", status=str(args[1]) if len(args) > 1 else "unknown"),
                flush=True,
            )

        def send(self, code: int, data, kind: str = "application/json") -> None:
            payload = (
                data
                if isinstance(data, bytes)
                else json.dumps(data, default=str, allow_nan=False).encode()
            )
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def role(self) -> str:
            auth = self.headers.get("Authorization", "").encode()
            for name, token in tokens.items():
                if hmac.compare_digest(auth, ("Bearer " + token).encode()):
                    return name
            return ""

        def body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if (
                not 0 < length <= 16384
                or self.headers.get("Content-Type", "").split(";")[0] != "application/json"
            ):
                raise ValueError("bounded application/json body required")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
            return data

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            args = parse_qs(urlparse(self.path).query)
            if path == "/health":
                self.send(200, {"status": "ready"})
                return
            if path.startswith(("/api/", "/mock/")):
                role = self.role()
                if not role:
                    self.send(401, {"error": "bearer required"})
                    return
                try:
                    if path == "/api/documents":
                        data = {
                            "documents": store.listing(),
                            "metrics": store.metrics(),
                            "role": role,
                            "llm_enabled": os.getenv("DOCKET_LLM") == "1",
                        }
                    elif path == "/api/evidence":
                        file = ROOT / "docs/results/evaluation.json"
                        data = (
                            json.loads(file.read_text())
                            if file.exists()
                            else {"status": "not measured"}
                        )
                        # Dashboard access never grants raw fixture/source/model-output access.
                        data.pop("rows", None)
                        model_file = ROOT / "docs/results/model-evaluation.json"
                        if model_file.exists():
                            model = json.loads(model_file.read_text())
                            data["model"] = {
                                key: value for key, value in model.items() if key != "rows"
                            }
                    elif path == "/api/document":
                        data = store.get(args.get("id", [""])[0])
                        if role == "viewer" and data["result"]:
                            data["result"] = {
                                "text": redact(data["result"]["text"]),
                                "fields": {},
                                "redacted": True,
                            }
                            data["review"] = None
                            data["llm"] = None
                            data["matches"] = []
                    elif path == "/api/image":
                        if role != "reviewer":
                            self.send(403, {"error": "reviewer image access required"})
                            return
                        doc = args.get("id", [""])[0]
                        metadata = store.get(doc)
                        payload = image_path(doc).read_bytes()
                        if hashlib.sha256(payload).hexdigest() != metadata["sha"]:
                            self.send(409, {"error": "immutable source checksum mismatch"})
                            return
                        self.send(200, payload, "image/png")
                        return
                    elif path == "/mock/payer":
                        if role != "reviewer":
                            self.send(403, {"error": "reviewer required"})
                            return
                        doc = args.get("document", [""])[0]
                        with store.connection() as c:
                            row = c.execute(
                                "SELECT * FROM mock_payer WHERE document=%s", (doc,)
                            ).fetchone()
                            if not row:
                                raise KeyError(doc)
                            status = "denied" if int(doc[4:]) % 7 == 0 else "accepted"
                            c.execute(
                                "UPDATE mock_payer SET status=%s WHERE document=%s", (status, doc)
                            )
                        data = {
                            "document": doc,
                            "amount": row["amount"],
                            "status": status,
                            "mock": True,
                        }
                    else:
                        self.send(404, {"error": "not found"})
                        return
                    self.send(200, data)
                except (KeyError, FileNotFoundError):
                    self.send(404, {"error": "document not found"})
                except ValueError:
                    self.send(400, {"error": "invalid query"})
                return
            web = ROOT / "apps/web/dist"
            file = (web / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
            if not file.is_relative_to(web.resolve()) or not file.is_file():
                self.send(404, {"error": "not found"})
                return
            kind = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript",
                ".css": "text/css",
            }.get(file.suffix, "application/octet-stream")
            self.send(200, file.read_bytes(), kind)

        def do_POST(self) -> None:
            self.connection.settimeout(10)
            role = self.role()
            if not role:
                self.send(401, {"error": "bearer required"})
                return
            if role != "reviewer":
                self.send(403, {"error": "reviewer required"})
                return
            try:
                body = self.body()
                if self.path == "/api/ingest":
                    n = body.get("fixture")
                    if type(n) is not int or not 0 <= n < 120:
                        raise ValueError("synthetic fixture index must be 0..119")
                    path = image_path(f"doc-{n:04d}")
                    if path.exists():
                        from .documents import fixture

                        meta = {
                            **fixture(n),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    else:
                        meta = render(n, path)
                    data = {"id": store.enqueue(meta)}
                elif self.path == "/api/review":
                    data = store.review(
                        body["id"],
                        body["revision"],
                        body["values"],
                        body.get("attested", False),
                        body.get("note", ""),
                    )
                elif self.path == "/api/payer":
                    store.request_payer(body["id"])
                    data = {"state": "enqueued", "mock": True}
                elif self.path == "/api/model":
                    if os.getenv("DOCKET_LLM") != "1":
                        self.send(
                            503,
                            {
                                "error": "optional local model disabled; run make model and enable DOCKET_LLM=1"
                            },
                        )
                        return
                    from .llm import propose

                    doc = store.get(body["id"])
                    data = propose(doc["result"]["text"])
                    data["source_sha256"] = doc["sha"]
                    with store.connection() as c:
                        c.execute(
                            "UPDATE documents SET llm=%s WHERE id=%s", (Jsonb(data), doc["id"])
                        )
                        store.audit(
                            c,
                            doc["id"],
                            "model_proposed",
                            "reviewer",
                            {"schema_valid": data["schema_valid"], "auto_approved": False},
                        )
                elif self.path == "/api/check-claim":
                    doc = store.get(body["id"])
                    claim = body["claim"]
                    if not isinstance(claim, str) or not 1 <= len(claim) <= 500:
                        raise ValueError("bounded claim required")
                    data = {
                        "supported": claim_supported(doc["result"]["text"], claim),
                        "scope": "exact whole OCR sentence; not semantic or clinical entailment",
                    }
                elif self.path == "/mock/payer":
                    doc, amount = body.get("document"), body.get("amount")
                    if (
                        not isinstance(doc, str)
                        or not re.fullmatch(r"doc-\d{4}", doc)
                        or type(amount) is not int
                        or not 0 <= amount <= 9999999999
                    ):
                        raise ValueError("invalid mock claim")
                    delayed = False
                    with store.connection() as c:
                        old = c.execute(
                            "SELECT * FROM mock_payer WHERE document=%s FOR UPDATE", (doc,)
                        ).fetchone()
                        if old and old["amount"] != amount:
                            raise RuntimeError("mock payer idempotency conflict")
                        if not old:
                            delayed = int(doc[4:]) % 2 == 0
                            c.execute(
                                "INSERT INTO mock_payer(document,amount,status,delayed) VALUES (%s,%s,'submitted',%s)",
                                (doc, amount, delayed),
                            )
                    # Genuine ambiguous timeout: the DB commit precedes a slow HTTP response.
                    if delayed:
                        time.sleep(0.2)
                    data = {"document": doc, "amount": amount, "status": "submitted", "mock": True}
                else:
                    self.send(404, {"error": "not found"})
                    return
                self.send(200, data)
            except RuntimeError:
                self.send(409, {"error": "revision or idempotency conflict"})
            except (KeyError, ValueError, TypeError, OverflowError):
                # Never echo raw payloads, exceptions, member IDs or credentials into responses/logs.
                self.send(400, {"error": "invalid request or missing source attestation"})

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(*args)

    def handle_error(self, request, address):
        print(log_record(event="http", error="request_failed"), flush=True)

    def process_request(self, request, address):
        request.settimeout(10)
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def main() -> None:
    host = os.getenv("DOCKET_HOST", "127.0.0.1")
    tokens = {
        "reviewer": os.getenv("DOCKET_REVIEW_TOKEN", "local-review"),
        "viewer": os.getenv("DOCKET_VIEW_TOKEN", "local-view"),
    }
    if (
        len(set(tokens.values())) != 2
        or host not in ("127.0.0.1", "localhost", "::1")
        and any(len(t) < 24 or t.startswith("local-") for t in tokens.values())
    ):
        raise SystemExit("external binding requires distinct private tokens and TLS proxy")
    store.initialize()
    seed()
    http = Server((host, int(os.getenv("PORT", "8096"))), handler(tokens))
    stopped = threading.Event()
    base = f"http://127.0.0.1:{http.server_port}"
    workers = [
        threading.Thread(target=loop, args=(stopped, base, tokens["reviewer"]), daemon=True)
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()

    def stop(_signum, _frame):
        stopped.set()
        threading.Thread(target=http.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(log_record(event="ready", status=f"http://{host}:{http.server_port}"), flush=True)
    try:
        http.serve_forever()
    finally:
        stopped.set()
        http.server_close()
        for worker in workers:
            worker.join(timeout=17)


if __name__ == "__main__":
    main()
