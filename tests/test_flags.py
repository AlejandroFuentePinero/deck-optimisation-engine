"""The flag layer at the same seam the rest of the pipeline is tested at: raw
payloads in, verdicts out.

A flag is a verdict about a time series, so these fixtures are written rather
than captured (see `tests/synthetic.py`). Everything else holds: the payloads
are shaped as the site's are, nothing asserts on an intermediate table, and the
verdicts are the externally meaningful ones: which configuration was flagged,
what finish it followed, and what the lifecycle did to it.
"""

import pytest

from deck_engine import flags, ledger, store
from tests import synthetic
from tests.synthetic import challenge, entry, league

# The configuration the synthetic series is about, and the camp that adopts it.
HYPED = "Kavaero, Mind-Bitten"
CAMP = "non-fallaji"


def _dump(day, taken, card=HYPED, configuration=(1, 0), size=6):
    """A league day: `size` trophies, the first `taken` of them running `card`."""
    return league(
        day,
        [
            entry(f"{day}-trophy{i}", CAMP, {card: configuration} if i < taken else None)
            for i in range(size)
        ],
    )


# The prior fortnight and the spike fortnight either side of 2026-06-28, a
# Sunday and so the end of a tournament week. One trophy of twelve mains the
# card before, eight of twelve after: 8% to 67% inside two weeks.
SPIKE_SERIES = [
    _dump("2026-06-03", 0),
    _dump("2026-06-10", 1),
    _dump("2026-06-17", 4),
    _dump("2026-06-28", 4),
    # The visible finish the copying followed: jussupinator third on the
    # Saturday. Lavaridge registered the same configuration and finished 17th,
    # outside the cut that separates performance from tiebreakers.
    challenge(
        "2026-06-13",
        [
            entry("jussupinator", CAMP, {HYPED: (1, 0)}, points=18, placement=3),
            entry("Lavaridge", CAMP, {HYPED: (1, 0)}, points=12, placement=17),
            entry("Phryziel", CAMP, points=15, placement=8),
            entry("St1ffler", CAMP, points=9, placement=25),
        ],
        event_id="12846001",
    ),
]


# The same spike with the challenge stratum reading either side of it. The
# Saturday inside the spike fortnight is what the configuration's presence and
# tilt are later compared against; the Saturday after it is the weekend the
# domain calls the week's verdict.
SPIKE_WEEKEND = challenge(
    "2026-06-20",
    [
        entry("felider", CAMP, {HYPED: (1, 0)}, points=18, placement=4),
        entry("Jonii", CAMP, {HYPED: (1, 0)}, points=12, placement=12),
        entry("oosunq", CAMP, points=15, placement=8),
        entry("Dubb", CAMP, points=9, placement=20),
    ],
    event_id="12846002",
)


def _resolution_series(after: list[dict]) -> list[dict]:
    """The spike, its challenge reading, and whatever the fortnight after it did."""
    return [*SPIKE_SERIES, SPIKE_WEEKEND, *after]


def _flag(db):
    """The one episode a resolution series holds."""
    (raised,) = flags.hype(db)
    return raised


def _built(tmp_path, series):
    db = tmp_path / "engine.duckdb"
    store.build(synthetic.write_cache(tmp_path / "raw", series), db)
    return db


def test_a_configuration_spiking_behind_a_visible_finish_is_raised_as_hype(tmp_path):
    """Hype is adoption density, not card quality, and it is caught at the spike.

    The reading is the league stratum's, which is where novelty and copying show
    first and where a camp publishes enough lists a fortnight to read a share
    off. The finish behind it is a challenge finish, since that is what is
    visible to copy from: it is recorded on the flag, because a spike with no
    finish behind it is drift rather than hype.

    Lavaridge registered the same configuration and finished 17th, which is the
    17-32 band and no evidence of anything. The finish that gets recorded is the
    one the field would have seen.
    """
    db = tmp_path / "engine.duckdb"
    store.build(synthetic.write_cache(tmp_path / "raw", SPIKE_SERIES), db)

    raised = flags.hype(db)

    assert raised == [
        {
            "kind": "hype",
            "camp": CAMP,
            "card": HYPED,
            "main": 1,
            "side": 0,
            "raised_on": "2026-06-28",
            "from_adoption": pytest.approx(1 / 12),
            "to_adoption": pytest.approx(2 / 3),
            "population": 12,
            "origin_pilot": "jussupinator",
            "origin_event": "Modern Challenge 64",
            "origin_date": "2026-06-13",
            "origin_placement": 3,
            "tilt": None,
            "state": "raised",
            "league_after": None,
            "challenge_before": None,
            "challenge_after": None,
            "tilt_after": None,
            "resolved_on": None,
            # Where the configuration stands as the run reads it, which is beside
            # the episode's own verdict and never instead of it. The spike is the
            # freshest thing this series holds, so it is still up.
            "now_adoption": pytest.approx(2 / 3),
            "standing": "holding",
        }
    ]


def test_an_episode_the_camp_has_since_abandoned_reads_as_lapsed(tmp_path):
    """A hype state is a verdict on a fortnight, and the fortnight does not come back.

    The episode happened and the reading of it stands: this configuration was
    copied and it held through the weekend that judges a copied list. What the
    camp is doing now is a different question, and one the frozen verdict cannot
    answer. Left alone the ledger would carry `established` on a configuration
    the camp went on to abandon entirely, which is the engine asserting something
    the data has since reversed.

    So the standing is read fresh on every run, in the stratum the spike was read
    in, and kept beside the state rather than overwriting it. A reader gets both:
    what the field decided then, and whether it still holds.
    """
    # The camp keeps publishing a month on, and none of it registers the card.
    abandoned = [
        league(f"2026-08-{day:02d}", [entry(f"drifter{seat}", CAMP) for seat in range(12)])
        for day in (1, 2, 3)
    ]
    db = _built(tmp_path, _resolution_series([*HELD_UP, *abandoned]))

    raised = _flag(db)

    assert raised["state"] == "established", "the episode held through its own weekend"
    assert raised["now_adoption"] == 0, "and the camp has since stopped registering it"
    assert raised["standing"] == "lapsed"


def _weekend_challenge(taken, event_id, points):
    """The weekend that judges the spike: eight of the camp's lists, the first
    `taken` of them still registering the configuration, on `points` apiece."""
    return challenge(
        "2026-07-04",
        [
            entry(
                f"finisher{i}",
                CAMP,
                {HYPED: (1, 0)} if i < taken else None,
                points=score,
                placement=2 + i * 3,
            )
            for i, score in enumerate(points)
        ],
        event_id=event_id,
    )


# The fortnight after the spike, with the copied configuration surviving it: the
# camp keeps trophying with it, and half its weekend challenge lists still
# register it. Those four are worth 18 + 18 + 15 + 12 of the event's best 18, so
# 7/2 of the camp's 35/6: a weighted 3/5 against a raw 1/2, tilting +1/10.
HELD_UP = [
    _dump("2026-07-01", 4),
    _weekend_challenge(4, "12846500", [18, 18, 15, 12, 15, 12, 9, 6]),
    _dump("2026-07-08", 4),
]


def test_a_flag_the_challenge_stratum_bore_out_resolves_as_established(tmp_path):
    """The spike survived the weekend that judges it, so it was not hype.

    Resolution is read in the challenge stratum, because that is the one that
    publishes standings: the question a hype flag asks is whether the copied
    configuration performs, and a league dump cannot answer it. Half the camp's
    challenge lists still register the configuration a fortnight on, and they
    finished slightly ahead of the camp while doing it.
    """
    raised = _flag(_built(tmp_path, _resolution_series(HELD_UP)))

    assert (raised["state"], raised["resolved_on"]) == ("established", "2026-07-08")
    assert raised["challenge_before"] == pytest.approx(1 / 2)
    assert raised["challenge_after"] == pytest.approx(1 / 2)
    assert raised["tilt_after"] == pytest.approx(1 / 10)
    # The league stratum held too, which is what tells this apart from a decay.
    assert raised["league_after"] == pytest.approx(2 / 3)


def test_one_episode_is_one_flag_however_many_windows_can_see_it(tmp_path):
    """A fortnight window slides, so a single spike sits inside several of them.

    Two week ends reading the same climb are two views of one episode, not two
    episodes, and raising both would put the same configuration on the watchlist
    twice with two different dates for when the field moved. The flag is dated
    at the first window that saw it.
    """
    raised = flags.hype(_built(tmp_path, [*SPIKE_SERIES, _dump("2026-06-30", 4)]))

    assert [(flag["card"], flag["raised_on"]) for flag in raised] == [(HYPED, "2026-06-28")]


# A climb that is not yet visible from the Sunday behind it: one of twelve in
# the fortnight ending 2026-06-28, and then the camp arrives on it. The week ends
# that follow are midweek days, which is what the runs below land on.
LATE_CLIMB = [
    _dump("2026-06-03", 0),
    _dump("2026-06-10", 0),
    _dump("2026-06-17", 0),
    _dump("2026-06-24", 1),
    _dump("2026-06-30", 6),
    SPIKE_SERIES[-1],
]


def test_an_episode_is_dated_on_the_week_that_has_been_played(tmp_path):
    """A run midweek reads a week in progress, and a week in progress is not one.

    The day a window ends on is the day the episode is dated at, and that date is
    what tells one episode from the same configuration spiking again months
    later. So a window ending wherever the cache happens to stop would give one
    climb a new date every day the field publishes, and the ledger, which keeps
    what it has raised, would fill up with the same episode over and over.

    The bin is the tournament week for the reason the weekend is the judge: it is
    the unit the field's play is distributed over. Until the Sunday lands there is
    no week to have an opinion about.
    """
    raw, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    def episodes(ledger):
        return [(f["card"], f["raised_on"]) for f in ledger if f["kind"] == "hype"]

    store.build(synthetic.write_cache(raw, LATE_CLIMB), db)
    assert episodes(ledger.record(db, today="2026-06-30")) == [], "the week is still being played"

    store.build(synthetic.write_cache(raw, [_dump("2026-07-01", 0)]), db)
    assert episodes(ledger.record(db, today="2026-07-01")) == []

    store.build(synthetic.write_cache(raw, [_dump("2026-07-05", 6)]), db)

    assert episodes(ledger.record(db, today="2026-07-05")) == [(HYPED, "2026-07-05")]


def test_a_flag_cannot_resolve_before_a_weekend_of_challenge_data_has_landed(tmp_path):
    """One week of play corrects a hyped list, and the weekend is the judge.

    Tournament density is concentrated on the weekend, so the midweek challenges
    after a spike are too thin a field for the correction to have landed in. A
    flag that resolved on them would call an episode a fortnight before the data
    that decides it exists.
    """
    midweek = challenge(
        "2026-06-30",
        [
            entry("Kaiser_ITA", CAMP, {HYPED: (1, 0)}, points=18, placement=3),
            entry("SrDurum", CAMP, points=12, placement=14),
        ],
        event_id="12846600",
    )

    raised = _flag(_built(tmp_path, _resolution_series([midweek])))

    assert raised["state"] == "raised"
    assert (raised["challenge_after"], raised["resolved_on"]) == (None, None)


def test_the_weekend_that_matures_a_flag_has_to_be_one_the_resolution_reads(tmp_path):
    """Otherwise the flag is resolved by a weekend it never looked at.

    The fortnight after the spike is the window the verdict is taken over, so a
    weekend past the end of it is a weekend outside the evidence. Counting it as
    the arrival of the field's verdict lets the episode be called on the midweek
    challenges alone, which is the exact reading the maturity rule exists to
    refuse.
    """
    stranded = _resolution_series(
        [
            _eight("2026-06-30", 1, "12846900", [18, 15, 15, 12, 12, 9, 9, 6]),
            _eight("2026-07-25", 1, "12846901", [18, 15, 15, 12, 12, 9, 9, 6]),
        ]
    )

    raised = _flag(_built(tmp_path, stranded))

    assert raised["state"] == "raised", "the weekend that judges it has not landed"
    assert (raised["challenge_after"], raised["resolved_on"]) == (None, None)


# The same fortnight, with the copied configuration coming apart in it: the
# league dumps keep registering it while the weekend's challenge drops it to one
# list of eight, and that one scored 6 of the event's best 18. It holds 1/3 of
# the camp's 35/6, a weighted 2/35 against a raw 1/8, tilting -19/280.
DECAYED = [
    _dump("2026-07-01", 4),
    _weekend_challenge(1, "12846501", [6, 18, 18, 15, 15, 12, 12, 9]),
    _dump("2026-07-08", 4),
]


def test_the_decay_signature_resolves_a_flag_as_decayed(tmp_path):
    """League adoption holding while challenge presence and tilt fall away.

    That shape is the whole reason the two strata are never blended. The herd is
    still registering the configuration where 5-0s are easy to come by, and it
    has stopped finishing with it where standings are published: soft evidence
    holding up while hard evidence collapses. Pooled, the two would average into
    a configuration that merely slipped a little.
    """
    raised = _flag(_built(tmp_path, _resolution_series(DECAYED)))

    assert raised["state"] == "decayed"
    # The league stratum holds exactly where it spiked to.
    assert (raised["to_adoption"], raised["league_after"]) == (pytest.approx(2 / 3),) * 2
    # The challenge stratum does not, and what is left of it is finishing badly.
    assert raised["challenge_before"] == pytest.approx(1 / 2)
    assert raised["challenge_after"] == pytest.approx(1 / 8)
    assert raised["tilt"] == pytest.approx(1 / 18)
    assert raised["tilt_after"] == pytest.approx(-19 / 280)


def _eight(day, taken, event_id, points):
    """A challenge of eight lists from the camp, the first `taken` on the card."""
    return challenge(
        day,
        [
            entry(f"{day}-{i}", CAMP, {HYPED: (1, 0)} if i < taken else None,
                  points=score, placement=2 + i * 3)
            for i, score in enumerate(points)
        ],
        event_id=event_id,
    )


# A climb the challenge stratum picked up rather than dropped: one of eight
# registering it while the leagues spiked, two of eight a fortnight later. It
# never reaches the share the leagues did, and it never fell either.
GREW = [
    _eight("2026-06-20", 1, "12846800", [18, 15, 15, 12, 12, 9, 9, 6]),
    _dump("2026-07-01", 4),
    _eight("2026-07-04", 2, "12846801", [18, 15, 15, 12, 12, 9, 9, 6]),
    _dump("2026-07-08", 4),
]


def test_a_configuration_the_challenges_kept_is_not_decayed_for_missing_a_league_bar(
    tmp_path,
):
    """Decay is a fall, and a fall is measured against where the thing stood.

    The bar a spike is raised on is a league bar: it is calibrated on how hard
    copying shows in the stratum that publishes 5-0s. Holding a challenge share
    to that same absolute figure compares one stratum's number against another's
    threshold, which is the blend the whole module is built to avoid, and it
    reports a configuration the challenges were picking up as one they dropped.

    So the fall is read within the challenge stratum, against what that stratum
    said while the herd was adopting. The league bar still stands as the other
    way to be established: a configuration that reaches it has arrived whatever
    it climbed from.
    """
    raised = _flag(_built(tmp_path, [*SPIKE_SERIES, *GREW]))

    assert raised["challenge_before"] == pytest.approx(1 / 8)
    assert raised["challenge_after"] == pytest.approx(1 / 4)
    assert raised["state"] == "established", "it grew; a bar it never met is not a decay"


def test_a_rising_configuration_carries_what_the_challenges_said_while_it_climbed(
    tmp_path,
):
    """How the herd's new configuration was finishing while it was being copied.

    Performance tilt is what the challenge stratum says about a configuration
    the moment it is climbing: points-weighted adoption under raw adoption means
    the lists registering it finished behind the camp's that did not. Read at the
    raise, it is on the record a fortnight before the flag may resolve.

    It is a figure and never a verdict. Nothing branches on its sign, because a
    tilt is a difference between two shares of one thin fortnight and the sign
    of a small one says less than it looks like it does.
    """
    sinking = challenge(
        "2026-06-20",
        [
            entry("felider", CAMP, {HYPED: (1, 0)}, points=6, placement=26),
            entry("Jonii", CAMP, {HYPED: (1, 0)}, points=9, placement=22),
            entry("oosunq", CAMP, points=18, placement=2),
            entry("Dubb", CAMP, points=15, placement=6),
        ],
        event_id="12846003",
    )

    raised = _flag(_built(tmp_path, [*SPIKE_SERIES, sinking]))

    assert raised["state"] == "raised", "the verdict is still a fortnight away"
    assert raised["tilt"] == pytest.approx(-3 / 16)


# Two cards the archetype's history reads differently. One is barely in it at
# all; the other was a staple of the camp, fell out of the pool for seven weeks,
# and is back.
NOVEL = "Pest Control"
RETURNED = "Force of Negation"


# Ten weeks of trophies, sixty lists. Force of Negation is in twelve of the
# first eighteen, then in none until the last day; Pest Control turns up once,
# in the fortnight that is still fresh.
FRINGE_SERIES = [
    _dump("2026-06-03", 4, RETURNED),
    _dump("2026-06-10", 4, RETURNED),
    _dump("2026-06-17", 4, RETURNED),
    *[_dump(day, 0) for day in ("2026-06-24", "2026-07-01", "2026-07-08", "2026-07-15")],
    _dump("2026-07-22", 0),
    _dump("2026-07-29", 1, NOVEL, configuration=(0, 1)),
    _dump("2026-08-05", 1, RETURNED),
]


def test_a_card_the_archetype_barely_plays_is_flagged_when_it_appears(tmp_path):
    """Innovation-grade novelty at a delta of one, which aggregates lose.

    A card under a tenth of the archetype's history is a card almost nobody
    plays, so one pilot registering it is a deliberate choice rather than a
    share moving. The flag carries the appearance that raised it, because what
    is worth looking at is the list, not the percentage.

    A card returning to the pool after falling out of it is fringe on the same
    grounds, whatever its history says: Force of Negation was in two thirds of
    the camp's trophies and then in none for seven weeks, so a pilot sleeving it
    again is news the historical share alone would file as a staple.
    """
    raised = flags.fringe(_built(tmp_path, FRINGE_SERIES))

    assert [(flag["card"], flag["returning"]) for flag in raised] == [
        (NOVEL, False),
        (RETURNED, True),
    ]

    novel, returned = raised
    assert (novel["main"], novel["side"]) == (0, 1)
    assert novel["appeared_on"] == "2026-07-29"
    assert novel["historical_adoption"] == 0.0, "forty-eight lists, none of them on it"
    assert (novel["pilot"], novel["event"]) == ("2026-07-29-trophy0", "Modern League")
    assert novel["absent_days"] is None

    assert returned["appeared_on"] == "2026-08-05"
    assert returned["historical_adoption"] == pytest.approx(12 / 54)
    assert returned["absent_days"] == 49


# A card the archetype had never played, taken up by most of the camp the moment
# it arrived: ten of the last twelve trophies, and none of the forty-eight before.
BREAKOUT = "Winternight Stories"
BREAKOUT_SERIES = [
    *[
        _dump(day, 0)
        for day in (
            "2026-06-03", "2026-06-10", "2026-06-17", "2026-06-24",
            "2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22",
        )
    ],
    _dump("2026-07-29", 5, BREAKOUT),
    _dump("2026-08-05", 5, BREAKOUT),
]


def test_a_cards_history_is_read_as_of_the_day_it_turned_up(tmp_path):
    """Otherwise the news counts itself, and the hottest card is the one lost.

    Fringeness asks how much of the archetype's life a card has been part of,
    which is a question about the days before it appeared. Measured over the
    whole history instead, a card the camp piles onto the week it arrives carries
    its own adoption into its own denominator: the harder it breaks out, the more
    of the history it holds, and past a tenth of it the flag never fires. The one
    card everybody is suddenly playing is exactly the one worth looking at.
    """
    raised = flags.fringe(_built(tmp_path, BREAKOUT_SERIES))

    assert [flag["card"] for flag in raised] == [BREAKOUT]
    assert raised[0]["appeared_on"] == "2026-07-29"
    assert raised[0]["historical_adoption"] == 0.0, "the archetype had never played it"


def test_a_flag_keeps_the_day_it_was_raised_while_its_state_moves_on(tmp_path):
    """The lifecycle is a record, so a run advances a flag rather than replacing it.

    The store is rebuilt from the cache every run and carries no memory, but
    when the engine first said a configuration was spiking is not in the cache
    to rebuild from. So the ledger sits beside the store: the run that raised a
    flag and the day the field moved both survive the fortnight it takes for the
    weekend to judge it.
    """
    raw, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    store.build(synthetic.write_cache(raw, _resolution_series([])), db)
    raised = ledger.record(db, today="2026-06-29")
    assert [(flag["state"], flag["first_seen"]) for flag in raised] == [("raised", "2026-06-29")]

    store.build(synthetic.write_cache(raw, HELD_UP), db)
    resolved = ledger.record(db, today="2026-07-09")

    assert [(flag["state"], flag["first_seen"]) for flag in resolved] == [
        ("established", "2026-06-29")
    ]
    assert resolved[0]["raised_on"] == "2026-06-28"
    assert ledger.load(db) == resolved


def _fringe_cards(recorded: list[dict]) -> set:
    """The cards the ledger's fringe flags name, whatever else is filed beside them."""
    return {flag["card"] for flag in recorded if flag["kind"] == "fringe"}


def test_a_flag_stays_in_the_ledger_after_the_appearance_that_raised_it_scrolls_out(tmp_path):
    """A fringe flag fires on an appearance, and an appearance is a moment.

    Two weeks on, the list that carried the card has left the fresh window and
    there is nothing left to detect. The card was still played, and a pilot
    still chose it: dropping the flag when the window moved past would make the
    engine's memory exactly as long as its fresh window.
    """
    raw, db = tmp_path / "raw", tmp_path / "engine.duckdb"

    store.build(synthetic.write_cache(raw, FRINGE_SERIES), db)
    appeared = _fringe_cards(ledger.record(db, today="2026-08-06"))
    assert appeared == {NOVEL, RETURNED}

    quiet = [_dump("2026-08-12", 0), _dump("2026-08-19", 0)]
    store.build(synthetic.write_cache(raw, quiet), db)

    assert flags.fringe(db) == [], "the appearances are behind the fresh window now"
    kept = ledger.record(db, today="2026-08-20")
    assert _fringe_cards(kept) == {NOVEL, RETURNED}
    assert {flag["first_seen"] for flag in kept if flag["kind"] == "fringe"} == {"2026-08-06"}


def test_a_verdict_is_not_read_off_a_challenge_window_too_thin_to_carry_one(tmp_path):
    """The population guard belongs on the verdict most of all.

    A camp publishes single figures of challenge lists in a thin fortnight, and
    there one pilot deciding differently swings the share past any bar. The raise
    is already held to a floor for that reason; the resolution is the reading
    that goes on the record as what happened to the configuration, so it is held
    to the same one. Below it the flag has matured and is waiting on evidence,
    which is not the same as evidence that the configuration failed.
    """
    thin = challenge(
        "2026-07-04",
        [
            entry("MarcoBelacca95", CAMP, {HYPED: (1, 0)}, points=18, placement=2),
            entry("PDeS", CAMP, points=12, placement=14),
        ],
        event_id="12846502",
    )

    raised = _flag(_built(tmp_path, _resolution_series([_dump("2026-07-01", 4), thin])))

    assert raised["state"] == "matured", "the weekend landed; the evidence did not"
    assert raised["challenge_after"] is None
