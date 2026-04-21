"""
Print sorted bin + cold timing for a file or folder.

Usage examples:
  python scripts/bin_from_path.py "data/Magic the gathering Iphone/Screenshot 2026-04-13 185409.png"
  python scripts/bin_from_path.py "data/Magic the gathering Iphone" --mode type
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure `src` imports work when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import process_image
from src.scryfall_client import ScryfallClient
from src.sorting import sort_cards

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _iter_images(target: Path) -> list[Path]:
    # If user gives one file, return only that file.
    if target.is_file():
        return [target]
    # If user gives a folder, return image files inside that folder.
    if target.is_dir():
        return sorted(
            p for p in target.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
    # Path does not exist or is not file/folder.
    return []


def _bin_label_for_record(mode: str, record) -> str:
    # sort_cards returns groups like {"Creatures": [record], ...}
    # We find the one group that contains this card.
    groups = sort_cards([record], mode)
    return next(name for name, cards in groups.items() if cards)


def run(target: Path, mode: str) -> int:
    # 1) Build list of images from a file path or folder path.
    images = _iter_images(target)
    if not images:
        print(f"No images found at: {target}")
        return 1

    # Reuse one client object for all images in this run.
    client = ScryfallClient()
    print(f"Mode: {mode} | Cache: OFF (cold)")
    print(f"Images: {len(images)}")

    for image_path in images:
        # 2) Measure total time for one full image process.
        started_at = time.perf_counter()
        record, err = process_image(image_path, client, use_cache=False)
        elapsed = time.perf_counter() - started_at
        elapsed_ms = elapsed * 1000

        # If OCR / lookup fails, print error and continue with next image.
        if err or not record:
            print(f"[ERROR] {image_path.name} | {elapsed:.3f}s ({elapsed_ms:.1f} ms) | {err}")
            continue

        # 3) Convert card record to a bin label.
        bucket = _bin_label_for_record(mode, record)
        print(
            f"[OK] {image_path.name} | card={record.name} ({record.set}) "
            f"| bin={bucket} | {elapsed:.3f}s ({elapsed_ms:.1f} ms)"
        )

    return 0


def main() -> int:
    # Command-line argument setup.
    parser = argparse.ArgumentParser(
        description="Get sorted bin and cold timing for image path(s)."
    )
    parser.add_argument(
        "path",
        help="Path to one image file, or a folder containing images.",
    )
    parser.add_argument(
        "--mode",
        choices=["color", "type", "value"],
        default="type",
        help="Sort mode used to choose the bin.",
    )
    args = parser.parse_args()
    # Resolve to absolute path so output is consistent.
    return run(Path(args.path).resolve(), args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
