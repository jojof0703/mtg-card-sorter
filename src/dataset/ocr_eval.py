"""
OCR evaluation harness: run Vision OCR and measure card identification accuracy.

Given a dataset (from build_dataset) with metadata.jsonl, we:
1. Run Vision OCR on each image (or use cached ocr/*.txt)
2. Parse collector/set/name from OCR text
3. Look up the card on Scryfall (same logic as the main pipeline)
4. Compare predicted card vs expected (from metadata)

Output: results.json (accuracy, by_group), failures.csv (wrong/missed cards).
Use scripts/debug_ocr_failure.py to inspect individual failures.
"""

import csv
import json
from pathlib import Path
from typing import Optional

from src.ocr_parsing import parse_ocr_for_lookup
from src.services.scryfall_client import ScryfallClient
from src.services.vision_ocr import VisionOCR


def _similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity 0-1. Used to pick best match from search results."""
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    wa, wb = set(a.split()), set(b.split())
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def _best_match(name: str, cards: list[dict]) -> Optional[dict]:
    """From a list of cards, return the one with highest name similarity to `name`."""
    if not cards:
        return None
    return max(cards, key=lambda c: _similarity(name, c.get("name", "")))


def identify_card_from_ocr(
    client: ScryfallClient,
    collector_number: Optional[str],
    set_code: Optional[str],
    name_guess: str,
) -> Optional[dict]:
    """
    Identify card via Scryfall. Same logic as main pipeline but uses services client.

    Order: 1) set+collector (exact), 2) fuzzy name (try A- for showcase), 3) search+similarity.
    Validates set+collector result against name (wrong parsing can return wrong card).
    """
    if set_code and collector_number:
        card = client.get_card_by_collector(set_code, collector_number)
        if card and name_guess:
            # Validate: wrong set/collector parsing often returns wrong card
            card_name = card.get("name", "")
            if " // " in card_name:
                card_names = [n.strip() for n in card_name.split(" // ")]
            else:
                card_names = [card_name]
            if any(_similarity(n, name_guess) >= 0.5 for n in card_names):
                return card
            # Name doesn't match; fall through to name-based lookup
        elif card and not name_guess:
            return card

    if name_guess:
        card = client.get_card_by_fuzzy_name(name_guess, set_code)
        card_a = None
        if not name_guess.startswith("A-"):
            card_a = client.get_card_by_fuzzy_name(f"A-{name_guess}", set_code)
            # OCR often drops "A-"; wrong set_code (e.g. artist name) can make A- lookup fail
            if not card_a and set_code:
                card_a = client.get_card_by_fuzzy_name(f"A-{name_guess}", None)
        # When both exist: prefer A- (showcase) as OCR often drops prefix
        if card and card_a:
            return card_a
        if card_a:
            return card_a
        if card:
            return card

    if not name_guess:
        return None

    results = client.search_cards_list(name_guess)
    card = _best_match(name_guess, results)
    if not card and not name_guess.startswith("A-"):
        results_a = client.search_cards_list(f"A-{name_guess}")
        card = _best_match(f"A-{name_guess}", results_a) if results_a else None
    return card


def run_ocr_eval(
    dataset_root: Path,
    limit: Optional[int] = 200,
    use_document_ocr: bool = True,
) -> dict:
    """
    Run OCR eval on dataset. Returns results dict.

    limit: max images to evaluate (None = all). use_document_ocr: use
    DOCUMENT_TEXT_DETECTION (better for cards) vs TEXT_DETECTION.
    """
    metadata_path = dataset_root / "metadata.jsonl"
    if not metadata_path.exists():
        raise FileNotFoundError(f"No metadata.jsonl at {dataset_root}")

    records = []
    with open(metadata_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if limit:
        records = records[:limit]

    ocr_dir = dataset_root / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)

    ocr_engine = VisionOCR(use_document=use_document_ocr)
    client = ScryfallClient()

    correct = 0
    total = len(records)
    by_group: dict[str, dict] = {}
    failures: list[dict] = []

    for rec in records:
        group = rec.get("group", "unknown")
        if group not in by_group:
            by_group[group] = {"correct": 0, "total": 0}

        expected_id = rec.get("scryfall_id", "")
        image_path = dataset_root / rec.get("image_path", "")
        expected_name = rec.get("name", "")

        if not image_path.exists():
            failures.append({
                "group": group,
                "expected_id": expected_id,
                "predicted_id": "",
                "expected_name": expected_name,
                "predicted_name": "",
                "image_path": str(image_path),
                "ocr_snippet": "",
                "reason": "image_not_found",
            })
            by_group[group]["total"] += 1
            continue

        # Cache key: stem of image filename
        cache_stem = Path(rec["image_path"]).stem
        cache_path = ocr_dir / f"{cache_stem}.txt"

        try:
            image_bytes = image_path.read_bytes()
            ocr_text = ocr_engine.extract_text_cached(image_bytes, cache_path)
        except Exception as e:
            failures.append({
                "group": group,
                "expected_id": expected_id,
                "predicted_id": "",
                "expected_name": expected_name,
                "predicted_name": "",
                "image_path": str(image_path),
                "ocr_snippet": str(e)[:200],
                "reason": "ocr_error",
            })
            by_group[group]["total"] += 1
            continue

        collector, set_code, name_guess = parse_ocr_for_lookup(ocr_text)

        if not name_guess and not (set_code and collector):
            failures.append({
                "group": group,
                "expected_id": expected_id,
                "predicted_id": "",
                "expected_name": expected_name,
                "predicted_name": "",
                "image_path": str(image_path),
                "ocr_snippet": ocr_text[:200] if ocr_text else "(no text)",
                "reason": "no_text",
            })
            by_group[group]["total"] += 1
            continue

        card = identify_card_from_ocr(client, collector, set_code, name_guess)
        predicted_id = card.get("id", "") if card else ""
        predicted_name = card.get("name", "") if card else ""

        by_group[group]["total"] += 1
        # Correct if exact UUID match, or same card name (different printing)
        is_correct = predicted_id == expected_id or (
            predicted_name and predicted_name == expected_name
        )
        if is_correct:
            correct += 1
            by_group[group]["correct"] += 1
        else:
            failures.append({
                "group": group,
                "expected_id": expected_id,
                "predicted_id": predicted_id,
                "expected_name": expected_name,
                "predicted_name": predicted_name,
                "image_path": str(image_path),
                "ocr_snippet": ocr_text[:200] if ocr_text else "",
                "reason": "wrong_card",
            })

    accuracy = correct / total if total else 0
    group_acc = {
        g: (d["correct"] / d["total"] if d["total"] else 0)
        for g, d in by_group.items()
    }

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "by_group": group_acc,
        "failures_count": len(failures),
        "failures": failures,
    }


def write_results(dataset_root: Path, results: dict) -> None:
    """Write results.json (summary) and failures.csv (detailed failure list)."""
    results_path = dataset_root / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        out = {k: v for k, v in results.items() if k != "failures"}
        json.dump(out, f, indent=2)

    failures_path = dataset_root / "failures.csv"
    failures = results.get("failures", [])
    if failures:
        with open(failures_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["group", "expected_id", "predicted_id", "expected_name", "predicted_name", "image_path", "ocr_snippet", "reason"])
            w.writeheader()
            w.writerows(failures)
