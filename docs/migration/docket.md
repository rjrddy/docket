# Docket salvage provenance

| Older repository by name | Used or declined | New implementation |
|---|---|---|
| Document extraction with field-level eval | Adapted render → real OCR → independent field/template/threshold evaluation pattern | Bundled licensed font, six degraded template families, word offsets/boxes and per-field minimum confidence; all measurements rerun |
| Finance Q&A with citation checker | Adapted conservative context/value checking idea; declined public SEC facts and TF-IDF retrieval | Synthetic-only labeled-span checks; no semantic entailment claim, no SEC data imported; Atlas documented its separate decision |
| Human-review loop | Adapted redaction patterns, confidence routing and audit behavior | Real Postgres leases/revisions, authenticated reviewer flow, source-image attestation, value-free audit; removed simulated correctness as an accuracy proof |
| Referral/fax document extractor | Adapted watermarked synthetic referral/degradation and value-free failure sentinels | Shared real Tesseract TSV path, persisted source/reviewer evidence; no patient records, specialty triage or clinical routing |
| Clinical summary with source checking | Adapted exact-source sentence checking and number/negation controls | Optional actual local extraction proposals plus strict schema/label/offset gates; exact matching remains conservative, not clinical factuality |
| Eligibility and claims mock pipeline | Adapted ambiguous post-commit timeout, idempotency and reconciliation scenario | Real HTTP mock over durable Postgres state/outbox with leases and retries; no real payer integration |
| Entity matching quality harness | Adapted normalized name/zone/domain weighted similarity and P/R sweeps | New synthetic registry/pairs and integrated OCR candidate evaluation; rerun all outcomes |

No old metric was reused as a Docket result. Old repository files and remotes remain untouched. Local Postgres lifecycle tooling follows the existing standalone pattern but is owned here, with persistent demo data and isolated gate clusters. React, source overlays, revision-pinned drafts, optional Qwen adapter, queue/payer persistence, failure regressions and CI/container proof are new work. Public pretrained weights are model inputs with recorded revision/hash/license, not employer code or a project dependency on another checkout. The earlier SmolLM trial reused a verified public weight cache, not Lean/Pulse code or results.
