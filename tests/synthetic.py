"""Synthetic MTGO payloads, for the readings no captured day can hold.

A flag is a verdict about a time series: a configuration climbing over a
fortnight, a weekend arriving, a camp's challenge presence falling away after
it. The live cache holds such episodes, and criterion by criterion it holds
them one at a time, tangled with everything else the archetype was doing. So
the lifecycle is driven here, where a series can be written down as the series
it is, and the payloads are shaped exactly as the site's are: the seam stays
raw cache in, verdicts out.
"""

import json
from pathlib import Path

from deck_engine import config

# The signature cards are taken from the membership rule rather than restated,
# because what every synthetic list has to be is a member of the archetype: a
# rule that grows a card should not quietly empty these series of the deck they
# are about.
# Two copies apiece: the rule is about a card being in the mainboard, so the
# count is not what any of these series turn on.
SIGNATURE = {card: 2 for card in config.SIGNATURE_CARDS}

# A filler block, identical in every synthetic list rather than padded out to a
# legal 60. A filler whose copy count moved with whatever else a list registered
# would be a configuration coming and going across the series, which is a spike
# the detector would have every right to raise: the fixture would be arguing
# with itself. Nothing downstream reads a list's size, and the captured fixtures
# carry every claim about how Goryo's is actually built.
FILLER_MAIN = {
    name: 4 for name in ("Thoughtseize", "Grief", "Unmask", "Fatal Push", "Faithful Mending")
}
FILLER_LANDS = {
    "Polluted Delta": 4,
    "Marsh Flats": 4,
    "Flooded Strand": 4,
    "Watery Grave": 3,
    "Island": 3,
    "Swamp": 3,
}
FILLER_SIDE = {"Consign to Memory": 4, "Wrath of the Skies": 4, "Mystical Dispute": 4}

# One challenge class throughout: every class but league is challenge-class, so
# which of them a synthetic event is makes no difference to any reading here.
CHALLENGE_KIND = "challenge-64"

FALLAJI_COPIES = {"fallaji": 4, "non-fallaji": 0}


def entry(pilot, camp="non-fallaji", cards=None, points=None, placement=None) -> dict:
    """One pilot's registered 75, and how they finished if the event ranked them.

    `cards` is what the series is about, as the configuration the domain reads:
    `{"Kavaero, Mind-Bitten": (1, 0)}` mains one copy and sides none.
    """
    main = SIGNATURE | FILLER_MAIN | FILLER_LANDS
    if FALLAJI_COPIES[camp]:
        main["Fallaji Archaeologist"] = FALLAJI_COPIES[camp]
    side = dict(FILLER_SIDE)
    for card, (in_main, in_side) in (cards or {}).items():
        if in_main:
            main[card] = in_main
        if in_side:
            side[card] = in_side
    return {"pilot": pilot, "points": points, "placement": placement, "main": main, "side": side}


def _card_rows(cards: dict[str, int]) -> list[dict]:
    """Cards as the payload publishes them, typed so the land count can be read."""
    return [
        {
            "qty": str(qty),
            "card_attributes": {
                "card_name": name,
                "card_type": "LAND" if name in FILLER_LANDS else "CREATURE",
            },
        }
        for name, qty in cards.items()
    ]


def _decklists(entries: list[dict]) -> list[dict]:
    return [
        {
            "loginid": str(index),
            "player": e["pilot"],
            "main_deck": _card_rows(e["main"]),
            "sideboard_deck": _card_rows(e["side"]),
            "wins": {"wins": "5", "losses": "0"},
        }
        for index, e in enumerate(entries)
    ]


def league(day: str, entries: list[dict]) -> dict:
    """A day's trophy dump: 5-0s, no standings, and so no points to weigh with."""
    return {
        "site_name": f"modern-league-{day}10847",
        "name": "Modern League",
        "publish_date": day,
        "decklists": _decklists(entries),
    }


def challenge(day: str, entries: list[dict], event_id: str) -> dict:
    """A Swiss event's published top 32: placement and Swiss points per pilot."""
    return {
        "site_name": f"modern-{CHALLENGE_KIND}-{day}{event_id}",
        "event_id": event_id,
        "description": "Modern Challenge 64",
        "starttime": f"{day} 00:00:00.0",
        "decklists": _decklists(entries),
        "standings": [
            {"loginid": str(i), "rank": str(e["placement"]), "score": str(e["points"])}
            for i, e in enumerate(entries)
        ],
        "winloss": [
            {"loginid": str(i), "wins": str(e["points"] // 3), "losses": "0"}
            for i, e in enumerate(entries)
        ],
        "final_rank": [],
    }


def write_cache(raw_dir: Path, events: list[dict]) -> Path:
    """The series, on disk as the immutable raw cache the pipeline reads."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for payload in events:
        path = raw_dir / f"{payload['site_name']}.json"
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return raw_dir
