# Run Docket

Prerequisites: Python with venv, Node/npm, Tesseract with English data, PostgreSQL `initdb`/`pg_ctl`. On macOS the Postgres server tools must be on PATH. No model/account is required for the core OCR/review demo.

```
make demo
```

Open http://127.0.0.1:8096 . Access settings accept loopback `local-review` and `local-view`. The source image is always synthetic. Select a field to see actual Tesseract boxes, toggle OCR text, correct missing values, attest to the image and enter a review note. Draft revisions remain pinned until save/reload; stale parallel reviews return conflict. Approved referrals can be sent to the explicit mock payer; some first replies time out after commit and then reconcile through idempotent retry.

The demo owns `.cache/postgres-demo` and `.cache/documents`. Ctrl-C stops its HTTP worker/server and owned database, preserving those ignored demo files. Do not start two default demos against that directory at once. `DATABASE_URL` selects an explicitly supplied database; no cluster is created or stopped in that mode. Tests/benchmark default to isolated temporary clusters and source-image directories. If setting DATABASE_URL for tests/CI, use a dedicated synthetic test database: test gates truncate Docket tables. A local trust-auth database is not a remote deployment configuration.

`make lint test bench` runs source checks, actual Postgres/HTTP tests, real OCR evaluation, scripted review corrections and matching curves. `scripts/seed.py` generates/enqueues the default synthetic fixture set against the configured database, and startup also seeds it idempotently. The renderer's truth is not passed into extraction. The evaluation book reads recorded measurements, while the desk reads live persisted case state.

## Actual optional LLM

Run `make model` to install pinned optional runtime, download/verify the public Qwen weights and execute the retained small extraction study. It needs disk/RAM and network for public packages/weights. Then start `DOCKET_LLM=1 make demo` and use Run local model. The source gate and schema validation remain mandatory; proposals never auto-approve. The default demo disables this memory-heavy feature explicitly. The earlier failed smaller model, envelope failure and regressed label-hint prompt trial are retained.

The weight-dependent actual HTTP integration test is `DOCKET_MODEL_TEST=1 .venv/bin/python scripts/local.py test`. It is recorded locally; routine CI skips this long optional-weight test and still runs schema/source checks. No remote provider API or paid inference cost is claimed.

## Ninety-second demo plan

- 0–15s: select a synthetic statement and field; show the original source image, actual OCR boxes and confidence.
- 15–30s: toggle OCR and reject a negation-substring claim. Explain that source support can still reflect an OCR error.
- 30–45s: correct a referral using the image, attest and save. Show revision and value-free audit. An old revision must conflict.
- 45–60s: send the approved referral to the mock payer. Show retry after ambiguous timeout and final reconciliation; label it mock.
- 60–75s: open the evaluation book, field/template table and automation curve. Show zero default auto-routes and truth-assisted review limits.
- 75–90s: switch to viewer access/redacted OCR, restore reviewer access, narrow the viewport and review another case.

Automated proof: install `requirements-browser.txt` into `.venv`, run `.venv/bin/python -m playwright install chromium ffmpeg`, then `.venv/bin/python scripts/local.py review --record`. It owns a temporary Postgres cluster, source directory and server and records changed real review actions. With weights installed, prepend DOCKET_LLM=1 to exercise actual model suggestions as well. Corrections are explicitly truth-assisted scripted operations, not a human study. Verify real duration with `ffprobe docs/results/browser/docket-demo.webm`; no padding. Use PLAYWRIGHT_BROWSERS_PATH only for an installed matching browser cache.

## Container and hosting preparation

`docker compose up --build` starts Postgres with database and source volumes plus the nonroot application. Local compose demo credentials are synthetic, not remote secrets. Set distinct private DOCKET_REVIEW_TOKEN/DOCKET_VIEW_TOKEN for external binding and TLS at the proxy. The actual Linux container gate uses its own isolated test schema and exercises OCR, review, UID and SIGKILL/restart.

Dockerfile and Render free-plan configuration are prepared only; no account or deployment was created. Supply an approved database and durable source storage. Free ephemeral web storage alone cannot guarantee source preservation across recreation: https://render.com/docs/free . PDFs/multipage input, real payer contracts, encrypted storage, individual identities and independent human benefit validation remain unfinished.
