"""Network layer: discover and fetch MTGO decklist payloads into the raw cache.

Every event page is a JS app that embeds its whole payload as
``window.MTGO.decklists.data = {...};``. That blob is the API.

The network is excluded from the automated test seam by design (see the PRD's
Testing Decisions), and is verified by spot-checking fetched counts against the
live site. The calendar rule deciding which month may have no index yet is not
network, and is tested.
"""

import json
import re
import time
from datetime import date

import requests

BASE = "https://www.mtgo.com"
PAYLOAD_RE = re.compile(r"window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});\s*\n", re.S)
SLUG_RE = re.compile(r'href="/decklist/([a-z0-9-]+?-(\d{4}-\d{2}-\d{2})\d+)"')
SLUG_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?=\d+$)")

TIMEOUT = 90
ATTEMPTS = 5
BACKOFF = 10  # seconds, lengthening with each attempt


class Unavailable(RuntimeError):
    """The site never served a page carrying what was asked for."""


def _get(url: str, usable) -> str:
    """The page, retried until `usable` says it carries what was asked for.

    Across a six-month backfill the site drops the odd request and intermittently
    serves a 200 whose content is missing: a month index listing no events, or an
    event page whose payload holds the event's metadata and no lists at all.
    Taken at face value, either silently drops published lists from the cache.
    A page too truncated for `usable` to read is unusable for the same reason,
    and is retried rather than allowed to end the run.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            if usable(response.text):
                return response.text
        except (requests.RequestException, ValueError) as dropped:
            if attempt == ATTEMPTS:
                raise Unavailable(f"{url}: {dropped}") from dropped
        if attempt < ATTEMPTS:
            time.sleep(BACKOFF * attempt)
    raise Unavailable(f"{url} served no usable page in {ATTEMPTS} attempts")


def slug_day(slug: str) -> str:
    """The day a slug publishes under."""
    return SLUG_DATE_RE.search(slug).group()


def _months(since: str, until: str) -> list[tuple[int, int]]:
    """Every (year, month) the range touches, oldest first."""
    start, end = date.fromisoformat(since), date.fromisoformat(until)
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def event_slugs(since: str, fmt: str, until: str, today: str) -> list[str]:
    """Slugs of every published `fmt` event from `since` to `until` (YYYY-MM-DD).

    Local time turns the month over some fourteen hours before MTGO does, so a
    month beginning on `today` or later is one the site has published nothing
    into yet: its index is empty rather than missing. A month already open and
    failing to serve is the site stubbing, which is common and does not reliably
    clear, so reading that as empty would silently drop the month from the run.
    """
    now = date.fromisoformat(today)
    slugs = set()
    for year, month in _months(since, until):
        try:
            page = _get(f"{BASE}/decklists/{year}/{month:02d}", SLUG_RE.search)
        except Unavailable:
            if date(year, month, 1) < now:
                raise
            continue
        slugs.update(
            slug
            for slug, day in SLUG_RE.findall(page)
            if since <= day <= until and slug.startswith(f"{fmt}-")
        )
    return sorted(slugs)


def _carries_lists(page: str) -> bool:
    """A payload with no lists in it is the stub, not the event as published."""
    match = PAYLOAD_RE.search(page)
    return match is not None and bool(json.loads(match.group(1)).get("decklists"))


def fetch_payload(slug: str) -> dict:
    """The event's embedded JSON payload, exactly as published."""
    page = _get(f"{BASE}/decklist/{slug}", _carries_lists)
    return json.loads(PAYLOAD_RE.search(page).group(1))
