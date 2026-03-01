"""
Scryfall API client with rate limiting and fallback lookup.

Scryfall (scryfall.com) is a free, community-run database of all MTG cards.
Their API lets us look up cards by:
- Set + collector number (exact: /cards/m21/123)
- Fuzzy name (handles typos: /cards/named?fuzzy=Lightning Bolt)
- Search (returns many matches: /cards/search?q=...)

We add rate limiting (100ms between requests) to be polite per their guidelines.
When multiple cards match a name, we can ask the user to pick (on_ambiguous).
"""

import time
import urllib.parse
from typing import Callable, Optional

import requests

USER_AGENT = "MTGCardSorter/1.0 (School Project; +https://github.com)"
RATE_LIMIT_DELAY_SEC = 0.1  # 100ms between requests per Scryfall guidelines


class ScryfallClient:
    """
    Scryfall API client with rate limiting.

    Wraps HTTP requests to api.scryfall.com. We use a requests.Session
    for connection reuse and add a small delay between requests to avoid
    hitting their rate limit (they ask for <10 req/sec).
    """

    def __init__(self, delay: float = RATE_LIMIT_DELAY_SEC):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        self._delay = delay
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        """Wait if needed so we don't exceed Scryfall's rate limit."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request = time.monotonic()

    def _get(self, url: str) -> Optional[dict]:
        self._rate_limit()
        try:
            r = self._session.get(url, timeout=15)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            return None

    def get_by_id(self, scryfall_id: str) -> Optional[dict]:
        """Lookup by Scryfall UUID: GET /cards/{id}."""
        if not scryfall_id or len(scryfall_id) < 32:
            return None
        url = f"https://api.scryfall.com/cards/{scryfall_id}"
        return self._get(url)

    def get_by_collector(self, set_code: str, collector_number: str) -> Optional[dict]:
        """Exact lookup: GET /cards/{set}/{collector_number} (e.g. m21/123)."""
        if not set_code or not collector_number:
            return None
        url = f"https://api.scryfall.com/cards/{set_code.lower()}/{collector_number}"
        return self._get(url)

    def get_by_fuzzy_name(self, name: str, set_code: Optional[str] = None) -> Optional[dict]:
        """Fuzzy name lookup. Handles typos. Optional set_code narrows results."""
        if not name or len(name) < 2:
            return None
        params = {"fuzzy": name}
        if set_code:
            params["set"] = set_code.lower()
        qs = urllib.parse.urlencode(params)
        url = f"https://api.scryfall.com/cards/named?{qs}"
        return self._get(url)

    def search(self, query: str) -> list[dict]:
        """Search by query string. Returns list of card dicts (may be many)."""
        if not query or len(query) < 2:
            return []
        qs = urllib.parse.urlencode({"q": query})
        url = f"https://api.scryfall.com/cards/search?{qs}"
        data = self._get(url)
        if not data or data.get("object") != "list":
            return []
        return data.get("data", [])

    def identify_card(
        self,
        collector_number: str,
        set_code: str,
        card_name: str,
        on_ambiguous: Optional[Callable[[str, list[dict]], Optional[dict]]] = None,
    ) -> Optional[dict]:
        """
        Identify card using fallback order (most reliable first):

        1. Set + collector number: exact match if we parsed both
        2. Fuzzy name: handles OCR typos, optional set filter
        3. Search + best match: when fuzzy fails, search and pick by similarity
           If multiple close matches and on_ambiguous is set, ask the user.
        """
        # 1. Set + collector number
        if set_code and collector_number:
            card = self.get_by_collector(set_code, collector_number)
            if card:
                return card

        # 2. Fuzzy name
        if card_name:
            card = self.get_by_fuzzy_name(card_name, set_code)
            if card:
                return card

        # 3. Search
        if not card_name:
            return None

        results = self.search(card_name)
        if not results:
            return None

        if len(results) == 1:
            return results[0]

        # Multiple results: pick best by similarity, or ask user
        best = _best_match(card_name, results)
        if best and on_ambiguous:
            candidates = _top_n_similar(card_name, results, 3)
            chosen = on_ambiguous(card_name, candidates)
            if chosen is not None:
                return chosen
            return best
        return best


def _similarity(a: str, b: str) -> float:
    """Simple string similarity (0-1)."""
    a = a.lower().strip()
    b = b.lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Jaccard-like: overlap of words
    wa = set(a.split())
    wb = set(b.split())
    if not wa:
        return 0.0
    inter = len(wa & wb)
    return inter / len(wa)


def _best_match(name: str, cards: list[dict]) -> Optional[dict]:
    """Return card with highest name similarity."""
    if not cards:
        return None
    best = max(cards, key=lambda c: _similarity(name, c.get("name", "")))
    return best


def _top_n_similar(name: str, cards: list[dict], n: int) -> list[dict]:
    """Return top N cards by similarity to name."""
    scored = [(c, _similarity(name, c.get("name", ""))) for c in cards]
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:n]]
