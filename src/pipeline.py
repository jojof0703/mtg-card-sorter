"""
End-to-end pipeline: image/frame -> OCR -> parse -> Scryfall -> CardRecord
"""

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
from src.ocr_parser import parse_ocr_text
from src.scryfall_client import ScryfallClient


# ============================================================
# FRAME → OCR ADAPTER
# ============================================================
def extract_text_from_array(frame: np.ndarray) -> str:
    """
    Bridges OpenCV frames into existing file-based OCR pipeline.
    """
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(tmp.name, frame)

    return extract_text_from_image(tmp.name)


# ============================================================
# MAIN PIPELINE
# ============================================================
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
        if cached:
            return cached, None

    # -----------------------------
    # Scryfall lookup
    # -----------------------------
    card_data = scryfall.identify_card(
        parsed.collector_number,
        parsed.set_code,
        parsed.card_name,
        on_ambiguous=on_ambiguous,
    )

    if not card_data:
        return None, f"Card not found: {parsed.card_name}"

    # -----------------------------
    # Build record
    # -----------------------------
    record = CardRecord.from_scryfall(card_data)

    if use_cache:
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