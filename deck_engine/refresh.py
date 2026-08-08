"""The refresh entry point: cache a range of days' events, then rebuild the store."""

import json
from datetime import date, timedelta
from pathlib import Path

from . import config, index, ledger, mtgo, store


def refresh(
    since: str = config.HISTORY_START,
    until: str | None = None,
    raw_dir: Path = config.RAW_DIR,
    db_path: Path = config.DB_PATH,
    source=mtgo,
    today: str | None = None,
) -> index.Change:
    """Cache every published `config.FORMAT` event from `since` to `until`, then rebuild.

    A settled event on disk is never refetched, so the backfill runs once and
    every later refresh costs the month indexes plus what the site has published
    since. The last `config.UNSETTLED_DAYS` days are the exception: a league dump
    is still gaining 5-0s while its day runs, so those days are fetched again and
    overwritten until they settle. Which days those are is a fact about now, not
    about the range asked for, so a range running past today ends today.

    Only an event with nothing on disk is a gap. An unsettled day the site will
    not serve keeps the capture it already has, because that refetch was for
    what the day may have gained, not because the capture was wrong.

    What the run brought in is read off the index either side of the rebuild,
    and is returned rather than printed: an ingest that cannot say what it
    ingested leaves the question to be answered by hand from a cache that is not
    committed, and the days it is hardest to answer for are exactly the
    overwritten ones. A run that ends on a gap raises instead, so the gap is the
    news; the index still stands and the next run reports across both.
    """
    today = today or date.today().isoformat()
    until = min(until or today, today)
    settled = date.fromisoformat(until) - timedelta(days=config.UNSETTLED_DAYS)
    raw_dir.mkdir(parents=True, exist_ok=True)
    before = index.read(db_path)
    gaps = []
    for slug in source.event_slugs(since, config.FORMAT, until, today):
        path = raw_dir / f"{slug}.json"
        cached = path.exists()
        if cached and mtgo.slug_day(slug) < settled.isoformat():
            continue
        try:
            payload = source.fetch_payload(slug)
        except mtgo.Unavailable as gap:
            if not cached:
                gaps.append(str(gap))
            continue
        # Landed whole or not at all: a capture half written by a run that died
        # would be a settled file the cache never refetches and never parses.
        partial = path.with_suffix(".partial")
        partial.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        partial.replace(path)

    store.build(raw_dir, db_path)
    # The store is rebuilt from the cache and remembers nothing; the ledger
    # beside it is where a flag's lifecycle and the run that raised it survive.
    ledger.record(db_path, today)
    if gaps:
        raise mtgo.Unavailable(
            f"{len(gaps)} published event(s) the site would not serve; "
            f"everything else is cached, so re-run to pick them up:\n  " + "\n  ".join(gaps)
        )
    # Read back rather than kept from the rebuild, so what the run reports is
    # what the committed file says and not what this process believed it wrote.
    after = index.read(db_path)
    return index.Change(index.difference(after, before), index.difference(before, after))
