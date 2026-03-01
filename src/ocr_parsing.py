"""
Shared OCR parsing logic for MTG card identification.

When we run OCR (Optical Character Recognition) on a card image, we get
raw text—often messy, with line breaks and odd formatting. This module
extracts the three things we need to look up the card on Scryfall:

1. COLLECTOR NUMBER: The card's number in its set (e.g. 123/280, R 0263,
   A-257 for showcase cards). Formats vary: 123/280, 263s, ★123, etc.
2. SET CODE: 3–5 letter code (e.g. M21, 2XM, DOM). Appears near the bottom.
3. CARD NAME: From the top of the card. We skip type-line words like
   "Creature" or "Legendary" that OCR sometimes picks up first.

We use regex (regular expressions) to find these patterns. The logic is
complex because real cards have many formats (different sets, languages,
special printings like "A-" for showcase).
"""

import re
from typing import Optional

# Words that look like set codes (3-5 chars) but aren't. Exclude these when
# guessing the set from OCR. Includes: language codes (EN), card text (TAP,
# MAN), artist names, copyright words (WOTC, INC), etc.
_SET_CODE_EXCLUDE = frozenset({
    "THE", "AND", "FOR", "ART", "TAP", "MAN", "123", "280", "INC", "WOTC",
    "EN", "DOM", "LAY", "ILL", "TM", "ALL", "RES", "RIGHTS", "RESERVED",
    "COAST", "WIZARDS", "VIACOM", "COPY", "RIGHT", "YEAR", "GOD", "BAT",
    "ADD", "ONE", "TWO", "PUT", "TAP", "CRE", "SOR", "INS", "ENC",
    "ROGUE", "WARRIOR", "WIZARD", "CLERIC", "SPEND", "MANA", "ONLY",
    "AVON", "HUMAN", "MONK",  # artist/type-line words mistaken for set codes
})

# Type-line words to skip when extracting card name (first word only)
_NAME_SKIP_FIRST = frozenset({
    "legendary", "creature", "instant", "sorcery", "artifact", "enchantment",
    "land", "planeswalker", "tribal", "basic", "world",
})


def _normalize_ocr(s: str) -> str:
    """Collapse multiple spaces/newlines into one space, trim edges."""
    return re.sub(r"\s+", " ", s).strip()


def parse_collector_number(lines: list[str]) -> Optional[str]:
    """Extract collector number from bottom lines.

    Supports formats:
    - 123/280, 123/280a
    - R 0263, U 0270, M 0316 (rarity letter + space + digits)
    - 262/275 U, 263/280 M10 (slash with optional suffix)
    - A-257, A-253 (ZNR/KHM showcase)
    - 2XM-309 (plst style)
    - 263s, 42a (number with suffix)
    - ★123, *123
    - 243/ (truncated)
    - 347/383 (copyright line - prefer larger numbers near bottom)
    """
    # Collector number is usually at the bottom of the card. We look at last 6 lines.
    bottom_lines = lines[-6:] if len(lines) >= 6 else lines
    # We collect multiple candidates with a priority score. Lines nearer the bottom
    # get higher priority (we process reversed, so earlier = lower on card).
    candidates: list[tuple[str, int]] = []  # (value, priority: higher = better)

    for i, line in enumerate(reversed(bottom_lines)):
        line = line.strip()
        if not line:
            continue

        # Format: Rarity letter + space + digits (e.g. R 0263, U 0270)
        # WUBRGCML = White, Blue, Black, Red, Green, Colorless, Multicolor, Land
        m = re.search(r"\b([WUBRGCML])\s+0*(\d{1,5})([a-zA-Z]?)\b", line, re.I)
        if m:
            num = m.group(2) + m.group(3)
            if int(m.group(2)) <= 9999:  # Sanity: collector numbers are typically < 10000
                candidates.append((num, 100 - i))
                continue

        # A-257, A-253 (ZNR/KHM showcase - full string is collector number)
        m = re.search(r"\b([A-Z])-(\d{1,4})\b", line)
        if m:
            candidates.append((f"{m.group(1)}-{m.group(2)}", 95 - i))
            continue

        # 2XM-309 (plst style)
        m = re.search(r"\b([A-Z0-9]{2,4})-(\d{1,5})\b", line)
        if m:
            full = f"{m.group(1)}-{m.group(2)}"
            if m.group(1).upper() in ("2XM", "2X2", "CLB", "DMR", "PLST"):
                candidates.append((full, 90 - i))
                continue

        # Format: 123/280 or 123/280a (collector number / set size)
        # Skip power/toughness like 1/3, 2/2 (creatures have P/T, usually small numbers)
        m = re.search(r"(\d{1,5})\s*/\s*(\d{1,5})([a-zA-Z]?)\b", line)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= 9999 and not (a <= 6 and b <= 6):  # skip P/T like 1/3, 2/2
                num = m.group(1) + m.group(3)
                candidates.append((num, 85 - i))
                continue

        # Truncated: 243/ or 325/
        m = re.search(r"(\d{1,5})/\s*$", line)
        if m and int(m.group(1)) <= 9999:
            candidates.append((m.group(1), 70 - i))
            continue

        # ★123 or *123 or 263s (standalone)
        m = re.search(r"[★\*]?\s*(\d{1,5})([a-zA-Z]?)\b", line)
        if m:
            num = m.group(1) + m.group(2)
            # Avoid power/toughness (1/1, 2/2, 3/3, 4/4, 5/5) - usually small
            n = int(m.group(1))
            if n >= 10 and n <= 9999:  # Collector numbers typically 10-9999
                candidates.append((num, 60 - i))
                continue

        # Copyright line: "347/383" or "317/350" - last occurrence in line
        m = re.search(r"(\d{1,4})\s*/\s*(\d{1,4})\s*$", line)
        if m and int(m.group(1)) >= 10:
            candidates.append((m.group(1), 50 - i))
            continue

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]


def parse_set_code(lines: list[str]) -> Optional[str]:
    """Extract 3-5 char set code from bottom lines.

    Prefers tokens near the bottom, excludes common non-set words (EN, DOM, etc.).
    Set codes typically appear before "EN" (language) or artist name.
    Excludes 4-digit years (1990-2030) from copyright lines.
    """
    pattern = re.compile(r"\b([A-Za-z0-9]{3,5})\b")
    bottom_lines = lines[-5:] if len(lines) >= 5 else lines

    def _is_year(s: str) -> bool:
        """Exclude 4-digit years from copyright (e.g. 2025, 2026)."""
        if len(s) != 4 or not s.isdigit():
            return False
        y = int(s)
        return 1990 <= y <= 2030

    for line in reversed(bottom_lines):
        tokens = pattern.findall(line)
        for tok in tokens:
            cand = tok.upper()
            if cand in _SET_CODE_EXCLUDE:
                continue
            if _is_year(cand):
                continue
            # Prefer codes that look like set codes: start with letter, 3-5 chars
            if re.match(r"^[A-Z][A-Z0-9]{2,4}$", cand) or re.match(r"^\d[A-Z0-9]{2,3}$", cand):
                return cand
        # Also accept any 3-5 alphanumeric not in exclude (for codes like 2XM, M10)
        for tok in tokens:
            cand = tok.upper()
            if cand in _SET_CODE_EXCLUDE:
                continue
            if _is_year(cand):
                continue
            if len(cand) >= 3 and not cand.isdigit():
                return cand
    return None


def _clean_name_for_lookup(name: str) -> str:
    """Remove OCR artifacts that break Scryfall fuzzy lookup.

    - Trailing numbers (e.g. 'Aclazotz, Deepest Betrayal 3' -> 'Aclazotz, Deepest Betrayal')
    - Trailing punctuation
    """
    if not name:
        return name
    # Strip trailing " 123" or " 2" (collector/set number stuck to name line)
    name = re.sub(r"\s+\d{1,5}\s*$", "", name)
    return name.strip()


def parse_name_guess(lines: list[str]) -> str:
    """Extract card name from top lines.

    - Preserves A- prefix (A-Base Camp, A-Bretagard Stronghold)
    - Skips type-line words as first word (Legendary, Creature, etc.)
    - Prefers first substantial line that looks like a card name
    - Strips trailing numbers (OCR often attaches collector to name line)
    - Handles DFC: may get one face; caller can try both if needed
    """
    for line in lines[:12]:
        line = _normalize_ocr(line)
        if len(line) < 3:
            continue
        first_word = line.split()[0].lower() if line.split() else ""
        if first_word in _NAME_SKIP_FIRST:
            continue
        # Must have letters, reasonable length for a card name
        if not re.search(r"[A-Za-z]", line):
            continue
        if len(line) < 2 or len(line) > 80:
            continue
        # Reject lines that look like rules text (start with digit, colon, etc.)
        if re.match(r"^[\d:•\-\*]", line):
            continue
        # Reject single short tokens that are likely not names
        words = line.split()
        if len(words) == 1 and len(line) < 4:
            continue
        return _clean_name_for_lookup(line)
    return ""


def parse_ocr_for_lookup(raw_text: str) -> tuple[Optional[str], Optional[str], str]:
    """Parse OCR text into (collector_number, set_code, name_guess) for Scryfall lookup."""
    if not raw_text or not raw_text.strip():
        return None, None, ""

    lines = [ln.strip() for ln in raw_text.strip().splitlines() if ln.strip()]
    if not lines:
        return None, None, ""

    collector = parse_collector_number(lines)
    set_code = parse_set_code(lines)
    name = parse_name_guess(lines)

    return collector, set_code, name
