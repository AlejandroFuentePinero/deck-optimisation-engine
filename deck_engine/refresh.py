"""The refresh entry point: cache a range of days' events, then rebuild the store."""

import json
from datetime import date, timedelta
from pathlib import Path

from . import config, mtgo, store


def refresh(
    since: str = config.HISTORY_START,
    until: str | None = None,
    raw_dir: Path = config.RAW_DIR,
    db_path: Path = config.DB_PATH,
    source=mtgo,
    today: str | None = None,
) -> Path:
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
    """
    today = today or date.today().isoformat()
    until = min(until or today, today)
    settled = date.fromisoformat(until) - timedelta(days=config.UNSETTLED_DAYS)
    raw_dir.mkdir(parents=True, exist_ok=True)
    gaps = []
    for slug in source.event_slugs(since, config.FORMAT, until):
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
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    store.build(raw_dir, db_path)
    if gaps:
        raise mtgo.Unavailable(
            f"{len(gaps)} published event(s) the site would not serve; "
            f"everything else is cached, so re-run to pick them up:\n  " + "\n  ".join(gaps)
        )
    return db_path
