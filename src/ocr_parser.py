"""
Parse OCR output into card identifiers for Scryfall lookup.

This is a thin wrapper around ocr_parsing. It takes the raw OCR text,
calls parse_ocr_for_lookup() to get (collector, set_code, name), and
returns a ParsedOCR dataclass. We also clean the name (remove junk chars)
and handle empty/missing values.

The pipeline uses ParsedOCR to decide what to send to Scryfall.
"""

import re
from dataclasses import dataclass

from src.ocr_parsing import parse_name_candidates, parse_ocr_for_lookup


@dataclass
class ParsedOCR:
    """
    Parsed identifiers from card OCR.

    Holds the three things we extracted from the image text, plus the
    raw text for debugging. Empty strings mean we couldn't find that field.
    """

    collector_number: str
    set_code: str
    card_name: str
    raw_text: str


def _clean_name(s: str) -> str:
    """Remove junk chars (punctuation, etc.) that break Scryfall fuzzy lookup."""
    s = re.sub(r"[^\w\s\-'./]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_ocr_text(raw_text: str) -> ParsedOCR:
    """
    Parse OCR output into best identifiers.

    Delegates to parse_ocr_for_lookup() in ocr_parsing, then wraps the
    result in a ParsedOCR with cleaned name and empty-string fallbacks.
    """
    collector, set_code, name = parse_ocr_for_lookup(raw_text or "")
    return ParsedOCR(
        collector_number=collector or "",
        set_code=set_code or "",
        card_name=_clean_name(name) if name else "",
        raw_text=raw_text or "",
    )


def parse_ocr_name_candidates(raw_text: str, max_candidates: int = 5) -> list[str]:
    """
    Return likely card-name candidates from OCR text, ordered best-first.
    """
    if not raw_text or not raw_text.strip():
        return []
    lines = [ln.strip() for ln in raw_text.strip().splitlines() if ln.strip()]
    if not lines:
        return []
    return parse_name_candidates(lines, max_candidates=max_candidates)
