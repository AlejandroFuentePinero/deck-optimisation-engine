"""The ingest index: one committed row per published list the cache holds.

The raw cache is hundreds of megabytes of payloads and is not committed, so
nothing in the repo records what the analysis history was built from, and no run
can tell its own population from the last one's. The unsettled window makes that
concrete: a league dump gains 5-0s through its own day, so a refresh overwrites
captures it already held, and a record kept at the event would report those days
unchanged while lists appeared inside them. The index is therefore kept at the
list, which is the grain the overwriting happens at.

It is free of the archetype rule, and of every other reading. What membership
makes of a list moves when `config.SIGNATURE_CARDS` moves; what the site
published does not. An index carrying the rule would restate itself the day the
rule changed, and an ingest diff has to be the field's news rather than this
engine's. Which of the new lists are Goryo's is a question asked of the store
afterwards, against the index rather than inside it.

Every field is held as the site's own text, empty where the site published
nothing, so what is read back is what was written and a diff answers to the file
rather than to how this module happens to parse it today.
"""

import csv
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from . import config
from .parse import Decklist

# The index lives beside the store, as the ledger does: it is a fact about the
# cache that store was built from, and a run reading one is reading the other.
# Unlike the ledger it is committed, which is the whole point of it.
INDEX = "index.csv"


class Row(NamedTuple):
    """One published list, as much of it as identifies the list and no more.

    The cards are not here. This says what the site published, and the store
    beside it says what was in it; a copy of the 75 would be a second answer to
    a question the raw cache already answers, free to drift from the first.

    `date` is the event's own date and `event_id` carries the slug's, which are
    not always the same day: the site occasionally republishes an event under a
    wrongly dated slug, and the payload names the event it really is.
    """

    date: str
    event_id: str
    event_class: str
    pilot: str
    placement: str
    swiss_points: str


HEADER = tuple(Row._fields)


def _text(value) -> str:
    """A field as the file holds it, with nothing standing in for absence.

    A league publishes no placement and no points. Writing a `0` there would be
    a finish nobody had, and writing `None` would be Python's word for it in a
    file read back as text.
    """
    return "" if value is None else str(value)


def rows(decklists: list[Decklist]) -> list[Row]:
    """The index of a parsed cache, in the order the file keeps it.

    Sorted so that the file is a diff and not a shuffle: two rebuilds of the same
    cache have to produce the same bytes, or every run would report the whole
    history as new. Chronological, so a fresh day lands at the end of the file
    and a day that grew is an insertion where that day already sits.
    """
    return sorted(
        (
            Row(
                d.date,
                d.event_id,
                d.event_class,
                d.pilot,
                _text(d.placement),
                _text(d.swiss_points),
            )
            for d in decklists
        ),
        # A league's rows have no placement to order on, so they follow the
        # event's finishes rather than sorting to the front of them. Placement
        # orders as the number it is: as text, 10th precedes 9th.
        key=lambda r: (r.date, r.event_id, r.placement == "", int(r.placement or 0), r.pilot),
    )


def path(db_path: Path = config.DB_PATH) -> Path:
    return db_path.with_name(INDEX)


def read(db_path: Path = config.DB_PATH) -> list[Row]:
    """The index as it stands, or nothing where no run has written one yet."""
    source = path(db_path)
    if not source.exists():
        return []
    with source.open(newline="", encoding="utf-8") as handle:
        return [Row(*row) for row in csv.reader(handle)][1:]


def write(decklists: list[Decklist], db_path: Path = config.DB_PATH) -> Path:
    """File the parsed cache as the index, replacing whatever stood before."""
    target = path(db_path)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows(decklists))
    return target


class Change(NamedTuple):
    """What one ingest did to the index.

    Withdrawals are reported beside arrivals because they happen: the site
    republishes an event under a wrongly dated slug and later takes one of them
    down, and lists leaving the history silently is the same failure as lists
    arriving silently.
    """

    added: list[Row]
    withdrawn: list[Row]


def difference(rows: list[Row], against: list[Row]) -> list[Row]:
    """The rows of `rows` that `against` does not account for, counted rather
    than set-subtracted.

    One pilot can trophy twice in a single league dump on two lists that are not
    the same 75, and those two lists are two rows this index cannot tell apart.
    Subtracting sets would report the day he published a second one as nothing
    having happened, which is the reading this whole file exists to prevent.
    """
    unclaimed = Counter(against)
    surplus = []
    for row in rows:
        if unclaimed[row]:
            unclaimed[row] -= 1
        else:
            surplus.append(row)
    return surplus
