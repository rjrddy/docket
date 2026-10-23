"""Allowlisted value-free operational/audit logging; redaction is a separate view aid."""

import hashlib
import json
import re

ALLOWED = {"event", "document", "status", "role", "fields", "revision", "error", "attempt"}


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def log_record(**values) -> str:
    if set(values) - ALLOWED:
        raise ValueError("log payload is not allowlisted")
    return json.dumps(values, sort_keys=True)


def redact(text: str) -> str:
    text = re.sub(
        r"(?im)^((?:Member|Account|Customer|Patient|Provider|Entity|Vendor):)[^\n]*",
        r"\1 [REDACTED]",
        text,
    )
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b\d{3}[- .]\d{3}[- .]\d{4}\b", "[PHONE]", text)
    text = re.sub(r"\bDEMO\d{6}\b|\b\d{3}-\d{2}-\d{4}\b", "[ID]", text)
    return text
