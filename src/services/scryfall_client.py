"""
Scryfall API client with pagination and image download for dataset harness.

This is a separate client from src/scryfall_client. It's used by:
- build_dataset: search cards, download images, paginate through results
- ocr_eval: lookup by set+collector, fuzzy name, search

Key differences from main client: pagination (search_cards yields), image
download, method names (get_card_by_collector vs get_by_collector).
Uses RateLimitedSession from utils for retries and throttling.
"""

import urllib.parse
from pathlib import Path
from typing import Iterator, Optional

from src.utils.http import RateLimitedSession

BASE_URL = "https://api.scryfall.com"


class ScryfallClient:
    """
    Scryfall client with rate limiting, pagination, and image download.

    Used by dataset build and ocr_eval. Wraps RateLimitedSession.
    """

    def __init__(self, delay: float = 0.11):
        self._session = RateLimitedSession(delay=delay)

    def search_cards(
        self,
        query: str,
        unique: str = "prints",
    ) -> Iterator[dict]:
        """
        Paginate through cards/search results. Yields card objects.
        Scryfall returns 175 cards per page; we follow next_page until done.
        """
        qs = urllib.parse.urlencode({"q": query, "unique": unique})
        url = f"{BASE_URL}/cards/search?{qs}"

        while url:
            r = self._session.get(url)
            if r.status_code == 404:
                break
            r.raise_for_status()
            data = r.json()

            if data.get("object") == "error":
                break

            for card in data.get("data", []):
                yield card

            url = data.get("next_page") if data.get("has_more") else None

    def get_card_by_collector(self, set_code: str, collector_number: str) -> Optional[dict]:
        """Exact lookup by set + collector number."""
        url = f"{BASE_URL}/cards/{set_code.lower()}/{collector_number}"
        r = self._session.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def get_card_by_fuzzy_name(self, name: str, set_code: Optional[str] = None) -> Optional[dict]:
        """Fuzzy name lookup. Optional set_code narrows to that set."""
        params = {"fuzzy": name}
        if set_code:
            params["set"] = set_code.lower()
        qs = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/cards/named?{qs}"
        r = self._session.get(url)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def search_cards_list(self, query: str, unique: str = "prints") -> list[dict]:
        """Search and return all cards as a list (fetches all pages)."""
        qs = urllib.parse.urlencode({"q": query, "unique": unique})
        url = f"{BASE_URL}/cards/search?{qs}"
        results = []
        while url:
            r = self._session.get(url)
            if r.status_code == 404:
                break
            r.raise_for_status()
            data = r.json()
            if data.get("object") == "error":
                break
            results.extend(data.get("data", []))
            url = data.get("next_page") if data.get("has_more") else None
        return results

    def download_image(self, image_url: str, dest_path: Path) -> None:
        """Download image from URL to dest_path. Uses same rate limit as API calls."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        r = self._session.get(image_url, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
