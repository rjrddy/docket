"""Render and enqueue only seeded synthetic documents into the configured Postgres."""

from docket import store
from docket.server import seed

store.initialize()
print({"synthetic_document_ids": seed()})
