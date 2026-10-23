# Database leases and a separately idempotent mock boundary

Postgres queue consumers claim with FOR UPDATE SKIP LOCKED and random lease tokens. Publication checks token, state and database-clock expiry in the same transaction as document/audit update. Expired jobs retry under an attempt budget; exhausted abandoned jobs become explicit errors. This is at-least-once processing with fenced publication, not exactly-once execution.

An outbox captures approved referral amount once. The mock payer stores a unique document key and immutable amount. Selected first HTTP responses deliberately sleep AFTER the payer transaction commits, causing actual client timeout and retry. The retry reuses the key, then GET reconciles amount/document/status. Neither side can claim a real eligibility/payment decision.

The local demo owns a persistent ignored Postgres data directory; tests/bench use isolated temporary clusters. DATABASE_URL selects caller-owned persistence, and compose provides a database volume. Local auto-start uses trust auth on loopback for synthetic data only; deployment uses explicit env credentials. No external account or deployment created.
