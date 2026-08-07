"""Published MTGO payloads to decklist records.

Leagues and challenge-class events publish different shapes: a league carries
per-list win/loss and no placement (only 5-0s are published), a challenge-class
event carries standings that have to be joined onto the lists by pilot login.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

# What a slug appends to the event kind: publication date plus event id.
DATED_SUFFIX_RE = re.compile(r"-\d{4}-\d{2}-\d{2}\d+$")

# How the payload types a land, in the fixed-width column it publishes types in.
LAND_TYPE = "LAND"


@dataclass
class Decklist:
    """A published list: the 75 as registered, with its provenance."""

    pilot: str
    event: str
    event_id: str
    event_class: str
    date: str
    placement: int | None
    swiss_points: int | None
    record: str | None
    mainboard: dict[str, int]
    sideboard: dict[str, int]
    lands: int
    archetype: str | None = None
    camp: str | None = None


def _cards(entries: list[dict]) -> dict[str, int]:
    """A board's cards and copies, printings of one card counted as that card.

    The site publishes a list under whichever printing its pilot registered, and
    a pilot may register two printings of the same card. Merging them here, at
    the point names first become counts, is what stops a two-of reading as two
    separate one-ofs and one card's adoption history splitting down the middle.
    """
    counts: dict[str, int] = {}
    for entry in entries:
        name = entry["card_attributes"]["card_name"]
        name = config.CARD_ALIASES.get(name, name)
        counts[name] = counts.get(name, 0) + int(entry["qty"])
    return counts


def _lands(entries: list[dict]) -> int:
    """The list's land count, which the domain reads as a configuration of the
    75 as a whole.

    The mainboard's alone: how much land a deck runs is a decision about the
    60, and a sideboard land is a card brought in for a matchup.

    The payload types the cards it publishes, so no list of lands is kept here,
    and what it types is the front face. So this is the front-face count: a
    modal double-faced card with a land back is typed by its spell half and does
    not reach it. Sink into Stupor is the one this archetype plays, and a list
    running it reads a land lighter here than its pilot would call it.

    A split card carries no type at all, which is no loss: the site publishes
    none whose halves are lands.
    """
    return sum(
        int(entry["qty"])
        for entry in entries
        if (entry["card_attributes"].get("card_type") or "").strip() == LAND_TYPE
    )


def _event_class(payload: dict) -> str:
    """The kind the site publishes, e.g. `modern-last-chance-2026-07-19...` is a
    last-chance. Everything but a league is challenge-class: Swiss then a cut."""
    kind = DATED_SUFFIX_RE.sub("", payload["site_name"])
    return kind.split("-", 1)[1]


def _placements(payload: dict) -> dict[str, int]:
    """Published finish per pilot login.

    `final_rank` is the placement after the playoff; `standings` is the Swiss
    order the playoff reshuffles. Events without a playoff publish standings
    only, and there the Swiss order is the finish.
    """
    ranking = payload["final_rank"] if payload.get("final_rank") else payload["standings"]
    return {row["loginid"]: int(row["rank"]) for row in ranking}


def parse_event(payload: dict) -> list[Decklist]:
    is_challenge_class = "standings" in payload
    if is_challenge_class:
        event = payload["description"]
        date = payload["starttime"][:10]
        rank = _placements(payload)
        swiss = {row["loginid"]: int(row["score"]) for row in payload["standings"]}
        record = {w["loginid"]: f"{w['wins']}-{w['losses']}" for w in payload["winloss"]}
    else:
        event = payload["name"]
        date = payload["publish_date"]

    lists = []
    for raw in payload["decklists"]:
        if is_challenge_class:
            placement = rank.get(raw["loginid"])
            swiss_points = swiss.get(raw["loginid"])
            result = record.get(raw["loginid"])
        else:
            placement = swiss_points = None
            result = f"{raw['wins']['wins']}-{raw['wins']['losses']}"
        lists.append(
            Decklist(
                pilot=raw["player"],
                event=event,
                event_id=payload["site_name"],
                event_class=_event_class(payload),
                date=date,
                placement=placement,
                swiss_points=swiss_points,
                record=result,
                mainboard=_cards(raw["main_deck"]),
                sideboard=_cards(raw["sideboard_deck"]),
                lands=_lands(raw["main_deck"]),
            )
        )
    return lists


def parse_cache(raw_dir: Path) -> list[Decklist]:
    """Every cached event in `raw_dir`, parsed, counted once.

    The site occasionally lists an event a second time under a wrongly dated
    slug. Both slugs serve the same payload, and that payload names the event it
    really is, so `site_name` is the event's identity and the filename is not.
    """
    lists, seen = [], set()
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["site_name"] in seen:
            continue
        seen.add(payload["site_name"])
        lists.extend(parse_event(payload))
    return lists
