"""The paper Spotlight readings: membership, position, record, and the chain.

Same seam as the rest of the suite: payloads shaped as melee publishes them in
one end, and the verdict a reader would act on out the other. What is asserted
here is never a query or an intermediate, it is whether the deck reads as
present, as having finished well, and as having changed something.

The payloads are written rather than captured because every claim below is about
two events of deliberately different size, or about a name disagreeing with the
cards under it, and no fetched event holds one of those disentangled from the
rest of what a nine-hundred-player field was doing.
"""

import json

import pytest

from deck_engine import config, melee, spotlight, weekly

SIGNATURE = {card: 4 for card in config.TRACKED_DECKS["blink"]["signature"]}
ESPER = {"Watery Grave": 1}
FILLER = {"Thoughtseize": 4, "Solitude": 4, "Flooded Strand": 4, "Plains": 2}

BRISBANE = {"id": 441441, "label": "Spotlight Brisbane", "date": "2026-08-29"}
DALLAS = {"id": 405590, "label": "Spotlight Dallas", "date": "2026-09-05"}


def _list(rank, main=None, side=None, name="Esper Blink", wins=8, losses=4, draws=0, points=None):
    return {
        "decklist_id": f"d{rank}",
        "rank": rank,
        "pilot": f"pilot{rank}",
        "name": name,
        "record": f"{wins}-{losses}-{draws}",
        "wins": wins,
        "losses": losses,
        "draws": draws,
        # Swiss points, which is a separate figure from the record and not
        # derivable from it: a playoff match is a win that earns none.
        "points": wins * 3 if points is None else points,
        "main": {**SIGNATURE, **ESPER, **FILLER, **(main or {})},
        "side": side or {},
    }


def _payload(spot, lists, players=None):
    return {
        "tournament": {
            "id": spot["id"],
            "name": spot["label"],
            "organiser": "test",
            "start": f"{spot['date']}T00:00:00Z",
            "round": "Finals",
            "players": players or len(lists),
        },
        "lists": lists,
    }


def _cache(tmp_path, spot, payload):
    tmp_path.mkdir(parents=True, exist_ok=True)
    spotlight.cached(spot, tmp_path).write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_a_double_faced_card_is_folded_to_the_face_mtgo_publishes():
    """The fold is what makes a paper list of this deck classify at all.

    Melee writes a modal double-faced card as `Front // Back` and MTGO writes
    the front face, and one of this deck's four signature cards is one. Left
    unfolded the name never matches, every Blink list in the field fails
    membership on it, and the deck reads as absent from paper entirely, which is
    a far worse failure than a missing card because nothing about it looks wrong.
    """
    markup = (
        '<div class="decklist-category-title">Creature (4)</div>'
        '<div class="decklist-record"><span class="decklist-record-quantity">4</span>'
        '<a class="decklist-record-name" href="/Card/View/x">'
        "Witch Enchanter // Witch-Blessed Meadow</a></div>"
    )
    main, _ = melee.boards(markup)
    assert main == {"Witch Enchanter": 4}


def test_the_sideboard_is_split_on_its_heading_and_not_on_a_count():
    """A companion sits under its own heading and is not a 61st mainboard card."""
    markup = (
        '<div class="decklist-category-title">Instant (2)</div>'
        '<div class="decklist-record"><span class="decklist-record-quantity">2</span>'
        '<a class="decklist-record-name" href="/x">Ephemerate</a></div>'
        '<div class="decklist-category">'
        '<div class="decklist-category-title">Sideboard (1)</div>'
        '<div class="decklist-record"><span class="decklist-record-quantity">1</span>'
        '<a class="decklist-record-name" href="/x">Clarion Conqueror</a></div>'
    )
    main, side = melee.boards(markup)
    assert main == {"Ephemerate": 2}
    assert side == {"Clarion Conqueror": 1}


def test_membership_is_the_cards_and_never_the_name_the_pilot_typed():
    """A decklist name on melee is free text and cannot decide an archetype.

    The same seventy-five was registered as "Esper Blink", "Azorius Blink" and a
    bare "Esper" at one event, and lists that are not the deck were registered
    as "Esper Blink". Counting by name would put both errors into every share.
    """
    # Named for another deck and holding the rule, against named for this one
    # and one signature card short of it.
    impostor = _list(3, name="Esper Blink")
    del impostor["main"]["Flickerwisp"]
    payload = _payload(
        BRISBANE,
        [_list(1, name="Azorius Blink"), _list(2, name="Mono-Green Eldrazi"), impostor],
    )
    assert [row["rank"] for row in spotlight.members(payload)] == [1, 2]


def test_a_spotlight_sits_on_the_week_it_was_played_in():
    """Keyed by that week's Monday and read by its Sunday, like every other week.

    A Spotlight is a Saturday, and the report's calendar is weeks. Brisbane on
    29 August is the week ending 30 August and Dallas on 5 September is the week
    ending 6 September, which is what puts the two in different weeks rather
    than in the one fortnight bin that happens to contain both.
    """
    assert spotlight.week(BRISBANE) == "2026-08-24"
    assert spotlight.week(DALLAS) == "2026-08-31"
    assert weekly.week_label(spotlight.week(BRISBANE)) == "2026-08-30"
    assert weekly.week_label(spotlight.week(DALLAS)) == "2026-09-06"


def test_position_is_read_against_the_field_and_not_as_a_rank():
    """Rank 100 is a different result at 932 seats than at 574.

    This is the whole reason the positional axis is a share. Two lists that
    finished in the same tenth of two differently sized rooms have to read as
    the same result, and two lists on the same rank must not.
    """
    small = _payload(BRISBANE, [_list(rank) for rank in range(1, 101)])
    big = _payload(DALLAS, [_list(rank) for rank in range(1, 1001)])
    # One list at a tenth of the way down each field.
    tenth_of_small = spotlight.reading(small)["placings"][10]
    tenth_of_big = spotlight.reading(big)["placings"][100]
    assert tenth_of_small == pytest.approx(tenth_of_big)


def test_the_win_rate_counts_matches_and_never_points():
    """Points stop accruing at the top cut and the record does not.

    The pilot who wins the event plays three more matches than the Swiss leader
    and earns no points for them, so a rate read off points scores the winner
    below somebody they beat.
    """
    # Won the event: 12-3 through the Swiss for 36 points, then three playoff
    # wins that earn none. Against the pilot who topped the Swiss and lost in
    # the quarter-final, on more points and fewer wins.
    winner = _list(1, wins=15, losses=3, points=36)
    swiss_leader = _list(2, wins=13, losses=2, points=39)
    reading = spotlight.reading(_payload(DALLAS, [winner, swiss_leader]))
    assert reading["wins"] == 28
    assert reading["losses"] == 5
    assert reading["win_rate"] == pytest.approx(28 / 33)
    # The two figures disagree about which pilot had the better tournament, and
    # the record is the one that gets it right.
    assert winner["wins"] > swiss_leader["wins"]
    assert winner["points"] < swiss_leader["points"]


def test_conversion_is_the_cut_against_the_whole_room():
    """A deck that held more of the top 32 than of the field converted.

    The reading MTGO cannot make, its challenge data being a top 32 with no
    field under it to divide by. Above 1.00 the deck finished above its numbers.
    """
    # Six of 320 lists, and three of them in the top 32: a tenth of the cut
    # against a fiftieth of the room.
    ours = [_list(rank) for rank in (1, 5, 20)]
    theirs = [_list(rank, name="Other") for rank in range(33, 350)]
    for row in theirs:
        row["main"] = {"Lightning Bolt": 4}
    reading = spotlight.reading(_payload(DALLAS, ours + theirs))
    assert reading["cut_lists"] == 3
    assert reading["conversion"] > 1
    assert reading["best"] == 1


def test_the_second_spotlight_is_read_against_the_first_and_not_against_mtgo(tmp_path):
    """Paper to paper is the only clean comparison the two events allow.

    Both fell inside one MTGO fortnight, so a bin lookup would read each against
    the same rows and call the second one's change a repeat of the first's. The
    chain reads Dallas against Brisbane, which is one week apart with the format
    and the medium held constant.
    """
    plain = [_list(rank) for rank in range(1, 21)]
    adopted = [_list(rank, side={"Clarion Conqueror": 3}) for rank in range(1, 21)]
    _cache(tmp_path, BRISBANE, _payload(BRISBANE, plain))
    _cache(tmp_path, DALLAS, _payload(DALLAS, adopted))

    chain = spotlight.chain(config.DB_PATH, spotlights=(BRISBANE, DALLAS), directory=tmp_path)
    assert chain[1]["against"] == "Spotlight Brisbane"
    assert chain[1]["cross_population"] is False
    climbed = [row for row in chain[1]["found"] if row["card"] == "Clarion Conqueror"]
    assert climbed and "climbed" in climbed[0]["text"]


def test_the_first_spotlight_is_marked_as_crossing_populations(tmp_path):
    """Its baseline is MTGO, which is a different room and says so.

    An Australian paper field and the MTGO field are two populations, so a card
    at nine tenths of one and half of the other is not the deck changing its
    mind. The row carries the flag rather than the reader being expected to
    remember which side of the chain it came from.
    """
    _cache(tmp_path, BRISBANE, _payload(BRISBANE, [_list(rank) for rank in range(1, 21)]))
    chain = spotlight.chain(config.DB_PATH, spotlights=(BRISBANE,), directory=tmp_path)
    assert chain[0]["cross_population"] is True
    assert chain[0]["against"].startswith("the fortnight to ")


def test_a_thin_spotlight_does_not_earn_rows_off_the_size_difference(tmp_path):
    """The fortnight's count gate inverts when the two populations differ tenfold.

    It asks the number of lists to move by five, which holds the evidence
    constant only while both sides are about the same size. Eleven paper lists
    against a hundred and twelve MTGO ones is not that: a card at a seventh of
    the big population and a third of the small one differs by thirteen lists on
    the denominators alone, and every moderately played card would earn a row.

    So a small real move is suppressed and a large one is not, at a size ratio
    that would pass both under the fortnight's own gate.
    """
    baseline = [_list(rank) for rank in range(1, 113)]
    for row in baseline[:16]:
        row["side"] = {"Nihil Spellbomb": 2}
    for row in baseline[:85]:
        row["side"] = {**row["side"], "Damping Sphere": 2}

    thin = [_list(rank) for rank in range(1, 12)]
    # A seventh of the big field to a third of the small one: a real-looking
    # jump that eleven lists cannot actually evidence.
    for row in thin[:4]:
        row["side"] = {"Nihil Spellbomb": 2}
    # And a card most of the baseline ran that almost none of these do.
    for row in thin[:3]:
        row["side"] = {**row["side"], "Damping Sphere": 2}

    found = {row["card"] for row in spotlight.findings(thin, baseline)}
    assert "Nihil Spellbomb" not in found
    assert "Damping Sphere" in found


def test_a_card_in_both_boards_counts_once_as_the_store_counts_it():
    """Melee publishes the two boards apart and the store does not.

    A list running three in the mainboard and two in the side is one mainboard
    registration to the store, so counting it in both zones here would make every
    split card read as a sideboard adoption the moment paper met MTGO.
    """
    split = [
        _list(rank, main={"Ghost Vacuum": 3}, side={"Ghost Vacuum": 2}) for rank in range(1, 12)
    ]
    plain = [_list(rank) for rank in range(1, 12)]
    # Nothing about the sideboard moved, so nothing about it is a finding.
    found = spotlight.findings(split, plain)
    assert not [row for row in found if row["zone"] == "side"]
    assert [row["zone"] for row in found] == ["main"]


def test_a_card_changing_zone_is_one_row_and_not_two():
    """Promoting a sideboard card is a decision about what it is for.

    Read one board at a time it is a card the deck took up and a card the deck
    put down, in the same week, which is two findings about one move and reads
    as the deck contradicting itself.
    """
    before = [_list(rank, side={"Consign to Memory": 3}) for rank in range(1, 12)]
    after = [_list(rank, main={"Consign to Memory": 3}) for rank in range(1, 12)]
    found = spotlight.findings(after, before)
    assert [row["kind"] for row in found] == ["migration"]
    assert "moves to the mainboard" in found[0]["text"]


def test_a_week_never_reports_a_spotlight_it_had_not_seen_yet(tmp_path, monkeypatch):
    """Rebuilt in October, the August report has to say what it said in August.

    Every other part of the report is cut off at the week being rendered, the
    weekly rows and the timeline included, because a report whose past changes
    under it is a report nobody can cite. A Spotlight cache is the one input
    that arrives for all events at once, so without this the week before
    Brisbane would show Dallas, an event a fortnight in its own future.
    """
    monkeypatch.setattr(config, "MELEE_DIR", tmp_path)
    _cache(tmp_path, BRISBANE, _payload(BRISBANE, [_list(rank) for rank in range(1, 12)]))
    _cache(tmp_path, DALLAS, _payload(DALLAS, [_list(rank) for rank in range(1, 12)]))

    def shown(week):
        return [entry["label"] for entry in weekly.spotlights_through(week)]

    assert shown("2026-08-17") == []
    assert shown(spotlight.week(BRISBANE)) == ["Spotlight Brisbane"]
    assert shown(spotlight.week(DALLAS)) == ["Spotlight Brisbane", "Spotlight Dallas"]


def test_a_spotlight_never_reports_a_returning_card(tmp_path):
    """A card absent from MTGO and present in paper is a different field building.

    The return reading is a claim about one population's history over months.
    Pointed at a paper event it would announce a card the Australian field simply
    plays as the deck rediscovering it, every time.
    """
    _cache(tmp_path, BRISBANE, _payload(BRISBANE, [_list(rank) for rank in range(1, 21)]))
    exotic = [_list(rank, main={"Karakas": 2}) for rank in range(1, 21)]
    _cache(tmp_path, DALLAS, _payload(DALLAS, exotic))
    chain = spotlight.chain(config.DB_PATH, spotlights=(BRISBANE, DALLAS), directory=tmp_path)
    assert not [row for row in chain[1]["found"] if row["kind"] == "return"]


def _sized(main: dict, total: int) -> dict:
    """`main` padded with basics to exactly `total` cards, the guard being a count."""
    return {**main, "Wastes": total - sum(main.values())}


def test_a_list_whose_boards_did_not_separate_is_not_read_as_a_member():
    """A parse failure may not add lists to the archetype.

    Melee groups a decklist page under type headings and the split is the
    heading, so a sideboard filed under one the fetch does not know puts the
    whole 75 in the mainboard. Membership is a mainboard test, so a list that
    only sideboarded a signature card would join the deck on that failure.
    Melee's own history carries three such lists, at 75, 76 and 146 cards.
    """
    # A non-member whose sideboarded signature cards landed in the mainboard.
    leaked = _list(5)
    leaked["main"] = _sized({**FILLER, "Broadside Bombardiers": 4, **SIGNATURE, **ESPER}, 75)
    leaked["side"] = {}
    assert spotlight.unread(leaked)

    payload = _payload(BRISBANE, [_list(1), leaked])
    assert [row["rank"] for row in spotlight.members(payload, "blink", "esper")] == [1]
    reading = spotlight.reading(payload, "blink", "esper")
    # Published and in the field, so still in every denominator; just not ours.
    assert (reading["field"], reading["lists"], reading["unread"]) == (2, 1, 1)


def test_a_pilot_who_registered_no_sideboard_is_read_normally():
    """Sixty cards and an empty sideboard is a legal registration, not a failure.

    The signature of the failure is the pair: a mainboard past 60 *and* nothing
    in the sideboard. Melee's history has three lists on 60 with no sideboard,
    and turning those away would be the guard costing real lists.
    """
    bare = _list(2)
    bare["main"] = _sized(bare["main"], 60)
    bare["side"] = {}
    assert not spotlight.unread(bare)
    assert len(spotlight.members(_payload(BRISBANE, [_list(1), bare]), "blink", "esper")) == 2


def _other(rank):
    """A finisher of some other deck: the shape of a row, none of the signature."""
    return {**_list(rank, name="Other"), "main": {"Lightning Bolt": 4, "Mountain": 56}}


def test_the_reading_names_who_finished():
    """The finishes, with pilots and records, not just the best rank.

    A Spotlight is the biggest tournament of its era and the paper paragraph
    leads with who finished. Left out of the reading, those names come off the
    standings page by hand, which is the one part of the report written from
    whatever the writer happened to scroll past.
    """
    field = [_other(rank) for rank in range(1, 101)]
    field[0] = _list(1, wins=13, losses=1)
    field[39] = _list(40, wins=11, losses=4)
    top = spotlight.reading(_payload(DALLAS, field))["top"]
    assert [(row["rank"], row["pilot"], row["record"]) for row in top] == [
        (1, "pilot1", "13-1-0")
    ]


def test_a_deck_that_missed_the_cut_still_reports_its_best_finish():
    """Nothing in the top 32 is a finding, not a blank: the best list is named."""
    field = [_other(rank) for rank in range(1, 101)]
    field[39] = _list(40, wins=11, losses=4)
    assert spotlight.reading(_payload(DALLAS, field))["top"] == [
        {"rank": 40, "pilot": "pilot40", "record": "11-4-0"}
    ]


def test_the_weeks_spotlight_reaches_the_summary_writer(tmp_path):
    """The paper figures are in the JSON the summary is written from, or nowhere.

    Every other clause is written from that file. This one was written off the
    rendered page, and nothing in the file said an event had fallen in the week
    at all, so whether the report got a paper paragraph depended on the writer
    remembering it had.
    """
    _cache(tmp_path, BRISBANE, _payload(BRISBANE, [_list(rank) for rank in range(1, 12)]))
    _cache(tmp_path, DALLAS, _payload(DALLAS, [_list(rank) for rank in range(1, 21)]))
    chain = spotlight.chain(config.DB_PATH, spotlights=(BRISBANE, DALLAS), directory=tmp_path)

    reported = weekly._paper(chain, spotlight.week(DALLAS))
    assert reported["label"] == "Spotlight Dallas"
    assert reported["top"][0]["pilot"] == "pilot1"
    # Both sides of the comparison, because the clause quotes both.
    assert reported["against"] == "Spotlight Brisbane"
    assert reported["against_row"]["lists"] == 11
    assert weekly._paper(chain, "2026-08-17") is None


AMSTERDAM = {"id": 434455, "label": "Pro Tour Amsterdam", "date": "2026-07-17", "format": "Modern"}


def test_each_event_reads_against_whatever_the_storyline_said_last(tmp_path):
    """A major event is a storyline entry, not a thing only another event may follow.

    MTGO moves what pilots take to a Pro Tour and a Pro Tour moves what turns up
    on MTGO the fortnight after, so an event weeks from the nearest other one is
    read against the fortnight that closed before it rather than against
    nothing. Dallas is the other case: Brisbane was played after that fortnight
    closed, so Brisbane is the entry it follows.
    """
    field = [_list(rank) for rank in range(1, 4)] + [_other(rank) for rank in range(4, 6)]
    _cache(tmp_path, AMSTERDAM, _payload(AMSTERDAM, field))
    _cache(tmp_path, BRISBANE, _payload(BRISBANE, [_list(rank) for rank in range(1, 12)]))
    _cache(tmp_path, DALLAS, _payload(DALLAS, [_list(rank) for rank in range(1, 21)]))

    amsterdam, brisbane, dallas = spotlight.chain(
        config.DB_PATH, spotlights=(AMSTERDAM, BRISBANE, DALLAS), directory=tmp_path
    )
    assert amsterdam["lists"] == 3 and amsterdam["field"] == 5
    assert amsterdam["against"] == "the fortnight to 2026-07-12"
    assert brisbane["against"] == "the fortnight to 2026-08-23"
    assert (dallas["against"], dallas["cross_population"]) == ("Spotlight Brisbane", False)


def test_the_constructed_rounds_of_a_two_format_event_are_read_apart():
    """Which rounds a Pro Tour's record is taken over, and where each run opens.

    Melee publishes a running total over the whole event, so the Modern record is
    the difference across each Modern run: the standings at its last round, less
    the standings at the round before it started. Read whole instead, a Modern
    deck's win rate is six rounds of limited and the column means nothing.
    """
    played = [
        {"id": str(n), "name": name, "format": fmt}
        for n, (name, fmt) in enumerate(
            [(f"Round {r}", fmt) for r, fmt in enumerate(
                ["Draft"] * 3 + ["Modern"] * 5 + ["Draft2"] * 3 + ["Modern"] * 5, start=1
            )]
            + [("Quarterfinals", "Draft 3"), ("Semifinals", "Draft 3"), ("Finals", "Draft 3")],
            start=1,
        )
    ]
    # Rounds 4 to 8 opening off round 3, and 12 to 16 opening off round 11.
    assert melee._blocks(played, "Modern") == [("3", "8"), ("11", "16")]


def test_an_empty_paper_row_says_it_was_the_sample_and_not_the_fetch():
    """A bare "stable" on a thin event reads as data that failed to arrive.

    Esper Blink took eight lists to Amsterdam against a fortnight of twenty
    seven, and the gate wants the move worth five lists in the smaller of the
    two, so five of those eight have to change their mind about one card. The
    row says which entry it was read against and how much of the event a finding
    costs, because a reader cannot otherwise tell a quiet event from a broken
    fetch.

    Whichever of the two bars asks for more lists is the one quoted. Past
    twenty-five lists the count gate is no longer the binding one and the
    adoption share is, so a row there costs a fifth of the smaller side rather
    than a flat five.
    """
    thin = {"against": "the fortnight to 2026-07-12", "build_lists": 8, "baseline_lists": 27}
    assert "the fortnight to 2026-07-12" in weekly._stable(thin)
    assert "at 8 lists" in weekly._stable(thin)
    assert f"worth {config.TRACK_MIN_LISTS} of them" in weekly._stable(thin)

    fat = {"against": "Spotlight Brisbane", "build_lists": 77, "baseline_lists": 29}
    assert "at 29 lists" in weekly._stable(fat)
    assert "worth 6 of them" in weekly._stable(fat)
