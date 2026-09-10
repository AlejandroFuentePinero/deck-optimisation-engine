"""The weekly readings of a tracked deck: presence, conversion, drift, stability.

A tracked deck gets no slot audit and no hypotheses. What it gets is a fixed set
of numbers, computed the same way every week, that say how much of the field it
holds, whether it converts that presence into finishes, and whether it is still
being built or merely copied.

Every reading here is a share of a published stratum rather than a bare count.
A week that ran three challenges publishes three times the top-32 slots of a week
that ran one, so a count rises with the calendar and a share does not. The counts
are carried beside the shares regardless, because a share off two lists is a
figure nobody should read without seeing the two.

Read within one variant, never across both. The archetype's two variants are
different decks in the sense that matters to a build reading, and the Orzhov
half is thin enough that pooling it would move the Esper numbers without ever
being visible in them.
"""

from pathlib import Path

import duckdb

from . import config
from .store import _rows

# The week bucket. ISO weeks start Monday, and the report is generated Monday
# for the week that just closed, so a bucket is always a settled week.
_WEEK = "CAST(CAST(date_trunc('week', CAST(date AS DATE)) AS DATE) AS VARCHAR)"

# The challenge-class stratum: every event that publishes a placement. The event
# classes differ in size and in prestige and are pooled deliberately, since what
# the reading wants is the whole of the field that keeps standings.
_CHALLENGE = "event_class <> 'league'"


def weekly(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    since: str = config.REGIME_BOUNDARY,
) -> list[dict]:
    """One row per week: the deck's presence and conversion against the field.

    Weeks come from the field rather than from the deck, so a week the deck
    published nothing in is a zero on the plot instead of a gap in it. The
    denominators are the whole published stratum that week: every challenge-class
    list for presence, every challenge-class list that placed top 8 for
    conversion, every league list for trophies.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        return _rows(
            con.execute(
                f"""
                WITH field AS (
                    SELECT {_WEEK} AS week,
                           count(*) FILTER ({_CHALLENGE}) AS chal_field,
                           count(*) FILTER ({_CHALLENGE} AND placement <= 8) AS top8_field,
                           count(*) FILTER (event_class = 'league') AS league_field
                    FROM decklists WHERE date >= ? GROUP BY week
                ),
                deck AS (
                    SELECT {_WEEK} AS week,
                           count(*) FILTER ({_CHALLENGE}) AS chal,
                           count(*) FILTER ({_CHALLENGE} AND placement <= 8) AS top8,
                           count(*) FILTER ({_CHALLENGE} AND placement <= 16) AS top16,
                           count(*) FILTER (event_class = 'league') AS trophies,
                           count(*) AS lists
                    FROM decklists
                    WHERE archetype = ? AND camp = ? AND date >= ? GROUP BY week
                )
                SELECT f.week,
                       coalesce(d.lists, 0) AS lists,
                       coalesce(d.chal, 0) AS chal,
                       f.chal_field,
                       coalesce(d.chal, 0) / f.chal_field AS chal_share,
                       coalesce(d.top8, 0) AS top8,
                       f.top8_field,
                       CASE WHEN f.top8_field > 0
                            THEN coalesce(d.top8, 0) / f.top8_field END AS top8_share,
                       coalesce(d.top16, 0) AS top16,
                       coalesce(d.trophies, 0) AS trophies,
                       f.league_field,
                       CASE WHEN f.league_field > 0
                            THEN coalesce(d.trophies, 0) / f.league_field END AS trophy_share
                FROM field f LEFT JOIN deck d USING (week)
                ORDER BY f.week
                """,
                [since, deck, variant, since],
            )
        )


def copy_drift(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    since: str = config.REGIME_BOUNDARY,
) -> list[dict]:
    """Mean mainboard copies per week, for the cards the deck argues about.

    The cards are named in the deck's own config entry rather than found by a
    scan, so the plot carries the same lines every week and a line appearing is
    a decision somebody made. What they have in common is near-universal
    adoption: nothing about them shows up in an adoption reading, because every
    list plays them and the whole of the disagreement is how many.

    The mean is taken over the lists that register the card, which separates the
    count decision from the inclusion one. The list count rides along, since a
    mean off four lists is not a mean.
    """
    cards = list(config.TRACKED_DECKS[deck]["copy_drift"])
    placeholders = ",".join("?" * len(cards))
    with duckdb.connect(db_path, read_only=True) as con:
        return _rows(
            con.execute(
                f"""
                SELECT {_WEEK} AS week, c.card,
                       avg(c.main) AS mean_copies, count(*) AS lists
                FROM decklists d JOIN configurations c USING (list_id)
                WHERE d.archetype = ? AND d.camp = ? AND d.date >= ?
                  AND c.main > 0 AND c.card IN ({placeholders})
                GROUP BY week, c.card ORDER BY week, c.card
                """,
                [deck, variant, since, *cards],
            )
        )


def signatures(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    since: str = config.REGIME_BOUNDARY,
) -> list[dict]:
    """Every list's mainboard as one string, with the week it was published in.

    The unit a stability reading needs: two lists are the same 75 or they are
    not, and a comparison card by card would call a one-card difference most of
    a match. Sideboards are left out because they are the part of a copied list
    a pilot changes first, so a stability reading taken over all 75 would report
    the field's sideboarding as innovation.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        return _rows(
            con.execute(
                f"""
                SELECT d.list_id, {_WEEK} AS week,
                       string_agg(c.card || '#' || c.main, '|' ORDER BY c.card) AS mainboard
                FROM decklists d JOIN configurations c USING (list_id)
                WHERE d.archetype = ? AND d.camp = ? AND d.date >= ? AND c.main > 0
                GROUP BY d.list_id, week ORDER BY week
                """,
                [deck, variant, since],
            )
        )


def stability(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    since: str = config.REGIME_BOUNDARY,
) -> list[dict]:
    """Per week, how much of it is last week's most-played list registered again.

    The direct reading of whether a deck is still being built. Every other
    reading here answers it by absence: a week nothing moved in looks the same
    whether the field settled or the field was quiet. This one says which, and
    it is also the warning that a fat week is not the independent sample its
    list count claims, since a week most of which is one list copied carries
    about as much evidence as its distinct builds do.
    """
    by_week: dict[str, list[str]] = {}
    for row in signatures(db_path, deck, variant, since):
        by_week.setdefault(row["week"], []).append(row["mainboard"])

    readings, previous_top = [], None
    for week in sorted(by_week):
        lists = by_week[week]
        copied = sum(1 for m in lists if m == previous_top) if previous_top else 0
        readings.append(
            {
                "week": week,
                "lists": len(lists),
                "distinct": len(set(lists)),
                "copied": copied,
                "copied_share": copied / len(lists) if lists else None,
            }
        )
        previous_top = max(set(lists), key=lists.count)
    return readings


def excluded(
    db_path: Path = config.DB_PATH, deck: str = "blink", since: str = config.REGIME_BOUNDARY
) -> int:
    """How many lists the colour rule turned away, so the rule stays visible.

    A list holding every signature card and a red source is a different deck,
    and the rule that says so is a hand-written list of card names. Printed
    every week because it is the one part of membership that goes stale
    silently: a red build on a source nobody listed reads as a member, and
    nothing else in the report would say so.
    """
    rule = config.TRACKED_DECKS[deck]
    signature = ",".join("?" * len(rule["signature"]))
    off_colour = ",".join("?" * len(rule["off_colour"]))
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(
            f"""
            WITH member AS (
                SELECT list_id FROM configurations WHERE card IN ({signature}) AND main > 0
                GROUP BY list_id HAVING count(DISTINCT card) = ?
            ),
            off AS (
                SELECT DISTINCT list_id FROM configurations
                WHERE card IN ({off_colour}) AND main > 0
            )
            SELECT count(*) FROM member JOIN decklists USING (list_id)
            WHERE date >= ? AND list_id IN (SELECT list_id FROM off)
            """,
            [*rule["signature"], len(rule["signature"]), *rule["off_colour"], since],
        ).fetchone()[0]
