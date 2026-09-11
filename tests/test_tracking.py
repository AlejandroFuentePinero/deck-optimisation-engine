"""The tracked deck's readings: membership, the weekly figures, the timeline.

Same seam as the rest of the suite: synthetic payloads written as the site
publishes them, in one end, and the verdict a reader would act on out the other.
Nothing here asserts on a query, a column or an intermediate table.

The series are written rather than captured for the reason `synthetic.py`
gives. Every claim below is about a card moving, or failing to move, across
particular fortnights either side of the regime boundary, and no captured day
holds one of those disentangled from everything else the deck was doing.
"""

from pathlib import Path

import duckdb
import pytest

from deck_engine import config, store, timeline, tracking, weekly
from deck_engine.classify import classify_cache
from tests import synthetic
from tests.synthetic import blink, challenge, entry, league

# Bins are anchored at the regime boundary and run a fortnight each, so these
# are bin -1, bin 0 and bin 1: the fortnight before the boundary, the one that
# opens on it, and the one after.
BEFORE, FIRST, SECOND = "2026-05-06", "2026-05-20", "2026-06-03"


def _built(tmp_path: Path, events: list[dict]) -> Path:
    """A store built from written payloads, as a refresh would leave it."""
    raw = synthetic.write_cache(tmp_path / "raw", events)
    db = tmp_path / "engine.duckdb"
    store.build(raw, db)
    return db


def _mixed(day: str, registered: list[dict], event_id: str) -> dict:
    """One event whose lists differ, so a card can hold part of a bin rather than all."""
    entries = [
        blink(f"p{day}{i}", placement=i + 1, points=15, cards=cards)
        for i, cards in enumerate(registered)
    ]
    return challenge(day, entries, event_id)


def _lists(day: str, count: int, **kwargs) -> dict:
    entries = [blink(f"pilot{day}{i}", placement=i + 1, points=15, **kwargs) for i in range(count)]
    return challenge(day, entries, event_id=f"{day.replace('-', '')}01")


def test_the_optimised_archetype_is_tested_first(tmp_path):
    """A list answering to both rules takes one name, and it is Goryo's.

    The rules are ordered rather than independent because a list counted in two
    decks is counted twice by anything summing the field, and the archetype
    being optimised is the one whose population must not move.
    """
    both = entry("ambidextrous", cards={card: (2, 0) for card in synthetic.BLINK_SIGNATURE})
    db = _built(tmp_path, [challenge(FIRST, [both | {"placement": 1, "points": 18}], "e1")])
    with duckdb.connect(db, read_only=True) as con:
        assert con.execute("SELECT DISTINCT archetype FROM decklists").fetchall() == [("goryos",)]


def test_an_off_colour_source_is_a_different_deck(tmp_path):
    """Holding every signature card is not enough: the deck is Esper or Orzhov.

    The build that shares the four and splashes red is a real population, not a
    stray list, and reading it as a variant would put its numbers inside the
    deck's own.
    """
    clean = blink("orzhov_pilot", variant="orzhov", placement=1, points=15)
    red = blink("mardu_pilot", variant="orzhov", placement=2, points=15,
                off_colour="Sacred Foundry")
    db = _built(tmp_path, [challenge(FIRST, [clean, red], "e1")])
    rows = tracking.weekly(db, "blink", "orzhov", since=FIRST)
    assert sum(row["chal"] for row in rows) == 1
    assert tracking.excluded(db, "blink", since=FIRST) == 1


@pytest.mark.parametrize("variant,expected", [("esper", 1), ("orzhov", 0)])
def test_the_variant_rule_splits_on_the_one_card(tmp_path, variant, expected):
    """Presence of the blue source is the whole of the split, not a count."""
    db = _built(tmp_path, [_lists(FIRST, 1, variant="esper")])
    assert sum(row["chal"] for row in tracking.weekly(db, "blink", variant, since=FIRST)) == expected


def test_presence_is_a_share_of_what_the_week_published(tmp_path):
    """The denominator is the field, so a busier week does not flatter the deck.

    Two identical weeks for the deck, one of them twice the size for everyone
    else: a count would call them the same week and the share says which is
    which.
    """
    quiet = challenge(FIRST, [blink("a", placement=1, points=15)] +
                      [entry(f"other{i}", placement=i + 2, points=12) for i in range(3)], "e1")
    busy = challenge(SECOND, [blink("b", placement=1, points=15)] +
                     [entry(f"more{i}", placement=i + 2, points=12) for i in range(7)], "e2")
    db = _built(tmp_path, [quiet, busy])
    weeks = {row["week"]: row for row in tracking.weekly(db, "blink", "esper", since=FIRST)}
    assert weeks["2026-05-18"]["chal"] == weeks["2026-06-01"]["chal"] == 1
    assert weeks["2026-05-18"]["chal_share"] == pytest.approx(0.25)
    assert weeks["2026-06-01"]["chal_share"] == pytest.approx(0.125)


def test_league_trophies_are_never_capped_per_pilot(tmp_path):
    """One pilot's repeats are part of how much of the stratum the deck holds.

    The cap belongs to the rate readings. What this panel measures is occupancy,
    and a grinder trophying three times has occupied three of the day's slots.
    """
    dump = league(FIRST, [blink("grinder"), blink("grinder"), blink("grinder")])
    db = _built(tmp_path, [dump])
    assert sum(row["trophies"] for row in tracking.weekly(db, "blink", "esper", since=FIRST)) == 3


def test_a_delta_never_crosses_the_regime_boundary(tmp_path):
    """What the deck played before the ban is not what it put down after it.

    A card every pre-regime list ran and no post-regime list does is the largest
    move the detector could see, and it must not report one: the two fortnights
    are different eras and the glossary forbids a window spanning them.
    """
    db = _built(tmp_path, [
        _lists(BEFORE, 8, cards={"Orcish Bowmasters": (4, 0)}),
        _lists(FIRST, 8),
    ])
    opening = timeline.findings(db, "blink", "esper")[0]
    assert opening["start"] == "2026-05-18"
    assert not [row for row in opening["found"] if row["card"] == "Orcish Bowmasters"]


def test_a_card_that_only_skipped_a_fortnight_is_not_a_return(tmp_path):
    """A staple missing one thin bin is a dropout, not the field rediscovering it.

    This is the failure the absence window exists for: at a fortnight's lookback
    a card running at a few lists a week clears the bar on chance alone, and the
    timeline fills with staples announcing themselves.
    """
    db = _built(tmp_path, [
        _lists(FIRST, 8, cards={"Ghost Vacuum": (0, 3)}),
        _lists(SECOND, 8),
        _lists("2026-06-17", 8, cards={"Ghost Vacuum": (0, 3)}),
    ])
    third = timeline.findings(db, "blink", "esper")[2]
    assert not [row for row in third["found"] if row["kind"] == "return"]


def test_a_return_has_to_beat_what_the_card_ever_held(tmp_path):
    """A one-off coming back as a one-off is not news; coming back bigger is.

    Both cards here are gone the same length of time and come back in the same
    bin. Only the one the deck actually turned to is a row.
    """
    vacuum, emrakul = {"Ghost Vacuum": (0, 3)}, {"Emrakul, the Aeons Torn": (0, 3)}
    db = _built(tmp_path, [
        # Before the gap: the vacuum is a two-list one-off, Emrakul is in every list.
        _mixed(BEFORE, [vacuum | emrakul] * 2 + [emrakul] * 6, "e0"),
        _lists(FIRST, 8),
        _lists(SECOND, 8),
        # After it, they swap: the deck turned to one and remembered the other.
        _mixed("2026-06-17", [vacuum] * 8 + [emrakul] * 4, "e3"),
    ])
    returns = {
        row["card"]
        for entry_ in timeline.findings(db, "blink", "esper")
        for row in entry_["found"]
        if row["kind"] == "return"
    }
    assert "Ghost Vacuum" in returns
    assert "Emrakul, the Aeons Torn" not in returns


def test_a_card_crossing_the_boards_is_a_migration_and_says_so(tmp_path):
    """Moving a card to the mainboard is not the deck discovering it.

    Read one zone at a time the card is new to the mainboard, which is true and
    reads as novelty. The row has to say which it is, or a sideboard staple
    being promoted looks like an innovation every time it happens.
    """
    db = _built(tmp_path, [
        _lists(FIRST, 8, cards={"Wrath of the Skies": (0, 3)}),
        _lists(SECOND, 8, cards={"Wrath of the Skies": (3, 0)}),
    ])
    texts = [row["text"] for row in timeline.findings(db, "blink", "esper")[1]["found"]]
    assert any("Wrath of the Skies moves to the mainboard" in text for text in texts)


def test_a_frozen_week_is_never_rewritten(tmp_path, monkeypatch):
    """What was reported stands, even when the store changes under it.

    A league dump gains trophies through its own day, so a past week really can
    move. The report renders the row that was written, because a timeline whose
    history is rebuilt every Monday is a timeline nobody can cite.
    """
    monkeypatch.setattr(config, "TRACKING_DIR", tmp_path / "tracking")
    db = _built(tmp_path, [league(FIRST, [blink("a")])])
    weekly.freeze(db, "blink", "esper", through="2026-05-18")

    fuller = _built(tmp_path / "again", [league(FIRST, [blink("a"), blink("b"), blink("c")])])
    added = weekly.freeze(fuller, "blink", "esper", through="2026-05-18")

    assert added["weeks_added"] == 0
    rows = weekly._read(weekly.deck_dir("blink") / "weekly.csv")
    assert [row["trophies"] for row in rows] == ["1"]


def test_the_reported_week_is_the_last_one_that_closed():
    """Monday's report covers the week behind it, never the one it is in.

    MTGO's density is on the weekend, so a week read before its Sunday is a week
    missing most of its own evidence.
    """
    assert weekly.last_complete_week("2026-09-14") == "2026-09-07"
    assert weekly.last_complete_week("2026-09-11") == "2026-08-31"
    assert weekly.last_complete_week("2026-09-13") == "2026-08-31"


def test_a_week_is_stored_by_its_monday_and_read_by_its_sunday():
    """The label is the day the week closed, not the day it opened.

    Both names are for the same seven days, and the stored one has to stay the
    Monday because every frozen row and summary file is written under it. What
    a reader sees is the Sunday: a chart whose last point says the Monday reads
    as a chart missing the week it is actually showing.
    """
    assert weekly.week_label("2026-08-31") == "2026-09-06"


def test_membership_is_read_off_the_rule_and_not_a_list_of_names(tmp_path):
    """A rule that grows a card takes effect everywhere, including here."""
    raw = synthetic.write_cache(tmp_path / "raw", [_lists(FIRST, 1)])
    assert {deck.archetype for deck in classify_cache(raw)} == {"blink"}


def test_a_list_short_of_one_signature_card_is_not_the_deck(tmp_path):
    """Membership is every signature card, so three of four is another deck."""
    short = blink("nearly", placement=1, points=15, cards={"Flickerwisp": (0, 0)})
    db = _built(tmp_path, [challenge(FIRST, [short], "e1")])
    assert sum(row["chal"] for row in tracking.weekly(db, "blink", "esper", since=FIRST)) == 0
