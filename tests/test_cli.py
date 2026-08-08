"""The terminal surface, at the layer it decides what a reader is told.

The other surface has its own tests. This one is where the readings are turned
into the lines a pilot actually reads at the prompt, and a field the analysis
computed and this drops is a finding the engine took and never delivered. So
every test here is about what reaches the line, given a row the audit produced.

The rows are written rather than captured, because what is under test is the
display rule and not the arithmetic behind it: `reference.slots` is tested on
the store it reads, and a row here is one of its answers held still.
"""

from deck_engine import cli, config, index


def _slot(**over) -> dict:
    """One audited flex slot as `reference.slots` returns it.

    Two configurations meet on the row and each says whose it is: the pilot's
    count and its share of the camp, then what the camp did about the card.
    """
    return {
        "card": "Wrath of the Skies",
        "main": 0,
        "side": 2,
        "population": 40,
        "lists": 3,
        "confidence": 0.075,
        "boundary": None,
        "tilt": None,
        "delta": -0.09,
        "core": False,
        "bucket": "unexamined-deviation",
        "note": None,
        "missing": False,
        "camp_playing": 1.0,
        "camp_main": 0,
        "camp_side": 3,
        "camp_adoption": 0.925,
        "camp_delta": 0.22,
    } | over


def test_the_terminal_says_what_the_camp_did_about_the_card_and_not_only_the_count():
    """The share alone is two opposite findings and only this tells them apart.

    A slot at 8% of the camp is either a card the camp barely plays, where the
    pilot is out on his own, or a card the camp is unanimous on where he is one
    copy light. The second is the actionable one, and it is the one a bare
    percentage buries: the pilot is told his slot is an 8% deviation and not
    from what.
    """
    line = cli._slot_line(_slot())

    assert "100% play it, 92% on 0/3" in line
    assert "8%" in line and "unexamined-deviation" in line


def test_a_slot_the_camp_never_registered_says_so_rather_than_reading_as_a_share():
    """A card none of the camp plays is a share of none, not a missing reading.

    Left to the camp columns it would print as a pair of zeroes, which reads as
    a configuration the camp registered and went to nobody.
    """
    line = cli._slot_line(_slot(camp_playing=0.0, camp_main=None, camp_side=None, camp_adoption=None))

    assert "the camp registered none of it" in line


def test_every_share_carries_the_count_it_was_taken_over():
    """A verdict off forty lists is one a couple of them could reverse.

    The population is printed once at the head of the audit and the share on
    every row, and a reader cannot get from one to the other without doing the
    arithmetic the bare percentage invited them to skip.
    """
    assert "3/40" in cli._slot_line(_slot())
    assert "3/40" in cli._missing_line(_slot(missing=True, camp_tilt=None))


def test_a_bucket_a_list_or_two_would_refile_says_which_bar_it_turns_on():
    """A bucket is a categorical claim taken off forty-odd lists.

    At that population the bars sit a couple of registrations apart, so a slot
    within one of them is a verdict a single pilot changing his mind reverses.
    Marked on the row rather than softened into a fifth bucket.
    """
    assert "turns on" not in cli._slot_line(_slot())
    assert "turns on supported-minority" in cli._slot_line(_slot(boundary="supported-minority"))


def test_a_tilt_under_the_floor_is_not_displayed_at_all():
    """Every published list already finished, so the points are bunched.

    Across this archetype's configurations the tilt runs to a point or two, and
    a column of figures that size reads as a performance lens while carrying
    none. The figure stays on the row; what is suppressed is the display of it.

    The floor is where the domain put it and not where each surface decides, so
    the same rule holds for a flag's tilt as for a slot's.
    """
    under = config.TILT_FLOOR / 2
    assert "tilt" not in cli._slot_line(_slot(tilt=under))
    assert "tilt" not in cli._slot_line(_slot(tilt=-under))
    assert "tilt" not in cli._missing_line(_slot(missing=True, camp_tilt=under))

    over = config.TILT_FLOOR * 2
    assert f"tilt {over:+.2f}" in cli._slot_line(_slot(tilt=over))
    assert f"tilt {over:+.3f}" in cli._tilt(over, 3)


def test_a_card_the_site_publishes_under_two_printings_is_asked_for_under_either():
    """The store was built with the printings already merged.

    Asked for under the printing the pilot registered rather than the canonical
    name, an unresolved argument matches nothing and every reading on the card
    comes back empty: a confident null about a card a third of the camp plays,
    which is worse than an error because it reads as an answer.
    """
    for published, canonical in config.CARD_ALIASES.items():
        assert cli._resolved(published) == canonical
        assert cli._resolved(canonical) == canonical


def _arrival(**over) -> dict:
    """One of the archetype's lists as `store.arrivals` returns it."""
    return {
        "pilot": "_must_be_nice",
        "event": "Modern League",
        "event_id": "modern-league-2026-08-0510847",
        "event_class": "league",
        "date": "2026-08-05",
        "placement": None,
        "swiss_points": None,
        "record": "5-0",
        "camp": "non-fallaji",
    } | over


def _row(**over) -> index.Row:
    return index.Row(
        date="2026-08-05",
        event_id="modern-league-2026-08-0510847",
        event_class="league",
        pilot="_must_be_nice",
        placement="",
        swiss_points="",
    )._replace(**over)


def test_an_ingest_counts_the_lists_it_brought_in_and_not_only_the_events():
    """The days hardest to speak about are the ones already cached.

    A league dump gains 5-0s through its own day, so the unsettled window
    overwrites captures the cache already held. Reporting events alone would say
    nothing arrived on exactly the day something did, which is the reading the
    index was kept for.
    """
    added = [_row(pilot=f"pilot{n}") for n in range(18)]
    line = cli._ingest_lines(index.Change(added, []), [_arrival()])[0]

    assert "18 new list(s)" in line
    assert "1 event(s)" in line, "one day, eighteen arrivals"
    assert "1 of them Goryo's" in line


def test_an_ingest_names_the_archetype_s_arrivals_and_leaves_the_field_a_number():
    """What the rest of the session is about is which Goryo's lists are new, so
    those are named. The field's hundreds are a count: naming them would bury
    the four lines that matter."""
    lines = cli._ingest_lines(
        index.Change([_row()], []),
        [_arrival(), _arrival(pilot="PTarts2win", event="Modern Challenge 64", placement=10)],
    )

    assert "5-0" in lines[1] and "_must_be_nice" in lines[1] and "non-fallaji" in lines[1]
    assert "#10" in lines[2] and "PTarts2win" in lines[2]


def test_a_run_that_brought_nothing_in_says_so_rather_than_printing_a_zero():
    assert cli._ingest_lines(index.Change([], []), []) == [
        "  no list published since the last run"
    ]


def test_lists_the_site_no_longer_publishes_are_said_out_loud():
    """A withdrawn event is not a gap and not an error, but lists leaving the
    history quietly is the same failure as lists arriving quietly."""
    lines = cli._ingest_lines(index.Change([], [_row(), _row(pilot="pepeteam")]), [])

    assert lines[-1] == "  2 list(s) the site no longer publishes"


def test_a_first_run_counts_the_history_it_filed_rather_than_reciting_it():
    """A first run's index was empty, so its arrivals are the whole history.

    That is not news and must not print as though it were. It is not nothing
    either, so what was dropped off the end is counted rather than left silent.
    """
    ours = [_arrival(pilot=f"pilot{n}") for n in range(cli.NAMED_ARRIVALS + 14)]
    lines = cli._ingest_lines(index.Change([_row()], []), ours)

    assert len(lines) == cli.NAMED_ARRIVALS + 2, "the count, the named, then the remainder"
    assert lines[-1] == "    and 14 more, further back"
