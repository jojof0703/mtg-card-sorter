"""
Command-Line Interface (CLI) for MTG Card Sorter.

This is the main entry point when you run the program from the terminal.
It provides two ways to use the app:

1. INTERACTIVE MODE (default): Run `python -m src.cli` with no arguments.
   You'll see a menu to scan images, sort cards, clear data, or quit.

2. COMMAND MODE: Run specific commands like:
   - `python -m src.cli dataset build`     - Download card images for testing
   - `python -m src.cli dataset ocr-eval`  - Measure how accurate our OCR is
   - `python -m src.cli scan-inbox`        - Process images in data/inbox and sort them

MTG = Magic: The Gathering, a trading card game. Each card has a name,
set code (e.g. "M21"), and collector number (e.g. "123/280").
"""

import argparse
import json
import sys
from pathlib import Path

from src.cache import _cache_dir
from src.models import CardRecord

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

    return 0


def _cmd_dataset_build(args: argparse.Namespace) -> int:
    """Build dataset: download card images from Scryfall into data/datasets/<name>/."""
    from src.dataset.build_dataset import build_dataset

    out = Path(args.out)
    build_dataset(
        name=args.name,
        per_group=args.per_group,
        out_dir=out,
        unique="prints" if args.prints else "cards",
    )
    print(f"Dataset built: {out / args.name}")
    return 0


def _cmd_scan_inbox(args: argparse.Namespace) -> int:
    """Scan images in inbox, identify cards, sort into output folders."""
    from src.dataset.scan_inbox import scan_and_sort, seed_inbox

    inbox = Path(args.inbox).resolve()
    out_dir = Path(args.out_dir).resolve()
    mode = args.mode

    if getattr(args, "seed", None) is not None:
        dataset_root = (Path("data/datasets") / "baseline_v1").resolve()
        if not dataset_root.exists():
            print(f"Error: dataset not found at {dataset_root}. Run: python -m src.cli dataset build")
            return 1
        n = seed_inbox(inbox, dataset_root, args.seed)
        print(f"Seeded inbox with {n} images from dataset.")

    ok, err_count, errors = scan_and_sort(inbox, out_dir, mode=mode)
    if ok == 0 and err_count == 0:
        print(f"No images in {inbox}. Add .png/.jpg files or use --seed 5 to copy samples.")
        return 0
    print(f"Identified {ok} card(s), sorted into {out_dir}/")
    if err_count:
        print(f"Errors ({err_count}):")
        for path, msg in errors:
            print(f"  {path}: {msg}")
    return 0 if err_count == 0 else 1


def _cmd_dataset_ocr_eval(args: argparse.Namespace) -> int:
    """Run OCR evaluation on dataset: measure identification accuracy."""
    from src.dataset.ocr_eval import run_ocr_eval, write_results

    out = Path(args.out)
    dataset_root = out / args.name
    if not dataset_root.exists():
        print(f"Error: dataset not found at {dataset_root}")
        return 1

    results = run_ocr_eval(
        dataset_root=dataset_root,
        limit=args.limit,
        use_document_ocr=True,
    )
    write_results(dataset_root, results)

    print(f"Accuracy: {results['accuracy']:.1%} ({results['correct']}/{results['total']})")
    print("By group:", results["by_group"])
    print(f"Failures: {results['failures_count']} -> failures.csv")
    print(f"Results: {dataset_root / 'results.json'}")
    return 0


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments. Defines subcommands: dataset (build, ocr-eval), scan-inbox."""
    parser = argparse.ArgumentParser(prog="mtg-card-sorter")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    ds_parser = subparsers.add_parser("dataset", help="Dataset harness")
    ds_sub = ds_parser.add_subparsers(dest="dataset_cmd", required=True)

    build_p = ds_sub.add_parser("build", help="Build dataset from Scryfall")
    build_p.add_argument("--name", default="baseline_v1", help="Dataset name")
    build_p.add_argument("--per_group", type=int, default=50, help="Images per group")
    build_p.add_argument("--out", default="data/datasets", help="Output directory")
    build_p.add_argument("--prints", action="store_true", help="unique=prints (default)")
    build_p.add_argument("--cards", dest="prints", action="store_false", help="unique=cards")
    build_p.set_defaults(prints=True)

    eval_p = ds_sub.add_parser("ocr-eval", help="Run OCR evaluation")
    eval_p.add_argument("--name", default="baseline_v1", help="Dataset name")
    eval_p.add_argument("--out", default="data/datasets", help="Dataset root")
    eval_p.add_argument("--limit", type=int, default=200, help="Max items to evaluate")

    scan_p = subparsers.add_parser("scan-inbox", help="OCR images in inbox, sort into folders")
    scan_p.add_argument("--in", dest="inbox", default="data/inbox", help="Input directory with images")
    scan_p.add_argument("--out", dest="out_dir", default="data/sorted", help="Output directory for sorted folders")
    scan_p.add_argument("--mode", choices=["color", "type", "value"], default="type",
                        help="Sort mode: color, type (Creatures/Lands/etc), or value")
    scan_p.add_argument("--seed", type=int, metavar="N",
                        help="Copy N random images from dataset into inbox first (for demo)")

    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.command == "dataset":
        if args.dataset_cmd == "build":
            sys.exit(_cmd_dataset_build(args))
        if args.dataset_cmd == "ocr-eval":
            sys.exit(_cmd_dataset_ocr_eval(args))
        print("Use: dataset build | dataset ocr-eval")
        sys.exit(1)

    if args.command == "scan-inbox":
        sys.exit(_cmd_scan_inbox(args))

    # No command: interactive mode
    sys.exit(main())
