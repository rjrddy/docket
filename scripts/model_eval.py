"""Actual free JSON generation over fixed real OCR text, with independent generator truth."""

import json
from pathlib import Path

import torch
import transformers

from docket.documents import FIELDS
from docket.llm import propose

ROOT = Path(__file__).resolve().parents[1]
eval_rows = json.loads((ROOT / "docs/results/evaluation.json").read_text())["rows"]
rows = []
for index in [0, 1, 2, 18, 30, 35]:
    item = eval_rows[index]
    result = propose(item["result"]["text"])
    correct = {
        field: result["fields"].get(field, {}).get("value") == item["truth"][field]
        for field in FIELDS
    }
    rows.append(
        {
            "id": item["id"],
            "source_text": item["result"]["text"],
            "correct": correct,
            "result": result,
        }
    )
    print(item["id"], result["schema_valid"], sum(correct.values()), flush=True)
fields = [f for r in rows for f in r["result"]["fields"].values() if f["value"]]
unsupported = sum(not f["supported"] for f in fields)
report = {
    "model": "Qwen/Qwen2.5-0.5B-Instruct",
    "revision": "7ae557604adf67be50417f59c2c2f167def9a775",
    "torch": torch.__version__,
    "transformers": transformers.__version__,
    "documents": len(rows),
    "schema_valid_documents": sum(r["result"]["schema_valid"] for r in rows),
    "correct_fields": sum(sum(r["correct"].values()) for r in rows),
    "total_fields": len(rows) * len(FIELDS),
    "proposed_nonempty_fields": len(fields),
    "unsupported_fields": unsupported,
    "unsupported_rate": unsupported / len(fields) if fields else None,
    "accepted_fields": sum(f["supported"] for f in fields),
    "accepted_incorrect_fields": sum(
        proposal["supported"] and not row["correct"][field]
        for row in rows
        for field, proposal in row["result"]["fields"].items()
    ),
    "seconds": sum(r["result"]["seconds"] for r in rows),
    "scope": "unconstrained greedy generation; unsupported proposals rejected; schema failures separate; no automatic approval or clinical factuality claim",
    "rows": rows,
}
(ROOT / "docs/results/model-evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
