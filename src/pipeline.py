"""
End-to-end pipeline: image -> OCR -> parse -> Scryfall -> CardRecord.

This is the core workflow. Given a photo of an MTG card, we:

1. OCR (Optical Character Recognition): Extract raw text from the image
   using Google Cloud Vision. Result: a blob of text like "Lightning Bolt\n..."
2. PARSE: Pull out the card name, set code (e.g. M21), and collector number
   from that text. OCR is messy, so we use regex and heuristics.
3. SCRYFALL LOOKUP: Use those identifiers to fetch full card data from
   Scryfall's free API (name, colors, type, price, etc.).
4. CARD RECORD: Convert Scryfall's response into our CardRecord format.

We cache OCR and Scryfall results to avoid repeating API calls.
"""

from pathlib import Path
from typing import Callable, Optional

from src.cache import get_cached_card, get_cached_ocr, parsed_key, set_cached_card, set_cached_ocr
from src.models import CardRecord
from src.ocr import extract_text_from_image
from src.ocr_parser import parse_ocr_text, ParsedOCR
from src.scryfall_client import ScryfallClient


def process_image(
    image_path: str | Path,
    scryfall: ScryfallClient,
    on_ambiguous: Optional[Callable[[str, list[dict]], Optional[dict]]] = None,
    use_cache: bool = True,
) -> tuple[Optional[CardRecord], Optional[str]]:
    """
    Process one image: OCR -> parse -> Scryfall -> CardRecord.

    Args:
        image_path: Path to the card image file (PNG, JPG, etc.)
        scryfall: Client for looking up cards on Scryfall
        on_ambiguous: Optional callback when multiple cards match; user picks one
        use_cache: If True, reuse cached OCR and Scryfall results

    Returns:
        (CardRecord, None) on success, or (None, error_message) on failure.
        Error messages are user-friendly (e.g. "Re-take photo with better lighting").
    """
    path = Path(image_path)
    if not path.exists():
        return None, f"File not found: {path}"

    # Step 1: OCR (Optical Character Recognition) - extract text from image
    # We check cache first to avoid calling Google Vision API again
    text = None
    if use_cache:
        text = get_cached_ocr(path)
    if text is None:
        try:
            text = extract_text_from_image(path)
        except Exception as e:
            return None, f"OCR failed: {e}. Try better lighting and fill the frame."
        if use_cache and text:
            set_cached_ocr(path, text)

    if not text or not text.strip():
        return None, "OCR could not extract text. Re-take photo with better lighting and fill frame."

    # Step 2: Parse - extract card name, set code, collector number from raw text
    parsed = parse_ocr_text(text)
    if not parsed.card_name and not (parsed.set_code and parsed.collector_number):
        return None, "Could not extract card name or set+number. Re-take photo with better lighting."

    # Step 3: Check cache - have we looked up this card before?
    key = parsed_key(parsed.collector_number, parsed.set_code, parsed.card_name)
    if use_cache:
        cached = get_cached_card(key)
        if cached:
            return cached, None

    # Step 4: Scryfall lookup - fetch full card data from the API
    card_data = scryfall.identify_card(
        parsed.collector_number,
        parsed.set_code,
        parsed.card_name,
        on_ambiguous=on_ambiguous,
    )

    if not card_data:
        return None, f"Could not identify card (name: {parsed.card_name}). Try clearer photo."

    record = CardRecord.from_scryfall(card_data)
    if use_cache:
        set_cached_card(key, record)
    return record, None


def process_images_batch(
    image_paths: list[str | Path],
    scryfall: ScryfallClient,
    on_ambiguous: Optional[Callable[[str, list[dict]], Optional[dict]]] = None,
    use_cache: bool = True,
) -> tuple[list[CardRecord], list[tuple[str, str]]]:
    """
    Process multiple images. Returns (cards, [(path, error), ...]).

    Loops over each path, calls process_image, and collects successes
    and failures. Useful for batch scanning (e.g. 10 photos at once).
    """
    cards: list[CardRecord] = []
    errors: list[tuple[str, str]] = []

    for p in image_paths:
        record, err = process_image(p, scryfall, on_ambiguous, use_cache)
        if record:
            cards.append(record)
        if err:
            errors.append((str(p), err))

    return cards, errors
