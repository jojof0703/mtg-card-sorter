"""
HTTP utilities: headers, rate limiting, retry.

RateLimitedSession extends requests.Session to:
- Add a delay between requests (throttle to ~9 req/sec)
- Retry on 429 (rate limit) or connection errors (up to max_retries)
- Set User-Agent and timeout by default

Used by the dataset Scryfall client (services/scryfall_client).
"""

import time
from typing import Optional

import requests

USER_AGENT = "MTGCardSorter/0.1 (contact: school-project)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}
RATE_LIMIT_DELAY = 0.11  # ~9 req/sec, under 10/sec


class RateLimitedSession(requests.Session):
    """
    Session with rate limiting and retry.

    _throttle() runs before each request. On 429, we sleep 2s and retry.
    On other RequestException, we retry up to max_retries times with 1s delay.
    """

    def __init__(
        self,
        delay: float = RATE_LIMIT_DELAY,
        max_retries: int = 3,
        headers: Optional[dict] = None,
    ):
        super().__init__()
        self.headers.update(headers or DEFAULT_HEADERS)
        self._delay = delay
        self._last_request = 0.0
        self._max_retries = max_retries

    def _throttle(self) -> None:
        """Wait if needed to stay under rate limit."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", 30)
        for attempt in range(self._max_retries):
            self._throttle()
            try:
                r = super().request(method, url, **kwargs)
                if r.status_code == 429:
                    time.sleep(2)
                    continue
                return r
            except requests.RequestException:
                if attempt == self._max_retries - 1:
                    raise
                time.sleep(1)
        raise requests.RequestException("Max retries exceeded")
