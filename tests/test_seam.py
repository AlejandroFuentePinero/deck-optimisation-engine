"""The pipeline's single test seam: real cached payloads in, verdicts out.

Fixtures are the immutable raw cache of every Modern event published on
2026-08-05, captured from the live site. Nothing here asserts on parser
internals, schema shape, or intermediate tables.
"""

import csv
import json
from pathlib import Path

import pytest

from deck_engine import config, meta, mtgo, reference, store
from deck_engine.classify import camp, classify_cache
from deck_engine.refresh import refresh

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"
# One captured Last Chance: a Swiss-only event of a kind the day's cache lacks.
FIXTURE_KINDS = Path(__file__).parent / "fixtures" / "kinds"
# The 2026-07-08 challenge as the site served it: under its own slug, and again
# under a second slug dated 2026-07-24 that the site later withdrew.
FIXTURE_DUPLICATE = Path(__file__).parent / "fixtures" / "duplicate"
# One captured league dump in which a pilot trophied twice on the day, on two
# lists that are not the same 75.
FIXTURE_REPEATS = Path(__file__).parent / "fixtures" / "repeats"
# Two captured challenges holding a list of every camp shape, plus a near-miss.
FIXTURE_CAMPS = Path(__file__).parent / "fixtures" / "camps"
# Both strata either side of the 2026-05-18 regime boundary, with a grinder in
# them: Rvng took three of the four post-regime Fallaji league trophies here.
FIXTURE_CONVERSION = Path(__file__).parent / "fixtures" / "conversion"
# Eight captured events reaching back from 2026-08-05: both strata inside the
# fresh fortnight, both strata behind it in the baseline, and a pre-regime
# challenge the baseline has to stop short of. Every camp is represented, and
# the day's non-Fallaji challenge lists disagree on where Consign to Memory
# goes at a constant four copies.
FIXTURE_ADOPTION = Path(__file__).parent / "fixtures" / "adoption"
# One captured showcase qualifier whose only non-Fallaji list, karatedom's,
# scored nothing: a camp whose whole window is worth zero points.
FIXTURE_POINTLESS = Path(__file__).parent / "fixtures" / "zero-points"
# The pilot's own 75 as captured, which is not a fixture but the real thing.
REFERENCE_CAPTURE = Path(__file__).parent.parent / "reference" / "2026-08-07-moxfield.txt"
# The meta history as it stands, which is likewise the real thing: the 14-day
# MTGGoldfish snapshot of 2026-08-07, transcribed from the screenshot by hand.
META_HISTORY = Path(__file__).parent.parent / "data" / "meta"

# The day's Goryo's lists, read off the published decklists by hand.
GORYOS_PILOTS_2026_08_05 = {
    "frekinsmart",
    "pepeteam",
    "_must_be_nice",
    "AldenCates",
    "Kollslaw",
    "Acecalna",
}

# AldenCates' 15-card sideboard from Modern Challenge 32 12849509, read off the
# published decklist by hand.
ALDENCATES_SIDEBOARD = {
    "Celestial Purge": 1,
    "Consign to Memory": 3,
    "March of Otherworldly Light": 2,
    "Mystical Dispute": 3,
    "Nihil Spellbomb": 2,
    "Teferi, Time Raveler": 1,
    "Wrath of the Skies": 3,
}


def test_trio_rule_selects_exactly_the_days_goryos_lists():
    lists = classify_cache(FIXTURE_RAW)

    members = {d.pilot for d in lists if d.archetype == "goryos"}
    assert members == GORYOS_PILOTS_2026_08_05


def test_a_list_carries_its_published_sideboard_alongside_its_mainboard():
    """A list is a 75, and the 15 are where sideboard plans live.

    Their absence would read a main-to-side migration as a straight cut, so the
    sideboard is loaded as published, next to the mainboard it was registered
    with.
    """
    lists = classify_cache(FIXTURE_RAW)

    alden = next(d for d in lists if d.pilot == "AldenCates")
    assert alden.sideboard == ALDENCATES_SIDEBOARD
    assert sum(alden.sideboard.values()) == 15
    assert sum(alden.mainboard.values()) == 60


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


def test_a_cards_main_and_side_copies_are_queryable_separately_and_as_a_total(tmp_path):
    """A configuration is the pair, so the two halves must stay tellable apart.

    AldenCates registered Consign to Memory 1 main and 3 side: a count of main
    copies alone calls that a one-of, and a count of the 75 calls it a playset.
    Only the pair says what the list actually does.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_RAW, db)

    def copies(card):
        rows = {row["pilot"]: row for row in store.card_configurations(card, db, "2026-08-05")}
        row = rows["AldenCates"]
        return row["main"], row["side"], row["total"]

    assert copies("Consign to Memory") == (1, 3, 4)
    assert copies("Wrath of the Skies") == (0, 3, 3)
    assert copies("Goryo's Vengeance") == (4, 0, 4)


def test_one_pilots_two_trophies_are_two_lists_with_their_own_configurations(tmp_path):
    """A league dump publishes every 5-0, so a pilot can appear in it twice.

    Zeect trophied twice on 2026-06-24 having moved a Solitude to the sideboard
    between runs: 4 main and 0 side, then 3 main and 1 side. That is the
    migration at a constant total the whole configuration reading exists for, so
    the two lists have to stay two, and a query keyed on the pilot would lose it.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_REPEATS, db)

    rows = [r for r in store.card_configurations("Solitude", db) if r["pilot"] == "Zeect"]

    assert len({r["list_id"] for r in rows}) == 2
    assert {(r["main"], r["side"], r["total"]) for r in rows} == {(4, 0, 4), (3, 1, 4)}


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


def test_camps_split_the_archetype_by_the_divergence_card():
    """Fallaji Archaeologist is the fork in the archetype's construction.

    Read off the two captured challenges: Rvng on three copies and BERNASTORRES
    on four are the Fallaji camp, Walker735 and Darkchrome6538 on none are the
    non-Fallaji camp, and Gerardo94 on two has committed to neither.
    """
    lists = classify_cache(FIXTURE_CAMPS)

    camps = {d.pilot: d.camp for d in lists if d.archetype == "goryos"}
    assert camps == {
        "Rvng": "fallaji",
        "BERNASTORRES": "fallaji",
        "Gerardo94": "hybrid",
        "Walker735": "non-fallaji",
        "Darkchrome6538": "non-fallaji",
    }


def test_a_camps_consensus_population_is_its_own_lists_and_never_the_hybrids(tmp_path):
    """Consensus is computed per camp, so a camp's population is only its own.

    Gerardo94's two copies are an experiment in neither direction: counting that
    list into either camp would move that camp's consensus towards a build no
    pilot in it registered. It stays in the archetype, and out of both.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_CAMPS, db)

    fallaji = {row["pilot"] for row in store.goryos_lists(db, camp="fallaji")}
    non_fallaji = {row["pilot"] for row in store.goryos_lists(db, camp="non-fallaji")}

    assert fallaji == {"Rvng", "BERNASTORRES"}
    assert non_fallaji == {"Walker735", "Darkchrome6538"}
    assert "Gerardo94" in {row["pilot"] for row in store.goryos_lists(db)}


def test_near_miss_lists_are_watchlisted_with_what_they_kept_and_what_they_dropped(tmp_path):
    """A near-miss is potential variant innovation, not a member.

    nikkuniku finished 25th on 2026-07-22 playing Goryo's Vengeance and Psychic
    Frog with no Atraxa: exactly the shape worth watching, and exactly the shape
    that would drag the archetype's own numbers towards a deck it isn't.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_CAMPS, db)

    watchlist = store.near_miss_lists(db)

    assert [(r["pilot"], r["date"], r["placement"]) for r in watchlist] == [
        ("nikkuniku", "2026-07-22", 25)
    ]
    assert watchlist[0]["kept"] == ["Goryo's Vengeance", "Psychic Frog"]
    assert watchlist[0]["dropped"] == ["Atraxa, Grand Unifier"]

    # Watchlisted, and out of every archetype figure: no membership, no camp.
    assert "nikkuniku" not in {row["pilot"] for row in store.goryos_lists(db)}


def test_the_camp_ratio_is_queryable_as_a_series_over_time(tmp_path):
    """Which way the archetype is drifting is a question about the split.

    The two captured days answer it: one non-Fallaji list on 2026-07-22, then
    four lists on 2026-07-29 split two Fallaji, one non-Fallaji, one hybrid. The
    hybrids are in the denominator because how much of the archetype is
    experimenting is part of the picture, and the shares sum to the day.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_CAMPS, db)

    challenge = "challenge-class"
    assert store.camp_ratio(db) == [
        {"date": "2026-07-22", "stratum": challenge, "camp": "non-fallaji", "lists": 1, "share": 1.0},
        {"date": "2026-07-29", "stratum": challenge, "camp": "fallaji", "lists": 2, "share": 0.5},
        {"date": "2026-07-29", "stratum": challenge, "camp": "hybrid", "lists": 1, "share": 0.25},
        {"date": "2026-07-29", "stratum": challenge, "camp": "non-fallaji", "lists": 1, "share": 0.25},
    ]


def test_the_camp_ratio_never_pools_the_league_and_challenge_strata(tmp_path):
    """A day's two strata publish on different terms, so they get separate shares.

    2026-08-05 is the case: one Fallaji list of three in the day's challenges,
    none of the three league trophies. Pooled, the day reads 17% Fallaji, which
    is a number no stratum reported and which moves with how many leagues
    happened to publish rather than with what pilots registered.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_RAW, db)

    assert store.camp_ratio(db) == [
        {
            "date": "2026-08-05",
            "stratum": "challenge-class",
            "camp": "fallaji",
            "lists": 1,
            "share": pytest.approx(1 / 3),
        },
        {
            "date": "2026-08-05",
            "stratum": "challenge-class",
            "camp": "non-fallaji",
            "lists": 2,
            "share": pytest.approx(2 / 3),
        },
        {
            "date": "2026-08-05",
            "stratum": "league",
            "camp": "non-fallaji",
            "lists": 3,
            "share": 1.0,
        },
    ]


def test_the_conversion_gap_is_a_camps_league_pilot_share_less_its_challenge_share(tmp_path):
    """What a camp converts into 5-0s, against how much of the field it is.

    A league trophy is a real win record, but its denominator is unpublished: a
    camp's trophy count is entries times conversion, and only the product is
    served. The challenge stratum supplies the proxy denominator, so the gap is
    the whole reading and neither raw count is.

    Read off the seven captured payloads by hand. Post-regime the leagues hold
    four Fallaji trophies from two pilots, Rvng having taken three of them, and
    eight non-Fallaji trophies from seven; the two challenges hold one Fallaji,
    one hybrid and six non-Fallaji lists, a pilot apiece. Pre-regime is one
    trophy each way and a showcase challenge of one Fallaji to two non-Fallaji.

    Every row carries its own controls, because the gap alone is unreadable:
    the pilot counts it was computed over, the uncapped figure the per-pilot cap
    was applied to, and the same figure the far side of the regime boundary.

    The hybrids are in it for the reason they are in the camp ratio: a camp
    converting worse than the experiment is the same news as it converting worse
    than the other camp. Post-regime they hold a challenge list and no trophy,
    which is a gap of the whole of their challenge share.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_CONVERSION, db)

    assert store.conversion_gap(db) == [
        {
            "regime": "pre-regime",
            "camp": "fallaji",
            "league_pilots": 1,
            "challenge_pilots": 1,
            "league_share": pytest.approx(1 / 2),
            "challenge_share": pytest.approx(1 / 3),
            "gap": pytest.approx(1 / 6),
            "uncapped": pytest.approx(1 / 6),
            "cap_effect": "holds",
        },
        {
            "regime": "pre-regime",
            "camp": "non-fallaji",
            "league_pilots": 1,
            "challenge_pilots": 2,
            "league_share": pytest.approx(1 / 2),
            "challenge_share": pytest.approx(2 / 3),
            "gap": pytest.approx(-1 / 6),
            "uncapped": pytest.approx(-1 / 6),
            "cap_effect": "holds",
        },
        {
            "regime": "post-regime",
            "camp": "fallaji",
            "league_pilots": 2,
            "challenge_pilots": 1,
            "league_share": pytest.approx(2 / 9),
            "challenge_share": pytest.approx(1 / 8),
            "gap": pytest.approx(7 / 72),
            "uncapped": pytest.approx(5 / 24),
            "cap_effect": "collapses",
        },
        {
            "regime": "post-regime",
            "camp": "hybrid",
            "league_pilots": 0,
            "challenge_pilots": 1,
            "league_share": pytest.approx(0.0),
            "challenge_share": pytest.approx(1 / 8),
            "gap": pytest.approx(-1 / 8),
            "uncapped": pytest.approx(-1 / 8),
            "cap_effect": "holds",
        },
        {
            "regime": "post-regime",
            "camp": "non-fallaji",
            "league_pilots": 7,
            "challenge_pilots": 6,
            "league_share": pytest.approx(7 / 9),
            "challenge_share": pytest.approx(3 / 4),
            "gap": pytest.approx(1 / 36),
            "uncapped": pytest.approx(-1 / 12),
            "cap_effect": "flips",
        },
    ]


def test_a_gap_one_grinder_produced_is_caught_by_the_cap_rather_than_published(tmp_path):
    """The confound the gap would otherwise be: one pilot playing a great deal.

    Rvng took three of the four post-regime Fallaji league trophies here. Over
    published lists the camp converts far above its challenge share, and that
    figure is mostly one pilot's grinding. Counting each pilot once leaves under
    half of it standing, so the row reports a collapse rather than the gap.

    The reading is the pair and never the survivor alone: a camp whose gap the
    cap leaves intact has a different claim from one whose gap it guts, and
    nothing in the row is dropped for the reader to have to ask for.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_CONVERSION, db)

    trophies = [
        row
        for row in store.goryos_lists(db, camp="fallaji")
        if row["event_class"] == "league" and row["date"] >= "2026-05-18"
    ]
    assert len(trophies) == 4
    assert sum(row["pilot"] == "Rvng" for row in trophies) == 3

    fallaji = next(
        row
        for row in store.conversion_gap(db)
        if (row["regime"], row["camp"]) == ("post-regime", "fallaji")
    )
    assert (fallaji["league_pilots"], fallaji["cap_effect"]) == (2, "collapses")


def _configurations(rows, card, camp, stratum):
    """One card's rows for one camp in one stratum, keyed by the configuration."""
    return {
        (row["main"], row["side"]): row
        for row in rows
        if (row["card"], row["camp"], row["stratum"]) == (card, camp, stratum)
    }


def test_adoption_is_read_per_camp_per_stratum_and_per_window(tmp_path):
    """Four terms make an adoption figure, and dropping any of them makes it a
    different number: which camp, which stratum, which window, which configuration.

    Consign to Memory in the fresh fortnight is the case. The non-Fallaji camp's
    three challenge lists split two to one over where the fourth copy goes; the
    Fallaji camp's three are unanimous on all four in the side; the three league
    trophies are unanimous the other way. Pooled, that is a card at 100% adoption
    on a configuration nobody in the archetype agrees about.

    The camp's own baseline sits beside each figure, since a share on its own
    says nothing about which way it is moving.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)

    rows = store.adoption(db)

    def fresh(camp, stratum):
        return {
            configuration: (row["fresh_lists"], row["fresh_population"], row["fresh_adoption"])
            for configuration, row in _configurations(
                rows, "Consign to Memory", camp, stratum
            ).items()
        }

    # AldenCates and Kollslaw main one and side three; Walker735 sides all four.
    assert fresh("non-fallaji", "challenge-class") == {
        (1, 3): (2, 3, pytest.approx(2 / 3)),
        (0, 4): (1, 3, pytest.approx(1 / 3)),
        # Registered in the baseline by Phryziel and Prim3Time, by nobody since.
        (2, 2): (0, 3, 0.0),
    }
    assert fresh("fallaji", "challenge-class") == {(0, 4): (3, 3, 1.0)}
    assert fresh("non-fallaji", "league") == {(1, 3): (3, 3, 1.0)}

    # The delta is against the camp's own baseline, in its own stratum: the
    # main copy is new since, and the split the camp used to run is gone.
    moved = _configurations(rows, "Consign to Memory", "non-fallaji", "challenge-class")
    assert (moved[(1, 3)]["baseline_lists"], moved[(1, 3)]["baseline_population"]) == (0, 4)
    assert moved[(1, 3)]["delta"] == pytest.approx(2 / 3)
    assert moved[(2, 2)]["baseline_adoption"] == pytest.approx(1 / 2)
    assert moved[(2, 2)]["delta"] == pytest.approx(-1 / 2)


def test_a_main_to_side_migration_at_a_constant_total_is_a_configuration_change(tmp_path):
    """The reading the configuration unit exists for.

    Zeect trophied twice in the same league dump having moved a Solitude to the
    sideboard between runs, and every non-Fallaji challenge list in the fresh
    window runs four Consign to Memory. On totals both cards look untouched: the
    camp is on four copies before and four copies after, and a count of copies
    would report nothing to see. Where the copies go changed, and adoption
    splits across the two configurations to say so.

    The Solitude half is Zeect alone, since he is the whole of that window's
    Fallaji league population: one pilot changing his mind between runs, which
    the row says by carrying a population of two lists. The Consign half is
    three pilots at three seats, and there the split is the camp's.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)

    rows = store.adoption(db)

    migrated = _configurations(rows, "Solitude", "fallaji", "league")
    assert {
        configuration: row["baseline_adoption"] for configuration, row in migrated.items()
    } == {(4, 0): 0.5, (3, 1): 0.5}
    assert {main + side for main, side in migrated} == {4}

    consign = _configurations(rows, "Consign to Memory", "non-fallaji", "challenge-class")
    assert {main + side for main, side in consign} == {4}
    assert consign[(1, 3)]["fresh_adoption"] == pytest.approx(2 / 3)
    assert consign[(0, 4)]["fresh_adoption"] == pytest.approx(1 / 3)


def test_points_weighting_is_each_finish_against_its_own_events_best(tmp_path):
    """Raw adoption counts lists; weighted adoption counts how they finished.

    A list is worth its Swiss points over the best Swiss total its event
    published, so a 96-player challenge running more rounds cannot outvote a
    challenge 32 on round count alone. Walker735's 12 points came out of an
    event topping out at 21 and AldenCates' 12 out of one topping out at 18: the
    same points, and not the same finish.

    The fresh non-Fallaji challenge lists are AldenCates 12/18, Kollslaw 12/18
    and Walker735 12/21, so the camp's weight is 2/3 + 2/3 + 4/7 = 40/21. The
    two lists maining a Consign to Memory hold 4/3 of it, which is 0.7 against a
    raw 2/3, so the configuration tilts +1/30. Walker735's sided fourth copy
    takes the other side of it.

    The tilt is the pair's difference and is only ever read beside them: +1/30
    on two lists of three is a camp that has barely finished ahead, and the raw
    share is what says so.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)

    rows = store.adoption(db)

    consign = _configurations(rows, "Consign to Memory", "non-fallaji", "challenge-class")
    assert consign[(1, 3)]["fresh_adoption"] == pytest.approx(2 / 3)
    assert consign[(1, 3)]["fresh_weighted"] == pytest.approx(0.7)
    assert consign[(1, 3)]["fresh_tilt"] == pytest.approx(1 / 30)
    assert consign[(0, 4)]["fresh_weighted"] == pytest.approx(0.3)
    assert consign[(0, 4)]["fresh_tilt"] == pytest.approx(-1 / 30)

    # The Fallaji camp is Acecalna 12/18, Rvng 12/21 and BERNASTORRES 18/21, so
    # its weight is 44/21. The playset is the two of them holding 32/21 of it,
    # which is 8/11 against a raw 2/3: Rvng's three-copy build is the drag.
    playset = _configurations(rows, "Fallaji Archaeologist", "fallaji", "challenge-class")
    assert playset[(4, 0)]["fresh_adoption"] == pytest.approx(2 / 3)
    assert playset[(4, 0)]["fresh_weighted"] == pytest.approx(8 / 11)
    assert playset[(4, 0)]["fresh_tilt"] == pytest.approx(2 / 33)
    assert playset[(3, 0)]["fresh_tilt"] == pytest.approx(-2 / 33)


def test_no_league_list_reaches_a_points_weighted_figure_or_the_performance_tilt(tmp_path):
    """Performance tilt is Swiss points, and a league publishes none.

    The rule was recorded in `CONTEXT.md` before there was any tilt code for it
    to bind to, and it would otherwise hold only by accident: league rows carry
    no `swiss_points` for a weighting to pick up. So the fixture puts both
    strata inside the fresh window and the rule is asserted rather than assumed.

    The non-Fallaji camp published six lists in the fortnight, three trophies
    and three challenge finishes, and the trophies main the Consign the
    challenge lists disagree about. Pooled, they would be three quarters of the
    camp on that configuration and would weigh nothing while they said so.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)

    rows = store.adoption(db)

    trophies = [row for row in rows if row["stratum"] == "league"]
    assert trophies, "the fixture has to carry the stratum for the rule to bind"
    assert not [
        row
        for row in trophies
        if any(
            row[figure] is not None
            for figure in ("fresh_weighted", "fresh_tilt", "baseline_weighted", "baseline_tilt")
        )
    ]

    # The weighted figure is the challenge stratum's own population, and the
    # camp's trophies are no part of it.
    consign = _configurations(rows, "Consign to Memory", "non-fallaji", "challenge-class")
    assert consign[(1, 3)]["fresh_population"] == 3
    assert consign[(1, 3)]["fresh_weighted"] == pytest.approx(0.7)
    assert _configurations(rows, "Consign to Memory", "non-fallaji", "league")[(1, 3)] == {
        "camp": "non-fallaji",
        "stratum": "league",
        "card": "Consign to Memory",
        "main": 1,
        "side": 3,
        "fresh_lists": 3,
        "fresh_population": 3,
        "fresh_adoption": 1.0,
        "fresh_weighted": None,
        "fresh_tilt": None,
        # No non-Fallaji trophy was published in the baseline, so the camp has
        # no league reading there to compare against and no delta to report.
        "baseline_lists": 0,
        "baseline_population": 0,
        "baseline_adoption": None,
        "baseline_weighted": None,
        "baseline_tilt": None,
        "delta": None,
    }


def test_a_camp_whose_window_scored_nothing_is_read_raw_rather_than_crashed_on(tmp_path):
    """A weighting divides by what the camp's window was worth, and a window can
    be worth nothing.

    karatedom took the only non-Fallaji seat of the 2026-07-25 qualifier and
    dropped every Swiss round, so the camp's whole challenge population that
    fortnight weighs zero. There is no performance to distribute over: the raw
    share still stands, since the list was registered and published, but a
    weighted share of a pointless window is not a figure with a meaning.

    Thin camps in a fortnight are the ordinary case here, not a contrived one.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_POINTLESS, db)

    rows = store.adoption(db)

    pointless = _configurations(rows, "Psychic Frog", "non-fallaji", "challenge-class")
    assert pointless[(4, 0)]["fresh_adoption"] == 1.0
    assert pointless[(4, 0)]["fresh_weighted"] is None
    assert pointless[(4, 0)]["fresh_tilt"] is None

    # The camp beside it scored, so it is read as usual: nothing here suppresses
    # a weighting beyond the population that has no points to weigh with.
    scoring = _configurations(rows, "Psychic Frog", "fallaji", "challenge-class")
    assert scoring[(4, 0)]["fresh_weighted"] == 1.0


def test_both_windows_are_configuration_values_and_the_baseline_stops_at_the_regime(
    tmp_path, monkeypatch
):
    """How far back the archetype is read is a decision, and it is held in one place.

    The fresh window is a length in days and the baseline is what is left of the
    regime behind it, so the pair moves with `FRESH_WINDOW_DAYS` and
    `REGIME_BOUNDARY` and with nothing else. Lengthening the fresh window pulls
    the older challenges into it; moving the boundary back is what it takes to
    reach a list from the era before it.

    The 2026-03-21 showcase is in the fixture and in no window: its three lists
    are the archetype as it was built before the B&R change, and averaging them
    into a baseline the fresh window is compared against would report the
    correction the format made as a change of the camp's mind.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)

    def population(window, camp, stratum):
        rows = _configurations(store.adoption(db), "Solitude", camp, stratum)
        return next(iter(rows.values()))[f"{window}_population"]

    # 2026-07-22 is a fortnight and a day behind the last published list, so
    # Darkchrome6538 is the baseline's and the fresh window holds the day's three.
    assert population("fresh", "non-fallaji", "challenge-class") == 3
    assert population("baseline", "non-fallaji", "challenge-class") == 4
    assert len(store.goryos_lists(db, "2026-03-21")) == 3, "the pre-regime lists are cached"

    monkeypatch.setattr(config, "FRESH_WINDOW_DAYS", 40)
    assert population("fresh", "non-fallaji", "challenge-class") == 7

    monkeypatch.undo()
    monkeypatch.setattr(config, "REGIME_BOUNDARY", "2026-01-01")
    assert population("baseline", "non-fallaji", "challenge-class") == 6


def test_the_land_count_is_a_configuration_of_the_list_as_a_whole(tmp_path):
    """The manabase is a deck-level decision, and it is read like any other.

    AldenCates registered 22 lands on 2026-08-05, counted off the published list
    by hand: four Flooded Strand, four Polluted Delta, four Marsh Flats and ten
    singleton duals, basics and creaturelands. Kollslaw matched him and
    Walker735 came in a land lighter, so the camp's fresh challenge lists split
    two to one, exactly as they do over where the fourth Consign goes.

    Read against the baseline, that is the camp having moved up: no list behind
    it ran 22. The two baseline lists counted at 20 each run a Sink into Stupor,
    which the payload types as an instant, so the split there is the front-face
    count and not two pilots disagreeing about the manabase.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_ADOPTION, db)

    rows = store.land_counts(db)

    def distribution(window, camp, stratum):
        return {
            row["lands"]: row[f"{window}_adoption"]
            for row in rows
            if (row["camp"], row["stratum"]) == (camp, stratum)
            and row[f"{window}_lists"]
        }

    assert distribution("fresh", "non-fallaji", "challenge-class") == {
        22: pytest.approx(2 / 3),
        21: pytest.approx(1 / 3),
    }
    assert distribution("fresh", "fallaji", "challenge-class") == {21: 1.0}
    assert distribution("fresh", "non-fallaji", "league") == {
        22: pytest.approx(2 / 3),
        21: pytest.approx(1 / 3),
    }
    assert distribution("baseline", "non-fallaji", "challenge-class") == {
        21: pytest.approx(1 / 2),
        20: pytest.approx(1 / 2),
    }

    # A deck-level configuration answers the same questions a card's does: the
    # 22-land build is new since the baseline, and it tilts the way the two
    # lists registering it finished.
    climbing = next(
        row
        for row in rows
        if (row["camp"], row["stratum"], row["lands"]) == ("non-fallaji", "challenge-class", 22)
    )
    assert (climbing["baseline_adoption"], climbing["delta"]) == (0.0, pytest.approx(2 / 3))
    assert climbing["fresh_tilt"] == pytest.approx(1 / 30)


def test_the_reference_list_capture_belongs_to_the_non_fallaji_camp():
    """The pilot's own 75 is read by the rule the field is read by.

    It has to be: the slot audit compares the reference list against its camp's
    consensus, so a reference list of no camp would have nothing to answer to.
    The 2026-08-07 capture plays no Fallaji Archaeologist.
    """
    mainboard, sideboard = reference.read(REFERENCE_CAPTURE)

    assert camp(mainboard) == "non-fallaji"
    assert (sum(mainboard.values()), sum(sideboard.values())) == (60, 15)


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

    def event_slugs(self, since, fmt, until, today):
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


def test_a_first_run_that_caches_nothing_still_says_what_it_could_not_reach(tmp_path):
    """The gap report is the whole value of a run that captured nothing.

    A first run against a site serving none of what it published leaves an empty
    cache, and the rebuild of an empty cache must not fail on its own account:
    that would bury the one thing the run has to say under a database error.
    """

    class WithholdingSite(CapturedSite):
        def fetch_payload(self, slug):
            raise mtgo.Unavailable(slug)

    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    with pytest.raises(mtgo.Unavailable, match="published event"):
        refresh("2026-08-01", "2026-08-31", raw_dir, db, source=WithholdingSite(), today="2026-08-31")

    assert store.goryos_lists(db) == []


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


def test_a_capture_interrupted_mid_write_is_not_left_in_the_cache(tmp_path, monkeypatch):
    """A settled event on disk is never refetched, so a payload left half
    written by a run that died would be kept forever, and every later rebuild
    would fail to parse it.

    A capture therefore lands whole or not at all. Killing the process is stood
    in for by truncating the write itself, since the cost is the same either way.
    """
    site = CapturedSite()
    raw_dir, db = tmp_path / "raw", tmp_path / "engine.duckdb"
    killed = "modern-challenge-32-2026-08-0512850696"
    whole_write = Path.write_text

    def die_partway(self, data, *args, **kwargs):
        if killed not in self.name:
            return whole_write(self, data, *args, **kwargs)
        whole_write(self, data[: len(data) // 2], *args, **kwargs)
        raise KeyboardInterrupt(self.name)

    monkeypatch.setattr(Path, "write_text", die_partway)
    with pytest.raises(KeyboardInterrupt):
        refresh("2026-08-01", "2026-08-31", raw_dir, db, source=site, today="2026-08-31")
    monkeypatch.undo()

    assert not (raw_dir / f"{killed}.json").exists()

    # Nothing on disk is a gap, so the re-run captures it and the day is whole.
    site.fetches.clear()
    refresh("2026-08-01", "2026-08-31", raw_dir, db, source=site, today="2026-08-31")
    assert killed in site.fetches
    assert {row["pilot"] for row in store.goryos_lists(db, "2026-08-05")} == GORYOS_PILOTS_2026_08_05


def _transcribe(path: Path, rows) -> Path:
    """A MTGGoldfish screenshot as the pilot transcribes it: archetype, share, decks.

    What the site shows carries no capture date and no window, which is what the
    ingest supplies, so a transcription on its own is not yet a snapshot.
    """
    lines = "".join(f"{archetype},{pct},{decks}\n" for archetype, pct, decks in rows)
    path.write_text("archetype,meta_pct,deck_count\n" + lines, encoding="utf-8")
    return path


def test_a_transcribed_snapshot_is_ingested_under_the_date_and_window_it_reads(tmp_path):
    """A meta share is a reading of a window, and unreadable without both terms.

    MTGGoldfish shows the table and not when it was taken or over how long, so the
    ingest stamps the pair on. Two shares of the same archetype only compare on
    the strength of it.
    """
    source = _transcribe(
        tmp_path / "goldfish.csv",
        [("Goryo's Vengeance", 10.0, 118), ("Boros Energy", 9.7, 115)],
    )
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"

    meta.ingest(source, "2026-08-07", 14, meta_dir)
    store.build(FIXTURE_RAW, db, meta_dir)

    assert store.meta_trend("Goryo's Vengeance", db) == [
        {
            "captured_on": "2026-08-07",
            "window_days": 14,
            "share": pytest.approx(0.100),
            "deck_count": 118,
        }
    ]


def test_the_mirror_share_helper_answers_with_the_reading_that_stood_on_a_date(tmp_path):
    """A conditional hypothesis is argued on the meta it was argued in.

    Goryo's is the field's number one deck, so the mirror is a matchup the 75
    has to price in, and how much of the field is the mirror is the join such a
    slot decision turns on. Readings are dated and sparse, so the answer for a
    date is the last one taken on or before it, and it carries its own date so
    a stale reading can be seen to be stale.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    for captured_on, pct, decks in [("2026-07-24", 7.5, 82), ("2026-08-07", 10.0, 118)]:
        source = _transcribe(tmp_path / "goldfish.csv", [("Goryo's Vengeance", pct, decks)])
        meta.ingest(source, captured_on, 14, meta_dir)
    store.build(FIXTURE_RAW, db, meta_dir)

    assert store.mirror_share("2026-08-07", db) == {
        "captured_on": "2026-08-07",
        "window_days": 14,
        "share": pytest.approx(0.100),
        "deck_count": 118,
    }

    # A date between readings gets the one that stood on it, not the later one.
    assert store.mirror_share("2026-08-01", db)["captured_on"] == "2026-07-24"

    # A date the history does not reach back to has no reading to give.
    assert store.mirror_share("2026-07-01", db) is None


def test_the_trend_reads_one_archetypes_share_across_the_whole_history(tmp_path):
    """Meta drift from today to submission day is the point of keeping history.

    A single reading says what the field is; two say which way it is going, and
    a slot bought on the mirror's density wants the second. Each archetype's
    line is its own: the field's decks rise and fall against each other, so a
    trend pooling them would be the history of nothing in particular.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    history = [
        ("2026-07-24", [("Goryo's Vengeance", 7.5, 82), ("Boros Energy", 11.2, 123)]),
        ("2026-08-07", [("Goryo's Vengeance", 10.0, 118), ("Boros Energy", 9.7, 115)]),
    ]
    for captured_on, table in history:
        meta.ingest(_transcribe(tmp_path / "goldfish.csv", table), captured_on, 14, meta_dir)
    store.build(FIXTURE_RAW, db, meta_dir)

    # Goryo's took the field's top spot off Boros Energy over the fortnight.
    assert [(r["captured_on"], r["share"]) for r in store.meta_trend("Goryo's Vengeance", db)] == [
        ("2026-07-24", pytest.approx(0.075)),
        ("2026-08-07", pytest.approx(0.100)),
    ]
    assert [(r["captured_on"], r["share"]) for r in store.meta_trend("Boros Energy", db)] == [
        ("2026-07-24", pytest.approx(0.112)),
        ("2026-08-07", pytest.approx(0.097)),
    ]


def test_ingesting_the_same_snapshot_twice_leaves_the_history_one_entry_long(tmp_path):
    """The history is a record of readings, and a reading happened once.

    A hand transcription is easy to run again, off a re-cropped screenshot or a
    corrected typo, and the second run is a correction rather than a new
    reading. So a snapshot is identified by the two terms it was read on and
    kept under them: re-ingesting rewrites that entry, and a trend built off the
    history never counts one day of the meta twice.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    capture = META_HISTORY / "2026-08-07_14d.csv"

    for _ in range(2):
        written = meta.ingest(capture, "2026-08-07", 14, meta_dir)
    store.build(FIXTURE_RAW, db, meta_dir)

    assert [path.name for path in meta_dir.iterdir()] == [written.name]
    assert len(store.meta_trend("Goryo's Vengeance", db)) == 1


def test_the_history_opens_with_the_14_day_reading_of_2026_08_07(tmp_path):
    """The first entry is the one the project starts from, and it is real.

    MTGGoldfish's 14-day table of 2026-08-07 has Goryo's at the top of the field on
    10.0% over 118 decks: the mirror is priced in, and the 75 is built knowing
    it. The whole table is kept, not the archetype's row, because what the rest
    of the field is doing is what a sideboard answers to.

    The committed entry is exactly what the ingest writes, which is what makes
    it an entry rather than a file that happens to be there.
    """
    db = tmp_path / "engine.duckdb"
    store.build(FIXTURE_RAW, db, META_HISTORY)
    capture = META_HISTORY / "2026-08-07_14d.csv"

    assert store.mirror_share("2026-08-07", db) == {
        "captured_on": "2026-08-07",
        "window_days": 14,
        "share": pytest.approx(0.100),
        "deck_count": 118,
    }
    assert len(meta.snapshot_rows(META_HISTORY)) == 28, "the field as the screenshot showed it"

    # Boros Energy, the field's other pillar, is the deck the rest is aimed at.
    assert store.meta_trend("Boros Energy", db) == [
        {
            "captured_on": "2026-08-07",
            "window_days": 14,
            "share": pytest.approx(0.097),
            "deck_count": 115,
        }
    ]

    # Byte for byte: the history is committed, so an ingest that rewrote a
    # reading it did not change would put the whole entry through the diff.
    re_ingested = meta.ingest(capture, "2026-08-07", 14, tmp_path / "meta")
    assert re_ingested.read_bytes() == capture.read_bytes()


def test_a_trend_is_read_within_one_window_and_never_across_two(tmp_path):
    """A share is a reading of a window, so two windows are two instruments.

    The 30-day table smooths what the 14-day table shows, and a line drawn
    through both would report the difference between the two as movement in the
    field. Screenshotting the page at both lengths on one day is the natural
    thing to do, so a query names the window it reads rather than taking what
    the history happens to hold.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    for window, pct, decks in [(14, 10.0, 118), (30, 8.2, 241)]:
        source = _transcribe(tmp_path / "goldfish.csv", [("Goryo's Vengeance", pct, decks)])
        meta.ingest(source, "2026-08-07", window, meta_dir)
    store.build(FIXTURE_RAW, db, meta_dir)

    fortnight = store.meta_trend("Goryo's Vengeance", db)
    assert [(r["window_days"], r["share"]) for r in fortnight] == [(14, pytest.approx(0.100))]

    month = store.meta_trend("Goryo's Vengeance", db, window_days=30)
    assert [(r["window_days"], r["share"]) for r in month] == [(30, pytest.approx(0.082))]

    # The mirror is priced off the fresh window, and never off whichever
    # reading of the day happened to be ingested last.
    assert store.mirror_share("2026-08-07", db)["window_days"] == 14


def test_a_transcription_that_carries_its_own_stamp_must_agree_with_the_one_given(tmp_path):
    """A typo in the stamp is not a correction, it is an invented reading.

    Re-ingesting a snapshot is normal, off a re-cropped screenshot or to fix a
    transcribed row, and it rewrites the entry it names. Naming the wrong date
    instead files a reading no screenshot was taken for, which the trend then
    reports as the field having moved. A snapshot already carries its terms, so
    the disagreement is caught here rather than published as drift.
    """
    meta_dir = tmp_path / "meta"
    capture = META_HISTORY / "2026-08-07_14d.csv"

    with pytest.raises(ValueError, match="2026-08-07"):
        meta.ingest(capture, "2026-08-08", 14, meta_dir)

    assert not meta_dir.exists(), "nothing is filed under a stamp the source denies"


def test_an_empty_transcription_never_overwrites_the_reading_already_filed(tmp_path):
    """A table of no archetypes is a transcription that went wrong, not a meta.

    It arrives the same way a corrected one does, off a re-cropped screenshot,
    and under the same stamp it would take the entry's place: the reading a
    screenshot was taken for would be gone, and the trend would show the field
    it recorded having never existed. The site never published an empty field.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    meta.ingest(META_HISTORY / "2026-08-07_14d.csv", "2026-08-07", 14, meta_dir)

    with pytest.raises(ValueError, match="no archetypes"):
        meta.ingest(_transcribe(tmp_path / "empty.csv", []), "2026-08-07", 14, meta_dir)

    store.build(FIXTURE_RAW, db, meta_dir)
    assert store.mirror_share("2026-08-07", db)["deck_count"] == 118


def test_a_capture_date_that_is_not_a_date_is_refused_before_anything_is_filed(tmp_path):
    """Every reading of the history is ordered on the capture date as text.

    So a date that is not zero-padded sorts by its digits and not by its day:
    2026-8-9 falls before 2026-08-10, and the mirror share as of that day comes
    back a reading the later one had already superseded, with nothing to say it
    had. The date also names the file, and a typed slash names a directory that
    does not exist, so it is parsed before either use is made of it.
    """
    source = _transcribe(tmp_path / "goldfish.csv", [("Goryo's Vengeance", 10.0, 118)])
    meta_dir = tmp_path / "meta"

    with pytest.raises(ValueError, match="2026-8-9"):
        meta.ingest(source, "2026-8-9", 14, meta_dir)

    assert not meta_dir.exists()


def test_a_file_in_the_history_that_is_not_a_snapshot_is_named_rather_than_crashed_on(tmp_path):
    """The history holds what the ingest wrote, and a transcription is not that.

    Dropping one beside the snapshots is the easy mistake, since that is where
    it is going. It carries no stamp, so it is no reading of anything yet, and
    every refresh ends by rebuilding the store: the daily loop is what stops. It
    must say which file and why, rather than fail on a column that isn't there.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    meta.ingest(META_HISTORY / "2026-08-07_14d.csv", "2026-08-07", 14, meta_dir)
    _transcribe(meta_dir / "goldfish.csv", [("Goryo's Vengeance", 10.0, 118)])

    with pytest.raises(ValueError, match="goldfish.csv"):
        store.build(FIXTURE_RAW, db, meta_dir)


def test_an_ingest_killed_part_way_leaves_the_reading_already_filed_standing(tmp_path, monkeypatch):
    """A snapshot is a raw capture in the sense a cached event is, so it lands
    whole or not at all.

    The history is committed and nothing refetches it, so an entry left half
    written stays half written. It would still parse, too: a CSV that stops
    early is a shorter table, and the trend would read the archetypes that never
    made it as a field that had shrunk. Killing the process is stood in for by
    dying after the header, the cost being the same either way.
    """
    meta_dir, db = tmp_path / "meta", tmp_path / "engine.duckdb"
    capture = META_HISTORY / "2026-08-07_14d.csv"
    meta.ingest(capture, "2026-08-07", 14, meta_dir)

    class DiesAfterTheHeader:
        def __init__(self, handle, **kwargs):
            self.handle = handle

        def writerow(self, row):
            self.handle.write(",".join(str(field) for field in row) + "\n")

        def writerows(self, rows):
            raise KeyboardInterrupt("part way through the entry")

    monkeypatch.setattr(csv, "writer", DiesAfterTheHeader)
    with pytest.raises(KeyboardInterrupt):
        meta.ingest(capture, "2026-08-07", 14, meta_dir)
    monkeypatch.undo()

    store.build(FIXTURE_RAW, db, meta_dir)
    assert store.mirror_share("2026-08-07", db)["deck_count"] == 118
