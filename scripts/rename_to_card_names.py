"""
Rename card images from UUIDs to "Card Name (set).png" format.

Usage:
  python -m scripts.rename_to_card_names

Renames files in data/inbox and data/sorted to match actual Scryfall card names.
"""

import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scryfall_client import ScryfallClient


def _sanitize_filename(name: str) -> str:
    """Make filename safe for Windows."""
    bad = set('/\\:*?"<>|')
    s = "".join("_" if c in bad else c for c in name).strip() or "card"
    return s[:200] if len(s) > 200 else s


def _extract_uuid(stem: str) -> str | None:
    """Extract Scryfall UUID from filename stem (handles _face0, _face1 suffix)."""
    # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    match = re.match(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})(?:_face\d+)?", stem, re.I)
    return match.group(1) if match else None


def rename_inbox(inbox_dir: Path, dry_run: bool = False) -> int:
    """Rename inbox files from UUID to Card Name (set).png. Returns count renamed."""
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    files = [p for p in inbox_dir.iterdir() if p.is_file() and p.suffix.lower() in extensions]
    if not files:
        return 0

    client = ScryfallClient()
    renamed = 0
    seen: dict[str, int] = {}

    for path in sorted(files):
        stem = path.stem
        uuid = _extract_uuid(stem)
        if not uuid:
            print(f"  Skip (no UUID): {path.name}")
            continue

        card = client.get_by_id(uuid)
        if not card:
            print(f"  Skip (Scryfall 404): {path.name}")
            continue

        name = card.get("name", "")
        set_code = card.get("set", "").upper()
        if not name:
            print(f"  Skip (no name): {path.name}")
            continue

        base = _sanitize_filename(f"{name} ({set_code})")
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 1

        new_name = f"{base}{path.suffix}"
        dest = path.parent / new_name

        if path.resolve() == dest.resolve():
            continue
        if dest.exists() and path != dest:
            print(f"  Skip (dest exists): {path.name} -> {new_name}")
            continue

        if dry_run:
            print(f"  Would rename: {path.name} -> {new_name}")
        else:
            path.rename(dest)
            print(f"  Renamed: {path.name} -> {new_name}")
        renamed += 1

    return renamed


def _parse_sorted_filename(path: Path) -> tuple[str, str] | None:
    """Parse 'Card Name (set).ext' -> (name, set). Returns None if unparseable."""
    stem = path.stem
    match = re.match(r"^(.+)\s+\(([a-z0-9]+)\)$", stem, re.I)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).lower()


def rename_sorted(sorted_dir: Path, dry_run: bool = False) -> int:
    """
    Verify sorted filenames match Scryfall. Fix any that have wrong names (e.g. OCR errors).
    Returns count fixed.
    """
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    client = ScryfallClient()
    fixed = 0

    for group_dir in sorted_dir.iterdir():
        if not group_dir.is_dir():
            continue
        for path in group_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue

            parsed = _parse_sorted_filename(path)
            if not parsed:
                continue

            name_in_file, set_code = parsed
            # Look up by set + name (restore // from __ for double-faced)
            search_name = name_in_file.replace(" __ ", " // ")
            card = client.get_by_fuzzy_name(search_name, set_code)
            if not card:
                continue

            actual_name = card.get("name", "")
            actual_set = card.get("set", "").upper()
            safe_name = _sanitize_filename(f"{actual_name} ({actual_set})")
            expected = f"{safe_name}{path.suffix}"

            if path.name != expected:
                dest = path.parent / expected
                if dest.exists() and path != dest:
                    print(f"  Skip (dest exists): {path.name} -> {expected}")
                    continue
                if dry_run:
                    print(f"  Would fix: {path.name} -> {expected}")
                else:
                    path.rename(dest)
                    print(f"  Fixed: {path.name} -> {expected}")
                fixed += 1

    return fixed


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    inbox = project_root / "data" / "inbox"
    sorted_dir = project_root / "data" / "sorted"

    dry_run = "--dry-run" in sys.argv

    total = 0
    if inbox.exists():
        print("Inbox:")
        total += rename_inbox(inbox, dry_run=dry_run)
        print()

    if sorted_dir.exists():
        print("Sorted:")
        total += rename_sorted(sorted_dir, dry_run=dry_run)

    print(f"\nTotal: {total} file(s) {'would be ' if dry_run else ''}renamed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
