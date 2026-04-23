"""
Local cache for OCR and Scryfall results.

To avoid repeating expensive work, we cache two things:

1. OCR RESULTS: Reading text from an image uses Google's Vision API (costs money,
   takes time). If we've already OCR'd an image, we store the text and reuse it.
   Key = filename + hash of image content (so we detect if the image changed).

2. SCRYFALL RESULTS: Looking up a card by name/set/number uses the Scryfall API.
   We cache the card data so we don't hit the API again for the same card.
   Key = "collector_number|set_code|card_name".

Cache files live in ~/.mtg_card_sorter/ (your home folder).
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from src.models import CardRecord


def _image_hash(path: Path) -> str:
    """
    Content hash of image for cache key.

    We use SHA256 (first 16 chars) so that if you replace an image file
    with the same name but different content, we re-run OCR instead of
    returning stale cached text.
    """
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _cache_dir() -> Path:
    """Directory for all cache files: ~/.mtg_card_sorter/"""
    d = Path.home() / ".mtg_card_sorter"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ocr_cache_path() -> Path:
    return _cache_dir() / "ocr_cache.json"


def _scryfall_cache_path() -> Path:
    return _cache_dir() / "scryfall_cache.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_cached_ocr(image_path: str | Path) -> Optional[str]:
    """
    Return cached OCR text for image, or None if not cached.

    Cache key = filename + hash of file contents. So "card1.png" and "card2.png"
    with different content get different cache entries.
    """
    path = Path(image_path)
    if not path.exists():
        return None
    key = f"{path.name}_{_image_hash(path)}"
    cache = _load_json(_ocr_cache_path())
    return cache.get(key)


def set_cached_ocr(image_path: str | Path, text: str) -> None:
    """Save OCR text for this image so we reuse it next time."""
    path = Path(image_path)
    key = f"{path.name}_{_image_hash(path)}"
    cache = _load_json(_ocr_cache_path())
    cache[key] = text
    _save_json(_ocr_cache_path(), cache)


def get_cached_card(parsed_key: str) -> Optional[CardRecord]:
    """
    Get cached CardRecord by parsed identifier key.

    Key format: "collector_number|set_code|card_name" (lowercase).
    If we've looked up this exact card before, we return it without hitting API.
    """
    cache = _load_json(_scryfall_cache_path())
    data = cache.get(parsed_key)
    if data:
        return CardRecord.from_dict(data)
    return None


def set_cached_card(parsed_key: str, card: CardRecord) -> None:
    """Cache CardRecord by parsed identifier key."""
    cache = _load_json(_scryfall_cache_path())
    cache[parsed_key] = card.to_dict()
    _save_json(_scryfall_cache_path(), cache)


def parsed_key(collector_number: str, set_code: str, card_name: str) -> str:
    """
    Build cache key from parsed OCR identifiers.

    Example: parsed_key("123", "M21", "Lightning Bolt") -> "123|m21|lightning bolt"
    """
    parts = [collector_number or "", set_code or "", card_name or ""]
    return "|".join(p.strip().lower() for p in parts)
