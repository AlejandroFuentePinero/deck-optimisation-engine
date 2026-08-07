"""Network layer: discover and fetch MTGO decklist payloads into the raw cache.

Every event page is a JS app that embeds its whole payload as
``window.MTGO.decklists.data = {...};``. That blob is the API.

Excluded from the automated test seam by design (see the PRD's Testing
Decisions); verified by spot-checking fetched counts against the live site.
"""

import json
import re

import requests

BASE = "https://www.mtgo.com"
PAYLOAD_RE = re.compile(r"window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});\s*\n", re.S)
SLUG_RE = re.compile(r'href="/decklist/([a-z0-9-]+?-(\d{4}-\d{2}-\d{2})\d+)"')


def _get(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def event_slugs(day: str, fmt: str) -> list[str]:
    """Slugs of every published `fmt` event on `day` (YYYY-MM-DD)."""
    year, month, _ = day.split("-")
    index = _get(f"{BASE}/decklists/{year}/{month}")
    return sorted(
        {
            slug
            for slug, slug_day in SLUG_RE.findall(index)
            if slug_day == day and slug.startswith(f"{fmt}-")
        }
    )


def fetch_payload(slug: str) -> dict:
    """The event's embedded JSON payload, exactly as published."""
    match = PAYLOAD_RE.search(_get(f"{BASE}/decklist/{slug}"))
    if match is None:
        raise ValueError(f"no decklist payload embedded in {slug}")
    return json.loads(match.group(1))
