"""Measured README and per-field tables generated solely from retained run JSON."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
r = json.loads((root / "docs/results/evaluation.json").read_text())
mfile = root / "docs/results/model-evaluation.json"
m = json.loads(mfile.read_text()) if mfile.exists() else None
current = next(c for c in r["curve"] if c["threshold"] == 0.93)
text = f"""# Docket

Docket extracts synthetic document fields, checks their source evidence, and persists reviewer corrections without erasing the original OCR.

## Result

Actual Tesseract on **{r["documents"]} synthetic pages / {r["fields_per_document"]} fields each**: {r["exact_documents"]}/{r["documents"]} pages fully correct; date {100 * r["field_accuracy"]["date"]:.2f}%, amount {100 * r["field_accuracy"]["amount"]:.2f}%. [Every field/template](docs/results/RESULTS.md).  
Scripted truth-assisted review: **{r["review_before_correct_fields"]}/{r["review_fields"]} → {r["review_after_correct_fields"]}/{r["review_fields"]} correct fields** across {len(r["reviews"])} persisted reviews; independent human accuracy/time savings **not measured**.  
Local Qwen study: **{m["schema_valid_documents"] if m else "not measured"}/{m["documents"] if m else "not measured"} schema-valid outputs; {m["correct_fields"] if m else "not measured"}/{m["total_fields"] if m else "not measured"} correct fields**, {m["unsupported_fields"] if m else "not measured"}/{m["proposed_nonempty_fields"] if m else "not measured"} nonempty proposals unsupported by the source gate; advisory only. [Actual output](docs/results/model-evaluation.json).

## Architecture

```mermaid
flowchart LR
  Images[Synthetic invoices / statements / referrals] --> Queue[Postgres leased work queue]
  Queue --> OCR[Tesseract TSV / labeled field spans]
  OCR --> Gate[Unique source + confidence routing]
  Gate --> Review[React source-image review desk]
  OCR --> LLM[Optional local Qwen proposals]
  LLM --> Check[Schema and source validation]
  Review --> Audit[Revision check / original OCR + audit]
  Review --> Match[Entity candidate scores]
  Audit --> Outbox[Postgres outbox]
  Outbox --> Payer[Explicit HTTP mock payer]
  Payer --> Reconcile[Timeout retry / idempotency / reconciliation]
```

## Run it

Python with venv, Node/npm, Tesseract and PostgreSQL server tools are prerequisites. No real records or paid API/account is needed.

```sh
make demo
# Open http://127.0.0.1:8096 · local-review / local-view · Ctrl-C stops owned services.
make lint test bench
```

[Demo, optional model and recording steps](docs/DEMO.md). The local demo preserves its own ignored Postgres data directory; test/bench clusters are temporary. Compose uses a database volume. **Not deployed.**

## Decisions and limits

- Synthetic PNG ingestion only. Six generator templates with rendered degradation, not real-world document validation. Each field needs a unique labeled OCR span. OCR citations can support an OCR error; image-attested human corrections have a separate evidence class. [Design](docs/DESIGN.md), [ADRs](docs/adr/).
- At the fixed default threshold 0.93, **{current["auto_count"]}/{r["documents"]}** evaluated pages auto-route. This conservative default remains unchanged; no calibrated safe-automation claim is made. The full automation/error curve retains lower-threshold fixture results and null rates when nothing is approved.
- Optional LLM generation is real, local and hash-pinned. Its extraction quality is limited; invalid schemas and unsupported fields are rejected, not replaced with fabricated output. The smaller model's complete schema failure and Qwen's envelope-format failure are retained. The model never approves cases or replaces reviewer decisions.
- The reviewer benchmark is truth-assisted script execution, not proof that humans save time or reduce errors. A genuine blinded human review study remains unfinished: **project status partial for that acceptance claim**.
- Postgres leases use a database clock after row-lock acquisition. A real test caught stale publication with transaction-start time; the fix and original failure are retained in [lease-clock-before-fix.log](docs/results/lease-clock-before-fix.log). Concurrent reviewer revisions conflict rather than silently overwrite.
- Payer and eligibility rules are explicitly mock. An actual HTTP timeout after payer commit exercises durable retries and reconciliation; no clinical, financial or company-use claim follows. Raw source/identifiers are excluded from operational logs; finite redaction canary tests are not a universal PHI guarantee.
- Viewer access gets redacted OCR, no images or writes. Local trust-auth Postgres is for synthetic loopback use only. Deployment needs private env credentials and TLS; configuration is prepared only. [Quality report](docs/QUALITY.md).

## Next

Blinded human review accuracy/time study; held-out templates and real-world-safe calibration; more capable model comparisons; PDF/multipage ingestion; reviewed entity linking; real payer contract work only with approved synthetic sandboxes; encrypted storage, individual identities, migration/versioning and hardened deployment. [Interview kit](INTERVIEW.md), [follow-up drill](DRILL.md), [salvage provenance](docs/migration/docket.md).
"""
(root / "README.md").write_text(text)
lines = [
    "# Docket actual measurements",
    "",
    r["scope"],
    "",
    f"{r['tesseract']}; OCR campaign {r['ocr_seconds']:.3f} seconds including rendering/database work; not service throughput.",
    "",
    "| Template | n | " + " | ".join(r["field_accuracy"]) + " |",
    "|---|---:|" + "---:|" * len(r["field_accuracy"]),
]
for row in r["per_template"]:
    lines.append(
        f"| {row['template']} | {row['documents']} | "
        + " | ".join(f"{100 * row['fields'][k]:.2f}%" for k in r["field_accuracy"])
        + " |"
    )
lines += [
    "",
    "## Automation/error curve",
    "",
    "| Threshold | Auto count | Auto rate | Auto error rate |",
    "|---|---:|---:|---:|",
]
for c in r["curve"]:
    rate = (
        f"{100 * c['auto_error_rate']:.2f}%"
        if c["auto_error_rate"] is not None
        else "not measured: no auto cases"
    )
    lines.append(f"| {c['threshold']} | {c['auto_count']} | {100 * c['auto_rate']:.2f}% | {rate} |")
lines += [
    "",
    "## Review scope",
    "",
    f"{r['review_before_correct_fields']}/{r['review_fields']} → {r['review_after_correct_fields']}/{r['review_fields']} correct fields via truth-assisted scripted corrections on {len(r['reviews'])} selected erroneous cases. This proves the persisted correction path, not an independent human effect. Human accuracy/time benefit: not measured.",
    "",
    "## Entity matching",
    "",
    f"{r['matching_pairs']} synthetic pairs; pipeline top-one {100 * r['pipeline_entity_top1']:.2f}% before review. Scores are similarities, not probabilities.",
    "",
    "| Threshold | Precision | Recall | TP / FP / FN |",
    "|---|---:|---:|---|",
]
for c in r["matching_curve"]:
    precision = f"{100 * c['precision']:.2f}%" if c["precision"] is not None else "not measured"
    lines.append(
        f"| {c['threshold']} | {precision} | {100 * c['recall']:.2f}% | {c['tp']} / {c['fp']} / {c['fn']} |"
    )
lines += [
    "",
    "## Negative controls",
    "",
    f"Raw-content logging rejected; {r['redaction_leaks']} leaks across {r['redaction_sentinels']} fixed redaction sentinels. Number/negation/empty claim controls are retained. These finite controls are not a clinical entailment evaluation or general privacy certification.",
    "",
    "[All OCR, independent fixture truth, source spans and review rows](evaluation.json). [Model raw generation and schema/source outcomes](model-evaluation.json). [Earlier smaller-model rejection](rejected-smollm-evaluation.json). Confidence is uncalibrated. In-sample empirical zero errors on a small accepted subset does not establish a production error bound.",
]
(root / "docs/results/RESULTS.md").write_text("\n".join(lines) + "\n")
print("Generated README.md and RESULTS.md from retained OCR/model run JSON")
