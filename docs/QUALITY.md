# Docket quality and acceptance report

**Status: partial.** The implemented OCR/source/review/payer/model stack is measured, but independent human review accuracy/time benefit is not measured. The corrected-field improvement is a truth-assisted script, not a blinded human study. General real-document capability is not established by the synthetic templates. No deployment occurred.

| Engineering gate | Evidence | Status |
|---|---|---|
| Hard core written and explained | TSV/source checks, leased queue, revision transaction, mock outbox; DESIGN/ADRs | PASS |
| One-command fresh clone | Actual make demo verification recorded under results/fresh-clone | PASS locally |
| Live source/review UI | Actual HTTP/DB browser receipts, original source boxes and recorded operations | PASS locally |
| Unit/integration/property/failure tests | Seeded citation mutations, Postgres lock/lease conflict, source corruption, mock timeout, process restart | PASS locally |
| Actual OCR benchmark | evaluation.json / RESULTS.md / raw stdout | PASS |
| Actual optional model study | model-evaluation.json, raw failures, pinned model provenance and model-http.json | PASS locally; quality limited |
| Demonstrated caught failure | lease-clock-before-fix.log, caught-evidence-row-exposure.log, caught-ci-ocr-readiness.log, caught-http-parser-canary.log, model schema/envelope rejection and privacy/source controls | PASS |
| ADRs / interview kit | docs/adr, INTERVIEW.md, DRILL.md | PASS |
| Dependency scans | Core/browser and optional model scans retained | PASS locally |
| CI including actual container/browser | [Actual Linux run](https://github.com/rjrddy/docket/actions/runs/40028135309); final exact head tracked by coordinator in DOCKET_CI_VERIFICATION.json | PASS on implementation run; final head checked separately |
| No unmeasured claims | Generated README; zero default automation, model errors and review limitation explicit | PASS within stated measurement scope |

Routine CI skips the heavyweight optional model/HTTP test requiring local weights; its actual run is retained separately. Ordinary schema/source tests always run. OCR results can vary by Tesseract/platform version, which is recorded; a CI artifact is not silently presented as the original laptop campaign.

No production calibration, clinical/financial semantics, arbitrary uploads/PDFs, individual identities, encrypted blob storage, general PHI certification, real payer contract or hosted availability is claimed. Viewer permissions and finite canary tests are real but limited. Existing repositories are preserved and no integration/deletion was performed.
