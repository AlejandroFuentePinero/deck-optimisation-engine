"""Whether the lists on a configuration finished differently from the lists without it.

Adoption says what the camp registered. This asks the harder question behind it:
whether registering the thing went with finishing better. The two are constantly
confused, and the confusion is what makes a share look like evidence about a card.

The instrument is a contrast inside the archetype, never a level. Every published
list already finished, so absolute performance is unreadable: what can be read is
whether the lists carrying a configuration are distributed differently across the
bands the site publishes than the lists of the same camp without it. Both arms are
truncated at the same bar, so the truncation cancels.

It is a disconfirmation instrument. At the populations this archetype publishes
the smallest difference it can see is tens of points of top-16 rate, which is far
larger than any flex slot moves, so it will almost never confirm that something
helps. It can rule out a large effect, and most of what a share tempts a reader
into believing is a large effect that is not there. Every reading therefore
carries the floor it was taken at, and a null says which.
"""

import math
from pathlib import Path

from . import config
from .store import CHALLENGE_CLASS, LEAGUE, _cap_effect, _rows

import duckdb

# The cut the bands are drawn at. Top-8 against the rest would split identical
# records on tiebreakers; top-16 against 17-32 is where performance separates.
BAND = config.PROVEN_PILOT_PLACEMENT

# When a difference is called rather than left as noise. The conventional bar,
# named here because the reading reports against it and a bar left implicit is
# one nobody can argue with.
ALPHA = 0.05

# The power the floor is quoted at: the difference this contrast would catch four
# times in five. Quoted rather than assumed, since a null is only as strong as
# the difference it could have seen, and a reader given the p-value alone would
# take "no difference found" for "no difference".
POWER_Z = 2.8

SEPARATES = "separates"
UNDETECTABLE = "undetectable"


def _arm_name(main: int | None, side: int | None, board: str | None) -> str:
    """What the arm was drawn on, as the row says it: a reading whose arm is not
    named is a difference between two populations nobody can identify."""
    if board:
        return f"{board}deck"
    if main is None and side is None:
        return "any count"
    return f"{main or 0}/{side or 0}"


def _fisher(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table, by summing every table at
    least as extreme as the observed one.

    Exact rather than a chi-square, because the arms here run to single figures
    of lists and the approximation is worst exactly there.
    """
    n = a + b + c + d
    if not all((a + b, c + d, a + c, b + d)):
        return 1.0

    def probability(hit: int) -> float:
        return math.comb(a + b, hit) * math.comb(c + d, a + c - hit) / math.comb(n, a + c)

    observed = probability(a)
    reachable = range(max(0, a + c - (c + d)), min(a + b, a + c) + 1)
    return min(
        1.0, sum(probability(hit) for hit in reachable if probability(hit) <= observed + 1e-12)
    )


def _floor(rate: float, with_arm: int, without_arm: int) -> float | None:
    """The smallest difference in top-16 rate this contrast could have caught.

    None where an arm is empty, there being no contrast to take. A reading whose
    floor is wider than any difference a card could produce is a null that says
    nothing, and the row has to be able to say so.
    """
    if not with_arm or not without_arm:
        return None
    return POWER_Z * math.sqrt(rate * (1 - rate) * (1 / with_arm + 1 / without_arm))


# A list is in the arm when it registered the configuration asked about. Named
# once, because the challenge contrast and the league conversion have to split
# the population the same way or they are not two readings of one thing.
_ARM = """
    SELECT d.list_id, d.pilot, d.placement,
           coalesce(max(CASE WHEN {match} THEN 1 ELSE 0 END), 0) AS arm
    FROM decklists d LEFT JOIN configurations c USING (list_id)
    WHERE d.archetype = ? AND d.camp = ? AND d.date >= ? AND d.date <= ?
      AND {stratum}
    GROUP BY 1, 2, 3
"""


def _match(main: int | None, side: int | None, board: str | None) -> tuple[str, list]:
    """What puts a list in the arm: the card at any count, in one board, or at
    one configuration.

    Three different claims, and the caller means one of them. At any count asks
    whether playing the card at all goes with finishing. In a board asks whether
    where the copies sit does, which is the question a migration raises: a camp
    moving a card out of the sideboard is not a camp changing how many it runs.
    At a configuration asks about this many copies in these boards, which is what
    a slot decision is finally about.
    """
    if board:
        return f"c.card = ? AND c.{board} > 0", []
    if main is None and side is None:
        return "c.card = ?", []
    return "c.card = ? AND c.main = ? AND c.side = ?", [main or 0, side or 0]


def _arms(
    con: duckdb.DuckDBPyConnection, card, main, side, board, camp, stratum, window
) -> list[dict]:
    match, extra = _match(main, side, board)
    clause = f"d.event_class {'=' if stratum == LEAGUE else '<>'} '{LEAGUE}'"
    # The arm's placeholders sit in the SELECT and so bind before the scope's,
    # which is the order the parameters go in: bound the other way round, a card
    # name would be compared against a date and the query would not even run.
    return _rows(
        con.execute(
            _ARM.format(match=match, stratum=clause),
            [card, *extra, config.ARCHETYPE, camp, *window],
        )
    )


def _band(lists: list[dict]) -> tuple[int, int]:
    """A population split into the two bands: above the cut, and below it.

    A list the event never ranked is in neither. Only challenge-class lists reach
    here, so that is a published top 32 with no standing attached rather than a
    league trophy, and counting it as having missed the cut would read a gap in
    the publication as a finish.
    """
    ranked = [row for row in lists if row["placement"]]
    made = sum(1 for row in ranked if row["placement"] <= BAND)
    return made, len(ranked) - made


def _conversion(con, card, main, side, board, camp, window) -> dict:
    """The league half: how much more of the trophies the arm holds than it holds
    of the challenge lists.

    A league publishes 5-0s and never the entries behind them, so there is no
    rate here to take: a configuration's trophy count is its entries times its
    conversion and only the product is served. The challenge stratum stands in
    for the entries, which is what turns two counts into a reading, and it is the
    same substitution `store.conversion_gap` makes at the camp level.

    Capped at one list per pilot per stratum, for the reason that reading caps:
    a dump is published without dedup, so one grinder repeating a build would
    otherwise report his habit as the configuration converting. The cache stays
    as published; the cap is on the reading.
    """
    shares = {}
    for stratum in (LEAGUE, CHALLENGE_CLASS):
        lists = _arms(con, card, main, side, board, camp, stratum, window)
        pilots: dict[str, int] = {}
        for row in lists:
            pilots[row["pilot"]] = max(pilots.get(row["pilot"], 0), row["arm"])
        shares[stratum] = {
            "pilots": len(pilots),
            "on_it": sum(pilots.values()),
            "share": sum(pilots.values()) / len(pilots) if pilots else None,
            "lists": len(lists),
            "uncapped": sum(row["arm"] for row in lists) / len(lists) if lists else None,
        }
    league, challenge = shares[LEAGUE], shares[CHALLENGE_CLASS]

    def difference(key: str) -> float | None:
        pair = (league[key], challenge[key])
        return pair[0] - pair[1] if None not in pair else None

    gap, uncapped = difference("share"), difference("uncapped")
    return {
        "league": league,
        "challenge": challenge,
        "gap": gap,
        "uncapped": uncapped,
        # What counting each pilot once did to it. A gap one grinder's repeated
        # trophies produced collapses or turns round here rather than being
        # published, which is the same guard the camp-level reading applies.
        "cap_effect": None if None in (gap, uncapped) else _cap_effect(gap, uncapped),
    }


def contrast(
    card: str,
    main: int | None = None,
    side: int | None = None,
    board: str | None = None,
    db_path: Path = config.DB_PATH,
    camp: str = "non-fallaji",
    since: str | None = None,
    until: str | None = None,
) -> dict:
    """Whether the camp's lists on a configuration finished differently from the rest.

    The window defaults to the whole post-regime history rather than the fresh
    fortnight, and deliberately: the fresh window splits into arms of twenty, at
    which the floor is over forty points of top-16 rate and every reading is a
    null that means nothing. The regime boundary still holds, since lists either
    side of it answered to different formats.

    The reading comes back with the floor it was taken at, always. A null under a
    floor of twenty points says the camp did not separate by twenty points, which
    is worth knowing and is not the same claim as the configuration being neutral.
    """
    window = (since or config.REGIME_BOUNDARY, until or "9999-12-31")
    with duckdb.connect(db_path, read_only=True) as con:
        lists = _arms(con, card, main, side, board, camp, CHALLENGE_CLASS, window)
        conversion = _conversion(con, card, main, side, board, camp, window)

    with_arm = [row for row in lists if row["arm"]]
    without = [row for row in lists if not row["arm"]]
    made_with, missed_with = _band(with_arm)
    made_without, missed_without = _band(without)
    ranked_with, ranked_without = made_with + missed_with, made_without + missed_without

    rates = {
        "with": made_with / ranked_with if ranked_with else None,
        "without": made_without / ranked_without if ranked_without else None,
    }
    difference = (
        rates["with"] - rates["without"] if None not in (rates["with"], rates["without"]) else None
    )
    pooled = (made_with + made_without) / (ranked_with + ranked_without) if lists else 0.0
    p = _fisher(made_with, missed_with, made_without, missed_without)

    return {
        "card": card,
        "configuration": _arm_name(main, side, board),
        "camp": camp,
        "since": window[0],
        "band": BAND,
        "with_lists": ranked_with,
        "with_made_band": made_with,
        "with_rate": rates["with"],
        "without_lists": ranked_without,
        "without_made_band": made_without,
        "without_rate": rates["without"],
        "difference": difference,
        "p": p,
        # What the contrast could have seen. A null is only as strong as this.
        "floor": _floor(pooled, ranked_with, ranked_without),
        "state": SEPARATES if p < ALPHA else UNDETECTABLE,
        "conversion": conversion,
    }
