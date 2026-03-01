#!/usr/bin/env python3
"""
Sort dataset images into folders by card type (Creatures, Spells, Permanents, Lands).

Takes a built dataset (with metadata.jsonl), reads type_line from each record,
and copies images into sorted_by_type/Creatures/, sorted_by_type/Lands/, etc.
Does NOT run OCR—uses metadata from build_dataset. Useful for organizing
the downloaded images for manual inspection.

Usage:
  python scripts/sort_dataset_by_type.py              # Uses baseline_v1
  python scripts/sort_dataset_by_type.py my_dataset    # Custom dataset name
"""

import json
import shutil
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _type_group(type_line: str) -> str:
    """Map type_line (e.g. 'Creature — Human') to bucket: Creatures, Spells, Permanents, Lands."""
    tl = (type_line or "").lower()
    if "land" in tl:
        return "Lands"
    if "creature" in tl:
        return "Creatures"
    if "instant" in tl or "sorcery" in tl:
        return "Spells"
    if any(t in tl for t in ("artifact", "enchantment", "planeswalker")):
        return "Permanents"
    return "Permanents"


def main():
    dataset_name = sys.argv[1] if len(sys.argv) > 1 else "baseline_v1"
    dataset_root = Path("data/datasets") / dataset_name
    out_dir = dataset_root / "sorted_by_type"

    metadata_path = dataset_root / "metadata.jsonl"
    if not metadata_path.exists():
        print(f"Metadata not found: {metadata_path}")
        return 1

    # Load records
    records = []
    with open(metadata_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Create output folders
    for group in ("Creatures", "Spells", "Permanents", "Lands"):
        (out_dir / group).mkdir(parents=True, exist_ok=True)

    # Copy each image to its type folder
    for rec in records:
        type_line = rec.get("type_line", "")
        group = _type_group(type_line)
        src = dataset_root / rec.get("image_path", "")
        if not src.exists():
            print(f"  Skip (missing): {src}")
            continue
        # Use scryfall_id to avoid name collisions
        filename = Path(rec["image_path"]).name
        dst = out_dir / group / filename
        shutil.copy2(src, dst)

    # Summary
    counts = {}
    for rec in records:
        g = _type_group(rec.get("type_line", ""))
        counts[g] = counts.get(g, 0) + 1

    print(f"Sorted {len(records)} cards into {out_dir}")
    for g in ("Lands", "Creatures", "Spells", "Permanents"):
        print(f"  {g}: {counts.get(g, 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
