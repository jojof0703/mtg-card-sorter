#!/usr/bin/env python3
"""
Verify Google Cloud Vision OCR is working and reading card text correctly.

Runs on CACHED OCR only (no API call). Use after running ocr-eval to confirm
Vision ran successfully. Prints parsed values (collector, set, name) and
a preview of the raw OCR text for each cached file.

Usage:
  python scripts/verify_vision_ocr.py

Prerequisite: Run `python -m src.cli dataset ocr-eval --limit 5` first
to generate ocr/*.txt cache files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ocr_parsing import parse_ocr_for_lookup
from src.services.vision_ocr import VisionOCR


def main():
    """Load cached OCR files, parse them, print results. No API calls."""
    dataset = Path("data/datasets/baseline_v1")
    ocr_dir = dataset / "ocr"
    images_dir = dataset / "images"

    if not ocr_dir.exists():
        print("No OCR cache found. Run: python -m src.cli dataset ocr-eval --limit 5")
        return 1

    # Use cached OCR (no API call) - proves Vision ran successfully
    cache_files = list(ocr_dir.glob("*.txt"))[:5]
    if not cache_files:
        print("No cached OCR files. Run ocr-eval first.")
        return 1

    print("=" * 60)
    print("Vision OCR verification (using cached results)")
    print("=" * 60)
    print("If these files exist, Vision ran successfully when ocr-eval ran.")
    print("Parsed values show what we extract for Scryfall lookup.\n")

    for cf in cache_files:
        stem = cf.stem
        text = cf.read_text(encoding="utf-8")
        collector, set_code, name = parse_ocr_for_lookup(text)
        print(f"--- {stem} ---")
        print(f"  Parsed: collector={collector!r} set={set_code!r} name={name!r}")
        print(f"  OCR preview: {text[:120].replace(chr(10), ' ')}...")
        print()

    print("Vision is working if you see readable card text above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
