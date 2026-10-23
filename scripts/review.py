"""Browser proof of source boxes, durable review, conflicts, payer and viewer redaction."""

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from docket.documents import fixture

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/results/browser"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    receipts, errors = [], []
    with (OUT / "server.log").open("w") as log:
        child = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "docket.server"],
            cwd=ROOT,
            env={**os.environ, "PORT": "18103"},
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(200):
                if child.poll() is not None:
                    raise RuntimeError((OUT / "server.log").read_text())
                try:
                    urllib.request.urlopen("http://127.0.0.1:18103/health", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=p.chromium.executable_path)
                context = browser.new_context(
                    viewport={"width": 1600, "height": 1100},
                    **(
                        {
                            "record_video_dir": str(OUT / "recording"),
                            "record_video_size": {"width": 1600, "height": 1100},
                        }
                        if args.record
                        else {}
                    ),
                )
                page = context.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto("http://127.0.0.1:18103")
                expect(page.get_by_label("Document ID", exact=True)).to_be_visible(timeout=30000)
                expect(page.get_by_alt_text("Synthetic source doc-0001")).to_be_visible()
                started = time.monotonic()
                page.get_by_label("Amount", exact=True).focus()
                expect(page.get_by_role("img", name="OCR source boxes for Amount")).to_be_visible()
                assert page.locator(".page-sheet rect").count() > 0
                page.screenshot(path=str(OUT / "desktop.png"), full_page=True)
                page.get_by_role("button", name="OCR text", exact=True).click()
                expect(page.locator(".ocr-text")).to_contain_text("SYNTHETIC")
                page.get_by_role("button", name="Show image").click()
                page.locator("summary").filter(has_text="Check a statement").click()
                page.get_by_role("button", name="Check source").click()
                expect(
                    page.get_by_text("Unsupported — no exact whole-sentence source.")
                ).to_be_visible()
                receipts.append({"kind": "unsupported-negation-rejected"})

                def correct(index: int):
                    doc = f"doc-{index:04d}"
                    page.get_by_role("button", name=f"Open {doc}", exact=True).click()
                    expect(page.get_by_alt_text(f"Synthetic source {doc}")).to_be_visible()
                    expect(page.get_by_label("Document ID", exact=True)).to_be_visible()
                    labels = {
                        "document_id": "Document ID",
                        "date": "Date",
                        "amount": "Amount",
                        "entity": "Entity",
                        "reference": "Member / account",
                        "zone": "Zone",
                        "domain": "Directory domain",
                    }
                    for field, value in fixture(index)["truth"].items():
                        page.get_by_label(labels[field], exact=True).fill(value)
                    page.get_by_label("I checked corrected or missing values").check()
                    page.get_by_label("Review note", exact=False).fill(
                        "Scripted truth-assisted synthetic image correction; not a human study"
                    )
                    # Exercise a real polling interval: the draft and pinned revision must survive it.
                    page.wait_for_timeout(1800)
                    expect(page.get_by_label("Document ID", exact=True)).to_have_value(
                        fixture(index)["truth"]["document_id"]
                    )
                    expect(page.get_by_label("Review note", exact=False)).to_have_value(
                        "Scripted truth-assisted synthetic image correction; not a human study"
                    )
                    with page.expect_response(lambda r: r.url.endswith("/api/review")) as response:
                        page.get_by_role("button", name="Record review decision").click()
                    data = response.value.json()
                    assert response.value.ok, data
                    expect(page.get_by_role("status")).to_contain_text("Decision recorded")
                    assert data["state"] == "reviewed"
                    receipts.append(
                        {
                            "kind": "scripted-truth-assisted-review",
                            "id": doc,
                            "revision": data["revision"],
                            "image_attested": data["review"]["image_attested"],
                        }
                    )
                    return data

                reviewed = correct(2)
                # Real stale revision conflict against the same HTTP service.
                request = urllib.request.Request(
                    "http://127.0.0.1:18103/api/review",
                    data=json.dumps(
                        {
                            "id": reviewed["id"],
                            "revision": reviewed["revision"] - 1,
                            "values": fixture(2)["truth"],
                            "attested": True,
                            "note": "stale scripted reviewer",
                        }
                    ).encode(),
                    headers={
                        "Authorization": "Bearer local-review",
                        "Content-Type": "application/json",
                    },
                )
                try:
                    urllib.request.urlopen(request, timeout=5)
                    raise AssertionError("stale revision accepted")
                except urllib.error.HTTPError as e:
                    assert e.code == 409
                receipts.append({"kind": "stale-review-rejected", "status": 409})
                page.get_by_role("button", name="Send to mock payer").click()
                expect(page.locator(".payer-state")).to_contain_text("accepted", timeout=20000)
                expect(page.locator(".audit-events")).to_contain_text("payer retry")
                receipts.append({"kind": "mock-payer-ambiguous-timeout-reconciled"})
                if os.getenv("DOCKET_LLM") == "1":
                    with page.expect_response(
                        lambda r: r.url.endswith("/api/model"), timeout=90000
                    ) as response:
                        page.get_by_role("button", name="Run local model").click()
                    proposal = response.value.json()
                    assert response.value.ok and proposal["automatic_approval"] is False
                    if proposal["schema_valid"]:
                        expect(page.locator(".model-proposals li")).to_have_count(7)
                    receipts.append(
                        {
                            "kind": "actual-local-model-proposals",
                            "schema_valid": proposal["schema_valid"],
                            "automatic_approval": False,
                        }
                    )
                page.get_by_role("button", name="Evaluation book").click()
                expect(
                    page.get_by_text("Human benefit remains unmeasured.", exact=False)
                ).to_be_visible()
                expect(page.get_by_text("Every template gets its own line.")).to_be_visible()
                page.screenshot(path=str(OUT / "evaluation.png"), full_page=True)
                page.get_by_role("button", name="Review desk", exact=False).click()
                page.locator("summary").filter(has_text="Access settings").click()
                page.get_by_label("Bearer token").fill("local-view")
                expect(
                    page.get_by_text("Viewer mode shows redacted OCR only.", exact=False)
                ).to_be_visible()
                page.get_by_role("button", name="OCR text", exact=True).click()
                expect(page.locator(".ocr-text")).to_contain_text("[REDACTED]")
                assert page.get_by_role("button", name="Record review decision").count() == 0
                receipts.append({"kind": "viewer-redacted-no-write"})
                page.get_by_label("Bearer token").fill("wrong-token")
                expect(page.get_by_role("alert")).to_contain_text("bearer required")
                page.get_by_label("Bearer token").fill("local-review")
                expect(page.get_by_label("Document ID", exact=True)).to_be_visible()
                if page.get_by_role("button", name="Show image").count():
                    page.get_by_role("button", name="Show image").click()
                for width in [390, 768, 1024, 1600]:
                    page.set_viewport_size({"width": width, "height": 1100})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        width
                    )
                    expect(
                        page.get_by_role("button", name="Record review decision")
                    ).to_be_visible()
                    if width == 390:
                        page.screenshot(path=str(OUT / "mobile.png"), full_page=True)
                    receipts.append({"kind": "responsive", "width": width, "no_overflow": True})
                index = 3
                while args.record and time.monotonic() - started < 92:
                    correct(index % 12)
                    index += 1
                    page.get_by_role("button", name="OCR text", exact=True).click()
                    expect(page.locator(".ocr-text")).to_be_visible()
                    page.wait_for_timeout(700)
                    page.get_by_role("button", name="Show image").click()
                page.get_by_role("button", name="Record review decision").focus()
                expect(page.get_by_role("button", name="Record review decision")).to_be_focused()
                assert not errors, errors
                elapsed = time.monotonic() - started
                video = page.video
                context.close()
                if video:
                    video.save_as(str(OUT / "docket-demo.webm"))
                    video.delete()
                browser.close()
                (OUT / "review.json").write_text(
                    json.dumps(
                        {
                            "elapsed_seconds": elapsed,
                            "page_errors": errors,
                            "receipts": receipts,
                            "review_scope": "scripted truth-assisted form operations, not independent human benefit",
                        },
                        indent=2,
                    )
                    + "\n"
                )
                print(
                    json.dumps(
                        {
                            "elapsed_seconds": elapsed,
                            "receipts": len(receipts),
                            "page_errors": errors,
                        }
                    )
                )
        finally:
            child.terminate()
            child.wait(timeout=30)


if __name__ == "__main__":
    main()
