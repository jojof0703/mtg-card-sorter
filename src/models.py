"""
Card record model and normalization from Scryfall responses.

This module defines what a "card" looks like in our app. When we identify
a card from an image, we get raw data from Scryfall (a free MTG card database).
We convert that into a CardRecord: a simple, flat structure with just the
fields we need for sorting and display.

Think of it like a form: Scryfall gives us a messy pile of data; we fill
in a clean form (CardRecord) with name, colors, type, price, etc.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CardRecord:
    """
    Normalized card record for sorting and display.

    A dataclass is a simple way to define a "record" or "struct" in Python.
    Each field (id, name, set, etc.) holds one piece of card info.
    We use this instead of raw Scryfall dicts so our code is cleaner.
    """

    id: str  # Scryfall's unique UUID for this card
    name: str
    set: str
    collector_number: str
    colors: list[str]
    color_identity: list[str]
    type_line: str
    mana_value: float
    rarity: str
    prices_usd: Optional[float] = None
    prices_usd_foil: Optional[float] = None
    image_uris: dict = field(default_factory=dict)
    scryfall_uri: str = ""
    edhrec_rank: Optional[int] = None

    @classmethod
    def from_scryfall(cls, data: dict) -> "CardRecord":
        """
        Build CardRecord from Scryfall API response.

        Scryfall returns nested JSON. We extract the fields we need and
        convert types (e.g. "123" string -> 123.0 float for mana value).
        """
        prices = data.get("prices") or {}
        usd = prices.get("usd")
        usd_foil = prices.get("usd_foil")

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            set=data.get("set", ""),
            collector_number=str(data.get("collector_number", "")),
            colors=data.get("colors") or [],
            color_identity=data.get("color_identity") or [],
            type_line=data.get("type_line", ""),
            mana_value=float(data.get("cmc", 0)),
            rarity=data.get("rarity", "common"),
            prices_usd=float(usd) if usd else None,
            prices_usd_foil=float(usd_foil) if usd_foil else None,
            image_uris=data.get("image_uris") or {},
            scryfall_uri=data.get("scryfall_uri", ""),
            edhrec_rank=data.get("edhrec_rank"),
        )

    def effective_usd_price(self) -> Optional[float]:
        """
        Higher of usd or usd_foil for grouping.

        Foil cards often cost more. When sorting by value, we use whichever
        price is higher so we don't undervalue foil printings.
        """
        if self.prices_usd is None and self.prices_usd_foil is None:
            return None
        a = self.prices_usd or 0
        b = self.prices_usd_foil or 0
        return max(a, b)

    def to_dict(self) -> dict:
        """Serialize for JSON cache."""
        return {
            "id": self.id,
            "name": self.name,
            "set": self.set,
            "collector_number": self.collector_number,
            "colors": self.colors,
            "color_identity": self.color_identity,
            "type_line": self.type_line,
            "mana_value": self.mana_value,
            "rarity": self.rarity,
            "prices_usd": self.prices_usd,
            "prices_usd_foil": self.prices_usd_foil,
            "image_uris": self.image_uris,
            "scryfall_uri": self.scryfall_uri,
            "edhrec_rank": self.edhrec_rank,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CardRecord":
        """Deserialize from JSON cache."""
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            set=d.get("set", ""),
            collector_number=str(d.get("collector_number", "")),
            colors=d.get("colors") or [],
            color_identity=d.get("color_identity") or [],
            type_line=d.get("type_line", ""),
            mana_value=float(d.get("mana_value", 0)),
            rarity=d.get("rarity", "common"),
            prices_usd=d.get("prices_usd"),
            prices_usd_foil=d.get("prices_usd_foil"),
            image_uris=d.get("image_uris") or {},
            scryfall_uri=d.get("scryfall_uri", ""),
            edhrec_rank=d.get("edhrec_rank"),
        )
