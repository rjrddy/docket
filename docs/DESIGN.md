# Docket: what makes the accuracy claim hard

A correct-looking value can be an OCR error. A correct OCR substring can be attached to the wrong field. A model can emit valid JSON with unsupported values. A reviewer can overwrite another review. A timed-out payer request may already have committed. Docket treats those as separate failure boundaries rather than reducing all of them to a confidence score.

## Source to field

The generator renders only synthetic invoices, statements and referrals as watermarked PNGs. Its truth mapping is separate from `ocr(path)`; the extractor receives image bytes and never the fixture index/truth. Six templates vary labels and rendering degradation. They are a small synthetic family, not held-out real-world coverage. The bundled DejaVu font fixes a source of rendering variation and retains its license.

Tesseract's TSV supplies actual word confidences and bounding boxes. Docket assembles stable text offsets, keeps all tokens, and extracts only unique complete labeled spans. A field's confidence is the minimum relevant word confidence. It is not a calibrated probability. Source validation requires a matching value, exact offsets, correct label context and uniqueness. Whole-sentence claim checking conservatively rejects changed numbers/negation substrings; it is not semantic or clinical entailment. An OCR error can still be internally source-supported. The image and original OCR remain independently visible.

The default threshold is fixed before the campaign. When it auto-routes nothing, the measurement reports that instead of silently lowering it. The evaluation retains all field/template rates and the automation/error curve. Empirical zero errors on a tiny selected subset is not a production bound.

## Reviewer semantics

The React reading room connects live cases, source pixels, actual OCR boxes, editable values, entity candidates, an audit trail and the explicit mock payer. A review uses an expected revision under a row lock. Stale revisions fail rather than overwrite. Draft state pins the old revision and survives polling. Missing/changed OCR values require explicit image attestation plus a bounded note; those corrections are labeled as reviewer image judgments, not invented OCR citations. Original OCR is retained. Notes and values are represented by hashes in audit events; the actual approved fields live in the document record.

The benchmark's corrections are scripted and truth-assisted. They prove that durable corrections change measured accuracy, not that human reviewers are accurate or faster. An independent blinded human study is outstanding. This acceptance claim is explicitly partial.

## Durable queue and actual failure

Postgres stores documents, OCR jobs, review versions, audit events, payer outbox and mock payer state. Claim uses a locked CTE with SKIP LOCKED, a random lease token and an attempt budget. OCR runs outside the transaction. Publication locks the job, checks token/state and current database-clock expiry, then updates result/state/audit and completes the job atomically. A stale worker cannot publish after a later owner or after expiry at the post-lock check. Work may execute more than once; only valid publication is fenced. There is no exactly-once execution claim or heartbeat extension for arbitrarily long jobs.

A real test caught the initial use of transaction-start `now()`: a worker began its transaction before expiry, waited on a row lock until after expiry, and incorrectly published. `clock_timestamp()` is checked after the lock. The failing run and regression are retained. Image bytes are hashed at ingestion, checked before OCR, and checked again before serving to the reviewer. Corruption fails closed. This is accidental-integrity checking, not hostile filesystem authentication or a power-loss durability guarantee.

Attempt exhaustion turns abandoned jobs into explicit errors. There is no hidden successful completion on failure. Operators would need a separate deliberate requeue policy for exhausted work.

## Local LLM boundary

The optional local Qwen model is loaded from pinned public safetensors with upstream LFS SHA verification. It receives OCR text only, with greedy generation and no tool execution. A single complete JSON code fence is a transport envelope; the content must still contain the exact expected string fields, no duplicates or surrounding prose. Each proposed nonempty value is checked independently against labeled source evidence. Missing/unsupported suggestions remain rejected, and model output cannot auto-approve or replace reviewer fields.

The earlier smaller model failed the schema contract. Qwen initially failed only on its JSON fence, which is retained as an interface failure. After explicit envelope handling, its actual extraction accuracy remains limited. Valid JSON is not a correctness claim. Exact source checking is also not semantic truth. The optional long local model/HTTP test is measured locally; routine CI runs the parser/gate tests and skips the heavyweight weight-dependent test.

## Payer boundary

Only approved synthetic referrals enter the outbox. Its immutable document/amount key prevents silently changing an already submitted amount. Workers lease rows, call a real local HTTP mock, then reconcile the final document/amount/status from GET. The payer persists its own unique key and rejects amount conflicts. Selected first responses deliberately sleep after commit, causing a genuine ambiguous client timeout. Retrying the same key does not create another claim.

Final statuses follow an arbitrary deterministic synthetic eligibility rule. This is not a real payer, medical policy, payment processor or clinical decision. Retry exhaustion is explicit; no production delivery/availability guarantee is claimed. HTTP restart and actual container SIGKILL recovery are separate checks from queue-unit tests.

## Privacy, access and operation

All ingested records are generated synthetic fixtures; arbitrary user uploads, PDFs and real records are outside scope. Reviewer/viewer bearer tokens are distinct, held in environment/memory. Viewer requests receive redacted OCR and no source images or write access; saved evaluation endpoints omit raw case/model rows. A new real HTTP viewer test caught an earlier response that included synthetic fixture rows; the failing output is retained and the endpoint now returns summary-only data. Operational logging accepts an explicit small metadata vocabulary and omits source, values, query strings and credentials. Handler failures emit generic codes. HTTP parser diagnostics occur before routing/auth and may embed request bytes: only a validated numeric status is logged. A malformed-version synthetic canary caught the earlier raw diagnostic leak; the failing run is retained in caught-http-parser-canary.log. Redaction is a finite tested view aid, not a universal PHI recognizer or anonymization guarantee. Audit hashes can reveal equality and are not encryption.

HTTP bodies, keys, worker count and request concurrency are bounded. There is no tenant fairness, individual identity, encrypted storage or formal security audit. Default local Postgres trust auth is loopback and synthetic only. The demo preserves its ignored data directory; tests and benchmark own temporary clusters. DATABASE_URL selects caller-owned persistence; compose uses a database/source volume. Test commands use a dedicated test database and truncate Docket tables there. The prepared free-plan service needs a supplied database, private credentials, TLS and durable source storage before any production deployment. No account or deployment was created.

## Primary sources

- Postgres locking and SKIP LOCKED: https://www.postgresql.org/docs/current/sql-select.html
- Database clock semantics: https://www.postgresql.org/docs/current/functions-datetime.html
- Tesseract TSV: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
- Pinned model card: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/tree/7ae557604adf67be50417f59c2c2f167def9a775
- Source-region interaction research (not IIIF implementation): https://iiif.io/api/cookbook/recipe/0021-tagging/
