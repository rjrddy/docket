"""Independent truth and rendered images. Extraction never receives the truth mapping."""

import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("document_id", "date", "amount", "entity", "reference", "zone", "domain")
LABELS = {
    "document_id": ("Document", "Reference document"),
    "date": ("Date", "Service date"),
    "amount": ("Total", "Balance", "Copay"),
    "entity": ("Entity", "Provider", "Vendor"),
    "reference": ("Account", "Member", "Customer"),
    "zone": ("Zone",),
    "domain": ("Directory",),
}


def fixture(index: int) -> dict:
    if type(index) is not int or not 0 <= index < 120:
        raise ValueError("synthetic fixture index out of range")
    rng = random.Random(7100 + index)
    kind = ["invoice", "statement", "referral"][index % 3]
    variant = (index // 3) % 2
    entity = index % 12
    truth = {
        "document_id": f"SYN-{index:04d}",
        "date": f"2026-02-{index % 28 + 1:02d}",
        "amount": f"{rng.randint(100, 9999)}.{rng.randint(0, 99):02d}",
        "entity": f"DEMO ENTITY {entity:02d}",
        "reference": f"DEMO{710000 + index}",
        "zone": f"TESTZONE-{entity % 3}",
        "domain": f"entity{entity:02d}.example.invalid",
    }
    labels = {
        "document_id": "Reference document" if variant else "Document",
        "date": "Service date" if variant else "Date",
        "amount": {"invoice": "Total", "statement": "Balance", "referral": "Copay"}[kind],
        "entity": {"invoice": "Vendor", "statement": "Entity", "referral": "Provider"}[kind],
        "reference": {"invoice": "Customer", "statement": "Account", "referral": "Member"}[kind],
        "zone": "Zone",
        "domain": "Directory",
    }
    return {
        "index": index,
        "kind": kind,
        "template": f"{kind}-{'b' if variant else 'a'}",
        "quality": index // 6 % 6,
        "truth": truth,
        "labels": labels,
    }


def render(index: int, destination: Path) -> dict:
    doc = fixture(index)
    image = Image.new("RGB", (900, 850), "white")
    draw = ImageDraw.Draw(image)
    quality = doc["quality"]
    size = [25, 24, 23, 20, 17, 14][quality]
    font = ImageFont.truetype(str(ROOT / "data/DejaVuSans.ttf"), size)
    heading = ImageFont.truetype(str(ROOT / "data/DejaVuSans.ttf"), 28)
    draw.text((40, 28), "SYNTHETIC / NOT A REAL RECORD", font=heading, fill="black")
    draw.text((40, 90), doc["template"].upper() + " — DEMO COPY", font=font, fill="black")
    for n, field in enumerate(FIELDS):
        draw.text(
            (45, 165 + n * 68),
            f"{doc['labels'][field]}: {doc['truth'][field]}",
            font=font,
            fill=(35, 35, 35) if quality > 2 else "black",
        )
    draw.text(
        (45, 735), "Contact: synthetic@example.invalid / 555-010-1234", font=font, fill="black"
    )
    draw.text(
        (45, 785), "No urgent action is stated. Synthetic evaluation only.", font=font, fill="black"
    )
    if quality in (1, 3):
        image = image.rotate(1.2 if quality == 1 else -1.7, fillcolor="white")
    if quality >= 2:
        image = image.filter(ImageFilter.GaussianBlur([0, 0, 0.5, 0.8, 1.0, 1.4][quality]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return {**doc, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
