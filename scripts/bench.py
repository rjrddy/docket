"""Real OCR evaluation and truth-assisted review simulation; no human-study claim."""

import json
import subprocess
import time
from pathlib import Path

from docket import store
from docket.documents import FIELDS, render
from docket.extract import candidates, claim_supported, ocr, registry, route, score
from docket.privacy import log_record, redact
from docket.worker import image_path, process_one

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/results"


def main() -> None:
    store.initialize()
    rows = []
    started = time.perf_counter()
    for index in range(36):
        meta = render(index, image_path(f"doc-{index:04d}"))
        doc = store.enqueue(meta)
        result = ocr(image_path(doc))
        job = store.claim()
        if job:
            # Publish the actual OCR for the claimed job only, using that immutable source.
            actual = result if job["document"] == doc else ocr(image_path(job["document"]))
            assert store.finish(job["document"], job["lease"], actual)
        correct = {k: result["fields"][k]["value"] == meta["truth"][k] for k in FIELDS}
        rows.append(
            {
                "id": doc,
                "template": meta["template"],
                "quality": meta["quality"],
                "source_sha256": meta["sha256"],
                "truth": meta["truth"],
                "result": result,
                "correct": correct,
                "exact": all(correct.values()),
                "match_top_id": candidates(result["fields"])[0]["id"],
                "match_truth_id": index % 12,
            }
        )
    while process_one():
        pass
    seconds = time.perf_counter() - started
    field_table = []
    for template in sorted({r["template"] for r in rows}):
        group = [r for r in rows if r["template"] == template]
        field_table.append(
            {
                "template": template,
                "documents": len(group),
                "fields": {k: sum(r["correct"][k] for r in group) / len(group) for k in FIELDS},
            }
        )
    curve = []
    for threshold in [0, 0.5, 0.8, 0.9, 0.93, 0.95, 0.99]:
        auto = [r for r in rows if route(r["result"], threshold) == "auto"]
        curve.append(
            {
                "threshold": threshold,
                "auto_count": len(auto),
                "auto_rate": len(auto) / len(rows),
                "auto_error_rate": sum(not r["exact"] for r in auto) / len(auto) if auto else None,
            }
        )
    reviews = []
    # Explicitly truth-assisted, scripted API-equivalent corrections, not independent human decisions.
    for r in [r for r in rows if not r["exact"]][:8]:
        old = store.get(r["id"])
        before = sum(old["result"]["fields"][k]["value"] == r["truth"][k] for k in FIELDS)
        changed = store.review(
            r["id"],
            old["revision"],
            r["truth"],
            True,
            "Scripted truth-assisted fixture correction; not a human study",
        )
        after = sum(changed["review"]["fields"][k]["value"] == r["truth"][k] for k in FIELDS)
        reviews.append(
            {
                "id": r["id"],
                "before_correct_fields": before,
                "after_correct_fields": after,
                "revision": changed["revision"],
            }
        )
    pairs = []
    for left in registry():
        for right in registry():
            noisy = {
                **right,
                "entity": right["entity"].replace("ENTITY", "ENTTY")
                if right["id"] % 3 == 0
                else right["entity"],
            }
            if right["id"] % 5 == 0:
                noisy["domain"] = "changed.example.invalid"
            pairs.append(
                {
                    "left": left,
                    "right": noisy,
                    "match": left["id"] == right["id"],
                    "score": score(left, noisy),
                }
            )
    matching = []
    for threshold in [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]:
        tp = sum(p["match"] and p["score"] >= threshold for p in pairs)
        fp = sum(not p["match"] and p["score"] >= threshold for p in pairs)
        fn = sum(p["match"] and p["score"] < threshold for p in pairs)
        matching.append(
            {
                "threshold": threshold,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn),
            }
        )
    controls = []
    source = "No urgent action is stated. Amount is 10.00."
    for claim, truth in [
        ("No urgent action is stated.", True),
        ("urgent action is stated.", False),
        ("Amount is 100.00.", False),
        ("Amount is 10.00.", True),
        ("", False),
    ]:
        actual = claim_supported(source, claim)
        assert actual == truth
        controls.append({"claim": claim, "expected": truth, "accepted": actual})
    sentinels = "Patient: Synthetic Canary\nMember: DEMO991234\nsynthetic-canary@example.invalid\n555-010-1234\n000-00-0000"
    redacted = redact(sentinels)
    leaks = [
        v
        for v in [
            "Synthetic Canary",
            "DEMO991234",
            "synthetic-canary@example.invalid",
            "555-010-1234",
            "000-00-0000",
        ]
        if v in redacted
    ]
    assert not leaks
    try:
        log_record(event="extracted", text=sentinels)
    except ValueError:
        rejected = True
    else:
        raise AssertionError("raw source accepted by logging gate")
    data = {
        "scope": "synthetic rendered PNGs, actual Tesseract OCR; confidence is uncalibrated; scripted truth-assisted review, NOT independent human review",
        "documents": len(rows),
        "fields_per_document": len(FIELDS),
        "ocr_seconds": seconds,
        "tesseract": subprocess.check_output(["tesseract", "--version"], text=True).splitlines()[0],
        "field_accuracy": {k: sum(r["correct"][k] for r in rows) / len(rows) for k in FIELDS},
        "exact_documents": sum(r["exact"] for r in rows),
        "per_template": field_table,
        "curve": curve,
        "reviews": reviews,
        "review_before_correct_fields": sum(r["before_correct_fields"] for r in reviews),
        "review_after_correct_fields": sum(r["after_correct_fields"] for r in reviews),
        "review_fields": len(reviews) * len(FIELDS),
        "matching_curve": matching,
        "matching_pairs": len(pairs),
        "pipeline_entity_top1": sum(r["match_top_id"] == r["match_truth_id"] for r in rows)
        / len(rows),
        "claim_controls": controls,
        "negative_control_unsupported_rate": sum(not r["accepted"] for r in controls)
        / len(controls),
        "redaction_sentinels": 5,
        "redaction_leaks": len(leaks),
        "raw_log_payload_rejected": rejected,
        "rows": rows,
    }
    (OUT / "evaluation.json").write_text(json.dumps(data, indent=2) + "\n")
    (OUT / "matching-pairs.json").write_text(json.dumps(pairs, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in data.items() if k not in ["rows", "claim_controls", "per_template"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
