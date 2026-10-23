"""Real Tesseract TSV, per-field evidence, conservative claims and entity matching."""

import csv
import io
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path

from .documents import FIELDS, LABELS

PATTERNS = {
    "document_id": r"SYN-\d{4}",
    "date": r"\d{4}-\d{2}-\d{2}",
    "amount": r"\d{1,8}\.\d{2}",
    "entity": r"DEMO ENTITY \d{2}",
    "reference": r"DEMO\d{6}",
    "zone": r"TESTZONE-\d",
    "domain": r"entity\d{2}\.example\.invalid",
}


def field_matches(text: str, field: str) -> list[re.Match]:
    labels = "|".join(re.escape(label) for label in LABELS[field])
    return list(re.finditer(rf"(?im)^(?:{labels}):\s*(?P<value>{PATTERNS[field]})\s*$", text))


def supported(text: str, field: str, value: str, start: int, end: int) -> bool:
    if (
        field not in FIELDS
        or type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(text)
    ):
        return False
    matches = field_matches(text, field)
    return (
        text[start:end] == value and len(matches) == 1 and matches[0].span("value") == (start, end)
    )


def claim_supported(source: str, claim: str) -> bool:
    # Whole-sentence equality only: substring/negation and changed-number claims fail closed.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source) if s.strip()]
    return bool(claim.strip()) and claim.strip() in sentences


def ocr(path: Path) -> dict:
    output = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "6", "tsv"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    tokens = []
    lines: dict[tuple, list[dict]] = {}
    for row in csv.DictReader(io.StringIO(output.stdout), delimiter="\t"):
        if row["level"] != "5" or not row["text"].strip():
            continue
        token = {
            "text": row["text"],
            "confidence": max(0, float(row["conf"]) / 100),
            "box": [int(row[k]) for k in ("left", "top", "width", "height")],
        }
        key = tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(token)
    text = ""
    for line in lines.values():
        if text:
            text += "\n"
        for n, token in enumerate(line):
            if n:
                text += " "
            token["start"] = len(text)
            text += token["text"]
            token["end"] = len(text)
            tokens.append(token)
    fields = {}
    for field in FIELDS:
        matches = field_matches(text, field)
        if len(matches) != 1:
            fields[field] = {
                "value": "",
                "confidence": 0.0,
                "supported": False,
                "start": None,
                "end": None,
                "boxes": [],
                "reason": "missing or ambiguous labeled span",
            }
            continue
        match = matches[0]
        start, end = match.span("value")
        words = [t for t in tokens if t["start"] < end and t["end"] > start]
        value = match.group("value")
        fields[field] = {
            "value": value,
            "confidence": min(t["confidence"] for t in words),
            "supported": supported(text, field, value, start, end),
            "start": start,
            "end": end,
            "boxes": [t["box"] for t in words],
            "reason": "unique exact labeled OCR span",
        }
    return {
        "text": text,
        "tokens": tokens,
        "fields": fields,
        "confidence": min(f["confidence"] for f in fields.values()),
        "method": "Tesseract TSV + labeled-span parser; confidence is not calibrated probability",
    }


def route(result: dict, threshold: float = 0.93) -> str:
    return (
        "auto"
        if all(f["supported"] and f["confidence"] >= threshold for f in result["fields"].values())
        else "review"
    )


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def score(left: dict, right: dict) -> float:
    name = SequenceMatcher(None, normalize(left["entity"]), normalize(right["entity"])).ratio()
    return (
        0.55 * name
        + 0.2 * float(normalize(left["zone"]) == normalize(right["zone"]))
        + 0.25 * float(normalize(left["domain"]) == normalize(right["domain"]))
    )


def registry() -> list[dict]:
    return [
        {
            "id": i,
            "entity": f"DEMO ENTITY {i:02d}",
            "zone": f"TESTZONE-{i % 3}",
            "domain": f"entity{i:02d}.example.invalid",
        }
        for i in range(12)
    ]


def candidates(fields: dict) -> list[dict]:
    query = {k: fields[k]["value"] for k in ("entity", "zone", "domain")}
    return sorted(
        [{**r, "score": score(query, r)} for r in registry()], key=lambda x: (-x["score"], x["id"])
    )[:3]
