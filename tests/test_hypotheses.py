"""The hypothesis layer at the seam the rest of the pipeline is tested at: raw
payloads in, verdicts out.

A hypothesis is a claim about how the 75 should be built, and what it is for is
to collect the evidence that settles it. So the readings here are the record as
the pilot and the agent read it back: what the claim is, what the camp did about
it on the day the evidence was taken, what the pilot found when he played it,
and how long is left to decide. Nothing asserts on how a record is stored.

The reference list is the real thing rather than a fixture, as it is in
`tests/test_seam.py`: a hypothesis is about the pilot's own 75 and there is only
one of those, and the camp it belongs to is the population every reading here is
taken over.
"""

import pytest

from deck_engine import hypotheses, ledger, reference, store
from tests import synthetic
from tests.test_flags import HELD_UP, SPIKE_SERIES, SPIKE_WEEKEND
from tests.test_seam import FIXTURE_ADOPTION, FIXTURE_META

# The day the reference list was captured on and the day after it, which is what
# every reading here is dated at: the submission is 2026-08-27, so a record open
# on 2026-08-08 has nineteen days left to be decided in.
TODAY = "2026-08-08"

# The land slots of the 2026-08-07 capture, read off it by hand. The capture is
# copies and card names as MTGO publishes a list, which carries no card types,
# so what counts as a land here is named rather than derived.
LAND_SLOTS = (
    "Marsh Flats",
    "Polluted Delta",
    "Flooded Strand",
    "Watery Grave",
    "Hallowed Fountain",
    "Godless Shrine",
    "Breeding Pool",
    "Meticulous Archive",
    "Undercity Sewers",
    "Shadowy Backstreet",
    "Plains",
    "Island",
    "Swamp",
)


def _record(hypotheses_dir, name, body):
    """One hypothesis on disk, as the pilot writes one."""
    hypotheses_dir.mkdir(parents=True, exist_ok=True)
    path = hypotheses_dir / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


TEFERI = """# A second Teferi, Time Raveler earns a slot in the 75

status: open
origin: pilot-experience
subject: Teferi, Time Raveler

## Evidence sought

Whether the camp registers a second copy, and what the second copy did for it.
"""


def test_a_record_reads_back_as_the_claim_it_makes_and_the_time_left_to_settle_it(tmp_path):
    """A hypothesis is a record, and what it carries is what a decision needs.

    The claim is what is being argued, the origin says whether it came from the
    pilot or from the data, the subjects are what in the field's lists speaks to
    it, and the status is where the argument has got to. The days remaining are
    the reason any of it is urgent: the 75 is submitted on a date, so an open
    record is a decision that has not been made yet with a clock on it.
    """
    _record(tmp_path, "second-teferi", TEFERI)

    (record,) = hypotheses.standing(tmp_path, today=TODAY)

    assert record["id"] == "second-teferi"
    assert record["claim"] == "A second Teferi, Time Raveler earns a slot in the 75"
    assert (record["status"], record["origin"]) == ("open", "pilot-experience")
    assert record["subjects"] == ["Teferi, Time Raveler"]
    assert record["sought"].startswith("Whether the camp registers a second copy")
    assert record["days_remaining"] == 19
    assert (record["verdict"], record["evidence"]) == (None, [])


CONSIGN = """# The first Consign to Memory belongs in the mainboard

status: open
origin: pilot-experience
subject: Consign to Memory

## Evidence sought

What the camp does with the first copy, and whether the main-deck build performs.
"""


def test_data_evidence_is_what_the_camps_lists_said_on_the_day_it_was_taken(tmp_path):
    """The evidence a run appends: the camp's own reading of what is at stake.

    The population is the one the reference list belongs to, in the challenge
    stratum, over the fresh window, because that is the only population a
    configuration of the 75 answers to. Every configuration of the subject the
    camp registered is served, since a hypothesis about where the first copy
    goes is a question about which of them the camp went to.

    The three fresh non-Fallaji challenge lists split: two main the first Consign
    and side three, one sides all four. The camp was on all four in half its
    baseline lists, so the main-deck build is the new one.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)
    _record(tmp_path / "hypotheses", "consign-mainboard", CONSIGN)

    entry = hypotheses.evidence(
        "consign-mainboard", "data", on=TODAY, db_path=db, hypotheses_dir=tmp_path / "hypotheses"
    )

    assert (entry["on"], entry["source"], entry["note"]) == (TODAY, "data", None)
    assert (entry["camp"], entry["stratum"]) == ("non-fallaji", "challenge-class")
    assert entry["population"] == 3
    assert [(r["subject"], r["configuration"], r["adoption"]) for r in entry["readings"]] == [
        ("Consign to Memory", "1/3", pytest.approx(2 / 3)),
        ("Consign to Memory", "0/4", pytest.approx(1 / 3)),
    ]
    assert [r["delta"] for r in entry["readings"]] == [
        pytest.approx(2 / 3),
        pytest.approx(1 / 3 - 1 / 2),
    ]

    # The record is the log, so what was appended is what reads back off it.
    (record,) = hypotheses.standing(tmp_path / "hypotheses", today=TODAY)
    (logged,) = record["evidence"]
    assert (logged["on"], logged["source"]) == (TODAY, "data")
    assert "Consign to Memory 1/3" in "\n".join(logged["lines"])


HYPED_RECORD = """# Kavaero, Mind-Bitten belongs in the mainboard

status: open
origin: data-suggested
subject: Kavaero, Mind-Bitten

## Evidence sought

Whether the camp's adoption is the card or the copying.
"""


def test_a_configuration_the_hype_detector_flagged_carries_the_caveat_into_the_log(tmp_path):
    """A share the herd produced is not the same evidence as a share it earned.

    Half the camp's challenge lists register the configuration, which read off
    the adoption alone is a claim with the field behind it. The flag layer knows
    the other half of that story: the camp arrived there in a fortnight, behind
    one visible finish, and what a run of adoption measures after a spike is how
    many pilots copied a list. So the reading and the caveat are appended
    together, and the reader never gets the first without the second.
    """
    db = tmp_path / "engine.duckdb"
    series = [*SPIKE_SERIES, SPIKE_WEEKEND, *HELD_UP]
    store.build(synthetic.write_cache(tmp_path / "raw", series), db)
    ledger.record(db, today=TODAY)
    _record(tmp_path / "hypotheses", "kavaero-mainboard", HYPED_RECORD)

    entry = hypotheses.evidence(
        "kavaero-mainboard", "data", on=TODAY, db_path=db, hypotheses_dir=tmp_path / "hypotheses"
    )

    assert [(r["configuration"], r["adoption"]) for r in entry["readings"]] == [
        ("1/0", pytest.approx(1 / 2))
    ]
    # The day the flag was raised rides with it, as the mirror reading's two
    # terms do: an episode from six weeks ago and one raised this week are
    # different evidence, and in a permanent log an undated flag cannot say which.
    assert entry["flags"] == [
        {
            "kind": "hype",
            "card": "Kavaero, Mind-Bitten",
            "configuration": "1/0",
            "state": "established",
            "raised": TODAY,
            "caveat": hypotheses.HYPE_CAVEAT,
        }
    ]

    (record,) = hypotheses.standing(tmp_path / "hypotheses", today=TODAY)
    assert hypotheses.HYPE_CAVEAT in "\n".join(record["evidence"][0]["lines"])


COUNTERMAGIC = """# Two Spell Snare and three Mystical Dispute is too much postboard countermagic

status: open
origin: pilot-experience
subject: Mystical Dispute
subject: Spell Snare
conditional-on: mirror

## Evidence sought

What the camp sides against blue, read against how much of the field is blue.
"""


def test_a_conditional_record_joins_the_camps_configurations_to_the_mirror_share(tmp_path):
    """A slot bought on mirror density is only earned while that density stands.

    Postboard countermagic is bought against the blue half of the field, of
    which the mirror is the largest part, so the camp's sideboard counts settle
    nothing on their own: three Mystical Dispute at ten percent mirror and three
    at two percent are different decisions. The join is what makes the claim
    answerable, so the reading that stood on the day goes into the entry beside
    the configurations, with its own two terms on it.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db, FIXTURE_META)
    _record(tmp_path / "hypotheses", "postboard-countermagic", COUNTERMAGIC)

    entry = hypotheses.evidence(
        "postboard-countermagic",
        "data",
        on=TODAY,
        db_path=db,
        hypotheses_dir=tmp_path / "hypotheses",
    )

    assert [(r["subject"], r["configuration"], r["adoption"]) for r in entry["readings"]] == [
        ("Mystical Dispute", "0/3", 1.0),
        ("Spell Snare", "0/1", pytest.approx(1 / 3)),
    ]
    assert entry["mirror"] == {
        "captured_on": "2026-08-07",
        "window_days": 14,
        "share": pytest.approx(0.10),
        "deck_count": 118,
    }

    (record,) = hypotheses.standing(tmp_path / "hypotheses", today=TODAY)
    assert "mirror 10.0%" in "\n".join(record["evidence"][0]["lines"])
    assert entry["unconditioned"] is False


def test_a_conditional_record_says_so_when_no_meta_reading_stood_on_the_day(tmp_path):
    """A condition that could not be read is not a condition that was met.

    The meta history is transcribed by hand and reaches back only as far as
    somebody took a screenshot, so a day before the first snapshot has no
    reading to condition on. Served the configurations alone, such an entry
    would be indistinguishable from an unconditional one, and the claim would
    quietly be decided on half of what it asked for.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db, FIXTURE_META)
    _record(tmp_path / "hypotheses", "postboard-countermagic", COUNTERMAGIC)

    entry = hypotheses.evidence(
        "postboard-countermagic",
        "data",
        on="2026-08-01",
        db_path=db,
        hypotheses_dir=tmp_path / "hypotheses",
    )

    assert (entry["mirror"], entry["unconditioned"]) == (None, True)
    # The configurations are still read; only the condition went unanswered.
    assert entry["readings"]

    (record,) = hypotheses.standing(tmp_path / "hypotheses", today=TODAY)
    assert "the condition went unread" in "\n".join(record["evidence"][0]["lines"])


def test_what_the_pilot_played_and_what_he_judged_are_entries_like_any_other(tmp_path):
    """The three sources are one log, because they argue about the one claim.

    Playtesting is where the data cannot decide, and judgment is what the pilot
    knows that no published list reports. Filed anywhere but beside the numbers
    they would be a second-class record, and the engine would be deciding the
    75 by arithmetic. So they append through the same call, into the same log,
    in the order they happened.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)
    _record(tmp_path / "hypotheses", "consign-mainboard", CONSIGN)
    hypotheses.evidence(
        "consign-mainboard", "data", on=TODAY, db_path=db, hypotheses_dir=tmp_path / "hypotheses"
    )

    played = hypotheses.evidence(
        "consign-mainboard",
        "playtest",
        note="Ten games against Belcher: the main-deck copy was live in six of them.",
        on="2026-08-09",
        db_path=db,
        hypotheses_dir=tmp_path / "hypotheses",
    )
    hypotheses.evidence(
        "consign-mainboard",
        "judgment",
        note="Dead against Boros Energy, which is the deck I expect to play twice.",
        on="2026-08-10",
        db_path=db,
        hypotheses_dir=tmp_path / "hypotheses",
    )

    # The pilot's entry is his note: no camp, no share, nothing computed for him.
    assert (played["readings"], played["camp"], played["mirror"]) == ([], None, None)

    (record,) = hypotheses.standing(tmp_path / "hypotheses", today=TODAY)
    assert [(e["on"], e["source"]) for e in record["evidence"]] == [
        (TODAY, "data"),
        ("2026-08-09", "playtest"),
        ("2026-08-10", "judgment"),
    ]
    assert record["evidence"][1]["lines"] == [
        "Ten games against Belcher: the main-deck copy was live in six of them."
    ]


def test_ruling_on_a_record_closes_it_with_the_decision_it_leaves_the_75_at(tmp_path):
    """Every claim is decided by submission day, inconclusive ones included.

    A hypothesis nobody rules on is a slot decided by default, so what closes a
    record is not the evidence running out but the pilot saying what the 75 does
    about it. The verdict is that decision and the status is how the evidence
    came out, and the two are separate: a claim the data contradicted and a
    claim nothing settled can both end at keeping what is already registered.

    A decided record has no days remaining, having nothing left to run out of.
    """
    _record(tmp_path, "second-teferi", TEFERI)

    ruled = hypotheses.rule(
        "second-teferi",
        "inconclusive",
        "keep the single copy; the camp is split and playtesting could not tell them apart",
        hypotheses_dir=tmp_path,
        today=TODAY,
    )

    assert ruled["status"] == "inconclusive"
    assert ruled["days_remaining"] == 19

    hypotheses.rule("second-teferi", "decided", "keep the single copy", hypotheses_dir=tmp_path)
    (record,) = hypotheses.standing(tmp_path, today=TODAY)
    assert (record["status"], record["verdict"]) == ("decided", "keep the single copy")
    assert record["days_remaining"] is None
    # The claim and what the pilot wrote under it survive the ruling: a verdict
    # with the argument for it thrown away is a decision nobody can revisit.
    assert record["sought"].startswith("Whether the camp registers a second copy")


LANDS = """# The manabase wants a twenty-second land

status: open
origin: pilot-experience
subject: lands

## Evidence sought

What the camp is running, and whether the twenty-second land is the new thing.
"""


def test_a_deck_level_subject_reads_the_camps_land_counts_and_not_a_cards(tmp_path):
    """How much land the camp runs is a configuration of the list as a whole.

    It is read exactly as a card's is, over the same camp, stratum and window,
    because the manabase climbing a land is the same kind of move as a copy
    crossing into the sideboard. Two of the camp's three fresh challenge lists
    are on twenty-two and none of its baseline lists were, so the extra land is
    where the camp has just gone.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)
    _record(tmp_path / "hypotheses", "twenty-second-land", LANDS)

    entry = hypotheses.evidence(
        "twenty-second-land", "data", on=TODAY, db_path=db, hypotheses_dir=tmp_path / "hypotheses"
    )

    assert [
        (r["subject"], r["configuration"], r["adoption"], r["delta"]) for r in entry["readings"]
    ] == [
        ("lands", "22", pytest.approx(2 / 3), pytest.approx(2 / 3)),
        ("lands", "21", pytest.approx(1 / 3), pytest.approx(1 / 3 - 1 / 2)),
    ]


SILENT = """# The green source should be a Hedge Maze

status: open
origin: pilot-experience
subject: Hedge Maze
subject: Mystycal Dispute

## Evidence sought

What the camp registers, and whether anyone has gone there at all.
"""


def test_a_subject_the_archetype_has_never_registered_reads_apart_from_one_it_dropped(tmp_path):
    """A card the camp is not on and a card that does not exist are not one thing.

    Both come back with no configuration, and read out the same way the second
    would be the strongest evidence a claim can get: nobody plays it, so the
    pilot would be alone in the field. A misspelt card name would earn that
    reading, permanently, in a log nothing rewrites.

    So the pool decides which it is. Hedge Maze the archetype has registered and
    this camp is currently not on; `Mystycal Dispute` no list has ever played,
    which is either a card outside the pool or a name typed wrong, and either
    way it is not a finding.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)
    _record(tmp_path / "hypotheses", "green-source", SILENT)

    entry = hypotheses.evidence(
        "green-source", "data", on=TODAY, db_path=db, hypotheses_dir=tmp_path / "hypotheses"
    )

    assert entry["readings"] == []
    assert entry["silent"] == ["Hedge Maze"]
    assert entry["unknown"] == ["Mystycal Dispute"]

    logged = "\n".join(hypotheses.standing(tmp_path / "hypotheses", today=TODAY)[0]["evidence"][0]["lines"])
    assert "Hedge Maze: the camp registered none in the fresh window." in logged
    assert "Mystycal Dispute: the archetype's history has never registered it" in logged


def test_a_record_naming_no_subject_is_refused_rather_than_logged_against(tmp_path):
    """A claim the evidence layer cannot reach is one that will be vibed after all.

    The subjects are what in the field's lists an entry is read off, so a record
    without them can still take data entries and every one of them would say
    nothing. That is worse than no entry: a log with readings in it looks like a
    claim somebody has been gathering evidence for.
    """
    _record(tmp_path, "second-teferi", TEFERI.replace("subject: Teferi, Time Raveler\n", ""))

    with pytest.raises(ValueError, match="names no subject"):
        hypotheses.standing(tmp_path, today=TODAY)


def test_a_record_at_a_status_the_vocabulary_does_not_know_is_refused(tmp_path):
    """The status is what says whether a claim is still open, so it is checked.

    Everything urgent about a record hangs off it: an unresolved one carries the
    clock to submission and a decided one is a slot closed. A word the
    vocabulary does not know would file the claim as neither, silently, and the
    pilot would find out on submission day.
    """
    _record(tmp_path, "second-teferi", TEFERI.replace("status: open", "status: resolved"))

    with pytest.raises(ValueError, match="resolved"):
        hypotheses.standing(tmp_path, today=TODAY)


def test_an_entry_from_a_source_the_log_does_not_know_is_refused(tmp_path):
    """The source is what an entry's standing is read off, so it is checked too.

    The three are the evidence this project accepts, and a misspelt one would
    file a run of the numbers as something the log cannot tell from a hunch. It
    is refused before anything is written, an appended log having no way to take
    an entry back.
    """
    _record(tmp_path, "second-teferi", TEFERI)

    with pytest.raises(ValueError, match="goldfishing"):
        hypotheses.evidence(
            "second-teferi", "goldfishing", note="felt fine", hypotheses_dir=tmp_path
        )

    assert hypotheses.standing(tmp_path, today=TODAY)[0]["evidence"] == []


def test_a_pilots_entry_carrying_no_note_is_refused_before_it_is_written(tmp_path):
    """A playtest entry is the pilot's note and nothing else, so it needs one.

    A data entry takes its numbers from the store and has something to say
    whatever else is passed to it. The other two carry only what the pilot
    wrote, so an entry without a note is a dated line saying that something
    happened, in a log that cannot take it back.
    """
    _record(tmp_path, "second-teferi", TEFERI)

    with pytest.raises(ValueError, match="note"):
        hypotheses.evidence("second-teferi", "playtest", hypotheses_dir=tmp_path)

    assert hypotheses.standing(tmp_path, today=TODAY)[0]["evidence"] == []


def test_an_entry_dated_by_something_that_is_not_a_date_is_refused(tmp_path):
    """Every reading the log joins to is answered by comparing dates as text.

    The mirror share that stood on a day is the last snapshot on or before it,
    read off the date as it is written, so `2026-8-1` falls before `2026-08-07`
    and the entry would carry a reading taken six days after the day it claims.
    That is the hazard `meta.ingest` guards, and this is the other door into it.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db, FIXTURE_META)
    _record(tmp_path / "hypotheses", "postboard-countermagic", COUNTERMAGIC)

    with pytest.raises(ValueError):
        hypotheses.evidence(
            "postboard-countermagic",
            "data",
            on="2026-8-1",
            db_path=db,
            hypotheses_dir=tmp_path / "hypotheses",
        )

    assert hypotheses.standing(tmp_path / "hypotheses", today=TODAY)[0]["evidence"] == []


def test_an_entry_lands_in_the_log_and_not_at_the_end_of_whatever_follows_it(tmp_path):
    """The log is a section of the record, not the bottom of the file.

    A record may carry sections after it, and an entry appended past them is on
    disk and out of the log: it would not read back, would not print, and
    nothing would say it had gone. A log whose whole premise is that it
    accumulates cannot lose an entry quietly.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)
    _record(
        tmp_path / "hypotheses",
        "consign-mainboard",
        CONSIGN + "\n## Evidence\n\n### 2026-08-01 judgment\n\nThe slot is worth more than the copy.\n"
        "\n## Where this came from\n\nA game on 2026-07-30.\n",
    )

    hypotheses.evidence(
        "consign-mainboard", "data", on=TODAY, db_path=db, hypotheses_dir=tmp_path / "hypotheses"
    )

    (record,) = hypotheses.standing(tmp_path / "hypotheses", today=TODAY)
    assert [(e["on"], e["source"]) for e in record["evidence"]] == [
        ("2026-08-01", "judgment"),
        (TODAY, "data"),
    ]
    # And the section that followed the log is still after it, unharmed.
    assert record["path"].read_text(encoding="utf-8").endswith("A game on 2026-07-30.\n")


def test_the_pilots_own_standing_hypotheses_open_the_tracked_set():
    """What Alejandro is already arguing with himself about, as of 2026-08-07.

    These are the real records rather than fixtures, as the reference list is:
    they are the eight questions the 75 is actually undecided on, stated before
    any of the data was read, so none of them is the engine having found what it
    went looking for. Every one is the pilot's, which is why they all open at
    pilot-experience: the data-suggested origin is for the claims the flag layer
    raises later.

    Each names what in the field's lists speaks to it, because a claim the
    evidence layer cannot reach is one that will be settled on vibes after all.
    """
    records = {record["id"]: record for record in hypotheses.standing(today=TODAY)}

    assert {
        "consign-mainboard",
        "fourth-thoughtseize",
        "graveyard-hate",
        "green-source",
        "land-count",
        "postboard-countermagic",
        "second-teferi",
        "wrath-density",
    } <= set(records)

    # Every one of them is the pilot's, and every one names what in the field's
    # lists an entry is to be read off. Their statuses and verdicts are not
    # asserted: ruling on them is the work this exists for, and a test that
    # pinned them open would fail the first time it was done.
    opening = [records[id] for id in records]
    assert {record["origin"] for record in opening} == {"pilot-experience"}
    assert all(record["claim"] and record["subjects"] and record["sought"] for record in opening)

    # The one claim that cannot be settled on the camp's lists alone: postboard
    # countermagic is bought against the blue half of the field, so how much of
    # the field is blue is half the question.
    assert records["postboard-countermagic"]["conditional_on"] == "mirror"

    # The claim is stated from the side of change, against what the 75 actually
    # registers. The reference list is on twenty-two lands, so a record arguing
    # for a twenty-second is one no evidence could ever contradict.
    assert records["land-count"]["subjects"] == ["lands"]
    registered = reference.current().mainboard
    assert sum(registered.get(card, 0) for card in LAND_SLOTS) == 22
