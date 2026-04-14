"""
Scan inbox directory: OCR images, identify cards, sort into output folders.

This powers the `scan-inbox` CLI command. You put card images in data/inbox/,
run the command, and the app:
1. Finds all .png/.jpg/.jpeg/.webp files
2. Runs OCR + Scryfall lookup on each
3. Sorts cards by the chosen mode (color, type, or value)
4. Copies images into subfolders under data/sorted/ (e.g. Creatures/, Lands/)

Useful for batch processing: drop 50 photos in inbox, run once, get organized folders.
"""

import random
import shutil
import time
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from src.models import CardRecord
from src.scryfall_client import ScryfallClient
from src.sorting import sort_cards

SortMode = Literal["color", "type", "value"]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _find_images(inbox: Path) -> list[Path]:
    """Find all image files in inbox (non-recursive). Returns sorted list of paths."""
    if not inbox.exists():
        return []
    return sorted(p for p in inbox.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


def scan_and_sort(
    inbox: Path,
    out_dir: Path,
    mode: SortMode = "type",
    on_ambiguous=None,
) -> tuple[int, int, list[tuple[str, str]]]:
    """
    Process all images in inbox, sort by mode, copy to out_dir subfolders.

    For each image: OCR -> parse -> Scryfall -> CardRecord. Then group cards
    by mode (color/type/value) and copy each image to the right folder.
    Duplicate names get _2, _3 suffix (e.g. Lightning Bolt (M21)_2.png).

    Returns (success_count, error_count, [(path, error_msg), ...]).
    """
    images = _find_images(inbox)
    if not images:
        return 0, 0, []

    from src.pipeline import process_image

    scryfall = ScryfallClient()
    cards: list[CardRecord] = []
    errors: list[tuple[str, str]] = []
    card_to_path: dict[str, Path] = {}
    card_to_sort_time: dict[str, float] = {}

    for path in images:
        path = path.resolve()
        started_at = time.perf_counter()
        record, err = process_image(path, scryfall, on_ambiguous, use_cache=True)
        elapsed = time.perf_counter() - started_at
        if record:
            cards.append(record)
            card_to_path[record.id] = path
            card_to_sort_time[record.id] = elapsed
        if err:
            errors.append((str(path), err))

    if not cards:
        return 0, len(errors), errors

    groups = sort_cards(cards, mode)

    out_dir.mkdir(parents=True, exist_ok=True)
    for group_name, group_cards in groups.items():
        group_dir = out_dir / _sanitize_folder_name(group_name)
        group_dir.mkdir(parents=True, exist_ok=True)
        seen: dict[str, int] = {}
        for card in group_cards:
            src = card_to_path.get(card.id)
            if src and src.exists():
                base = _sanitize_filename(f"{card.name} ({card.set})")
                if base in seen:
                    seen[base] += 1
                    base = f"{base}_{seen[base]}"
                else:
                    seen[base] = 1
                dest = group_dir / f"{base}{src.suffix}"
                elapsed = card_to_sort_time.get(card.id)
                if elapsed is not None:
                    _copy_with_timing_overlay(src, dest, elapsed)
                else:
                    shutil.copy2(src, dest)

    return len(cards), len(errors), errors


def _sanitize_folder_name(name: str) -> str:
    """Make folder name filesystem-safe (alphanumeric, space, underscore only)."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()


def _sanitize_filename(name: str) -> str:
    """
    Make filename safe for Windows.

    Windows forbids: / \\ : * ? " < > |
    We replace those with underscore. Also cap length (Windows path limit).
    """
    bad = set('/\\:*?"<>|')
    s = "".join("_" if c in bad else c for c in name).strip() or "card"
    return s[:200] if len(s) > 200 else s  # Windows path limit


def _copy_with_timing_overlay(src: Path, dest: Path, elapsed_seconds: float) -> None:
    """
    Copy image and stamp sort timing at the bottom.

    The text is white on a tightly padded black background.
    """
    label = f"Sort time: {elapsed_seconds:.2f}s"
    try:
        with Image.open(src) as image:
            image = image.convert("RGB")
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
            text_width = right - left
            text_height = bottom - top
            x_pad = 6
            y_pad = 3
            x = (image.width - text_width) // 2
            y = max(0, image.height - text_height - y_pad * 2 - 8)
            rect = (
                max(0, x - x_pad),
                max(0, y - y_pad),
                min(image.width, x + text_width + x_pad),
                min(image.height, y + text_height + y_pad),
            )
            draw.rectangle(rect, fill="black")
            draw.text((x, y), label, fill="white", font=font)
            image.save(dest)
    except OSError:
        # Fall back to plain copy if Pillow cannot decode this image.
        shutil.copy2(src, dest)


def seed_inbox(inbox: Path, dataset_root: Path, count: int = 5) -> int:
    """
    Copy random images from dataset into inbox for demo.

    Use --seed 5 when running scan-inbox to populate inbox with sample cards
    before processing. Helpful when you don't have your own photos yet.
    Returns number of images copied.
    """
    inbox.mkdir(parents=True, exist_ok=True)
    images_dir = dataset_root / "images"
    if not images_dir.exists():
        return 0

    all_images: list[Path] = []
    for sub in images_dir.iterdir():
        if sub.is_dir():
            all_images.extend(
                p for p in sub.iterdir()
                if p.suffix.lower() in IMAGE_EXTENSIONS
            )

    if not all_images:
        return 0

    chosen = random.sample(all_images, min(count, len(all_images)))
    for src in chosen:
        dest = inbox / src.name
        if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dest)
    return len(chosen)
