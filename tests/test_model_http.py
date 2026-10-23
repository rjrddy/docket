"""Optional long model integration; no network or fixture truth goes into inference."""

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.environ.get("DOCKET_MODEL_TEST") != "1",
    reason="optional local model weights/runtime; exercised separately and recorded",
)
def test_actual_model_http_source_gate(tmp_path):
    logfile = tmp_path / "model-server.log"
    with logfile.open("w") as log:
        process = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "docket.server"],
            cwd=ROOT,
            env={**os.environ, "DOCKET_LLM": "1", "PORT": "18104"},
            stdout=log,
            stderr=log,
        )
        try:

            def request(path, body=None):
                req = urllib.request.Request(
                    "http://127.0.0.1:18104" + path,
                    data=json.dumps(body).encode() if body else None,
                    headers={
                        "Authorization": "Bearer local-review",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=90) as response:
                    return json.load(response)

            for _ in range(200):
                try:
                    row = request("/api/document?id=doc-0001")
                    if row["result"]:
                        break
                except OSError:
                    pass
                time.sleep(0.05)
            result = request("/api/model", {"id": "doc-0001"})
            assert result["source_sha256"] == row["sha"]
            assert result["automatic_approval"] is False
            assert "raw" in result and "fields" in result
            from docket.extract import supported

            for field, proposal in result["fields"].items():
                if proposal["supported"]:
                    assert supported(
                        row["result"]["text"],
                        field,
                        proposal["value"],
                        proposal["start"],
                        proposal["end"],
                    )
            persisted = request("/api/document?id=doc-0001")
            assert persisted["llm"]["raw"] == result["raw"]
            assert any(a["event"] == "model_proposed" for a in persisted["audit"])
            summary = {
                "schema_valid": result["schema_valid"],
                "source_sha256": result["source_sha256"],
                "automatic_approval": False,
                "fields": result["fields"],
                "seconds": result["seconds"],
            }
            (ROOT / "docs/results/model-http.json").write_text(json.dumps(summary, indent=2) + "\n")
        finally:
            process.terminate()
            process.wait(timeout=30)
