"""
CLI (terminal) for this project.

Simple usage:
1) `python -m src.cli` -> interactive menu
2) `python -m src.cli scan-inbox ...` -> run one command directly

This text is intentionally simple for beginner readers.
"""

import argparse
import json
import sys
from pathlib import Path

from src.cache import _cache_dir
from src.models import CardRecord
import cv2
import time

from src.pipeline import process_image


def run_camera_scan(scryfall):
    import cv2
    import time

    cam = cv2.VideoCapture(1)

    last_time = 0
    cooldown = 2
    last_result = None

    print("Starting camera... press Q to quit")

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        #h, w, _ = frame.shape
        #frame_crop = frame[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]

        now = time.time()

        if now - last_time > cooldown:
            try:
                record, err = process_image(frame, scryfall)
            except Exception as e:
                print("OCR error:", e)
                record = None

            last_time = now

            if record:
                last_result = record
                print("CARD:", getattr(record, "name", record))

        if last_result:
            cv2.putText(
                frame,
                getattr(last_result, "name", str(last_result)),
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

        cv2.imshow("MTG Camera Scan", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()
    
SORT_MODES = {
    "1": ("color", "Color Bucket (Mono/Multi/Colorless/Lands)"),
    "2": ("type", "Card Type (Creatures/Spells/Permanents/Lands)"),
    "3": ("value", "Value (Hits/Good Stuff/Playable/Bulk)"),
}

DATA_FILE = _cache_dir() / "cards.json"


def _load_cards() -> list[CardRecord]:
    """Load the list of identified cards from disk (cards.json in cache dir)."""
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [CardRecord.from_dict(d) for d in data]
    except (json.JSONDecodeError, OSError):
        return []


def _save_cards(cards: list[CardRecord]) -> None:
    """Persist the card list to disk so we don't lose it between runs."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in cards], f, indent=2)


def _interactive_ambiguous(ocr_name: str, candidates: list[dict]) -> dict | None:
    """
    Let user pick from ambiguous results when multiple cards match.

    Sometimes the OCR'd name matches several different cards (e.g. "Bolt" could
    be Lightning Bolt, Arc Lightning, etc.). We show the top 3 candidates and
    let the user choose, or skip if none are correct.
    """
    print(f"\n  Multiple matches for '{ocr_name}'. Top candidates:")
    for i, c in enumerate(candidates[:3], 1):
        name = c.get("name", "?")
        set_code = c.get("set", "?")
        print(f"    {i}. {name} ({set_code})")
    print("    0. Skip this card")
    try:
        choice = input("  Enter number (1-3 or 0): ").strip()
        n = int(choice)
        if n == 0:
            return None
        if 1 <= n <= len(candidates):
            return candidates[n - 1]
    except (ValueError, EOFError):
        pass
    return candidates[0] if candidates else None


def _print_bins(groups: dict[str, list]) -> None:
    """Print each sort group with its cards and prices to the terminal."""
    for label, items in groups.items():
        print(f"\n  [{label}] ({len(items)} cards)")
        for c in items:
            price = c.effective_usd_price() if hasattr(c, "effective_usd_price") else None
            price_str = f" ${price:.2f}" if price else ""
            print(f"    - {c.name} ({c.set}){price_str}")


def main() -> int:
    """
    Run the interactive menu loop. Returns 0 on normal exit.
    User can: scan images, sort & view bins, clear cards, or quit.
    """
    from src.scryfall_client import ScryfallClient
    from src.sorting import sort_cards
    from src.pipeline import process_images_batch

    print("=== MTG Card Sorter ===\n")
    scryfall = ScryfallClient()
    cards = _load_cards()

    while True:
        print("\nOptions:")
        print("  1. Scan images (add cards)")
        print("  2. Sort & view bins")
        print("  3. Clear all cards")
        print("  4. Quit")
        print("  5. Use Phone Camera To Scan")
        choice = input("Choice: ").strip()

        if choice == "4":
            break

        if choice == "1":
            paths_input = input("Image path(s), comma-separated: ").strip()
            if not paths_input:
                continue
            paths = [p.strip() for p in paths_input.split(",") if p.strip()]
            if not paths:
                continue
            print("Processing...")
            new_cards, errors = process_images_batch(
                paths, scryfall, on_ambiguous=_interactive_ambiguous
            )
            cards.extend(new_cards)
            _save_cards(cards)
            print(f"  Added {len(new_cards)} card(s).")
            for path, err in errors:
                print(f"  Error [{path}]: {err}")

        elif choice == "2":
            if not cards:
                print("  No cards. Scan images first.")
                continue
            print("\nSort modes:")
            for k, (_, desc) in SORT_MODES.items():
                print(f"  {k}. {desc}")
            mode_choice = input("Mode (1-3): ").strip()
            mode_key = SORT_MODES.get(mode_choice, ("color", ""))[0]
            groups = sort_cards(cards, mode_key)
            _print_bins(groups)

        elif choice == "3":
            cards = []
            _save_cards(cards)
            print("  Cleared.")

        elif choice == "5":
            run_camera_scan(scryfall)


    return 0


def _cmd_scan_inbox(args: argparse.Namespace) -> int:
    """Scan images in inbox, identify cards, sort into output folders."""
    from src.dataset.scan_inbox import scan_and_sort

    inbox = Path(args.inbox).resolve()
    out_dir = Path(args.out_dir).resolve()
    mode = args.mode
    ok, err_count, errors = scan_and_sort(inbox, out_dir, mode=mode, use_cache=True)
    if ok == 0 and err_count == 0:
        print(f"No images in {inbox}. Add .png/.jpg files or use --seed 5 to copy samples.")
        return 0
    print(f"Identified {ok} card(s), sorted into {out_dir}/")
    if err_count:
        print(f"Errors ({err_count}):")
        for path, msg in errors:
            print(f"  {path}: {msg}")
    return 0 if err_count == 0 else 1


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments. Defines subcommands: scan-inbox."""
    parser = argparse.ArgumentParser(prog="mtg-card-sorter")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    scan_p = subparsers.add_parser("scan-inbox", help="OCR images in inbox, sort into folders")
    scan_p.add_argument("--in", dest="inbox", default="data/inbox", help="Input directory with images")
    scan_p.add_argument("--out", dest="out_dir", default="data/sorted", help="Output directory for sorted folders")
    scan_p.add_argument("--mode", choices=["color", "type", "value"], default="type",
                        help="Sort mode: color, type (Creatures/Lands/etc), or value")

    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.command == "scan-inbox":
        sys.exit(_cmd_scan_inbox(args))

    # No command: interactive mode
    sys.exit(main())
