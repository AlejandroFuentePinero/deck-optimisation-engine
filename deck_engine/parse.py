"""Published MTGO payloads to decklist records.

Leagues and tournaments publish different shapes: a league carries per-list
win/loss and no placement (only 5-0s are published), a tournament carries
standings that have to be joined onto the lists by pilot login.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Decklist:
    """A published list. Only the fields this tracer loads; sideboard and
    per-card configuration arrive with configuration tracking."""

    pilot: str
    event: str
    event_id: str
    event_class: str
    date: str
    placement: int | None
    record: str | None
    mainboard: dict[str, int]
    archetype: str | None = None


def _cards(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        name = entry["card_attributes"]["card_name"]
        counts[name] = counts.get(name, 0) + int(entry["qty"])
    return counts


def _event_class(payload: dict) -> str:
    """The published event kind, e.g. `modern-challenge-32-...` is a challenge."""
    return payload["site_name"].split("-")[1]


def _placements(payload: dict) -> dict[str, int]:
    """Published finish per pilot login.

    `final_rank` is the placement after the playoff; `standings` is the Swiss
    order the playoff reshuffles. Events without a playoff publish standings
    only, and there the Swiss order is the finish.
    """
    ranking = payload["final_rank"] if payload.get("final_rank") else payload["standings"]
    return {row["loginid"]: int(row["rank"]) for row in ranking}


def parse_event(payload: dict) -> list[Decklist]:
    is_tournament = "standings" in payload
    if is_tournament:
        event = payload["description"]
        date = payload["starttime"][:10]
        rank = _placements(payload)
        record = {w["loginid"]: f"{w['wins']}-{w['losses']}" for w in payload["winloss"]}
    else:
        event = payload["name"]
        date = payload["publish_date"]

    lists = []
    for raw in payload["decklists"]:
        if is_tournament:
            placement = rank.get(raw["loginid"])
            result = record.get(raw["loginid"])
        else:
            placement = None
            result = f"{raw['wins']['wins']}-{raw['wins']['losses']}"
        lists.append(
            Decklist(
                pilot=raw["player"],
                event=event,
                event_id=payload["site_name"],
                event_class=_event_class(payload),
                date=date,
                placement=placement,
                record=result,
                mainboard=_cards(raw["main_deck"]),
            )
        )
    return lists


def parse_cache(raw_dir: Path) -> list[Decklist]:
    """Every cached event in `raw_dir`, parsed."""
    lists = []
    for path in sorted(raw_dir.glob("*.json")):
        lists.extend(parse_event(json.loads(path.read_text(encoding="utf-8"))))
    return lists
