"""The refresh entry point: cache a day's events, then rebuild the store."""

import json
from pathlib import Path

from . import config, mtgo, store


def refresh(
    day: str,
    raw_dir: Path = config.RAW_DIR,
    db_path: Path = config.DB_PATH,
    source=mtgo,
) -> Path:
    """Cache every published `config.FORMAT` event on `day`, then rebuild.

    The raw cache is immutable: an event already on disk is never refetched, so
    re-running for the same day costs one index request and nothing else.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    for slug in source.event_slugs(day, config.FORMAT):
        path = raw_dir / f"{slug}.json"
        if path.exists():
            continue
        path.write_text(json.dumps(source.fetch_payload(slug), indent=1), encoding="utf-8")
    return store.build(raw_dir, db_path)
