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

import re
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import cv2

from src.cache import (
    get_cached_card,
    get_cached_ocr,
    parsed_key,
    set_cached_card,
    set_cached_ocr,
)

from src.models import CardRecord
from src.ocr import extract_text_from_image
from src.ocr_parser import parse_ocr_name_candidates, parse_ocr_text, ParsedOCR
from src.scryfall_client import ScryfallClient


def _name_tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def _name_query_matches_record(query_name: str, record_name: str) -> bool:
    """
    Conservative guard to avoid reusing/caching mismatched name-only lookups.

    For single-token queries (e.g. "Excavator"), only accept exact single-token
    card names. This prevents cache pollution from partial-name fuzzy matches like
    "Diligent Excavator" for query "Excavator".
    """
    q = _name_tokens(query_name)
    r = _name_tokens(record_name)
    if not q or not r:
        return False
    if q == r:
        return True
    if len(q) == 1:
        return len(r) == 1 and q[0] == r[0]
    return set(q).issubset(set(r))


def _is_cache_safe(parsed: ParsedOCR, record: CardRecord, query_name: Optional[str] = None) -> bool:
    """
    Decide whether a resolved card is safe to cache for this OCR parse key.
    """
    # We sometimes switch to a fallback name candidate (for example, from "Hero"
    # to "The Slayer"). Use the actual lookup name when available, so we only
    # cache results that match the name that succeeded.
    effective_query_name = query_name if query_name is not None else parsed.card_name
    if effective_query_name and not _name_query_matches_record(effective_query_name, record.name):
        return False
    # If name is missing, only trust cache when set+collector were parsed.
    if not effective_query_name:
        return bool(parsed.set_code and parsed.collector_number)
    return True


def process_image(
    image: str | Path | np.ndarray,
    scryfall: ScryfallClient,
    on_ambiguous: Optional[Callable[[str, list[dict]], Optional[dict]]] = None,
    use_cache: bool = True,
) -> tuple[Optional[CardRecord], Optional[str]]:
    """
    Process:
        image OR frame -> OCR -> parse -> Scryfall -> CardRecord
    """

    # -----------------------------
    # Normalize input
    # -----------------------------
    path: Path | None = None
    frame: np.ndarray | None = None

    if isinstance(image, (str, Path)):
        path = Path(image)
        if not path.exists():
            return None, f"File not found: {path}"

    elif isinstance(image, np.ndarray):
        frame = image

    else:
        return None, "Unsupported input type"

    # -----------------------------
    # OCR
    # -----------------------------
    text: str | None = None

    # cache only applies to file inputs
    if path is not None and use_cache:
        text = get_cached_ocr(path)

    if text is None:
        try:
            if path is not None:
                text = extract_text_from_image(path)
            else:
                text = extract_text_from_array(frame)
        except Exception as e:
            return None, f"OCR failed: {e}"

        if path is not None and use_cache and text:
            set_cached_ocr(path, text)

    if not text or not text.strip():
        return None, "OCR returned empty result"

    # -----------------------------
    # Parse OCR
    # -----------------------------
    parsed = parse_ocr_text(text)

    if not parsed.card_name and not (
        parsed.set_code and parsed.collector_number
    ):
        return None, "Could not extract card identity"

    # -----------------------------
    # Cache lookup (card)
    # -----------------------------
    key = parsed_key(
        parsed.collector_number,
        parsed.set_code,
        parsed.card_name,
    )

    if use_cache:
        cached = get_cached_card(key)
        # Only trust cached data when the cached name still matches what OCR saw.
        # This avoids a bad old match being reused forever.
        if cached and _is_cache_safe(parsed, cached):
            return cached, None

    # Step 4: Scryfall lookup - fetch full card data from the API
    used_query_name = parsed.card_name
    card_data = scryfall.identify_card(
        parsed.collector_number,
        parsed.set_code,
        used_query_name,
        on_ambiguous=on_ambiguous,
    )

    # Name fallback: OCR may return a type-line token ("Hero") before the actual
    # title ("The Slayer"). Try additional title-like lines before failing.
    if not card_data and text:
        for candidate in parse_ocr_name_candidates(text, max_candidates=5):
            # Skip empty or duplicate candidate names.
            if not candidate or candidate.lower() == (used_query_name or "").lower():
                continue
            candidate_data = scryfall.identify_card(
                parsed.collector_number,
                parsed.set_code,
                candidate,
                on_ambiguous=on_ambiguous,
            )
            if candidate_data:
                card_data = candidate_data
                used_query_name = candidate
                break

    if not card_data:
        return None, f"Card not found: {parsed.card_name}"

    # -----------------------------
    # Build record
    # -----------------------------
    record = CardRecord.from_scryfall(card_data)
    if use_cache and _is_cache_safe(parsed, record, query_name=used_query_name):
        set_cached_card(key, record)

    return record, None


# ============================================================
# BATCH MODE
# ============================================================
def process_images_batch(
    image_paths: list[str | Path],
    scryfall: ScryfallClient,
    on_ambiguous: Optional[Callable[[str, list[dict]], Optional[dict]]] = None,
    use_cache: bool = True,
) -> tuple[list[CardRecord], list[tuple[str, str]]]:

    cards: list[CardRecord] = []
    errors: list[tuple[str, str]] = []

    for p in image_paths:
        record, err = process_image(p, scryfall, on_ambiguous, use_cache)

        if record:
            cards.append(record)
        if err:
            errors.append((str(p), err))

    return cards, errors