"""Download a pinned public model, or verify an existing local cache against upstream LFS."""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
folder = ROOT / ".cache/model-qwen"
folder.mkdir(parents=True, exist_ok=True)
url = f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}?blobs=true"
with urllib.request.urlopen(url, timeout=30) as response:
    manifest = json.load(response)
expected = next(
    f["lfs"]["sha256"] for f in manifest["siblings"] if f["rfilename"] == "model.safetensors"
)
files = [
    "model.safetensors",
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "README.md",
]
files = [f for f in files if f in {row["rfilename"] for row in manifest["siblings"]}]
rows = []
for name in files:
    dest = folder / name
    source = f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}"
    if not dest.exists():
        temporary = dest.with_suffix(".download")
        urllib.request.urlretrieve(source, temporary)
        temporary.replace(dest)
    with dest.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if name == "model.safetensors" and digest != expected:
        raise RuntimeError("model weights differ from pinned upstream LFS SHA256")
    rows.append({"file": name, "sha256": digest, "bytes": dest.stat().st_size})
result = {
    "model": MODEL,
    "revision": REVISION,
    "license": "Apache-2.0 per pinned model card",
    "upstream_manifest": url,
    "weights_verified_against_lfs": True,
    "files": rows,
}
(ROOT / "docs/results/model-provenance.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
