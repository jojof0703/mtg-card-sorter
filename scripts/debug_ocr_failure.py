#!/usr/bin/env python3
"""
Debug individual OCR failures: show full OCR, parsed values, and expected vs predicted.

When ocr-eval runs, it writes failures to failures.csv. This script lets you
inspect a specific failure in detail: what did OCR see? What did we parse?
What did we expect vs what did we predict?

Usage:
  python scripts/debug_ocr_failure.py 0              # First failure (0-indexed)
  python scripts/debug_ocr_failure.py 5              # 6th failure
  python scripts/debug_ocr_failure.py 2e6c0b8d       # By image UUID substring
  python scripts/debug_ocr_failure.py --list 10      # List first 10 failures
  python scripts/debug_ocr_failure.py 0 --open      # Also open image in viewer
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ocr_parsing import parse_ocr_for_lookup


def load_failures(dataset_root: Path) -> list[dict]:
    """Load failures from failures.csv (created by ocr-eval)."""
    path = dataset_root / "failures.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_metadata(dataset_root: Path) -> dict[str, dict]:
    """Load metadata.jsonl. Returns {by_id: {...}, by_stem: {...}} for lookups."""
    path = dataset_root / "metadata.jsonl"
    by_id = {}
    by_stem = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            by_id[rec["scryfall_id"]] = rec
            stem = Path(rec["image_path"]).stem
            by_stem[stem] = rec
    return {"by_id": by_id, "by_stem": by_stem}


def get_full_ocr(dataset_root: Path, image_path: str) -> str:
    """Load full OCR text from cache (ocr/{stem}.txt). Returns '(no cached OCR)' if missing."""
    stem = Path(image_path).stem
    ocr_path = dataset_root / "ocr" / f"{stem}.txt"
    if ocr_path.exists():
        return ocr_path.read_text(encoding="utf-8")
    return "(no cached OCR)"


def main():
    parser = argparse.ArgumentParser(description="Debug OCR failures")
    parser.add_argument(
        "index_or_uuid",
        nargs="?",
        help="Failure index (0-based) or image UUID substring",
    )
    parser.add_argument(
        "--list",
        type=int,
        metavar="N",
        help="List first N failures with index",
    )
    parser.add_argument(
        "--dataset",
        default="data/datasets/baseline_v1",
        help="Dataset root path",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open image in default viewer",
    )
    args = parser.parse_args()

    dataset_root = Path(args.dataset)
    if not dataset_root.exists():
        print(f"Dataset not found: {dataset_root}")
        return 1

    failures = load_failures(dataset_root)
    meta = load_metadata(dataset_root)

    if args.list is not None:
        n = min(args.list, len(failures))
        print(f"First {n} failures (use index to inspect):\n")
        for i, f in enumerate(failures[:n]):
            stem = Path(f["image_path"]).name.replace(".png", "")
            exp = meta["by_id"].get(f["expected_id"], {})
            exp_set = exp.get("set", "?")
            exp_cn = exp.get("collector_number", "?")
            print(f"  [{i}] {stem[:20]}... | expected: {f['expected_name'][:30]} | {exp_set}/{exp_cn} -> {f['predicted_name'][:25] if f['predicted_name'] else '?'}")
        return 0

    if not args.index_or_uuid:
        parser.print_help()
        print("\nExamples: debug_ocr_failure.py 0  |  debug_ocr_failure.py --list 15")
        return 1

    # Resolve index or UUID
    idx = None
    if args.index_or_uuid.isdigit():
        idx = int(args.index_or_uuid)
        if idx < 0 or idx >= len(failures):
            print(f"Index {idx} out of range (0-{len(failures)-1})")
            return 1
    else:
        uuid_sub = args.index_or_uuid.lower()
        for i, f in enumerate(failures):
            if uuid_sub in f["image_path"].lower() or uuid_sub in f.get("expected_id", "").lower():
                idx = i
                break
        if idx is None:
            print(f"No failure matches '{args.index_or_uuid}'")
            return 1

    fail = failures[idx]
    image_path = dataset_root / fail["image_path"].replace("data\\datasets\\baseline_v1\\", "").replace("/", os.sep)
    if not image_path.exists():
        image_path = Path(fail["image_path"])
    if not image_path.is_absolute():
        image_path = dataset_root / image_path

    full_ocr = get_full_ocr(dataset_root, fail["image_path"])
    collector, set_code, name = parse_ocr_for_lookup(full_ocr)

    exp = meta["by_id"].get(fail["expected_id"], {})
    exp_set = exp.get("set", "?")
    exp_cn = exp.get("collector_number", "?")

    print("=" * 70)
    print(f"FAILURE #{idx}: {fail['expected_name']}")
    print("=" * 70)
    print(f"\nExpected:  {exp_set}/{exp_cn}  ->  {fail['expected_id'][:8]}...")
    print(f"Predicted: {fail['predicted_name']}  ->  {fail['predicted_id'][:8] if fail['predicted_id'] else '?'}...")
    print(f"\n--- PARSED FROM OCR ---")
    print(f"  collector_number: {collector!r}")
    print(f"  set_code:          {set_code!r}")
    print(f"  name_guess:       {name!r}")
    print(f"\n--- FULL OCR (cached) ---")
    print(full_ocr)
    print("--- end ---")

    # Diagnosis
    print("\n--- DIAGNOSIS ---")
    if not collector and not set_code:
        print("  -> No set+collector parsed; falling back to fuzzy name only.")
    elif set_code and collector:
        if exp_set and exp_cn and (set_code.lower() != exp_set.lower() or str(collector) != str(exp_cn)):
            print(f"  -> Parsed {set_code}/{collector} but expected {exp_set}/{exp_cn}")
            if fail["expected_name"] == fail["predicted_name"]:
                print("  -> Same card name, WRONG PRINTING (fuzzy returned different set)")
        else:
            print("  -> Set+collector parsed; check if Scryfall lookup succeeded.")
    if fail["expected_name"] != fail["predicted_name"] and fail["predicted_name"]:
        print(f"  -> Name mismatch: expected '{fail['expected_name']}' vs predicted '{fail['predicted_name']}'")

    if args.open and image_path.exists():
        print(f"\nOpening: {image_path}")
        try:
            if sys.platform == "win32":
                os.startfile(str(image_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(image_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(image_path)], check=False)
        except Exception as e:
            print(f"Could not open image: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
