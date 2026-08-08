"""The flag ledger: what the engine has raised, and when it first said so.

The store is rebuilt from the raw cache every run and carries no memory, but
when the engine first said a configuration was spiking, or that a pilot had
broken through, is not in that cache to rebuild from. So the ledger sits beside
the store: the run that raised a flag survives the fortnight it takes for the
field to answer it.

It is one file for every kind of flag because it is one memory. What raised a
flag is the detecting module's business, whether the reading is of a time series
or of who registered what; what has been raised is this one's.
"""

import json
from datetime import date
from pathlib import Path

from . import config, flags, pilots

# The ledger lives beside the store rather than at a path of its own: it is that
# store's memory, and a run reading one has to be reading the other.
LEDGER = "flags.json"

# The kinds this module joins by name. Drawn once, so the identity rule and the
# lineage reading cannot come to disagree about what a flag is.
HYPE = "hype"
BREAKTHROUGH = "breakthrough"


def detect(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every flag the store holds right now, time-series readings first."""
    return (
        flags.hype(db_path)
        + flags.fringe(db_path)
        + pilots.pet_tech(db_path)
        + pilots.breakthroughs(db_path)
    )


def _identity(flag: dict) -> tuple:
    """What makes two readings the same flag.

    A hype flag is an episode, so the day the field moved is part of it: the
    same configuration spiking again months later is a second episode and gets
    its own record. A fringe flag is a card coming back into view, so the
    configuration it came back in is not: a pilot sideboarding what used to be
    a maindeck card is the same piece of news.

    A pet-tech flag is a standing property of a configuration rather than
    anything that happened on a day, so it is identified by the configuration
    alone: the pilots and the count move as the history grows, and a flag that
    changed identity every time its owner sleeved the card again would fill the
    ledger with one preference over and over.

    A breakthrough is a list, and a list is a pilot at an event on a day. What
    it deviated by is deliberately not part of that: the camp's consensus moves
    as the camp publishes, so an identity carrying the deviation would file the
    same list twice the first time its camp shifted underneath it. One pilot
    trophying twice in a single league dump on two builds of the same idea is
    the one case this collapses, and those two lists are the one piece of news.
    """
    if flag["kind"] == HYPE:
        return (flag["kind"], flag["camp"], flag["card"], flag["main"], flag["side"],
                flag["raised_on"])
    if flag["kind"] == "pet-tech":
        return (flag["kind"], flag["camp"], flag["card"], flag["main"], flag["side"])
    if flag["kind"] == BREAKTHROUGH:
        return (flag["kind"], flag["pilot"], flag["event"], flag["date"])
    return (flag["kind"], flag["camp"], flag["card"])


def load(db_path: Path = config.DB_PATH) -> list[dict]:
    """The ledger as it stands, or nothing where no run has written one yet."""
    path = db_path.with_name(LEDGER)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def lineage(db_path: Path = config.DB_PATH, camp: str | None = None) -> list[dict]:
    """Departures traced through to what the field finally did with them.

    A breakthrough is a list that left its camp's build behind. Whether the
    change was any good is a question no single flag answers, and the engine
    already holds every part of the answer in a different place: the departure
    says somebody changed something, the follow-through says the field picked it
    up, and the hype resolution says whether it survived the weekend that judges
    a copied list. Read apart, the first is an anecdote and the third is a
    fortnight's share; read together they are the field's verdict on an idea,
    taken over hundreds of pilots, which is the highest-powered instrument this
    data has.

    The join is on the card, in the camp, after the departure. On the card
    because what spreads is the idea rather than the 75 around it, which is the
    same reason follow-through is counted there. After the departure because a
    spike the list came second to is the list following a trend rather than
    setting one.

    A departure with no episode behind it is still a row: most of them have none,
    and that is the answer rather than a gap. What it lacks is the field having
    piled in, which is exactly what did not happen.
    """
    recorded = load(db_path)
    episodes = [flag for flag in recorded if flag["kind"] == HYPE]
    traced = []
    for flag in recorded:
        if flag["kind"] != BREAKTHROUGH or (camp and flag["camp"] != camp):
            continue
        followed = [
            episode
            for card, _, _ in flag["novel"]
            for episode in episodes
            if episode["card"] == card
            and episode["camp"] == flag["camp"]
            and episode["raised_on"] >= flag["date"]
        ]
        # The earliest episode is the one this departure could have started. A
        # later spike on the same card is the field returning to it, and reading
        # the departure against that would credit it with somebody else's news.
        episode = min(followed, key=lambda e: e["raised_on"], default=None)
        traced.append(
            {
                "camp": flag["camp"],
                "stratum": flag.get("stratum"),
                "pilot": flag["pilot"],
                "event": flag["event"],
                "date": flag["date"],
                "placement": flag["placement"],
                "mode": flag["mode"],
                "delta": flag["delta"],
                "novel": flag["novel"],
                "missing": flag["missing"],
                "followed": flag["state"],
                "followers": flag["followers"],
                "needed": flag.get("needed"),
                "adopted_card": flag["adopted_card"],
                "spread_card": episode["card"] if episode else None,
                "spiked_on": episode["raised_on"] if episode else None,
                "resolved": episode["state"] if episode else None,
                "standing": episode.get("standing") if episode else None,
            }
        )
    return sorted(traced, key=lambda row: row["date"], reverse=True)


def record(db_path: Path = config.DB_PATH, today: str | None = None) -> list[dict]:
    """Merge what the store says now into the ledger, and say what it holds.

    Detection is a reading of the cache and the ledger is the engine's memory of
    what it has raised, so the merge keeps both: a flag's state is whatever this
    run makes of it, and `first_seen` stays the run that first said so.

    A flag the run no longer detects is kept rather than dropped. A fringe flag
    fires on an appearance, which is a moment, and the appearance leaves the
    fresh window a fortnight later; dropping it then would make the engine's
    memory exactly as long as its fresh window.
    """
    kept = {_identity(flag): flag for flag in load(db_path)}
    today = today or date.today().isoformat()
    for flag in detect(db_path):
        seen = kept.get(_identity(flag), {}).get("first_seen", today)
        kept[_identity(flag)] = flag | {"first_seen": seen}
    recorded = sorted(kept.values(), key=lambda flag: (flag["first_seen"], _identity(flag)))

    # Landed whole or not at all, as every capture here is: the ledger is what
    # a run remembers, and half of one is a memory with flags missing from it.
    path = db_path.with_name(LEDGER)
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(recorded, indent=1), encoding="utf-8")
    partial.replace(path)
    return recorded
