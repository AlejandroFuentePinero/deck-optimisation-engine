"""The analytical store: a DuckDB file rebuilt from the immutable raw cache."""

from pathlib import Path

import duckdb

from . import config
from .classify import classify_cache

SCHEMA = """
CREATE OR REPLACE TABLE decklists (
    pilot VARCHAR,
    event VARCHAR,
    event_id VARCHAR,
    event_class VARCHAR,
    date VARCHAR,
    placement INTEGER,
    record VARCHAR,
    archetype VARCHAR
)
"""


def build(raw_dir: Path = config.RAW_DIR, db_path: Path = config.DB_PATH) -> Path:
    """Rebuild the store from the raw cache. Derived data is never authoritative."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(db_path) as con:
        con.execute(SCHEMA)
        con.executemany(
            "INSERT INTO decklists VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    d.pilot,
                    d.event,
                    d.event_id,
                    d.event_class,
                    d.date,
                    d.placement,
                    d.record,
                    d.archetype,
                )
                for d in classify_cache(raw_dir)
            ],
        )
    return db_path


def goryos_lists(db_path: Path = config.DB_PATH, day: str | None = None) -> list[dict]:
    """The archetype's lists, most recent and best finishes first."""
    where = "archetype = ?" + (" AND date = ?" if day else "")
    params = [config.ARCHETYPE] + ([day] if day else [])
    with duckdb.connect(db_path, read_only=True) as con:
        cursor = con.execute(
            f"SELECT pilot, event, event_id, event_class, date, placement, record"
            f" FROM decklists WHERE {where}"
            f" ORDER BY date DESC, placement NULLS LAST, pilot",
            params,
        )
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
