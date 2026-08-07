"""The single test seam: real cached payloads in, externally meaningful verdicts out.

Fixtures are the immutable raw cache of every Modern event published on
2026-08-05, captured from the live site. Nothing here asserts on parser
internals, schema shape, or intermediate tables.
"""

import json
from pathlib import Path

from deck_engine import store
from deck_engine.classify import classify_cache
from deck_engine.refresh import refresh

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"

# The day's Goryo's lists, read off the published decklists by hand.
GORYOS_PILOTS_2026_08_05 = {
    "frekinsmart",
    "pepeteam",
    "_must_be_nice",
    "AldenCates",
    "Kollslaw",
    "Acecalna",
}


def test_trio_rule_selects_exactly_the_days_goryos_lists():
    lists = classify_cache(FIXTURE_RAW)

    members = {d.pilot for d in lists if d.archetype == "goryos"}
    assert members == GORYOS_PILOTS_2026_08_05


def test_placement_is_the_published_finish_not_the_swiss_standing():
    lists = classify_cache(FIXTURE_RAW)

    # BowBloBiw took the second challenge of the day; JustAnotherGuy83 led the
    # Swiss and lost in the playoff.
    won = [d.pilot for d in lists if d.event_id.endswith("12850696") and d.placement == 1]
    assert won == ["BowBloBiw"]


def test_query_returns_the_days_goryos_lists_with_their_provenance(tmp_path):
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_RAW, db)

    rows = {row["pilot"]: row for row in store.goryos_lists(db, "2026-08-05")}
    assert set(rows) == GORYOS_PILOTS_2026_08_05

    # A league trophy: published as a 5-0, with no placement to speak of.
    trophy = rows["frekinsmart"]
    assert (trophy["event"], trophy["event_class"], trophy["date"]) == (
        "Modern League",
        "league",
        "2026-08-05",
    )
    assert (trophy["record"], trophy["placement"]) == ("5-0", None)

    # A challenge finish: published with a rank within the top 32.
    finish = rows["AldenCates"]
    assert (finish["event"], finish["event_class"], finish["date"]) == (
        "Modern Challenge 32",
        "challenge",
        "2026-08-05",
    )
    assert (finish["record"], finish["placement"]) == ("4-3", 23)

    # Two Modern Challenge 32 events ran that day; a shared name is not identity.
    assert rows["Kollslaw"]["event_id"] == finish["event_id"]
    assert rows["Acecalna"]["event_id"] != finish["event_id"]


class CapturedSite:
    """The live site as it was on 2026-08-05, serving the captured payloads.

    The network layer itself is out of the test seam; this stands in for it so
    the cache's refetch-free promise can be observed.
    """

    def __init__(self):
        self.fetches: list[str] = []

    def event_slugs(self, day, fmt=None):
        return sorted(path.stem for path in FIXTURE_RAW.glob("*.json"))

    def fetch_payload(self, slug):
        self.fetches.append(slug)
        return json.loads((FIXTURE_RAW / f"{slug}.json").read_text(encoding="utf-8"))


def test_refresh_is_idempotent_for_a_single_day(tmp_path):
    site = CapturedSite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    refresh("2026-08-05", raw_dir, db, source=site)
    first_run = store.goryos_lists(db, "2026-08-05")
    assert len(site.fetches) == 3
    assert {row["pilot"] for row in first_run} == GORYOS_PILOTS_2026_08_05

    refresh("2026-08-05", raw_dir, db, source=site)
    assert len(site.fetches) == 3, "cached events must never be refetched"
    assert store.goryos_lists(db, "2026-08-05") == first_run
