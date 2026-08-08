"""The daily surface, at the seam the rest of the pipeline is tested at: the
cache, the captures and the records in, one rendered document out.

Nothing here asserts on markup. A section is located by the anchor it is
published under, which is part of what a document is, and everything else is
read off the text a reader would see: what the report has to carry is the
readings, not the tags they arrive in.

The store is built from the captured events of `tests/fixtures/adoption`, whose
last published day is 2026-08-05. The flag ledger is written beside it, because
that file is where a run's memory of what it raised lives and so is the report's
own input for everything a flag says.
"""

import json
import re
from html import unescape
from pathlib import Path

import pytest

from deck_engine import config, report, store

FIXTURE_ADOPTION = Path(__file__).parent / "fixtures" / "adoption"
# The frozen 14-day snapshot of 2026-08-07. The committed history grows as the
# pilot transcribes screenshots, and a rendered figure read off it would be a
# fact about how many he has taken rather than about what the page shows.
FIXTURE_META = Path(__file__).parent / "fixtures" / "meta"
REFERENCE_DIR = Path(__file__).parent.parent / "reference"
HYPOTHESES_DIR = Path(__file__).parent.parent / "hypotheses"

# The day the report is run on, two days after the last published list and
# twenty short of the day the 75 is handed in.
TODAY = "2026-08-07"

# Two flags as the detectors publish them, taken from the ledger a live run
# wrote. The captured events hold neither episode: a hype flag is a fortnight's
# climb and a breakthrough is a list read against a settled camp, and the eight
# events of the adoption fixture are too few days to carry either. The ledger
# file is where a run's memory of what it raised lives, and so is the report's
# own input for everything a flag says.
DECAYED_HYPE = {
    "kind": "hype",
    "camp": "non-fallaji",
    "card": "Consign to Memory",
    "main": 2,
    "side": 2,
    "raised_on": "2026-07-12",
    "from_adoption": 0.08823529411764706,
    "to_adoption": 0.4634146341463415,
    "population": 41,
    "origin_pilot": "KingHairy",
    "origin_event": "Modern Challenge 64",
    "origin_date": "2026-06-28",
    "origin_placement": 1,
    "tilt": -0.006594131223211397,
    "challenge_before": 0.2222222222222222,
    "state": "decayed",
    "league_after": 0.2,
    "challenge_after": 0.0,
    "tilt_after": 0.0,
    "resolved_on": "2026-07-26",
    "first_seen": "2026-07-26",
}

BREAKTHROUGH = {
    "kind": "breakthrough",
    "camp": "non-fallaji",
    "pilot": "KingHairy",
    "event": "Modern Challenge 64",
    "date": "2026-07-25",
    "placement": 3,
    "mode": "fringe",
    "delta": 1,
    "novel": [["Cephalid Coliseum", 1, 0]],
    "missing": ["Nihil Spellbomb"],
    "state": "trendsetter",
    "followers": ["Kollslaw", "Walker735"],
    "adopted_card": "Cephalid Coliseum",
    "first_seen": "2026-07-26",
}


def _text(markup: str) -> str:
    """What a reader sees: the markup's text, whitespace collapsed and the rows
    it was laid out in kept apart by a pipe, so a row can still be read alone."""
    rows = re.sub(r"</(tr|p|dd|h3|li)>", " | ", markup)
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", rows))).strip()


def _section(document: str, anchor: str) -> str:
    """One section of the report as its text, by the anchor it is published under."""
    assert f'id="{anchor}"' in document, f"no {anchor} section in the report"
    return _text(document.split(f'<section id="{anchor}"')[1].split("</section>")[0])


def _rendered(tmp_path, flags=()) -> str:
    """The report of a run over the captured events, with `flags` as its ledger."""
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db, FIXTURE_META)
    db.with_name("flags.json").write_text(json.dumps(list(flags)), encoding="utf-8")
    return report.render(db, REFERENCE_DIR, HYPOTHESES_DIR, TODAY)


def test_the_report_names_the_windows_it_was_read_over_and_how_stale_they_are(tmp_path):
    """Every figure in the document is a share of a population over a window, so
    the document says which windows it was taken over before it says anything.

    The windows are anchored on the last day the store holds a list for and not
    on the clock, so the run date and that day are both on the page: a report
    read on a quiet Monday is a fortnight of play ending on the Wednesday before
    it, and a reader who saw only one of the two dates would take it for a
    fortnight ending today.

    The clock is the third: what is left before the 75 is handed in is what makes
    an open question a piece of work rather than a note.
    """
    document = _rendered(tmp_path)

    run = _section(document, "run")
    # The fresh fortnight ends on the last published day and the baseline is the
    # fixed span behind it: disjoint, so a delta is movement, and the same span
    # every run, so a delta means the same thing twice.
    assert "2026-07-23 to 2026-08-05" in run
    assert "2026-06-25 to 2026-07-22" in run
    # Two days of clock have run since the last list was published.
    assert "2026-08-05" in run and "2 day" in run
    assert config.SUBMISSION_DATE in run and "20 day" in run


def test_the_report_carries_every_tracked_claim_with_the_clock_it_is_running(tmp_path):
    """The records are the work the run is for, so they are on the page whole.

    A claim, where the argument on it stands, and what is left of the clock: an
    unresolved record with no days beside it is a note rather than a piece of
    work, which is the whole of why the submission date is tracked at all.

    The eight standing records are the pilot's own, entered before any run, and
    none of them has been ruled on.
    """
    document = _rendered(tmp_path)

    tracked = _section(document, "hypotheses")
    assert "8 of 8 record(s) unresolved" in tracked
    for record in ("consign-mainboard", "land-count", "wrath-density"):
        assert record in tracked
    assert "The twenty-second land should come out for a spell" in tracked
    # Every one of them open, and every one of them 20 days from being decided
    # by default: the status and the clock are one reading and never printed apart.
    assert tracked.count("open, 20 day") == 8


def test_the_report_ranks_the_75s_slots_in_the_order_playtesting_should_reach_them(tmp_path):
    """The audit is the answer to what to test next, so it arrives as the queue.

    A slot is only ever a deviation from a population that could have registered
    it, so the section names its terms: the camp, the stratum and how many lists
    the share was taken over. Against the captured challenges the non-Fallaji
    camp fields three fresh lists, twenty of the 75's slots are the camp's core
    and the twelve flex ones queue least backed first.

    A core slot the pilot is with his camp on is not in the queue at all: it is
    not where the optimisation happens.
    """
    document = _rendered(tmp_path)

    audit = _section(document, "audit")
    assert "non-fallaji" in audit and "challenge-class" in audit and "3 list" in audit
    assert "20 core" in audit and "12 flex" in audit

    # Least backed first: four slots nobody in the camp registered, then the
    # three a third of it did.
    ranked = re.findall(r"(March of Otherworldly Light|Consign to Memory|Solitude)", audit)
    assert ranked == ["March of Otherworldly Light", "Consign to Memory"]
    assert "unexamined-deviation" in audit and "0%" in audit


def test_a_camp_staple_the_75_never_registered_queues_beside_the_slots_it_did(tmp_path):
    """The costlier error of the two, and the one the audit cannot see.

    A card the camp is near-unanimous on that the 75 has no copies of leaves no
    slot behind to bucket, so it is its own reading and never a fifth bucket.
    It queues among the audited slots all the same, on the confidence running
    none of it earns, because it is one piece of work and not two.

    The camp is unanimous on the single Griselbrand as the second reanimation
    target, so a capture that drops it is a 75 out of step with everyone.
    """
    versions = tmp_path / "reference"
    versions.mkdir()
    (versions / "v1-2026-08-07-dropped.txt").write_text(
        (REFERENCE_DIR / "v1-2026-08-07-moxfield.txt")
        .read_text(encoding="utf-8")
        .replace("1 Griselbrand\n", ""),
        encoding="utf-8",
    )
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db, FIXTURE_META)

    audit = _section(report.render(db, versions, HYPOTHESES_DIR, TODAY), "audit")

    assert "1 missing core slot" in audit
    # What the camp runs stands where an audited slot's bucket would, since the
    # four buckets are verdicts on slots the pilot took and this is one he never
    # had. His own configuration is no copies, which nobody in the camp shares.
    griselbrand = re.search(r"Griselbrand[^|]*", audit).group()
    assert "100% play it" in griselbrand
    assert "1/0" in griselbrand


def test_the_report_watches_the_lists_that_missed_the_archetype_by_one_card(tmp_path):
    """Where a variant comes from: a list that mainboarded the namesake and is
    not the deck.

    What it dropped is the whole reason to look at one, since the drop is the
    construction direction it is proposing, so the row carries both halves.
    These are not the archetype and no figure the report takes counts them.

    nikkuniku's 25th at the 2026-07-22 Challenge 32 is the captured one: it
    keeps the namesake and Psychic Frog and is neither Esper nor reanimating
    with Ephemerate.
    """
    document = _rendered(tmp_path)

    watchlist = _section(document, "near-miss")
    row = re.search(r"nikkuniku[^|]*", watchlist).group()
    assert "2026-07-22" in watchlist
    assert "Psychic Frog" in row and "Atraxa, Grand Unifier" in row


def test_the_hype_watchlist_names_both_strata_and_the_finish_the_copying_followed(tmp_path):
    """A hype episode is two readings and a finish, and the row says which is which.

    The spike is the league stratum's, because that is where copying shows
    first and hardest; the state is the challenge stratum's verdict on it. Side
    by side and unlabelled the two would read as one figure moving, which is the
    blend the strata are kept apart to prevent.

    The finish behind it is the third: a configuration climbing after nothing
    visible is drift, not an episode, so what the field was copying is on record
    from the raise.
    """
    document = _rendered(tmp_path, [DECAYED_HYPE])

    watchlist = _section(document, "hype")
    row = re.search(r"Consign to Memory[^|]*", watchlist).group()
    assert "9% -> 46%" in row
    assert "decayed" in row
    assert "KingHairy" in row and "#1" in row and "2026-06-28" in row
    # Both strata named, so neither share is read as the other's.
    assert "league" in watchlist and "challenge" in watchlist


def test_the_report_reports_a_departure_that_performed_and_what_the_field_did_next(tmp_path):
    """A breakthrough is a list that left its camp's build behind and finished.

    Both directions of the departure are on the row, because the delta counts
    both: the cards hardly any of the camp registered that it did, and the
    camp's own staples it ran none of. Only the first of them and the figure
    would contradict itself.

    Whether the field then took the idea up is a later and separate reading, so
    the state and the pilots who followed ride beside the departure rather than
    inside it.
    """
    document = _rendered(tmp_path, [BREAKTHROUGH])

    findings = _section(document, "lineage")
    row = re.search(r"KingHairy[^|]*", findings).group()
    assert "+Cephalid Coliseum" in row and "-Nihil Spellbomb" in row
    assert "1 (fringe)" in row
    assert "trendsetter" in row and "Kollslaw" in row and "Walker735" in row


def test_the_camp_ratio_is_reported_per_stratum_and_never_pooled_across_them(tmp_path):
    """How the archetype splits between its camps, newest day first.

    Composition and nothing about performance. The two strata keep their own
    rows because a league dump publishes an order of magnitude more lists than a
    challenge does, so a pooled share would swing with which events happened to
    run that day rather than with what pilots registered.

    On the last captured day the challenges published one Fallaji list and two
    non-Fallaji, and the league dump three non-Fallaji trophies.
    """
    document = _rendered(tmp_path)

    ratio = _section(document, "camps")
    latest = ratio.split("2026-07-29")[0]
    assert "challenge-class" in latest and "league" in latest
    assert "fallaji 33%" in latest and "non-fallaji 67%" in latest
    assert "non-fallaji 100%" in latest


def test_the_report_stops_at_the_regime_boundary_and_says_that_it_did(tmp_path):
    """A run is a reading of the era the 75 is being built for.

    Lists either side of a regime boundary belong to different eras and are not
    directly comparable, so a camp split or a near-miss build from before it is
    not a quieter signal but a reading of a different format. Every other figure
    in the report is already bounded that way, the two windows both stopping
    there; these two are series and would otherwise run back to the start of the
    history and bury the fortnight that matters.

    What is left out is on the page. A section that silently dropped half its
    rows would read as having covered everything.

    The captured events reach back to a pre-regime showcase challenge of
    2026-03-21, which is the day the bound has to lose.
    """
    document = _rendered(tmp_path)

    for anchor in ("camps", "near-miss"):
        section = _section(document, anchor)
        assert "2026-03-21" not in section, f"{anchor} reaches back past the regime boundary"
        assert config.REGIME_BOUNDARY in section, f"{anchor} does not say where it stops"
    # The post-regime days are all still there, most recent first.
    assert "2026-06-24" in _section(document, "camps")


def test_the_meta_trend_carries_the_window_every_reading_of_it_was_taken_over(tmp_path):
    """The field's own table, which is where the mirror share is read.

    A share over 30 days is a different measurement from one over 14, so a
    reading without both its terms cannot be compared to anything: the window is
    on the page with the date it was captured on. The snapshot rendered here is
    the frozen one, taken on 2026-08-07 over 14 days.
    """
    document = _rendered(tmp_path)

    trend = _section(document, "meta")
    assert "14" in trend and "2026-08-07" in trend
    assert "10.0%" in trend and "118" in trend
    assert config.META_ARCHETYPE in trend


def test_the_document_fetches_nothing_and_so_reads_the_same_wherever_it_is_opened(tmp_path):
    """The report is a file, not a page: it is read off a phone, out of an email,
    a fortnight after the run that wrote it.

    One that fetched a stylesheet, a font or a script would render as whatever
    the network felt like that day, and a run's evidence has to still say the
    same thing when it is read back.
    """
    document = _rendered(tmp_path, [DECAYED_HYPE, BREAKTHROUGH])

    assert document.startswith("<!doctype html>")
    for fetches in ("http://", "https://", "src=", "<link", "<script", "url(", "@import"):
        assert fetches not in document.lower(), f"the report reaches for {fetches}"


# Two spikes a week apart, both still waiting on the weekend that judges them.
# The 2026-08-16 episode has the 22nd to be answered on and the 75 is handed in
# on the 27th; the 2026-08-23 episode's first weekend is the 29th, which is two
# days after the deck is out of the pilot's hands.
LATE_HYPE = DECAYED_HYPE | {
    "card": "Spell Snare",
    "raised_on": "2026-08-23",
    "state": "raised",
    "league_after": None,
    "challenge_after": None,
    "tilt_after": None,
    "resolved_on": None,
}
EARLY_HYPE = LATE_HYPE | {"card": "Pest Control", "raised_on": "2026-08-16"}

# A departure the field has not had its fortnight to answer: published on the
# 20th, so the follow-through window closes on 2026-09-03. One pilot has taken
# the card up, which is short of the two that graduate a flag, so it is watching
# with a follower already on the board: the state a departure spends most of its
# fortnight in.
WATCHED_BREAKTHROUGH = BREAKTHROUGH | {
    "date": "2026-08-20",
    "state": "watching",
    "followers": ["Kollslaw"],
    "adopted_card": "Cephalid Coliseum",
}

# A spike the weekend landed on and the challenges were too thin to judge: the
# flag matured and is waiting on evidence, which is not evidence of anything.
MATURED_HYPE = DECAYED_HYPE | {
    "card": "Solitude",
    "raised_on": "2026-08-02",
    "state": "matured",
    "league_after": 0.2,
    "challenge_after": None,
    "tilt_after": None,
    "resolved_on": "2026-08-16",
}


def test_a_flag_that_cannot_be_answered_before_submission_day_says_so(tmp_path):
    """The clock the pilot heuristic puts on a flag, read against the one the
    tournament puts on the 75.

    Hype corrects in about a week and the weekend is what corrects it, so a
    spike raised after the last pre-tournament weekend has no data coming that
    could resolve it: it is decided by pilot judgment alone, and a row that read
    `raised` without saying so would look like a verdict still on its way.

    A breakthrough answers to the same reading for its own reason. The field is
    given a fortnight to take a departure up, and a fortnight that closes after
    submission day is one the 75 will never see the end of.
    """
    document = _rendered(tmp_path, [LATE_HYPE, EARLY_HYPE, DECAYED_HYPE, WATCHED_BREAKTHROUGH])

    watchlist = _section(document, "hype")
    late = re.search(r"Spell Snare[^|]*", watchlist).group()
    assert "2026-08-29" in late and "pilot judgment" in late

    # The one with a weekend still to come is waiting on evidence, not on the
    # pilot: it says when the answer lands and leaves it at that.
    early = re.search(r"Pest Control[^|]*", watchlist).group()
    assert "2026-08-22" in early and "pilot judgment" not in early

    # An episode the challenges already answered has no clock left to run.
    assert "pilot judgment" not in re.search(r"Consign to Memory[^|]*", watchlist).group()

    # A departure the field has begun to take up is still watching, so the same
    # clock runs on it: what the followers so far say is not the verdict, and a
    # row that reported them instead of the clock would drop the caveat exactly
    # where the flag looks most like it is going somewhere.
    departures = _section(document, "lineage")
    row = re.search(r"KingHairy[^|]*", departures).group()
    assert "Kollslaw" in row
    assert "2026-09-03" in row and "pilot judgment" in row


def test_a_flag_that_matured_on_too_little_evidence_is_not_reported_as_a_verdict(tmp_path):
    """Maturing is not resolving, and the row has to say which it did.

    A spike whose weekend landed on a fortnight too thin to read has had its
    evidence and got nothing from it, which is a different thing from evidence
    that the configuration failed. Beside `established` and `decayed`, the bare
    word would read as the third verdict rather than as the absence of one.
    """
    watchlist = _section(_rendered(tmp_path, [MATURED_HYPE, DECAYED_HYPE]), "hype")

    matured = re.search(r"Solitude[^|]*", watchlist).group()
    assert "matured" in matured and "waiting on" in matured
    # The one the challenges did answer says nothing about waiting.
    assert "waiting on" not in re.search(r"Consign to Memory[^|]*", watchlist).group()


def test_a_cache_with_nothing_published_in_it_is_declined_rather_than_reported(tmp_path):
    """A run over an empty cache has no windows to read and no camp to read
    against, so there is no report to render.

    Declined the way the slot audit declines a camp that published nothing: a
    document that rendered anyway would carry sections reporting that the
    archetype plays nothing, which is a claim no population made.
    """
    db = tmp_path / "engine.duckdb"
    store.build(tmp_path / "empty-cache", db, FIXTURE_META)

    with pytest.raises(ValueError, match="no published list"):
        report.render(db, REFERENCE_DIR, HYPOTHESES_DIR, TODAY)


def test_a_run_lands_as_one_file_named_for_the_day_it_read_the_cache_on(tmp_path):
    """The entry point: one run, one file, and the day it read on in its name.

    A report is the run's own evidence, so the file says which run it is rather
    than being overwritten by every later one. A second run on the same day is
    the same day's report and does replace it: what a report says is what the
    cache said when it was written, and the later read is the truer one.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db, FIXTURE_META)
    reports = tmp_path / "reports"

    landed = report.write(reports, db, REFERENCE_DIR, HYPOTHESES_DIR, TODAY)

    assert landed.name == f"{TODAY}.html"
    assert "2026-07-23 to 2026-08-05" in _section(landed.read_text(encoding="utf-8"), "run")

    # A second run of the same day replaces it, and a different day is a
    # different report: nothing a run wrote is edited after the fact.
    report.write(reports, db, REFERENCE_DIR, HYPOTHESES_DIR, TODAY)
    report.write(reports, db, REFERENCE_DIR, HYPOTHESES_DIR, "2026-08-08")
    assert sorted(path.name for path in reports.iterdir()) == ["2026-08-07.html", "2026-08-08.html"]
