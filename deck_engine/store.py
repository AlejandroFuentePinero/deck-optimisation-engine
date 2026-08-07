"""The analytical store: a DuckDB file rebuilt from the immutable raw cache."""

import csv
import tempfile
from collections.abc import Iterable
from pathlib import Path

import duckdb

from . import config
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
    camp VARCHAR
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


def build(raw_dir: Path = config.RAW_DIR, db_path: Path = config.DB_PATH) -> Path:
    """Rebuild the store from the raw cache. Derived data is never authoritative.

    The two tables are one picture of the cache, so they land together or not at
    all: a rebuild that died between them would leave lists whose cards had gone,
    and a card query would answer that nobody plays it rather than fail.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    lists = list(enumerate(classify_cache(raw_dir)))
    with duckdb.connect(db_path) as con:
        con.execute("BEGIN TRANSACTION")
        con.execute(DECKLISTS_SCHEMA)
        con.execute(CONFIGURATIONS_SCHEMA)
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


def _rows(cursor: duckdb.DuckDBPyConnection) -> list[dict]:
    """An executed cursor's rows, each keyed by the column it selected."""
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


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
                " FROM (SELECT date, camp, CASE WHEN event_class = 'league' THEN 'league'"
                "       ELSE 'challenge-class' END AS stratum"
                "       FROM decklists WHERE archetype = ?)"
                " GROUP BY date, stratum, camp ORDER BY date, stratum, camp",
                [config.ARCHETYPE],
            )
        )


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
