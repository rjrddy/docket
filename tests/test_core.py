"""Source/negation/number, privacy, and actual OCR properties on independent rendered truth."""

import random

import pytest

from docket.documents import FIELDS, fixture, render
from docket.extract import claim_supported, ocr, supported
from docket.privacy import log_record, redact


def test_citation_cannot_move_between_fields_or_change_numbers():
    text = "Document: SYN-0001\nDate: 2026-02-01\nTotal: 123.45\nAccount: DEMO710001"
    start = text.index("123.45")
    assert supported(text, "amount", "123.45", start, start + 6)
    assert not supported(text + "\nBalance: 999.99", "amount", "123.45", start, start + 6)
    rng = random.Random(42)
    for _ in range(500):
        bad = f"{rng.randint(200, 999)}.00"
        assert not supported(text, "amount", bad, start, start + 6)
        assert not supported(text, "reference", "123.45", start, start + 6)
    assert not claim_supported("No fever is reported. Temperature is 36.5 C.", "fever is reported.")
    assert not claim_supported(
        "No fever is reported. Temperature is 36.5 C.", "Temperature is 39.5 C."
    )
    assert claim_supported("No fever is reported. Temperature is 36.5 C.", "No fever is reported.")


def test_value_free_logs_and_redaction():
    sentinel = "Patient: CANARY NAME\nMember: DEMO991234\ncanary@example.invalid\n555-010-1234\n000-00-0000"
    text = redact(sentinel)
    assert all(
        v not in text
        for v in [
            "CANARY NAME",
            "DEMO991234",
            "canary@example.invalid",
            "555-010-1234",
            "000-00-0000",
        ]
    )
    for key in ["text", "name", "member", "token", "payload", "note"]:
        with pytest.raises(ValueError):
            log_record(event="ocr", **{key: sentinel})
    assert "CANARY" not in log_record(event="ocr", document="doc-0001", status="review")


def test_actual_ocr_bounds_and_no_truth_argument(tmp_path):
    path = tmp_path / "synthetic.png"
    meta = render(1, path)
    result = ocr(path)
    assert set(result["fields"]) == set(FIELDS)
    assert "SYNTHETIC" in result["text"]
    for field, value in result["fields"].items():
        assert 0 <= value["confidence"] <= 1
        if value["supported"]:
            assert result["text"][value["start"] : value["end"]] == value["value"]
            assert supported(result["text"], field, value["value"], value["start"], value["end"])
    assert meta["truth"] == fixture(1)["truth"]


def test_model_envelope_is_not_a_schema_or_source_bypass():
    import json

    from docket.llm import parse_proposal

    payload = {k: "" for k in FIELDS}
    assert parse_proposal(json.dumps(payload)) == payload
    assert parse_proposal("```json\n" + json.dumps(payload) + "\n```") == payload
    assert parse_proposal("Claim supported! " + json.dumps(payload)) is None
    assert parse_proposal('{"amount":"1.00","amount":"2.00"}') is None
    assert parse_proposal(json.dumps({**payload, "amount": 10})) is None
