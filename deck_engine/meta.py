"""The meta layer: dated MTGGoldfish snapshots, transcribed by hand and kept whole."""

import csv
from datetime import date
from pathlib import Path

from . import config

# A snapshot row as it is kept: the reading, under the two terms it was read on.
FIELDS = ("captured_on", "window_days", "archetype", "meta_pct", "deck_count")


def ingest(
    source: Path,
    captured_on: str,
    window_days: int,
    meta_dir: Path | None = None,
) -> Path:
    """Record a transcribed MTGGoldfish table as the snapshot it is, and say where.

    The site serves the table and neither of its terms, so the capture date and
    the window are stamped on here. They are also the snapshot's identity, and
    the file is named for them: ingesting the same reading again rewrites that
    one file rather than lengthening the history. A source already stamped says
    which reading it is, and one that disagrees with the arguments is refused: a
    mistyped date is not a correction but a reading no screenshot was taken for,
    and the trend would report it as the field having moved. A table of no
    archetypes is refused on the same ground: it is a transcription that went
    wrong, and it would take the place of a reading a screenshot was taken for.

    The shares are kept exactly as the site published them, percentages and all
    (see ADR 0001). A screenshot cannot be fetched again, so this file is a raw
    capture in the sense the event cache is, and the history is committed.
    """
    # Every reading of the history orders on this date as text, and it names the
    # file, so a date that is not one sorts by its digits and writes who knows
    # where. 2026-8-9 falling before 2026-08-10 is the whole hazard.
    date.fromisoformat(captured_on)
    with source.open(newline="", encoding="utf-8") as handle:
        table = list(csv.DictReader(handle))
    if not table:
        raise ValueError(f"{source} holds no archetypes; the site never published an empty field")
    stamps = {(row.get("captured_on"), row.get("window_days")) for row in table} - {(None, None)}
    if stamps and stamps != {(captured_on, str(window_days))}:
        raise ValueError(
            f"{source} reads {sorted(stamps)}, not {captured_on} over {window_days} days"
        )
    rows = [
        (captured_on, window_days, row["archetype"], row["meta_pct"], row["deck_count"])
        for row in table
    ]
    meta_dir = meta_dir or config.META_DIR
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = meta_dir / f"{captured_on}_{window_days}d.csv"
    # Landed whole or not at all, as a cached event is: a table that stops early
    # still parses, so a run that died part way through would leave a committed
    # reading of a field that had lost the archetypes it never wrote.
    partial = path.with_suffix(".partial")
    with partial.open("w", newline="", encoding="utf-8") as handle:
        # The history is committed, so the lines end the way the repo's do: an
        # ingest that changed nothing must leave nothing behind in the diff.
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(rows)
    partial.replace(path)
    return path


def snapshot_rows(meta_dir: Path | None = None) -> list[tuple]:
    """The whole history, as rows for the store.

    Which history is resolved here rather than bound as a default, so that where
    it lives is read at the call and not at import. Bound at import there is
    exactly one directory a caller who names none can reach, and it is the
    committed one: that makes the live history a silent input to everything that
    does not name a directory. The readings then answer to how many screenshots
    the pilot has transcribed, which is a fact about his week and not about the
    code, and a test that omits the argument is pinned to it without saying so.

    MTGGoldfish publishes a percentage and the store speaks in shares, every
    other one of which is a fraction of its population, so the reading is
    converted once, here, on the way into the derived layer.

    A file here that the ingest did not write is refused by name rather than
    skipped: the directory is the history, so something else in it is a mistake
    worth hearing about, and quietly passing over one would be quietly dropping
    a reading if the file were a snapshot after all.
    """
    rows = []
    for path in sorted((meta_dir or config.META_DIR).glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            if csv.DictReader(handle).fieldnames != list(FIELDS):
                raise ValueError(f"{path} is no snapshot; ingest a transcription, do not file it")
            handle.seek(0)
            rows += [
                (
                    row["captured_on"],
                    row["window_days"],
                    row["archetype"],
                    float(row["meta_pct"]) / 100,
                    row["deck_count"],
                )
                for row in csv.DictReader(handle)
            ]
    return rows
