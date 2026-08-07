"""The single test seam: real cached payloads in, externally meaningful verdicts out.

Fixtures are the immutable raw cache of every Modern event published on
2026-08-05, captured from the live site. Nothing here asserts on parser
internals, schema shape, or intermediate tables.
"""

import json
from pathlib import Path

import pytest

from deck_engine import mtgo, store
from deck_engine.classify import classify_cache
from deck_engine.refresh import refresh

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"
# One captured Last Chance: a Swiss-only event of a kind the day's cache lacks.
FIXTURE_KINDS = Path(__file__).parent / "fixtures" / "kinds"
# The 2026-07-08 challenge as the site served it: under its own slug, and again
# under a second slug dated 2026-07-24 that the site later withdrew.
FIXTURE_DUPLICATE = Path(__file__).parent / "fixtures" / "duplicate"

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
        "challenge-32",
        "2026-08-05",
    )
    assert (finish["record"], finish["placement"]) == ("4-3", 23)

    # Two Modern Challenge 32 events ran that day; a shared name is not identity.
    assert rows["Kollslaw"]["event_id"] == finish["event_id"]
    assert rows["Acecalna"]["event_id"] != finish["event_id"]


def test_challenge_rows_carry_swiss_points_and_leagues_carry_none(tmp_path):
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_RAW, db)

    rows = {row["pilot"]: row for row in store.goryos_lists(db, "2026-08-05")}

    # Read off the published standings: AldenCates finished 23rd on 12 points.
    assert (rows["AldenCates"]["placement"], rows["AldenCates"]["swiss_points"]) == (23, 12)
    # A league publishes 5-0s only: no standings, so no placement and no points.
    assert (rows["frekinsmart"]["placement"], rows["frekinsmart"]["swiss_points"]) == (None, None)


def test_points_are_swiss_only_so_the_winner_can_trail_a_lower_finisher():
    """The published `score` is the Swiss total, untouched by the playoff.

    Challenge 12850696 on 2026-08-05 proves it: BowBloBiw won the event on 15
    Swiss points while JustAnotherGuy83, who led the Swiss and lost the final,
    holds 18. A points-weighted metric therefore measures Swiss performance, not
    the bracket.
    """
    lists = classify_cache(FIXTURE_RAW)

    finishes = {
        d.pilot: (d.placement, d.swiss_points)
        for d in lists
        if d.event_id.endswith("12850696")
    }
    assert finishes["BowBloBiw"] == (1, 15)
    assert finishes["JustAnotherGuy83"] == (2, 18)


def test_every_published_event_kind_lands_under_its_own_class():
    """The class is the kind the site publishes, whatever that kind is.

    So a `last-chance` is not filed as a `last`, an `rc-super-qualifier` is not
    filed as an `rc`, and a `challenge-32` is not blended with a `challenge-64`.
    """
    day = classify_cache(FIXTURE_RAW)
    other_kinds = classify_cache(FIXTURE_KINDS)

    assert {d.event_class for d in day} == {"league", "challenge-32"}
    assert {d.event_class for d in other_kinds} == {"last-chance"}


def test_a_no_playoff_event_finishes_on_the_swiss_order():
    """A Last Chance runs Swiss only, so the standings are the finish."""
    lists = classify_cache(FIXTURE_KINDS)

    finishes = {d.pilot: (d.placement, d.swiss_points) for d in lists}
    assert finishes["ShowTime_"] == (1, 15)
    assert finishes["Lollopollo2001"] == (2, 15)


def test_an_event_listed_under_two_slugs_is_one_event():
    """The site occasionally lists an event a second time under a wrong date.

    Both slugs serve the same 32 lists, and the payload names the event it
    really is, so counting the cache by slug would inflate every metric.
    """
    lists = classify_cache(FIXTURE_DUPLICATE)

    assert len(lists) == 32
    assert len({d.pilot for d in lists}) == 32
    assert {d.date for d in lists} == {"2026-07-08"}


class CapturedSite:
    """The live site as it was, serving every captured payload it published.

    The network layer itself is out of the test seam; this stands in for it so
    the cache's refetch-free promise can be observed.
    """

    EVENTS = {
        path.stem: path for path in [*FIXTURE_RAW.glob("*.json"), *FIXTURE_KINDS.glob("*.json")]
    }

    def __init__(self):
        self.fetches: list[str] = []

    def event_slugs(self, since, fmt, until):
        """Everything it published, July and August alike. Which days the index
        lists is the site's business, and is verified against the live site."""
        return sorted(self.EVENTS)

    def fetch_payload(self, slug):
        self.fetches.append(slug)
        return json.loads(self.EVENTS[slug].read_text(encoding="utf-8"))


def test_refresh_backfills_a_range_of_months_then_fetches_nothing(tmp_path):
    site = CapturedSite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    refresh("2026-07-01", "2026-08-31", raw_dir, db, source=site, today="2026-08-31")
    backfilled = store.goryos_lists(db)
    assert len(site.fetches) == 4, "every event published in the range"
    assert {row["date"] for row in backfilled} == {"2026-07-19", "2026-08-05"}
    assert {row["pilot"] for row in backfilled} >= GORYOS_PILOTS_2026_08_05

    refresh("2026-07-01", "2026-08-31", raw_dir, db, source=site, today="2026-08-31")
    assert len(site.fetches) == 4, "settled events must never be refetched"
    assert store.goryos_lists(db) == backfilled


def test_refresh_refetches_only_the_days_that_can_still_grow(tmp_path):
    """A league dump gains 5-0s through its own day, so a day captured while it
    is still running is a partial capture the immutable cache would keep forever.

    The recent tail of the range is therefore refetched on every run; everything
    behind it has settled and is never fetched twice.
    """
    site = CapturedSite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    refresh("2026-07-01", "2026-08-06", raw_dir, db, source=site, today="2026-08-06")
    assert len(site.fetches) == 4

    site.fetches.clear()
    refresh("2026-07-01", "2026-08-06", raw_dir, db, source=site, today="2026-08-06")

    # 2026-08-05 is inside the unsettled tail of a run made on 2026-08-06.
    assert {mtgo.slug_day(slug) for slug in site.fetches} == {"2026-08-05"}
    assert len(site.fetches) == 3


def test_a_range_running_past_today_still_refetches_the_days_that_can_grow(tmp_path):
    """The unsettled tail is the last few days of real time, not of the range.

    Asking for everything by naming an `until` beyond today is the natural way
    to say it, and it must not quietly settle a day the site is still filling.
    """
    site = CapturedSite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    refresh("2026-07-01", "2026-12-31", raw_dir, db, source=site, today="2026-08-06")
    assert len(site.fetches) == 4

    site.fetches.clear()
    refresh("2026-07-01", "2026-12-31", raw_dir, db, source=site, today="2026-08-06")
    assert {mtgo.slug_day(slug) for slug in site.fetches} == {"2026-08-05"}


def test_refresh_caches_the_rest_when_the_site_withholds_an_event(tmp_path):
    """The site intermittently serves a page with the listing missing.

    A backfill of hundreds of events must not lose the run to one of them, nor
    quietly pretend the gap isn't there: it caches everything else, then says
    what it could not reach.
    """

    class FlakySite(CapturedSite):
        WITHHELD = "modern-challenge-32-2026-08-0512850696"

        def fetch_payload(self, slug):
            if slug == self.WITHHELD:
                raise mtgo.Unavailable(slug)
            return super().fetch_payload(slug)

    site = FlakySite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    with pytest.raises(mtgo.Unavailable, match=FlakySite.WITHHELD):
        refresh("2026-08-01", "2026-08-31", raw_dir, db, source=site, today="2026-08-31")

    cached = store.goryos_lists(db, "2026-08-05")
    assert {row["pilot"] for row in cached} == GORYOS_PILOTS_2026_08_05 - {"Acecalna"}

    # The site recovers; the re-run fetches only what the gap left behind.
    site.fetches.clear()
    refresh("2026-08-01", "2026-08-31", raw_dir, db, source=CapturedSite(), today="2026-08-31")
    assert {row["pilot"] for row in store.goryos_lists(db, "2026-08-05")} == GORYOS_PILOTS_2026_08_05


def test_a_withheld_refetch_leaves_the_capture_already_cached_standing(tmp_path):
    """An unsettled day is refetched for what it may have gained since, not
    because what is cached is wrong.

    So the site withholding one is nothing like it withholding an event never
    captured: the run keeps the capture it has and succeeds. Only an event with
    nothing on disk is a gap, since only that one costs lists.
    """
    site = CapturedSite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    refresh("2026-08-01", "2026-08-31", raw_dir, db, source=site, today="2026-08-31")
    captured = store.goryos_lists(db, "2026-08-05")

    class WithholdingSite(CapturedSite):
        def fetch_payload(self, slug):
            raise mtgo.Unavailable(slug)

    # 2026-08-05 is unsettled on 2026-08-06, so every event on it is refetched.
    refresh("2026-08-01", "2026-08-31", raw_dir, db, source=WithholdingSite(), today="2026-08-06")
    assert store.goryos_lists(db, "2026-08-05") == captured
