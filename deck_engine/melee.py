"""Network layer: fetch a paper Spotlight's standings and lists into the raw cache.

Melee is the second source of decklist-level data and the only one that is not
MTGO. It is here for one reason: a Spotlight publishes every finisher, where a
challenge publishes its top 32. That difference is the whole value of the source
and also the whole hazard, so the two never share a table (see `spotlight.py`).

Two endpoints do the work. The standings of the last round carry the final
ranking of the entire field, with each player's match record and the id of the
list they registered; the decklist page carries the cards. Both are the site's
own DataTables plumbing rather than a documented API, so both are pinned here
and nowhere else.

The site names modal double-faced cards `Front // Back` where MTGO names them by
the front face alone. Left alone that is not a missing card, it is a missing
archetype: every Blink list fails membership on Witch Enchanter and the deck
reads as absent from paper entirely. Folding to the front face is therefore part
of fetching, not part of reading.
"""

import html
import re
import time

import requests

from . import config

BASE = "https://melee.gg"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# The round buttons the tournament page carries, in the order it lists them, and
# the two halves of a decklist page. Scraped rather than requested as JSON
# because the site publishes no endpoint for either.
ROUND_RE = re.compile(r'class="btn btn-gray round-selector" data-id="(\d+)" data-name="([^"]*)"')
CATEGORY_RE = re.compile(
    r'<div class="decklist-category-title">([^<]*)</div>(.*?)'
    r'(?=<div class="decklist-category">|\Z)',
    re.S,
)
RECORD_RE = re.compile(
    r'<span class="decklist-record-quantity">(\d+)</span>\s*'
    r'<a class="decklist-record-name"[^>]*>([^<]*)</a>',
    re.S,
)

# The columns the standings grid asks for. The endpoint is a DataTables source
# and answers an incomplete column spec with a 500, so the list is exact.
COLUMNS = (
    "Rank",
    "Player",
    "Decklists",
    "MatchRecord",
    "GameRecord",
    "Points",
    "OpponentMatchWinPercentage",
    "TeamGameWinPercentage",
    "OpponentGameWinPercentage",
)

PAGE = 500  # standings rows per request
TIMEOUT = 90
ATTEMPTS = 5
BACKOFF = 10  # seconds, lengthening with each attempt
PAUSE = 0.45  # between decklist fetches, this being someone else's server


class Unavailable(RuntimeError):
    """The site never served a page carrying what was asked for."""


def _request(method: str, path: str, usable, **kwargs) -> requests.Response:
    """The response, retried until `usable` says it carries what was asked for."""
    url = f"{BASE}{path}"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            headers = {"User-Agent": UA, **kwargs.pop("headers", {})}
            response = requests.request(method, url, timeout=TIMEOUT, headers=headers, **kwargs)
            response.raise_for_status()
            if usable(response):
                return response
        except (requests.RequestException, ValueError) as dropped:
            if attempt == ATTEMPTS:
                raise Unavailable(f"{url}: {dropped}") from dropped
        if attempt < ATTEMPTS:
            time.sleep(BACKOFF * attempt)
    raise Unavailable(f"{url} served no usable response in {ATTEMPTS} attempts")


def details(tournament: int) -> dict:
    """The event's own metadata: its published name, organiser and start."""
    response = _request(
        "GET",
        f"/Tournament/GetTournamentDetails/{tournament}",
        lambda r: "Name" in r.json(),
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    return response.json()


def final_round(tournament: int) -> tuple[str, str]:
    """The id and name of the last round the event played.

    The last round and not the last Swiss one: its standings are the final
    ranking of the whole field, the top cut in playoff order and everyone else
    on Swiss tiebreakers. Taken as the page lists them rather than by name,
    since an event that ran no playoff ends on a numbered round.
    """
    response = _request("GET", f"/Tournament/View/{tournament}", lambda r: ROUND_RE.search(r.text))
    rounds = ROUND_RE.findall(response.text)
    if not rounds:
        raise Unavailable(f"tournament {tournament} published no rounds")
    return rounds[-1]


def _standings_page(tournament: int, round_id: str, start: int) -> dict:
    form = {
        "draw": "1",
        "start": str(start),
        "length": str(PAGE),
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
        "roundId": str(round_id),
    }
    for index, column in enumerate(COLUMNS):
        form |= {
            f"columns[{index}][data]": column,
            f"columns[{index}][name]": column,
            f"columns[{index}][searchable]": "true",
            f"columns[{index}][orderable]": "true",
            f"columns[{index}][search][value]": "",
            f"columns[{index}][search][regex]": "false",
        }
    response = _request(
        "POST",
        "/Standing/GetRoundStandings",
        lambda r: not r.json().get("Error") and "recordsTotal" in r.json(),
        data=form,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE}/Tournament/View/{tournament}",
        },
    )
    return response.json()


def standings(tournament: int, round_id: str) -> list[dict]:
    """Every row of that round's standings, paged until the field is complete."""
    first = _standings_page(tournament, round_id, 0)
    total, rows = first["recordsTotal"], list(first["data"])
    while len(rows) < total:
        time.sleep(PAUSE)
        rows += _standings_page(tournament, round_id, len(rows))["data"]
    if len(rows) != total:
        raise Unavailable(f"tournament {tournament}: {len(rows)} of {total} standings rows")
    return rows


def front_face(name: str) -> str:
    """The name MTGO publishes a card under, given the name melee publishes.

    Melee writes a modal double-faced card as `Front // Back`; MTGO writes the
    front face alone. Every reading downstream matches card names literally
    against MTGO's history, so the fold happens here or every comparison across
    the two sources quietly misses.

    The printing aliases apply after it, the same ones and for the same reason
    the MTGO parse applies them: two names for one card split its history down
    the middle wherever they are not merged at the point names become counts.
    """
    face = html.unescape(name).split(" // ")[0].strip()
    return config.CARD_ALIASES.get(face, face)


def boards(markup: str) -> tuple[dict[str, int], dict[str, int]]:
    """A decklist page's mainboard and sideboard, by card name and count.

    The page groups cards under type headings and the sideboard under its own,
    so the split is the heading rather than a count: a list with a companion
    heading would otherwise put it in the mainboard.
    """
    main: dict[str, int] = {}
    side: dict[str, int] = {}
    for title, body in CATEGORY_RE.findall(markup):
        board = side if title.strip().lower().startswith(("sideboard", "companion")) else main
        for quantity, name in RECORD_RE.findall(body):
            card = front_face(name)
            board[card] = board.get(card, 0) + int(quantity)
    return main, side


def decklist(decklist_id: str) -> tuple[dict[str, int], dict[str, int]]:
    """One registered list, as its page publishes it."""
    response = _request(
        "GET", f"/Decklist/View/{decklist_id}", lambda r: "decklist-record-name" in r.text
    )
    return boards(response.text)


def tournament(tournament_id: int, known: dict | None = None) -> dict:
    """A whole Spotlight: its metadata, its final standings, and every list.

    `known` is a cache of lists already fetched, keyed by decklist id. A field
    of nine hundred is nine hundred requests to someone else's server, so a
    refetch costs nothing it does not have to.
    """
    known = known or {}
    meta = details(tournament_id)
    round_id, round_name = final_round(tournament_id)
    rows = standings(tournament_id, round_id)
    lists = []
    for row in rows:
        players = row["Team"]["Players"]
        for entry in row["Decklists"]:
            cached = known.get(entry["DecklistId"])
            if cached:
                main, side = cached["main"], cached["side"]
            else:
                main, side = decklist(entry["DecklistId"])
                time.sleep(PAUSE)
            lists.append(
                {
                    "decklist_id": entry["DecklistId"],
                    "rank": row["Rank"],
                    "pilot": players[0]["Username"] if players else None,
                    "name": entry["DecklistName"].strip(),
                    "record": row["MatchRecord"],
                    "wins": row["MatchWins"],
                    "losses": row["MatchLosses"],
                    "draws": row["MatchDraws"],
                    "points": row["Points"],
                    "main": main,
                    "side": side,
                }
            )
    return {
        "tournament": {
            "id": tournament_id,
            "name": meta.get("Name"),
            "organiser": meta.get("OrganizationName"),
            "start": meta.get("StartDate"),
            "round": round_name,
            "players": len(rows),
        },
        "lists": lists,
    }
