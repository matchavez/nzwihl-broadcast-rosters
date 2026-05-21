"""Shared HTTP session with browser-like headers.

NZWIHL (esportsdesk) returns 403 to requests with non-browser User-Agents.
One Session is reused across all fetches so any cookies survive between requests.
"""
from __future__ import annotations

import requests

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-NZ,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_SESSION: requests.Session | None = None


def session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        s.headers.update(_HEADERS)
        _SESSION = s
    return _SESSION


def fetch(url: str, *, timeout: int = 30) -> str:
    resp = session().get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text
