"""The paper Spotlight readings: where the deck finished, and how it won.

A Spotlight is not a big challenge and is not read as one. Two differences drive
everything here.

The first is the denominator. A challenge publishes its top 32, so every MTGO
share in this project is a share of a cut and is already performance-weighted. A
Spotlight publishes every finisher, so a share of its field is a true metagame
share and its top 32 is a separate, smaller reading. The two quantities are not
interchangeable and never share an axis: the only number that can sit beside a
weekly figure is the Spotlight's own top-32 share, and it carries an n of a
handful.

The second is that rank is not comparable between events. Dallas seated 932 and
Brisbane 574, so rank 300 is the top third of one and past the halfway mark of
the other. Every positional reading here is therefore a share of the field the
list actually beat, which is the same quantity at both events, and the null is
explicit: a deck that performed exactly like the field is the diagonal.

Match record is read from the wins and losses melee publishes and never from
points, because points stop accruing at the top cut. A pilot who won the event
holds fewer points than the Swiss leader and three more match wins, and points
would score that as the worse tournament.

Lists here are classified by the same `classify` rule the MTGO path uses, on
mainboards normalised by `melee.front_face`. They are never loaded into the
store: the challenge-class readings are defined as every event class except
league, so a Spotlight landing in `decklists` would be counted as challenge-class
by default and nine hundred paper lists would swamp a weekly field of four
hundred.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from . import classify, config, timeline

# The band a Spotlight is read against the weekly report on. Thirty-two because
# that is what a challenge publishes, so it is the one slice of a paper event
# whose share means the same thing as `chal_share` does.
CUT = 32


def cached(spotlight: dict, directory: Path | None = None) -> Path:
    """Where a Spotlight's fetched payload lives."""
    return (directory or config.MELEE_DIR) / f"{spotlight['id']}.json"


def load(spotlight: dict, directory: Path | None = None) -> dict:
    """A Spotlight's payload, as fetched."""
    return json.loads(cached(spotlight, directory).read_text(encoding="utf-8"))


def week(spotlight: dict) -> str:
    """The Monday keying the week the Spotlight fell in.

    Keyed by its Monday and shown by its Sunday, exactly as every other weekly
    reading is, so a Spotlight sits on the report's own calendar rather than
    beside it. Brisbane on Saturday 29 August is the week ending 30 August.
    """
    day = date.fromisoformat(spotlight["date"])
    return (day - timedelta(days=day.weekday())).isoformat()


def members(payload: dict, deck: str = "blink", variant: str = "esper") -> list[dict]:
    """The Spotlight's lists that answer to the deck's rule, in finishing order.

    The rule and not the name melee publishes. A decklist name is typed by its
    pilot: this field carried "Esper Blink", "Azorius Blink" and a bare "Esper"
    for the same seventy-five, and carried "Esper Blink" for lists that are not
    the deck. Membership is the mainboard, tested by `classify`, or the paper
    numbers would answer to a different question from the MTGO ones.
    """
    found = []
    for entry in payload["lists"]:
        name = classify.archetype(SimpleNamespace(mainboard=entry["main"]))
        if name != deck or classify.variant(name, entry["main"]) != variant:
            continue
        found.append(entry)
    return sorted(found, key=lambda row: row["rank"])


def _rate(rows: list[dict]) -> tuple[float | None, int, int, int]:
    """Pooled match win rate over the lists given, and the record it came from."""
    wins = sum(row["wins"] for row in rows)
    losses = sum(row["losses"] for row in rows)
    draws = sum(row["draws"] for row in rows)
    played = wins + losses + draws
    return (wins / played if played else None), wins, losses, draws


def reading(payload: dict, deck: str = "blink", variant: str = "esper") -> dict:
    """Everything the report says about one Spotlight.

    `field_share` is the true metagame share the MTGO data cannot produce, and
    `cut_share` is the like-for-like one it can. `conversion` is the ratio of the
    two: above one, the deck held more of the top 32 than of the field, which is
    the honest performance number and is comparable between events of different
    size. `placings` is each list's finish as the share of the field above it,
    which is what makes two fields of different size one axis.
    """
    lists = payload["lists"]
    field = len(lists)
    ours = members(payload, deck, variant)
    cut = [row for row in ours if row["rank"] <= CUT]
    rate, wins, losses, draws = _rate(ours)
    field_rate, *_ = _rate(lists)
    return {
        "id": payload["tournament"]["id"],
        "name": payload["tournament"]["name"],
        "players": payload["tournament"]["players"],
        "field": field,
        "lists": len(ours),
        "field_share": len(ours) / field if field else 0.0,
        "cut_lists": len(cut),
        "cut_share": len(cut) / CUT,
        "conversion": (len(cut) / CUT) / (len(ours) / field) if ours and field else None,
        "best": ours[0]["rank"] if ours else None,
        "win_rate": rate,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "field_win_rate": field_rate,
        # Each finish as the share of the field that placed above it: 0 is the
        # winner, 0.5 the middle of the room. In these units a field of 932 and a
        # field of 574 are one axis, and a deck whose lists are spread evenly
        # through the standings plots as the diagonal, which is the null every
        # positional reading here is against.
        "placings": sorted((row["rank"] - 1) / field for row in ours),
    }


def mtgo_lists(db_path: Path, deck: str, variant: str, start: str, end: str) -> list[dict]:
    """The MTGO lists of the variant published between two days, boards apart.

    Shaped like a Spotlight's own lists so one comparison serves both sides of
    the chain: the first Spotlight is read against MTGO and the next against the
    Spotlight before it.
    """
    registered, _ = timeline._history(db_path, deck, variant)
    boards: dict[int, dict] = {}
    for row in registered:
        if not start <= row["date"] <= end:
            continue
        entry = boards.setdefault(row["list_id"], {"main": {}, "side": {}})
        zone = "main" if row["main"] > 0 else "side"
        entry[zone][row["card"]] = row["main"] if zone == "main" else 1
    return list(boards.values())


def chain(
    db_path: Path,
    deck: str = "blink",
    variant: str = "esper",
    spotlights: tuple[dict, ...] | None = None,
    directory: Path | None = None,
) -> list[dict]:
    """Each Spotlight's reading and findings, in the order they were played.

    The comparison is a chain and not a lookup against whatever bin a date falls
    in. The first Spotlight is read against the last MTGO fortnight that closed
    before it, which is the last thing the report said before the event; every
    Spotlight after it is read against the one before, which is the only clean
    comparison in this data, both sides being paper and a week apart.

    A row against MTGO is a cross-population reading and says so. The Australian
    field, the American field and the MTGO field are three populations, so a card
    at nine tenths of one and half of another is not the deck changing its mind.
    """
    entries = []
    previous: list[dict] | None = None
    previous_label = ""
    for spot in spotlights or config.SPOTLIGHTS:
        payload = load(spot, directory)
        ours = members(payload, deck, variant)
        if previous is None:
            index = timeline.bin_of(spot["date"]) - 1
            start = timeline.bin_start(index)
            end = (
                date.fromisoformat(start) + timedelta(days=config.TRACK_BIN_DAYS - 1)
            ).isoformat()
            baseline = mtgo_lists(db_path, deck, variant, start, end)
            previous_label = f"the MTGO fortnight to {end}"
            crossed = True
        else:
            baseline, crossed = previous, False
        entries.append(
            {
                **reading(payload, deck, variant),
                "label": spot["label"],
                "date": spot["date"],
                "week": week(spot),
                "against": previous_label,
                "cross_population": crossed,
                "baseline_lists": len(baseline),
                "found": findings(ours, baseline, deck),
            }
        )
        previous, previous_label = ours, spot["label"]
    return entries


def _held(rows: list[dict]) -> dict[tuple[str, str], list[int]]:
    """Card and zone to the mainboard copies of the lists registering it.

    A card in the mainboard counts as mainboard and not as both, even where the
    list also sideboards it. That is the store's own rule, and the two sides of
    a comparison have to answer to one: melee publishes the boards separately,
    so a card split three and two across them would count once on the MTGO side
    and twice here, and every split card would read as a sideboard adoption.
    """
    held: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        for card, copies in row["main"].items():
            held.setdefault((card, "main"), []).append(copies)
        for card in row["side"]:
            if card not in row["main"]:
                held.setdefault((card, "side"), []).append(0)
    return held


def _moved(n: int, size: int, was: int, was_size: int) -> bool:
    """Whether a share moved far enough to be a row, at two unequal sizes.

    The fortnight's own count gate does not transfer here and quietly inverts.
    It asks that the number of lists move by `TRACK_MIN_LISTS`, which holds the
    evidence constant only while the two populations are roughly the same size,
    as two MTGO fortnights are. A Spotlight of eleven lists against a fortnight
    of a hundred and twelve is a tenfold difference, and there the difference in
    raw counts is mostly the difference in population: eleven lists holding a
    card at a third and a hundred and twelve holding it at a seventh clears a
    five-list gate on the denominators alone, and every moderately played card in
    the field earns a row.

    So the gate is the same quantity read the way it was meant: the move has to
    be worth `TRACK_MIN_LISTS` in the smaller of the two populations, which is
    all the evidence there actually is. A thin Spotlight then reports little,
    which is the honest outcome. Eleven lists cannot evidence a five-list change
    at anything under a forty-five point swing, and saying so beats printing
    three rows that are the sample size talking.
    """
    share = n / size
    was_share = was / was_size if was_size else 0.0
    smaller = min(size, was_size)
    return abs(share - was_share) >= config.TRACK_ADOPTION_DELTA and (
        smaller * abs(share - was_share) >= config.TRACK_MIN_LISTS
    )


def findings(current: list[dict], baseline: list[dict], deck: str = "blink") -> list[dict]:
    """What the Spotlight's lists changed against the reading before it.

    Adoption and copies only. A return says a card the deck had stopped playing
    came back, which is a claim about one population's history over months, and a
    paper field is not that population: a card absent from MTGO for a month and
    present at Brisbane is the Australian field building differently, not the
    deck rediscovering anything.

    The thresholds are the fortnight's own, unchanged. They were calibrated on
    MTGO fortnights, so a Spotlight thin enough to clear the count gate on two
    pilots will produce noisy rows, and the caller says so rather than this
    silently raising the bar for paper.
    """
    size, was_size = len(current), len(baseline)
    if not size or not was_size:
        return []
    held, was_held = _held(current), _held(baseline)
    drift = set(config.TRACKED_DECKS[deck]["copy_drift"])
    found = []
    for (card, zone), copies in sorted(held.items()):
        n, was = len(copies), len(was_held.get((card, zone), []))
        if _moved(n, size, was, was_size):
            found.append(timeline.adoption_row(card, zone, n, size, was, was_size))
        if zone == "main" and card in drift and was:
            now = sum(copies) / n
            before = sum(was_held[(card, zone)]) / was
            if abs(now - before) >= config.TRACK_COPY_DELTA:
                found.append(timeline.copies_row(card, zone, now, before))
    # A card the deck dropped entirely shows up in neither loop above, having no
    # row of its own in the current bin, so it is read from the baseline's side.
    for (card, zone), copies in sorted(was_held.items()):
        if (card, zone) not in held and _moved(0, size, len(copies), was_size):
            found.append(timeline.adoption_row(card, zone, 0, size, len(copies), was_size))
    return _migrations(found, held, size)


def _migrations(found: list[dict], held: dict, size: int) -> list[dict]:
    """One card climbing in a board and falling in the other is one decision.

    It changed zone. Left as two rows it reads as the deck adopting a card and
    abandoning the same card in the same week, which is the confusion the
    fortnight timeline names a migration to avoid: promoting a sideboard staple
    is a decision about what the card is for, not the deck discovering it.
    """
    climbed = {row["card"] for row in found if row["zone"] == "main" and "climbed" in row["text"]}
    fell = {row["card"] for row in found if row["zone"] == "side" and "fell" in row["text"]}
    moved_zone = climbed & fell
    if not moved_zone:
        return found
    rows = [row for row in found if row["card"] not in moved_zone]
    for card in sorted(moved_zone):
        n = len(held[(card, "main")])
        rows.append(
            {
                "kind": "migration",
                "zone": "main",
                "card": card,
                "text": f"{card} moves to the mainboard, {n} of {size} lists ({n / size:.0%})",
            }
        )
    return rows
