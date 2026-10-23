# Docket interview kit

## Two-minute pitch

Docket is a synthetic document reading room whose difficult part is making accuracy claims that survive inspection. Real Tesseract OCR yields word boxes, offsets and per-field confidence. Conservative labeled-span checks separate source support from correctness. A Postgres work queue persists extraction jobs, reviewer revisions and audit events. Reviewers can correct OCR using a separately labeled image attestation; an optional local model can propose values but cannot approve them.

The strongest story is a failure we actually caught: transaction-start time allowed a worker that waited on a row lock to publish after lease expiry. The regression holds the lock across expiry; the fix checks current database time after acquiring it. Other controls catch negation/number changes, image corruption, stale reviewer revisions and a mock payer timeout after commit.

The measurement is intentionally limited. The full field/template/automation table comes from rendered synthetic pages and actual OCR. Truth-assisted scripted corrections prove the durable path, not human accuracy or time saved. The small local model is weak and its unsupported suggestions are retained/rejected. I would describe the human-benefit acceptance claim as partial, rather than present simulated review as a study.

## Ten-minute architecture walkthrough

Start at `documents.py`: separate generator truth, immutable rendered pixels, six template families and degradation. Follow `extract.py` through TSV words/offsets/boxes, unique label matches, minimum word confidence and conservative sentence support. Explain why an OCR-supported field may still be false in the image.

Walk through `store.claim/finish`: locked CTE, leases, random tokens, database clock, attempt budget and atomic publication/audit. Show the retained pre-fix lock-wait failure. Then follow the reviewer transaction: expected revision, original result retained, image attestation for corrections, hashes in audit and effective reviewed values.

Open the React desk: click a field and its boxes, inspect OCR, fill a correction and observe draft pinning through polling. Use viewer mode and explain the deliberate image/write restrictions. Open the evaluation book and distinguish live cases from recorded fixture results, default route threshold from lower-threshold curves, and scripted correction from a human study.

Follow the optional `llm.py`: pinned local weights, actual generation, JSON-envelope adapter, strict fields/types/duplicates and per-field source gate. Show failed raw outputs and the separate model accuracy/unsupported counts. No hidden heuristic stands in for inference.

Finish at the payer outbox: immutable document/amount key, leased worker, actual HTTP call, commit-before-timeout injection, idempotent retry and final reconciliation. This is synthetic contract behavior, not real eligibility. Show unit/property/HTTP/model tests, actual container recovery, raw outputs, fresh-clone command and remaining gaps.

## Five tradeoffs

- Strict labeled source spans are explainable and conservative but miss paraphrases and general document layouts.
- Minimum word confidence avoids averaging away a weak token but is uncalibrated and routes the measured default corpus entirely to review.
- Image-attested correction enables recovery when OCR is missing, but it is human judgment rather than machine-verifiable OCR support.
- Postgres queue/outbox reuse a known transaction engine, but add database-clock, lease, requeue and operational complexity.
- A small optional local model avoids paid services and keeps source local, but its extraction quality is limited and it requires separate memory/runtime setup.

## Five failures and handling

- Worker waits past expiry: post-lock clock/token/state checks reject publication; the old run failed and is retained.
- Reviewer edits an old revision: conflict, original OCR/audit preserved; drafts do not silently adopt polled revisions.
- OCR source/pixels are corrupted: checksum gate refuses extraction/image serving rather than presenting different pixels under the old evidence hash.
- Payer times out after committing: durable outbox retries the immutable key and reconciles; conflicting amounts fail.
- Model fabricates or malforms output: strict schema and source checks reject suggestions; no automatic approval or silent substitution.

## Fifteen likely questions

1. Why isn't a citation enough? It proves a qualified OCR span match, not that OCR transcribed the image correctly or that a statement is clinically true.
2. Why label context and uniqueness? Reusing a number from the wrong field or selecting among conflicting amounts can produce a plausible but misattributed claim.
3. Is confidence a probability? No; it is raw Tesseract word confidence aggregated conservatively, without real-world calibration.
4. Why does the default auto-route nothing? The fixed conservative threshold was not lowered after seeing results. The zero count is disclosed; production calibration is unfinished.
5. Does review prove accuracy improvement? The measured scripted correction path uses fixture truth. Human effectiveness remains unmeasured, hence the partial acceptance claim.
6. What is a lease token for? It distinguishes an owner from a later retry; an older worker cannot overwrite the newer owner's publication.
7. Why clock_timestamp instead of now? PostgreSQL now is transaction-start time. After a lock wait it can be stale; the current clock is checked under the lock.
8. Is execution exactly once? No. OCR may rerun; valid publication and audit completion are transactional and fenced.
9. What happens after repeated worker death? Expired exhausted jobs become errors. A deliberate operator requeue policy is future work.
10. Can a canceled model request stop native inference? Not currently; the optional path is bounded and serialized but not cooperatively preempted. It is outside OCR job leases.
11. Does local inference ensure correctness? No; raw study output demonstrates limited accuracy. Schema and source support are separate checks, not a semantic guarantee.
12. Why accept a JSON fence? It is a strictly recognized complete transport envelope. Surrounding prose, duplicate keys or incorrect fields still fail schema validation.
13. What prevents duplicate payer claims? Unique document key and immutable amount in the mock database, retried by the durable outbox. No universal provider guarantee is implied.
14. Are audit hashes anonymization? No. They avoid raw content in event payloads but can reveal equality and allow guessing; they are not encryption or a privacy certification.
15. What is actually durable? Postgres transactions persist decisions; source files need their own preserved directory/volume. Temporary test clusters and ephemeral hosting are not durable deployments.

## Three more months

Blinded reviewer accuracy/time study; held-out document families; calibrated automation with confidence intervals; more capable local model baselines; PDF/multipage ingestion; source blob storage tied to database lifecycle; individual reviewer identities and encrypted storage; real synthetic payer sandbox contracts; migration/requeue/observability work and approved deployment. Keep all rejected/losing results rather than promote a fragile confidence number.
