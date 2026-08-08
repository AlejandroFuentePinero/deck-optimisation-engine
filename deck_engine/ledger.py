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
    if flag["kind"] == "hype":
        return (flag["kind"], flag["camp"], flag["card"], flag["main"], flag["side"],
                flag["raised_on"])
    if flag["kind"] == "pet-tech":
        return (flag["kind"], flag["camp"], flag["card"], flag["main"], flag["side"])
    if flag["kind"] == "breakthrough":
        return (flag["kind"], flag["pilot"], flag["event"], flag["date"])
    return (flag["kind"], flag["camp"], flag["card"])


def load(db_path: Path = config.DB_PATH) -> list[dict]:
    """The ledger as it stands, or nothing where no run has written one yet."""
    path = db_path.with_name(LEDGER)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


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
