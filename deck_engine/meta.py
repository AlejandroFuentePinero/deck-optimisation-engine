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

    Decks the site tables under two names are summed here for the same reason
    printings of one card are summed at the point names first become counts: a
    deck read at two shares is one deck's density split down the middle, and
    every reading behind this one would report both halves as smaller than the
    field they are. Done on the way out and not on the way in, so the committed
    transcription stays what the screenshot showed, exactly as the cache stays
    what the site served (see ADR 0001). The whole history passes through here,
    so a merge decided today applies to every snapshot already taken.

    The site rounds each share to a tenth before publishing it, so a summed
    share carries both roundings and can sit a tenth off what the site would
    have printed for the merged deck. The deck counts are exact.

    A file here that the ingest did not write is refused by name rather than
    skipped: the directory is the history, so something else in it is a mistake
    worth hearing about, and quietly passing over one would be quietly dropping
    a reading if the file were a snapshot after all.
    """
    merged: dict[tuple[str, str, str], list] = {}
    for path in sorted((meta_dir or config.META_DIR).glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            if csv.DictReader(handle).fieldnames != list(FIELDS):
                raise ValueError(f"{path} is no snapshot; ingest a transcription, do not file it")
            handle.seek(0)
            for row in csv.DictReader(handle):
                archetype = config.META_ARCHETYPE_ALIASES.get(row["archetype"], row["archetype"])
                key = (row["captured_on"], row["window_days"], archetype)
                reading = merged.setdefault(key, [0.0, 0])
                reading[0] += float(row["meta_pct"]) / 100
                reading[1] += int(row["deck_count"])
    return [(*key, *reading) for key, reading in merged.items()]
