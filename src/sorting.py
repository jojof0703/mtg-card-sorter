"""
Three sort modes with 4 groups each.

MTG players often sort their cards in different ways. This module provides
three sorting strategies, each putting cards into 4 buckets:

1. COLOR BUCKET: Mono-Color, Multi-Color, Colorless, Lands
   (Useful for building decks by color)

2. CARD TYPE: Creatures, Spells (Instant/Sorcery), Permanents, Lands
   (Useful for organizing by what the card does)

3. VALUE: Hits (mythic/expensive), Good Stuff, Playable, Bulk
   (Useful for finding valuable cards vs. bulk)

Each function takes a list of CardRecords and returns a dict:
  { "Group Name": [card1, card2, ...], ... }
"""

from typing import Literal

from src.models import CardRecord

SortMode = Literal["color", "type", "value"]


def sort_color_bucket(cards: list[CardRecord]) -> dict[str, list[CardRecord]]:
    """
    Sort Mode A: Color Bucket (4 groups).

    MTG has 5 colors: W (white), U (blue), B (black), R (red), G (green).
    Cards can be:
    - Mono-Color: exactly 1 color (e.g. a red creature)
    - Multi-Color: 2+ colors (e.g. a red-blue spell)
    - Colorless: no colors (artifacts, some Eldrazi)
    - Lands: always go to Lands bucket regardless of color

    Returns dict like {"Mono-Color": [...], "Multi-Color": [...], ...}
    """
    groups: dict[str, list[CardRecord]] = {
        "Mono-Color": [],
        "Multi-Color": [],
        "Colorless": [],
        "Lands": [],
    }

    for c in cards:
        type_line = (c.type_line or "").lower()
        if "land" in type_line:
            groups["Lands"].append(c)
        elif len(c.colors) == 0:
            groups["Colorless"].append(c)
        elif len(c.colors) == 1:
            groups["Mono-Color"].append(c)
        else:
            groups["Multi-Color"].append(c)

    return groups


def sort_card_type(cards: list[CardRecord]) -> dict[str, list[CardRecord]]:
    """
    Sort Mode B: Card Type Simplified (4 groups).

    MTG cards have a "type line" like "Creature — Human Wizard" or
    "Instant". We bucket them as:
    - Creatures: stay on the battlefield
    - Spells: Instant or Sorcery (one-time effects)
    - Permanents: Artifact, Enchantment, Planeswalker
    - Lands: produce mana

    If a card has multiple types (e.g. "Creature — Artifact"), we use
    precedence: Lands > Creature > Spells > Permanents.
    """
    groups: dict[str, list[CardRecord]] = {
        "Creatures": [],
        "Spells": [],
        "Permanents": [],
        "Lands": [],
    }

    for c in cards:
        tl = (c.type_line or "").lower()
        if "land" in tl:
            groups["Lands"].append(c)
        elif "creature" in tl:
            groups["Creatures"].append(c)
        elif "instant" in tl or "sorcery" in tl:
            groups["Spells"].append(c)
        elif any(t in tl for t in ("artifact", "enchantment", "planeswalker")):
            groups["Permanents"].append(c)
        else:
            # Fallback: put in Permanents
            groups["Permanents"].append(c)

    return groups


def sort_value(cards: list[CardRecord]) -> dict[str, list[CardRecord]]:
    """
    Sort Mode C: How Useful / Valuable (4 groups).

    MTG has rarities: Common, Uncommon, Rare, Mythic. We combine rarity
    with market price (from Scryfall) to group cards:
    - Hits: Mythic rarity OR $10+ (the chase cards)
    - Good Stuff: Rare OR $2–$9.99
    - Playable: Uncommon OR $0.50–$1.99
    - Bulk: Common or cheap (often trade fodder)

    Uses the higher of usd and usd_foil (foil cards can be worth more).
    """
    groups: dict[str, list[CardRecord]] = {
        "Hits": [],
        "Good Stuff": [],
        "Playable Commons/Uncommons": [],
        "Bulk": [],
    }

    for c in cards:
        price = c.effective_usd_price()
        rarity = (c.rarity or "common").lower()

        if rarity == "mythic" or (price is not None and price >= 10):
            groups["Hits"].append(c)
        elif rarity == "rare" or (price is not None and 2 <= price < 10):
            groups["Good Stuff"].append(c)
        elif rarity == "uncommon" or (price is not None and 0.5 <= price < 2):
            groups["Playable Commons/Uncommons"].append(c)
        else:
            groups["Bulk"].append(c)

    return groups


def sort_cards(cards: list[CardRecord], mode: SortMode) -> dict[str, list[CardRecord]]:
    """
    Dispatch to the appropriate sort function based on mode.

    mode: "color" | "type" | "value"
    Returns a dict with 4 groups (keys vary by mode).
    """
    if mode == "color":
        return sort_color_bucket(cards)
    if mode == "type":
        return sort_card_type(cards)
    if mode == "value":
        return sort_value(cards)
    raise ValueError(f"Unknown sort mode: {mode}")
