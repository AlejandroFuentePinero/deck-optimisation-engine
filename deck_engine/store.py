"""The analytical store: a DuckDB file rebuilt from the immutable raw cache."""

import csv
import tempfile
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

import duckdb

from . import config, meta
from .classify import classify_cache

DECKLISTS_SCHEMA = """
CREATE OR REPLACE TABLE decklists (
    list_id INTEGER,
    pilot VARCHAR,
    event VARCHAR,
    event_id VARCHAR,
    event_class VARCHAR,
    date VARCHAR,
    placement INTEGER,
    swiss_points INTEGER,
    record VARCHAR,
    archetype VARCHAR,
    camp VARCHAR,
    lands INTEGER
)
"""

# A card in a list, as the pair the domain calls a configuration. One pilot can
# publish two 5-0 lists in one league dump, so the list a card belongs to is
# `list_id`, numbered by the rebuild, and never the pilot and event.
CONFIGURATIONS_SCHEMA = """
CREATE OR REPLACE TABLE configurations (
    list_id INTEGER,
    card VARCHAR,
    main INTEGER,
    side INTEGER
)
"""

# The meta history, keyed by the two terms a reading is taken on. Archetypes
# here are MTGGoldfish's own names for the whole field, and are nothing to do
# with `decklists.archetype`, this engine's membership rule over the one deck.
META_SNAPSHOTS_SCHEMA = """
CREATE OR REPLACE TABLE meta_snapshots (
    captured_on VARCHAR,
    window_days INTEGER,
    archetype VARCHAR,
    share DOUBLE,
    deck_count INTEGER
)
"""


def _load(con: duckdb.DuckDBPyConnection, table: str, rows: Iterable[tuple]) -> None:
    """Bulk-load `rows` into `table`.

    DuckDB inserts a row at a time some four orders of magnitude slower than it
    reads a file, and a card row per card per list is around 600,000 of them, so
    the rows go via a CSV it reads in one pass. An unquoted empty field is the
    database's own spelling of NULL, which is what `csv` writes `None` as.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)
        # A run the site served nothing to has an empty cache to rebuild from,
        # and an empty file has no dialect for the database to read.
        if path.stat().st_size:
            con.execute(f"COPY {table} FROM '{path}' (FORMAT CSV, HEADER false)")


def build(
    raw_dir: Path = config.RAW_DIR,
    db_path: Path = config.DB_PATH,
    meta_dir: Path = config.META_DIR,
) -> Path:
    """Rebuild the store from the raw cache. Derived data is never authoritative.

    The tables are one picture of the cache, so they land together or not at
    all: a rebuild that died between them would leave lists whose cards had gone,
    and a card query would answer that nobody plays it rather than fail. The meta
    history is rebuilt with them for the same reason it is kept on disk: what the
    field looked like is evidence a conditional hypothesis reads beside the lists.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    lists = list(enumerate(classify_cache(raw_dir)))
    history = meta.snapshot_rows(meta_dir)
    with duckdb.connect(db_path) as con:
        con.execute("BEGIN TRANSACTION")
        con.execute(DECKLISTS_SCHEMA)
        con.execute(CONFIGURATIONS_SCHEMA)
        con.execute(META_SNAPSHOTS_SCHEMA)
        _load(con, "meta_snapshots", history)
        _load(
            con,
            "decklists",
            (
                (
                    list_id,
                    d.pilot,
                    d.event,
                    d.event_id,
                    d.event_class,
                    d.date,
                    d.placement,
                    d.swiss_points,
                    d.record,
                    d.archetype,
                    d.camp,
                    d.lands,
                )
                for list_id, d in lists
            ),
        )
        _load(
            con,
            "configurations",
            (
                (list_id, card, d.mainboard.get(card, 0), d.sideboard.get(card, 0))
                for list_id, d in lists
                for card in d.mainboard | d.sideboard
            ),
        )
        con.execute("COMMIT")
    return db_path


# Which stratum a list was published under. Challenge-class is every class
# except league, so the rule is drawn once and both readings of it agree.
CHALLENGE_CLASS = "challenge-class"
_STRATUM = f"CASE WHEN event_class = 'league' THEN 'league' ELSE '{CHALLENGE_CLASS}' END"

# What a list's finish is worth: its Swiss points over the best Swiss total its
# own event published. Normalising per event puts a 96-player challenge running
# more rounds on the same scale as a challenge 32, so a configuration cannot
# climb on having been registered at the longer events. The best is taken over
# the whole event and not over the archetype's lists in it, since what a finish
# is measured against is the field it finished in front of. A league carries no
# points, so this is NULL there and no league list can ever weigh anything.
_WEIGHTED = """
    SELECT *, swiss_points / max(swiss_points) OVER (PARTITION BY event_id) AS weight
    FROM decklists
"""

# The archetype's lists inside the two windows, each carrying what an adoption
# figure is taken over: the camp that registered it, the stratum that published
# it, which of the windows it fell in, and what its finish is worth. The
# baseline is the rest of the regime behind the fresh window, so a list from the
# era before the boundary is in neither: it belongs to a different archetype in
# all but name.
_SCOPED = f"""
    SELECT list_id, camp, {_STRATUM} AS stratum, weight, lands,
           -- `window` is SQL's own word, so the domain's one is quoted.
           CASE WHEN date > ? THEN 'fresh' ELSE 'baseline' END AS "window"
    FROM ({_WEIGHTED}) WHERE archetype = ? AND date >= ? AND date <= ?
"""


def _rows(cursor: duckdb.DuckDBPyConnection) -> list[dict]:
    """An executed cursor's rows, each keyed by the column it selected."""
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _count(counts: list[dict], stratum: str, camp: str, unit: str) -> int:
    """One camp's population in one stratum, in `unit`: `pilots` counts a pilot
    once however many times they published, `lists` counts every publication."""
    return sum(c[unit] for c in counts if (c["stratum"], c["camp"]) == (stratum, camp))


def _share(counts: list[dict], stratum: str, camp: str, unit: str) -> float:
    """That population against the whole stratum's."""
    total = sum(c[unit] for c in counts if c["stratum"] == stratum)
    return _count(counts, stratum, camp, unit) / total


def _cap_effect(gap: float, uncapped: float) -> str:
    """What counting each pilot once did to the uncapped gap.

    A gap one grinder produced is caught here rather than published: their
    trophies are one pilot's, so capping either turns the figure round or takes
    most of it away. Only a gap the cap leaves standing is the camp's.
    """
    if gap * uncapped < 0:
        return "flips"
    if abs(gap) < config.CAP_COLLAPSE * abs(uncapped):
        return "collapses"
    return "holds"


def _query(db_path: Path, columns: str, source: str, where: str, params: list) -> list[dict]:
    """The archetype's rows for one question, most recent and best finishes first."""
    with duckdb.connect(db_path, read_only=True) as con:
        return _rows(
            con.execute(
                f"SELECT {columns} FROM {source}"
                f" WHERE archetype = ?{f' AND {where}' if where else ''}"
                f" ORDER BY date DESC, placement NULLS LAST, pilot",
                [config.ARCHETYPE] + params,
            )
        )


def goryos_lists(
    db_path: Path = config.DB_PATH, day: str | None = None, camp: str | None = None
) -> list[dict]:
    """The archetype's lists, most recent and best finishes first.

    Naming a `camp` narrows to that camp's population, which is what consensus
    is computed over: hybrids are members of the archetype and of no camp, so
    they answer to neither.
    """
    filters = {"date": day, "camp": camp}
    return _query(
        db_path,
        "pilot, event, event_id, event_class, date, placement, swiss_points, record, camp",
        "decklists",
        " AND ".join(f"{column} = ?" for column, value in filters.items() if value),
        [value for value in filters.values() if value],
    )


def meta_trend(
    archetype: str,
    db_path: Path = config.DB_PATH,
    window_days: int = config.META_WINDOW_DAYS,
) -> list[dict]:
    """One archetype's share of the field across the snapshot history, oldest first.

    `archetype` is MTGGoldfish's name for a deck and not this engine's: the meta
    layer is the whole field, which v1 does not classify, and only the site's
    vocabulary reaches across all of it.

    The trend is read within one window, because a share is a reading of a
    window: the 30-day table smooths what the 14-day table shows, so a line
    drawn through both would report the difference between two instruments as
    movement in the field. Each row still carries its window, since a reading
    without both its terms cannot be compared to anything.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        return _rows(
            con.execute(
                "SELECT captured_on, window_days, share, deck_count FROM meta_snapshots"
                " WHERE archetype = ? AND window_days = ? ORDER BY captured_on",
                [archetype, window_days],
            )
        )


def mirror_share(
    day: str,
    db_path: Path = config.DB_PATH,
    window_days: int = config.META_WINDOW_DAYS,
) -> dict | None:
    """How much of the field the archetype itself was, as of `day`.

    The mirror is a matchup the 75 is built against, so its density is the join
    a conditional hypothesis needs: a main-deck card earned by mirror volume is
    only earned while that volume stands.

    Readings are dated and sparse, so `day` is answered by the last one taken on
    or before it in `window_days`, which is the reading that stood on that day.
    It comes back whole, its own terms included, so a stale answer can be told
    from a fresh one. None means the history does not reach back that far, and
    there is no reading to condition on.
    """
    stood = [
        snapshot
        for snapshot in meta_trend(config.META_ARCHETYPE, db_path, window_days)
        if snapshot["captured_on"] <= day
    ]
    return stood[-1] if stood else None


def camp_ratio(db_path: Path = config.DB_PATH) -> list[dict]:
    """How the archetype splits between the camps, per stratum, oldest day first.

    Composition, and nothing about performance: it counts who registered what,
    over a population that is only ever the published winners of either stratum.

    A day's shares are taken over that stratum's lists, hybrids included: a camp
    losing ground to the experiment is the same news as it losing ground to the
    other camp, and dropping the hybrids would hide it. The two strata are never
    pooled, because a league dump publishes an order of magnitude more lists than
    a challenge does, so a pooled share would swing with which events happened to
    run that day rather than with what pilots registered.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        return _rows(
            con.execute(
                "SELECT date, stratum, camp, count(*) AS lists,"
                " count(*) / sum(count(*)) OVER (PARTITION BY date, stratum) AS share"
                f" FROM (SELECT date, camp, {_STRATUM} AS stratum"
                "       FROM decklists WHERE archetype = ?)"
                " GROUP BY date, stratum, camp ORDER BY date, stratum, camp",
                [config.ARCHETYPE],
            )
        )


def conversion_gap(db_path: Path = config.DB_PATH) -> list[dict]:
    """Each camp's share of league-trophy pilots less its share of challenge-class
    pilots, either side of the regime boundary.

    A league 5-0 is a real win record, so the stratum does carry performance
    information. What it does not publish is the denominator: a camp's trophy
    count is its entries times its conversion, and only the product is served.
    The challenge-class stratum stands in for that denominator, which is what
    turns two raw counts into a reading.

    The two strata truncate at different bars, so the gap measures the shape of
    a camp's outcomes and not its quality: a league 5-0 is the extreme right
    tail, a challenge top-32 a wide band. A camp short of 5-0s and long on
    challenge finishes is flatter, not worse. It is hypothesis-grade evidence
    that routes to playtesting, and it never enters performance tilt.

    Two confounds would otherwise make it noise, so the controls are in the row
    rather than available beside it. Grinding volume is one: one pilot's
    trophies are one pilot's, so the published `gap` counts each pilot once per
    camp, `uncapped` is the same figure over every published list, and
    `cap_effect` says what the cap did to it. ADR 0001 keeps the dumps as
    published, repeat 5-0s and all, and this does not reopen that: the cap is
    applied to the reading, and the publication count stays beside it. The
    regime boundary is the other confound, so each side of it gets its own row.

    A pilot who registered both camps counts once in each, so the shares are
    over camp commitments and sum to their stratum. Counting such a pilot once
    overall would leave the shares summing past 1 and no reading to take.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        counts = _rows(
            con.execute(
                "SELECT CASE WHEN date >= ? THEN 'post-regime' ELSE 'pre-regime' END AS regime,"
                f" {_STRATUM} AS stratum, camp,"
                " count(DISTINCT pilot) AS pilots, count(*) AS lists"
                " FROM decklists WHERE archetype = ? GROUP BY ALL",
                [config.REGIME_BOUNDARY, config.ARCHETYPE],
            )
        )

    rows = []
    for regime in ("pre-regime", "post-regime"):
        side = [c for c in counts if c["regime"] == regime]
        for camp in sorted({c["camp"] for c in side}):
            league_share = _share(side, "league", camp, "pilots")
            challenge_share = _share(side, "challenge-class", camp, "pilots")
            gap = league_share - challenge_share
            uncapped = _share(side, "league", camp, "lists") - _share(
                side, "challenge-class", camp, "lists"
            )
            rows.append(
                {
                    "regime": regime,
                    "camp": camp,
                    "league_pilots": _count(side, "league", camp, "pilots"),
                    "challenge_pilots": _count(side, "challenge-class", camp, "pilots"),
                    "league_share": league_share,
                    "challenge_share": challenge_share,
                    "gap": gap,
                    "uncapped": uncapped,
                    "cap_effect": _cap_effect(gap, uncapped),
                }
            )
    return rows


def _reading(window: str, stratum: str, population: dict | None, taken: dict | None) -> dict:
    """One window's reading of one configuration: how many lists took it, out of
    how many the camp published in that stratum, and what share that is.

    Inside the challenge stratum the share is read twice, raw and weighted by
    what each list's finish was worth, and the tilt is the second less the
    first: positive means the configuration is overrepresented among the better
    Swiss finishes. It is the pair that is the reading, since a tilt on three
    lists is a tilt on three lists.

    Weighting is the challenge stratum's alone. A league publishes 5-0s and no
    standings, so there is no finish there to weigh a list by, and a league
    share is raw or it is nothing. A camp whose whole window scored no Swiss
    points is read the same way: there is no performance to distribute over, so
    the raw share stands alone rather than the weighting dividing by nothing.

    A window the camp published nothing in has no reading rather than a zero:
    0% adoption says the camp registered lists and none took the configuration,
    which is a different claim from the camp not having shown up.
    """
    reading = {"lists": 0, "population": 0, "adoption": None, "weighted": None, "tilt": None}
    if population is not None:
        reading["lists"] = taken["lists"] if taken else 0
        reading["population"] = population["lists"]
        reading["adoption"] = reading["lists"] / population["lists"]
        if stratum == CHALLENGE_CLASS and population["weight"]:
            reading["weighted"] = (taken["weight"] if taken else 0.0) / population["weight"]
            reading["tilt"] = reading["weighted"] - reading["adoption"]
    return {f"{window}_{name}": value for name, value in reading.items()}


def _adoption_table(db_path: Path, keys: tuple[str, ...], join: str = "") -> list[dict]:
    """Adoption of whatever `keys` name, per camp, per stratum, per window.

    The windows are the two the archetype is read over, and they are drawn here
    once for every figure that spans them: the fresh window is the last
    `config.FRESH_WINDOW_DAYS` of published lists, the baseline is the rest of
    the regime behind it, and the two are disjoint so a delta is movement rather
    than a window compared against a period containing it.

    They are anchored on the last day the store holds a list for and not on the
    clock, so a quiet week shortens no window: what is fresh is the most recent
    fortnight of play, not whichever part of it happened to fall before today.
    """
    with duckdb.connect(db_path, read_only=True) as con:
        as_of = con.execute("SELECT max(date) FROM decklists").fetchone()[0]
        # An empty cache has no last published day to anchor on, and no windows.
        if as_of is None:
            return []
        fresh_start = date.fromisoformat(as_of) - timedelta(days=config.FRESH_WINDOW_DAYS)
        bounds = [fresh_start.isoformat(), config.ARCHETYPE, config.REGIME_BOUNDARY, as_of]

        def grouped(columns: str, joined: str = "") -> list[dict]:
            """The scoped lists tallied by camp, stratum and window, and by
            whatever else `columns` adds. The population is the same tally with
            nothing added, so a share and its denominator are counted one way."""
            return _rows(
                con.execute(
                    f"WITH scoped AS ({_SCOPED})"
                    f' SELECT camp, stratum, "window"{columns},'
                    " count(*) AS lists, sum(weight) AS weight"
                    f" FROM scoped {joined} GROUP BY ALL",
                    bounds,
                )
            )

        populations = grouped("")
        counts = grouped("".join(f", {key}" for key in keys), join)

    sizes = {(p["camp"], p["stratum"], p["window"]): p for p in populations}
    taken: dict[tuple, dict] = {}
    for count in counts:
        key = (count["camp"], count["stratum"], *(count[name] for name in keys))
        taken.setdefault(key, {})[count["window"]] = count

    rows = []
    for key, windows in sorted(taken.items()):
        row = dict(zip(("camp", "stratum", *keys), key))
        for window in ("fresh", "baseline"):
            size = sizes.get((row["camp"], row["stratum"], window))
            row |= _reading(window, row["stratum"], size, windows.get(window))
        fresh, baseline = row["fresh_adoption"], row["baseline_adoption"]
        row["delta"] = fresh - baseline if None not in (fresh, baseline) else None
        rows.append(row)
    return rows


def adoption(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every configuration the archetype registered, per camp, per stratum, over
    the fresh and baseline windows, with the delta between them.

    The unit is the configuration and never the card: a copy moving between the
    boards is a change the camp made at a constant total, and a count of copies
    would report that as nothing having happened.

    Camps are never pooled, because a configuration is only consensus within the
    camp that registered it, and the strata are never pooled for the reason ADR
    0001 gives: a league publishes 5-0s and a challenge publishes a top 32, so
    one share over both would move with which events happened to run.

    The unit of the population is the list and not the pilot, which the league
    stratum exposes: one grinder trophying twice in a dump is two lists here, so
    a thin league window can report one pilot changing his mind as a camp
    splitting. The row carries its population for that reason. `conversion_gap`
    caps per pilot because a league's trophy count is the whole of what it
    measures there; here the configuration is, and a pilot who registered a
    build twice did register it twice.
    """
    return _adoption_table(db_path, ("card", "main", "side"), "JOIN configurations USING (list_id)")


def land_counts(db_path: Path = config.DB_PATH) -> list[dict]:
    """How much land each camp runs, per stratum, over the same two windows.

    A land count is a configuration of the list as a whole rather than of a card
    in it, so it is read exactly as one: the distribution is the camp's lists
    across the counts they registered, and the manabase climbing a land is the
    same kind of movement as a copy crossing into the sideboard.
    """
    return _adoption_table(db_path, ("lands",))


def near_miss_lists(db_path: Path = config.DB_PATH, day: str | None = None) -> list[dict]:
    """The watchlist: lists mainboarding the namesake that miss full membership.

    Each row says what it kept of the signature cards and what it dropped, which
    is the whole reason to look at one: the drop is the variant it is proposing.
    They are not the archetype, so no archetype figure counts them, and every
    other query here is the archetype's.

    A row is one list, grouped on `list_id` and never on its pilot and event: a
    pilot near-missing twice in one league dump publishes two lists, and grouping
    those together would union what two different 75s kept into a list nobody
    registered.
    """
    signature = ", ".join("?" * len(config.SIGNATURE_CARDS))
    with duckdb.connect(db_path, read_only=True) as con:
        rows = _rows(
            con.execute(
                "SELECT list_id, pilot, event, event_id, event_class, date, placement,"
                " swiss_points, record, list(card) AS kept"
                " FROM decklists JOIN configurations USING (list_id)"
                f" WHERE archetype IS NULL AND main > 0 AND card IN ({signature})"
                + (" AND date = ?" if day else "")
                + " GROUP BY ALL HAVING list_contains(list(card), ?)"
                " ORDER BY date DESC, placement NULLS LAST, pilot",
                [*config.SIGNATURE_CARDS, *([day] if day else []), config.WATCHLIST_CARD],
            )
        )

    for row in rows:
        kept = set(row["kept"])
        row["kept"] = [card for card in config.SIGNATURE_CARDS if card in kept]
        row["dropped"] = [card for card in config.SIGNATURE_CARDS if card not in kept]
    return rows


def card_configurations(
    card: str, db_path: Path = config.DB_PATH, day: str | None = None
) -> list[dict]:
    """One card's configuration in each of the archetype's lists that plays it.

    Main and side copies stay apart because the pair is the unit adoption is
    tracked at: a copy moving between them is a change at a constant total. The
    row is keyed by `list_id` and not by its pilot, who may have trophied twice
    in one league dump on two different lists. That key is the rebuild's own
    numbering and means nothing to the run after it.
    """
    return _query(
        db_path,
        "list_id, pilot, event_id, date, camp, main, side, main + side AS total",
        "configurations JOIN decklists USING (list_id)",
        "card = ?" + (" AND date = ?" if day else ""),
        [card] + ([day] if day else []),
    )
