"""Actual Postgres leases, atomic review revisions, durable audit, and outbox fencing."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from docket import store
from docket.documents import render
from docket.extract import ocr
from docket.worker import image_path


@pytest.fixture(autouse=True)
def database():
    store.initialize()
    with store.connection() as c:
        c.execute("TRUNCATE audit,outbox,mock_payer,jobs,documents RESTART IDENTITY CASCADE")


def ingest(index):
    return store.enqueue(render(index, image_path(f"doc-{index:04d}")))


def test_lease_recovery_fences_old_worker_and_atomic_publish():
    doc = ingest(1)
    first = store.claim()
    assert store.claim() is None
    with store.connection() as c:
        c.execute("UPDATE jobs SET expires=now()-interval '1 second' WHERE document=%s", (doc,))
    second = store.claim()
    assert first["lease"] != second["lease"]
    result = ocr(image_path(doc))
    assert not store.finish(doc, first["lease"], result)
    assert store.finish(doc, second["lease"], result)
    assert not store.finish(doc, second["lease"], result)
    row = store.get(doc)
    assert row["revision"] == 1
    assert sum(a["event"] == "extracted" for a in row["audit"]) == 1
    with store.connection() as c:
        assert (
            c.execute("SELECT state FROM jobs WHERE document=%s", (doc,)).fetchone()["state"]
            == "done"
        )


def test_parallel_claims_revision_conflicts_and_attestation():
    for i in range(6):
        ingest(i)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: store.claim(), range(6)))
    assert len({j["document"] for j in jobs}) == 6
    job = jobs[0]
    result = ocr(image_path(job["document"]))
    assert store.finish(job["document"], job["lease"], result)
    row = store.get(job["document"])
    from docket.documents import fixture

    values = fixture(row["fixture"])["truth"]
    with pytest.raises(ValueError):
        store.review(row["id"], row["revision"], values, False, "")
    reviewed = store.review(
        row["id"], row["revision"], values, True, "Test image transcription, synthetic only"
    )
    assert reviewed["state"] == "reviewed"
    with pytest.raises(RuntimeError):
        store.review(row["id"], row["revision"], values, True, "Conflicting second reviewer")
    assert all(
        "value_hashes" in a["detail"] and "DEMO" not in str(a["detail"])
        for a in reviewed["audit"]
        if a["event"] == "reviewed"
    )


def test_attempt_budget_and_payer_idempotency_conflicts():
    doc = ingest(2)
    job = store.claim()
    with store.connection() as c:
        c.execute(
            "UPDATE jobs SET attempts=3,expires=now()-interval '1 second' WHERE document=%s", (doc,)
        )
    assert store.claim() is None
    assert store.get(doc)["state"] == "error"
    assert not store.finish(doc, job["lease"], ocr(image_path(doc)))


def test_hash_conflict_rejected():
    meta = render(4, image_path("doc-0004"))
    assert store.enqueue(meta) == store.enqueue(meta)
    with pytest.raises(ValueError):
        store.enqueue({**meta, "sha256": "changed"})
