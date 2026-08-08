"""What a camp is doing with a card, read as movement rather than as a level.

Four readings, each answering something a share cannot: whether the copies are
crossing between the boards, what the lists that went elsewhere spent the slot
on, which cards new to the pool are still being taken up, and what a real part of
the camp plays that the 75 has no copies of.

Written series rather than captured ones, since every one of these is a claim
about two windows and the captured days hold whatever the field happened to do.
"""

import json

from deck_engine import config, ledger, movement, store
from tests import synthetic
from tests.synthetic import challenge, entry

# The 75 the fixtures are read against: the build every synthetic list shares, so
# the only card the reference is missing is the one a test puts in the camp's
# hands and not in its own.
_MAIN = synthetic.SIGNATURE | synthetic.FILLER_MAIN | synthetic.FILLER_LANDS
HELD = {card: (copies, 0) for card, copies in _MAIN.items()} | {
    card: (0, copies) for card, copies in synthetic.FILLER_SIDE.items()
}

CAMP = "non-fallaji"
MOVED = "Teferi, Time Raveler"

# The two windows a movement is read across, as days the fixtures publish on.
# The fresh window is the fortnight to the last published day and the baseline
# is the fixed span behind it, so a day in each is all either reading needs.
FRESH_DAY = "2026-08-05"
BASELINE_DAY = "2026-07-15"


def _built(tmp_path, events):
    db = tmp_path / "engine.duckdb"
    store.build(synthetic.write_cache(tmp_path / "raw", events), db)
    return db


def _day(day, event_id, cards):
    """A challenge of eight of the camp's lists, each registering `cards[seat]`."""
    return challenge(
        day,
        [
            entry(f"seat{seat}", CAMP, cards(seat), points=18 - seat, placement=1 + seat)
            for seat in range(8)
        ],
        event_id=event_id,
    )


def test_a_camp_moving_a_card_between_the_boards_is_read_as_the_migration_it_is(tmp_path):
    """The reading the configuration unit exists for, taken over the two windows.

    The camp sideboarded two copies and now maindecks two, and the count it runs
    has not moved: eight lists on two copies before, eight lists on two copies
    after. Every reading that counts copies reports nothing to see, and what
    happened is that the camp changed its mind about what the card is for.

    Counted in copies rather than lists, since copies are what crossed.
    """
    db = _built(
        tmp_path,
        [
            _day(BASELINE_DAY, "12846200", lambda seat: {MOVED: (0, 2)}),
            _day(FRESH_DAY, "12846201", lambda seat: {MOVED: (2, 0)}),
        ],
    )

    moved = movement.migration(MOVED, db, CAMP)

    assert (moved["baseline"]["main_copies"], moved["baseline"]["side_copies"]) == (0, 16)
    assert (moved["fresh"]["main_copies"], moved["fresh"]["side_copies"]) == (16, 0)
    assert moved["baseline"]["lists"] == moved["fresh"]["lists"] == 8, "the count never moved"
    assert moved["shift"] == 1.0
    assert moved["direction"] == movement.TO_MAIN


def test_a_card_the_camp_holds_steady_is_not_a_migration(tmp_path):
    """A camp arguing about the count has not moved the card anywhere.

    Half the camp on three and half on four is a split about how many, which the
    adoption table already reports as two configurations. Reading it as movement
    would put every ordinary flex slot in a section about cards changing role.
    """
    db = _built(
        tmp_path,
        [
            _day(BASELINE_DAY, "12846202", lambda seat: {MOVED: (3, 0)}),
            _day(FRESH_DAY, "12846203", lambda seat: {MOVED: (4, 0) if seat < 4 else (3, 0)}),
        ],
    )

    assert movement.migration(MOVED, db, CAMP)["direction"] == movement.STEADY


def test_what_the_lists_that_went_elsewhere_registered_in_the_slots_place(tmp_path):
    """A slot decision is a trade, and adoption cannot see one.

    Half the fresh camp runs the two Wraths and half runs one Wrath and a Pest
    Control. The share reports the two configurations and stops; what the reader
    wants is what the half that went elsewhere spent the copy on, which is only
    visible by splitting the population and reading every other card in both.
    """
    db = _built(
        tmp_path,
        [
            _day(
                FRESH_DAY,
                "12846204",
                lambda seat: {"Wrath of the Skies": (0, 2)}
                if seat < 4
                else {"Wrath of the Skies": (0, 1), "Pest Control": (0, 1)},
            )
        ],
    )

    traded = movement.substitution("Wrath of the Skies", 0, 2, db, CAMP)

    assert traded[0]["card"] == "Pest Control"
    assert traded[0]["on_it"] == 0 and traded[0]["elsewhere"] == 1.0
    assert (traded[0]["on_it_lists"], traded[0]["elsewhere_lists"]) == (4, 4)


def test_a_card_new_to_the_pool_that_the_camp_is_taking_up_is_climbing(tmp_path):
    """Novelty and a rising delta, which mean something only together.

    A card the archetype has barely played is innovation-grade wherever it turns
    up, and a card the camp is going towards is news. Either alone is the thing
    it is constantly taken for: a fringe appearance on its own is one pilot's
    experiment, and a delta on its own is a staple drifting.

    One list in twenty-four registers the card before the fresh window and six
    of the eight in it do, which is fringe against the history behind it and a
    climb across the two windows.
    """
    db = _built(
        tmp_path,
        [
            _day("2026-07-01", "12846205", lambda seat: None),
            _day("2026-07-08", "12846209", lambda seat: None),
            _day(
                BASELINE_DAY,
                "12846210",
                lambda seat: {"Vexing Bauble": (0, 2)} if not seat else None,
            ),
            _day(
                FRESH_DAY,
                "12846206",
                lambda seat: {"Vexing Bauble": (0, 2)} if seat < 6 else None,
            ),
        ],
    )

    rising = movement.climbing(db, CAMP)

    assert [row["card"] for row in rising] == ["Vexing Bauble"]
    assert rising[0]["delta"] > 0
    assert (rising[0]["main"], rising[0]["side"]) == (0, 2)


def test_a_card_a_real_part_of_the_camp_plays_that_the_75_runs_none_of(tmp_path):
    """The blind spot between the two readings that look at the reference list.

    The slot audit reads the slots the pilot took, so it can only speak about
    cards he plays. The missing-core reading starts at near-unanimity. A card a
    third of the camp made a decision about falls between them and no other
    surface mentions it, which is the costliest kind of silence: it is a
    deliberate choice by a real part of the camp that the 75 has never answered.

    Six of the eight fresh lists register the card and the 75 has no copies. The
    floor is what decides whether that is worth the pilot's attention, so the one
    list on a card of its own has to stay out of the reading at the same time.
    """
    db = _built(
        tmp_path,
        [
            _day(
                FRESH_DAY,
                "12846207",
                lambda seat: {"Surgical Extraction": (0, 1)}
                if seat < 6
                else {"Pest Control": (0, 1)} if seat == 7 else None,
            )
        ],
    )

    absent = movement.unplayed(HELD, db)

    assert [row["card"] for row in absent] == ["Surgical Extraction"]
    assert absent[0]["camp_playing"] == 0.75
    assert absent[0]["confidence"] == 0.25, "which is the camp's share of running none of it"
    # The one list on Pest Control is under the floor: a card one pilot reached
    # for is the pool rather than a decision the camp made.
    assert all(row["card"] != "Pest Control" for row in absent)


def test_a_departure_is_traced_through_to_what_the_field_did_with_it(tmp_path):
    """The composite: somebody changed something, and here is the field's verdict.

    A departure alone is one pilot's anecdote and a spike alone is a fortnight's
    share. Joined on the card, in the camp, after the departure, they are the
    field's judgment on an idea taken over every pilot who saw it, which is the
    highest-powered instrument this data holds.

    The join is on the card because what spreads is the idea and not the 75
    around it, and it reaches forward only: an episode that preceded the list is
    the list following a trend rather than setting one.
    """
    db = tmp_path / "engine.duckdb"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.with_name(ledger.LEDGER).write_text(
        json.dumps(
            [
                {
                    "kind": "breakthrough",
                    "camp": CAMP,
                    "stratum": "challenge-class",
                    "pilot": "RealG_MTG",
                    "event": "Modern Challenge 64",
                    "date": "2026-05-29",
                    "placement": 3,
                    "mode": "fringe",
                    "delta": 1,
                    "novel": [["Kavaero, Mind-Bitten", 1, 0]],
                    "missing": [],
                    "state": "trendsetter",
                    "followers": ["Jonii", "akwz"],
                    "needed": 2,
                    "adopted_card": "Kavaero, Mind-Bitten",
                    "first_seen": "2026-05-30",
                },
                {
                    "kind": "hype",
                    "camp": CAMP,
                    "card": "Kavaero, Mind-Bitten",
                    "main": 1,
                    "side": 0,
                    "raised_on": "2026-06-21",
                    "state": "established",
                    "standing": "holding",
                    "first_seen": "2026-06-22",
                },
                # An episode on the same card in the other camp, which is another
                # population and no evidence about this departure at all.
                {
                    "kind": "hype",
                    "camp": "fallaji",
                    "card": "Kavaero, Mind-Bitten",
                    "main": 1,
                    "side": 0,
                    "raised_on": "2026-06-01",
                    "state": "decayed",
                    "standing": "lapsed",
                    "first_seen": "2026-06-02",
                },
            ]
        ),
        encoding="utf-8",
    )

    (traced,) = ledger.lineage(db, CAMP)

    assert traced["followed"] == "trendsetter" and traced["needed"] == 2
    assert traced["spread_card"] == "Kavaero, Mind-Bitten"
    assert traced["spiked_on"] == "2026-06-21", "the episode in this camp, after the departure"
    assert (traced["resolved"], traced["standing"]) == ("established", "holding")


def test_the_unplayed_floor_and_cap_are_configuration_values(tmp_path):
    """How much of the camp has to disagree before it is worth reading is a
    judgment, so it is held in one place and the reading says what it dropped.

    A floor low enough admits the whole card pool, and one at the core bar misses
    the card a third of the camp plays, which is the case the reading exists for.
    """
    db = _built(
        tmp_path,
        [
            _day(
                FRESH_DAY,
                "12846208",
                lambda seat: {"Surgical Extraction": (0, 1)}
                if seat < 6
                else {"Pest Control": (0, 1)} if seat == 7 else None,
            )
        ],
    )
    held = HELD

    assert len(movement.unplayed(held, db, floor=0.10)) == 2, "the one-list card clears a low floor"
    assert movement.unplayed(held, db, floor=config.CORE_ADOPTION) == [], (
        "and none of it clears the core bar"
    )

    # Capped at what is worth reading, and the count it dropped rides on the row
    # rather than the tail going silently missing.
    (only,) = movement.unplayed(held, db, floor=0.10, limit=1)
    assert only["card"] == "Surgical Extraction" and only["dropped"] == 1
