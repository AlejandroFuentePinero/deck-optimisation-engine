"""What changed in a tracked deck, fortnight by fortnight.

The plots are weekly and this is not, for one reason. A week of this deck runs
from nine published lists to sixty-four, so a threshold set as a share of the
week is measuring the sample size: at every bar from five points to twenty-five,
a change detected weekly reverses in the next week about two times in five, and
raising the bar loses findings without buying purity. Over a fortnight the same
bars reverse between fifteen and twenty-two percent of the time, and the rate
falls as the bar rises, which is what a threshold is supposed to do.

So a timeline row is a fortnight's row. The bins do not overlap, because
overlapping ones would report the same change twice and a reader cannot tell a
repeated finding from a continuing one. They are anchored at the regime boundary
rather than at today, so the bin a date falls in never moves and a row written
six weeks ago still describes the same fortnight. Bins before the boundary carry
negative indices and are never reported: they exist so that a card's history
reaches back past the boundary, which is what tells a return from a cold start.

Findings are written mechanically, from the numbers, in fixed forms. The
interpretation layer is the weekly summary written over the top of this; a row
that phrased itself differently on a later run would make the committed history
disagree with itself for no reason.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

import duckdb

from . import config
from .store import _rows


def bin_of(day: str, since: str = config.REGIME_BOUNDARY) -> int:
    """The bin a day falls in. Negative before the boundary, by design."""
    offset = (date.fromisoformat(day) - date.fromisoformat(since)).days
    return offset // config.TRACK_BIN_DAYS


def bin_start(index: int, since: str = config.REGIME_BOUNDARY) -> str:
    """The first day of bin `index`."""
    return (date.fromisoformat(since) + timedelta(days=index * config.TRACK_BIN_DAYS)).isoformat()


def _history(db_path: Path, deck: str, variant: str) -> tuple[list[dict], list[dict]]:
    """Every registration and every list of the variant, over the whole store.

    The whole store and not the post-regime window, because whether a card has
    been out of the deck for a month is a fact about the deck rather than about
    the regime. Read over the window alone, every card of the opening fortnight
    reads as new and the timeline opens on an innovation burst that is really a
    cold start.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        registered = _rows(
            con.execute(
                """
                SELECT c.list_id, c.card, c.main,
                       CASE WHEN c.main > 0 THEN 'main' ELSE 'side' END AS zone, d.date
                FROM decklists d JOIN configurations c USING (list_id)
                WHERE d.archetype = ? AND d.camp = ? AND (c.main > 0 OR c.side > 0)
                """,
                [deck, variant],
            )
        )
        lists = _rows(
            con.execute(
                "SELECT list_id, date FROM decklists WHERE archetype = ? AND camp = ?",
                [deck, variant],
            )
        )
    return registered, lists


def events(path: Path = config.EVENTS_PATH) -> list[dict]:
    """The dated events a plot marks and a row names. Empty when none are kept."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return sorted(csv.DictReader(handle), key=lambda row: row["date"])


def adoption_row(card: str, zone: str, n: int, size: int, was: int, was_size: int) -> dict:
    """The deck took a card up or put it down, phrased once.

    Shared with the Spotlight readings rather than written twice, so a paper row
    and a fortnight row that found the same thing say it the same way.
    """
    share = n / size
    was_share = was / was_size if was_size else 0.0
    return {
        "kind": "adoption",
        "zone": zone,
        "card": card,
        "text": f"{card} {'climbed' if share > was_share else 'fell'} in the "
        f"{zone}board, {was}/{was_size} to {n}/{size} lists "
        f"({was_share:.0%} to {share:.0%})",
    }


def copies_row(card: str, zone: str, now: float, before: float) -> dict:
    """The deck kept a card and changed its mind about how many."""
    return {
        "kind": "copies",
        "zone": zone,
        "card": card,
        "text": f"{card} {'up' if now > before else 'down'} from "
        f"{before:.1f} to {now:.1f} copies on average",
    }


def moved(n: int, size: int, was: int, was_size: int) -> bool:
    """Whether a share moved far enough, in both units, to be a row.

    The share is what makes a move large and the count is what makes it
    evidence, so a thin population cannot clear the bar on one pilot.
    """
    share = n / size
    was_share = was / was_size if was_size else 0.0
    return (
        abs(share - was_share) >= config.TRACK_ADOPTION_DELTA
        and abs(n - was) >= config.TRACK_MIN_LISTS
    )


def findings(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    since: str = config.REGIME_BOUNDARY,
) -> list[dict]:
    """One row per fortnight from `since`: what moved, phrased in fixed forms.

    Three readings, answering different questions. Adoption says the deck took a
    card up or put it down. Copies says it kept the card and changed its mind
    about how many, which no adoption reading can see, because the cards that
    happens to sit at total adoption and never move a share. Returns say a card
    the deck had stopped playing came back, and came back larger than it has
    ever been, which is the only version of that worth a row: a card that was
    always a one-off being a one-off again is not news.
    """
    registered, lists = _history(db_path, deck, variant)
    sizes: dict[int, int] = {}
    for row in lists:
        index = bin_of(row["date"], since)
        sizes[index] = sizes.get(index, 0) + 1

    held: dict[tuple[str, str], dict[int, list[int]]] = {}
    copies: dict[tuple[str, str], dict[int, list[int]]] = {}
    for row in registered:
        key, index = (row["card"], row["zone"]), bin_of(row["date"], since)
        held.setdefault(key, {}).setdefault(index, []).append(row["list_id"])
        copies.setdefault(key, {}).setdefault(index, []).append(row["main"])

    drift_cards = set(config.TRACKED_DECKS[deck]["copy_drift"])
    first = bin_of(since, since)
    timeline = []
    for index in sorted(i for i in sizes if i >= first):
        size, was_size = sizes[index], sizes.get(index - 1, 0)
        # A delta may not cross the regime boundary: the fortnight before the
        # first post-regime bin belongs to a different era, so what it played is
        # not what this deck put down. Returns still read past it, since how
        # long a card has been gone is a fact about the deck and not the regime.
        comparable = index - 1 >= first
        start = bin_start(index, since)
        end = (date.fromisoformat(start) + timedelta(days=config.TRACK_BIN_DAYS - 1)).isoformat()
        found = []

        for (card, zone), bins in sorted(held.items()):
            if index not in bins:
                continue
            n, was = len(bins[index]), len(bins.get(index - 1, []))
            share = n / size
            was_share = was / was_size if was_size else 0.0

            other = held.get((card, "side" if zone == "main" else "main"), {})
            if not was and _is_return(bins, index, sizes, zone, share):
                phrase = (
                    f"moves to the {zone}board"
                    if index - 1 in other
                    else _return_phrase(bins, index)
                )
                found.append(
                    {
                        "kind": "return",
                        "zone": zone,
                        "card": card,
                        "text": f"{card} {phrase}, {n} of {size} lists ({share:.0%})",
                    }
                )
            elif comparable and moved(n, size, was, was_size):
                found.append(adoption_row(card, zone, n, size, was, was_size))

            if comparable and zone == "main" and card in drift_cards and (card, zone) in copies:
                bin_copies = copies[(card, zone)]
                if index in bin_copies and index - 1 in bin_copies:
                    now = sum(bin_copies[index]) / len(bin_copies[index])
                    before = sum(bin_copies[index - 1]) / len(bin_copies[index - 1])
                    if abs(now - before) >= config.TRACK_COPY_DELTA:
                        found.append(copies_row(card, zone, now, before))

        for event in events():
            if start <= event["date"] <= end:
                found.append({"kind": "event", "zone": None, "card": None, "text": event["label"]})

        timeline.append({"bin": index, "start": start, "end": end, "lists": size, "found": found})
    return timeline


def _is_return(
    bins: dict[int, list[int]], index: int, sizes: dict[int, int], zone: str, share: float
) -> bool:
    """Whether an appearance with no bin behind it is a return worth a row.

    Three conditions, each dropping a different false one. The absence has to
    cover `RETURN_ABSENCE_DAYS`, because a staple running at a few lists a week
    misses a fortnight on chance alone and reads as having left. The gate is per
    zone, because a sideboard churns far harder than a mainboard: two thirds of
    the sideboard names this deck has registered appear in two weeks or fewer,
    and between them they carry four percent of its volume. And the appearance
    has to be a larger share than the card has ever held, which is what
    separates a card the field turned to from one that was always a one-off.
    """
    gate = config.TRACK_RETURN_MAIN_LISTS if zone == "main" else config.TRACK_RETURN_SIDE_LISTS
    if len(bins[index]) < gate:
        return False
    absence = config.RETURN_ABSENCE_DAYS // config.TRACK_BIN_DAYS
    if any(index - back in bins for back in range(1, absence + 1)):
        return False
    if not config.TRACK_RETURN_BEATS_PEAK:
        return True
    peak = max(
        (len(held) / sizes[i] for i, held in bins.items() if i < index and sizes.get(i)),
        default=0.0,
    )
    return share > peak


def _return_phrase(bins: dict[int, list[int]], index: int) -> str:
    """How the row says the card came back, or that it never went away first."""
    prior = [i for i in bins if i < index]
    if not prior:
        return "appears for the first time"
    weeks = (index - max(prior)) * config.TRACK_BIN_DAYS // 7
    return f"returns after {weeks} weeks away"
