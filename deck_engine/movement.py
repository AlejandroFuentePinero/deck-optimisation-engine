"""What a camp is doing with a card, as movement rather than as a level.

Adoption reports where a configuration stands. Three questions a slot decision
actually turns on are about where it is going, and none of them is answerable from
a share on its own: whether the copies are crossing between the boards, what the
lists that went elsewhere spent the slot on, and which of the cards new to the
pool are still climbing.

Each is a reading over the same two windows every other figure uses, in one camp
and one stratum, since a share over two of anything is a number no population
reported.
"""

from pathlib import Path

from . import config, flags
from .classify import camp as camp_of
from .store import CHALLENGE_CLASS, adoption, series, windows

# How far the copies have to cross before the camp is moving the card rather than
# arguing about how many. A share of copies, not of lists: a camp that keeps the
# count and moves where they sit has changed the card's role, which is the whole
# reading, and a count of lists playing it would report nothing at all.
BOARD_SHIFT = 0.15

TO_MAIN, TO_SIDE, STEADY = "to main", "to side", "steady"


def _boards(rows: list[dict], window: str) -> dict:
    """One window's copies of a card, by the board they were registered in.

    Counted as copies and not as lists, because that is what crosses. A list
    moving one of three copies to the sideboard still plays the card, and a
    tally of lists would see nothing happen.
    """
    lists = sum(row[f"{window}_lists"] for row in rows)
    main = sum(row["main"] * row[f"{window}_lists"] for row in rows)
    side = sum(row["side"] * row[f"{window}_lists"] for row in rows)
    copies = main + side
    return {
        "lists": lists,
        "population": next((row[f"{window}_population"] for row in rows), 0),
        "main_copies": main,
        "side_copies": side,
        "main_share": main / copies if copies else None,
    }


def migration(
    card: str,
    db_path: Path = config.DB_PATH,
    camp: str = "non-fallaji",
    stratum: str = CHALLENGE_CLASS,
) -> dict | None:
    """Whether a camp is moving a card between the boards, and which way.

    The reading the configuration unit exists for. A card whose total the camp
    holds steady while the copies cross into the maindeck is a card whose role
    the camp has changed its mind about, and every count-level figure reports
    that as nothing having happened.

    None where the camp registered the card in neither window: there is no
    movement in a card nobody played.
    """
    rows = [
        row
        for row in adoption(db_path)
        if row["card"] == card and (row["camp"], row["stratum"]) == (camp, stratum)
    ]
    if not rows:
        return None

    was, now = _boards(rows, "baseline"), _boards(rows, "fresh")
    shift = (
        now["main_share"] - was["main_share"]
        if None not in (was["main_share"], now["main_share"])
        else None
    )
    direction = STEADY
    if shift is not None and abs(shift) >= BOARD_SHIFT:
        direction = TO_MAIN if shift > 0 else TO_SIDE
    return {
        "card": card,
        "camp": camp,
        "stratum": stratum,
        "baseline": was,
        "fresh": now,
        "shift": shift,
        "direction": direction,
    }


def _fresh_lists(db_path: Path, camp: str, stratum: str) -> list[dict]:
    """The camp's fresh-window lists in one stratum, each with what it registered.

    Taken from the series rather than the adoption table because these readings
    are about what one list held alongside another, which a per-configuration
    share has already summed away.
    """
    read = windows(db_path)
    if read is None:
        return []
    return [
        row
        for row in series(db_path, read["fresh_start"])
        if (row["camp"], row["stratum"]) == (camp, stratum)
    ]


def substitution(
    card: str,
    main: int,
    side: int,
    db_path: Path = config.DB_PATH,
    camp: str = "non-fallaji",
    stratum: str = CHALLENGE_CLASS,
) -> list[dict]:
    """What the camp's lists that went elsewhere on a slot registered instead.

    A slot decision is a trade, and adoption cannot see one: it reports what
    share holds a configuration, never what the share that does not holds in its
    place. So the camp's fresh lists split on the configuration, and every other
    card is read in both halves. A card the half without it plays far more of is
    what that half spent the slot on.

    Returned for every card either half registered, most overrepresented among
    the lists that went elsewhere first, so the caller reads down as far as it is
    still interesting rather than being handed a cut somebody else chose. The
    signature cards come back with the rest and say nothing, being in every list
    of the archetype by the rule that admits it.
    """
    lists = _fresh_lists(db_path, camp, stratum)
    on_it = [row for row in lists if (card, main, side) in row["configurations"]]
    elsewhere = [row for row in lists if row not in on_it]
    if not on_it or not elsewhere:
        return []

    def plays(population: list[dict]) -> dict[str, int]:
        counted: dict[str, int] = {}
        for row in population:
            for played, _, _ in row["configurations"]:
                counted[played] = counted.get(played, 0) + 1
        return counted

    here, there = plays(on_it), plays(elsewhere)
    return sorted(
        (
            {
                "card": played,
                "on_it": here.get(played, 0) / len(on_it),
                "elsewhere": there.get(played, 0) / len(elsewhere),
                "difference": there.get(played, 0) / len(elsewhere)
                - here.get(played, 0) / len(on_it),
                "on_it_lists": len(on_it),
                "elsewhere_lists": len(elsewhere),
            }
            for played in here | there
        ),
        key=lambda row: (-row["difference"], row["card"]),
    )


def climbing(
    db_path: Path = config.DB_PATH,
    camp: str = "non-fallaji",
    stratum: str = CHALLENGE_CLASS,
) -> list[dict]:
    """The cards new to the pool that the camp is still taking up, steepest first.

    Two readings that only mean something together. Novelty says a card is
    innovation-grade rather than a staple the fortnight happened to move; the
    delta says the camp is going towards it rather than the card having turned up
    once. Either alone is the thing it is constantly mistaken for: a fringe flag
    on its own is one pilot's experiment, and a delta on its own is a staple
    drifting.

    Read in the camp's own stratum, and the flag is matched on the card rather
    than the configuration, since what is new is the card and where the copies go
    is the camp's next argument.
    """
    novel = {flag["card"] for flag in flags.fringe(db_path) if flag["camp"] == camp}
    rising: dict[str, dict] = {}
    for row in adoption(db_path):
        if (row["camp"], row["stratum"]) != (camp, stratum) or row["card"] not in novel:
            continue
        if not row["fresh_adoption"] or (row["delta"] or 0) <= 0:
            continue
        held = rising.setdefault(
            row["card"], {"card": row["card"], "camp": camp, "stratum": stratum, "delta": 0.0}
        )
        # A card's climb is the camp arriving at it, over whichever counts it
        # arrived at: read off one configuration, a card the camp took up at two
        # different counts would report half its own movement.
        held["delta"] += row["delta"]
        held["adoption"] = held.get("adoption", 0.0) + row["fresh_adoption"]
        if row["fresh_adoption"] > held.get("leading_adoption", 0.0):
            held |= {
                "leading_adoption": row["fresh_adoption"],
                "main": row["main"],
                "side": row["side"],
                "population": row["fresh_population"],
            }
    return sorted(rising.values(), key=lambda row: (-row["delta"], row["card"]))


def unplayed(
    reference_cards: dict[str, tuple[int, int]],
    db_path: Path = config.DB_PATH,
    stratum: str = CHALLENGE_CLASS,
    floor: float = config.UNPLAYED_FLOOR,
    limit: int = config.UNPLAYED_LIMIT,
) -> list[dict]:
    """The cards a real part of the pilot's camp plays that his 75 registers none of.

    The blind spot between the two readings that look at the reference list. The
    slot audit reads the slots he took, so it can only speak about cards he
    plays. `reference.missing_core` reads what the camp is near-unanimous on, so
    it speaks only above the core bar. Everything in between is a card a third of
    the camp made a decision about and no surface mentions.

    Read on the card and not the configuration, as the missing-core reading is
    and for its reason: a camp that agrees on playing a card and argues about how
    many still leaves the pilot who runs none of it standing outside all of them,
    and a per-configuration share would put every count under the floor exactly
    where the case is strongest.

    Capped at `limit`, because the floor is a judgment about how much of the camp
    has to disagree before it is worth the pilot's attention and the tail below
    the top of that is the pool rather than a finding. What was dropped is said
    on the reading rather than left silent.
    """
    rows = [row for row in adoption(db_path) if row["stratum"] == stratum]
    belongs = camp_of({card: main for card, (main, _) in reference_cards.items()})

    playing: dict[str, float] = {}
    leading: dict[str, dict] = {}
    for row in sorted(rows, key=lambda row: (row["card"], row["main"], row["side"])):
        if row["camp"] != belongs or not row["fresh_adoption"]:
            continue
        playing[row["card"]] = playing.get(row["card"], 0.0) + row["fresh_adoption"]
        if row["fresh_adoption"] > leading.get(row["card"], {}).get("fresh_adoption", 0.0):
            leading[row["card"]] = row

    absent = sorted(
        (
            {
                "camp": belongs,
                "stratum": stratum,
                "card": card,
                "camp_playing": playing[card],
                "camp_main": row["main"],
                "camp_side": row["side"],
                "camp_adoption": row["fresh_adoption"],
                "camp_delta": row["delta"],
                "population": row["fresh_population"],
                # Running none of it is a configuration like any other, and this
                # is the camp's share of it: what is left once every count the
                # camp does register the card at is taken out.
                "confidence": max(0.0, 1.0 - playing[card]),
            }
            for card, row in leading.items()
            if card not in reference_cards and playing[card] >= floor
        ),
        key=lambda row: (-row["camp_playing"], row["card"]),
    )
    for rank, row in enumerate(absent):
        row["dropped"] = max(0, len(absent) - limit) if rank == 0 else 0
    return absent[:limit]
