"""The pilot layer at the seam the rest of the pipeline is tested at: raw
payloads in, verdicts out.

These readings are about who registered a configuration rather than how much of
a camp did, so the fixtures are written rather than captured (see
`tests/synthetic.py`): a pet card is a pilot repeating himself over months, and
a breakthrough is one list and then the field following it, neither of which a
captured day holds on its own.
"""

from deck_engine import ledger, pilots, store
from tests import synthetic
from tests.synthetic import challenge, entry, league

CAMP = "non-fallaji"


def _built(tmp_path, series):
    db = tmp_path / "engine.duckdb"
    store.build(synthetic.write_cache(tmp_path / "raw", series), db)
    return db


# Two challenges inside the baseline window and two inside the fresh one, with a
# league dump between them. jussupinator top-16s both baseline challenges;
# Phryziel and Dubb manage one apiece; Lavaridge finishes outside the cut twice
# and trophies three times in the dump. felider top-16s twice, but in the fresh
# window, which is the period the tier is not read over.
TIER_SERIES = [
    challenge(
        "2026-06-13",
        [
            entry("jussupinator", CAMP, points=18, placement=3),
            entry("Phryziel", CAMP, points=15, placement=8),
            entry("Lavaridge", CAMP, points=12, placement=17),
            entry("St1ffler", CAMP, points=9, placement=25),
        ],
        event_id="12846001",
    ),
    challenge(
        "2026-06-20",
        [
            entry("jussupinator", CAMP, points=18, placement=4),
            entry("Dubb", CAMP, points=15, placement=12),
            entry("Lavaridge", CAMP, points=9, placement=20),
            entry("Phryziel", CAMP, points=6, placement=30),
        ],
        event_id="12846002",
    ),
    league("2026-06-24", [entry(f"Lavaridge{i}" if i else "Lavaridge", CAMP) for i in range(3)]),
    challenge(
        "2026-07-29",
        [
            entry("felider", CAMP, points=18, placement=2),
            entry("Jonii", CAMP, points=9, placement=22),
        ],
        event_id="12846003",
    ),
    challenge(
        "2026-08-03",
        [
            entry("felider", CAMP, points=18, placement=5),
            entry("Jonii", CAMP, points=9, placement=24),
        ],
        event_id="12846004",
    ),
]


def test_a_proven_pilot_is_one_the_baseline_saw_top_16_more_than_once(tmp_path):
    """The tier that tells a dissenter from an unknown, and it is a low bar.

    A challenge is a ten-hour tournament, so availability caps how often even a
    dedicated pilot enters one: a threshold that asked for many finishes would
    empty the tier of everyone who has a job. Top-16 is the cut because the
    top-8 boundary is mostly tiebreakers between identical records.

    It is read over the baseline window alone. The tier exists to say who was
    already proven when a fresh list turned up, and a pilot proven by the same
    fortnight the list is in would be proven by the news itself.

    A league trophy is not one of these finishes, however many a pilot takes:
    the dump publishes no standings, so there is no placement to make a cut at.
    """
    proven = pilots.proven_pilots(_built(tmp_path, TIER_SERIES))

    assert proven == {"jussupinator": 2}


# What the four cards below are for: a card one proven pilot keeps sleeving, a
# card one unknown keeps sleeving, a card three different pilots reached for,
# and a card its one pilot has only registered twice.
PET = "Pest Control"
UNKNOWN_PET = "Winternight Stories"
SHARED = "Force of Negation"
TWICE = "Sink into Stupor"
# And a fifth: a card the same proven pilot keeps sleeving, but only ever in
# league dumps, where there is no finish to have performed with it. And a sixth,
# which he did top-16 on, once.
LEAGUE_PET = "Orim's Chant"
ONCE_PET = "Ashiok, Dream Render"

# The same two baseline challenges that put jussupinator in the tier, with the
# four cards laid over them and two league dumps behind. Six pilots publish, so
# nothing the filler registers is concentrated enough to be anyone's pet.
PET_SERIES = [
    challenge(
        "2026-06-13",
        [
            entry("jussupinator", CAMP, {PET: (1, 0), ONCE_PET: (1, 0)}, points=18, placement=3),
            entry("Phryziel", CAMP, {SHARED: (2, 0)}, points=15, placement=8),
            entry("St1ffler", CAMP, {UNKNOWN_PET: (0, 2)}, points=9, placement=20),
        ],
        event_id="12846001",
    ),
    challenge(
        "2026-06-20",
        [
            entry("jussupinator", CAMP, {PET: (1, 0)}, points=18, placement=4),
            entry("Dubb", CAMP, {SHARED: (2, 0)}, points=15, placement=12),
            entry("St1ffler", CAMP, {UNKNOWN_PET: (0, 2)}, points=9, placement=22),
        ],
        event_id="12846002",
    ),
    league(
        "2026-07-01",
        [
            entry("jussupinator", CAMP, {PET: (1, 0), LEAGUE_PET: (2, 0)}),
            entry("St1ffler", CAMP, {UNKNOWN_PET: (0, 2)}),
            entry("Lavaridge", CAMP, {SHARED: (2, 0)}),
            entry("Jonii", CAMP, {TWICE: (3, 0)}),
            entry("Bugalugs", "hybrid"),
        ],
    ),
    league(
        "2026-07-08",
        [
            entry("Jonii", CAMP, {TWICE: (3, 0)}),
            entry("jussupinator", CAMP, {LEAGUE_PET: (2, 0), ONCE_PET: (1, 0)}),
            entry("Dubb", CAMP),
            entry("Bugalugs", "hybrid"),
        ],
    ),
    league(
        "2026-07-29",
        [
            entry("jussupinator", CAMP, {LEAGUE_PET: (2, 0), ONCE_PET: (1, 0)}),
            entry("Phryziel", CAMP),
            entry("Lavaridge", CAMP),
            entry("Bugalugs", "hybrid"),
        ],
    ),
]


def test_a_configuration_only_one_or_two_pilots_ever_register_is_pet_tech(tmp_path):
    """Concentrated adoption, which the share alone reports as agreement.

    Three appearances of a configuration are three pilots converging on it or
    one pilot repeating himself, and adoption counts lists, so it says the same
    number either way. The flag classifies rather than discounts: what it adds
    to the share is whose it is, and that cuts both ways, since the same
    concentration that inflates apparent field adoption is what makes a
    dissenter's repeated success worth a hypothesis.

    Force of Negation is three pilots reaching for the same card, which is the
    field and not a pet. Sink into Stupor is one pilot's, and he has registered
    it twice: a preference needs repeating before it is one.
    """
    raised = pilots.pet_tech(_built(tmp_path, PET_SERIES))

    assert [(flag["card"], flag["appearances"], flag["pilots"]) for flag in raised] == [
        (ONCE_PET, 3, ["jussupinator"]),
        (PET, 3, ["jussupinator"]),
        (UNKNOWN_PET, 3, ["St1ffler"]),
        (LEAGUE_PET, 3, ["jussupinator"]),
    ]
    assert [(flag["main"], flag["side"]) for flag in raised] == [(1, 0), (1, 0), (0, 2), (2, 0)]
    assert [flag["appeared_on"] for flag in raised] == ["2026-06-13"] * 3 + ["2026-07-01"]


def test_pet_tech_from_a_proven_pilot_is_a_hypothesis_candidate_and_from_an_unknown_is_noise(
    tmp_path,
):
    """A lone dissenting regular is better evidence than the herd's convergence.

    Mass adoption of a winner's 75 is largely copying, and it inflates belief in
    that 75 by exactly as much as it inflates the share. A pilot who goes the
    other way with a configuration of his own and keeps finishing with it is
    arguing against that, and he is the reason the pet-tech flag classifies
    rather than discounts.

    What decides which it is, is who the pilot is and what he did with the card.
    jussupinator top-16ed twice on Pest Control, so that pet is a claim worth
    putting to playtesting. St1ffler registered his exactly as often and
    finished nowhere, so his is one player's preference and the archetype has
    nothing to learn from it yet.

    Being proven is not on its own enough, which is what Orim's Chant is here
    for. jussupinator is the same proven pilot and sleeves it just as often, but
    only ever in league dumps, which publish no standings and so hold no finish
    he could have performed with it. A dissenter is a pilot performing well
    *with a configuration*, and league trophies are the soft evidence that
    drives novelty detection rather than the hard evidence that carries a claim.

    Nor is one finish enough, which is what Ashiok is here for. What argues
    against the herd is a pilot who keeps finishing with a card of his own, and
    a single top-16 is the same evidence a good player produces by turning up:
    he was going to finish somewhere, and the card was in the 75 when he did.
    The bar is the tier's own, since what the tier asks of a pilot is exactly
    what this asks of the card.
    """
    raised = pilots.pet_tech(_built(tmp_path, PET_SERIES))

    assert [(flag["card"], flag["hypothesis_candidate"]) for flag in raised] == [
        (ONCE_PET, False),
        (PET, True),
        (UNKNOWN_PET, False),
        (LEAGUE_PET, False),
    ]
    # What each dissenter did with the configuration, which is the claim itself:
    # the tier is only what makes his going against the herd worth reading. The
    # count stays on the row whether or not it reached the bar, because a reader
    # asking why a pet is not a candidate is asking this number.
    assert [flag["dissenters"] for flag in raised] == [
        {"jussupinator": 1},
        {"jussupinator": 2},
        {},
        {},
    ]


def test_a_hybrid_experiment_has_no_camp_for_a_configuration_to_be_concentrated_in(tmp_path):
    """The bucket that would otherwise report its own existence as a discovery.

    A pet is a share the field appears to hold that really belongs to one or two
    pilots, and it is read per camp because a configuration means one thing
    inside the camp that registered it. The hybrid bucket is not such a camp. It
    is the residue of the rule that draws the two, holding whoever falls between
    them, and it is thin by construction: almost anything registered in it is
    from one or two pilots, because one or two pilots are all it ever holds.

    Bugalugs is a whole camp on his own here, and he publishes the stock 75
    three times over. Read as a camp, every card he sleeves comes out as his pet
    on the same evidence, Fallaji Archaeologist included, which is the count
    that put him in the bucket in the first place: the flag would be reporting
    the camp rule back as his invention.

    So a list in no camp is folded into no camp's tally, which is what the
    breakthrough reading already does with the same lists and for the same
    reason. What is lost is real and small: a hybridist's genuine pet goes
    unflagged. What that costs is a flag; counting it would cost the reading.
    """
    raised = pilots.pet_tech(_built(tmp_path, PET_SERIES))

    assert [flag["camp"] for flag in raised] == [CAMP] * 4
    assert "Bugalugs" not in [pilot for flag in raised for pilot in flag["pilots"]]


# Five cards the archetype already knows: nothing here is novelty, and the
# camps disagree about them. The fallaji camp plays all five as a matter of
# course; the non-fallaji camp has a quarter of its lists on them.
POOL_CARDS = (
    "Emperor of Bones",
    "Malevolent Rumble",
    "Sheoldred, the Apocalypse",
    "Tamiyo, Inquisitive Student",
    "Wight of the Reliquary",
)
POOL = {card: (2, 0) for card in POOL_CARDS}


def _camp_lists(day, camp, placements, pooled):
    """One camp's eight lists in a challenge, those placed in `pooled` on the
    five pool cards and the rest on the camp's stock 75."""
    return [
        entry(
            f"{camp}-{day}-{place}",
            camp,
            POOL if place in pooled else None,
            points=max(3, 21 - place),
            placement=place,
        )
        for place in placements
    ]


# The two challenges that settle both camps. Every fallaji list runs the five
# pool cards, so the fallaji camp is unanimous on them; one of the sixteen
# non-fallaji lists does, which is under the bar where a slot has any of its
# camp behind it. That one finished 26th, outside the cut, so it is no
# breakthrough whatever it deviates by.
FALLAJI_PLACES = (3, 4, 7, 11, 15, 19, 23, 28)
SETTLED = [
    challenge(
        "2026-06-13",
        _camp_lists("2026-06-13", CAMP, (1, 2, 6, 9, 13, 18, 21, 26), pooled={26})
        + _camp_lists("2026-06-13", "fallaji", FALLAJI_PLACES, pooled=set(FALLAJI_PLACES)),
        event_id="12846001",
    ),
    challenge(
        "2026-06-20",
        _camp_lists("2026-06-20", CAMP, (1, 2, 6, 9, 13, 20, 24, 29), pooled=set())
        + _camp_lists("2026-06-20", "fallaji", FALLAJI_PLACES, pooled=set(FALLAJI_PLACES)),
        event_id="12846002",
    ),
]

# BREAKER takes the five pool cards into the non-fallaji shell and finishes
# third with them. DECOY registers the very same five in the fallaji shell and
# finishes fifth, having done nothing at all: they are what his camp plays.
IN_POOL_SERIES = [
    *SETTLED,
    challenge(
        "2026-07-04",
        [
            entry("BREAKER", CAMP, POOL, points=18, placement=3),
            entry("DECOY", "fallaji", POOL, points=15, placement=5),
            entry("Phryziel", CAMP, points=12, placement=9),
            entry("Dubb", CAMP, points=9, placement=14),
        ],
        event_id="12846003",
    ),
]


def test_a_list_rebuilding_five_slots_out_of_the_pool_breaks_through_its_own_camps_consensus(
    tmp_path,
):
    """A breakthrough deck deviates, performs, and sets the forward trend, and
    the deviation is measured against the camp it broke from.

    Which camp that is, is the whole reading. DECOY registers exactly what
    BREAKER does and has innovated nothing, because the fallaji camp is
    unanimous on all five: read against the wrong camp, one of these two lists
    is reported as the other. The departure is computed within a camp for that
    reason, and so is every share it is read off.

    The camp is read as it stood the day before, not as it stands now, for the
    same reason a card's fringeness is read as of the day it turned up: a list
    is a departure from what its camp had settled on when it was registered, and
    folding the list into its own denominator would let the field's answer to it
    decide whether it was a departure.

    Finishing is the other half. The one non-fallaji list that took the same
    five cards into the same shell a fortnight earlier came 26th, and a
    deviation that did not perform is not a breakthrough.
    """
    raised = pilots.breakthroughs(_built(tmp_path, IN_POOL_SERIES))

    assert [(flag["pilot"], flag["camp"], flag["mode"], flag["delta"]) for flag in raised] == [
        ("BREAKER", CAMP, "in-pool", 5)
    ]
    assert [card for card, _, _ in raised[0]["novel"]] == list(POOL_CARDS)
    assert (raised[0]["date"], raised[0]["placement"]) == ("2026-07-04", 3)


def _stock_dump(day, size=8, regulars=()):
    """A league day of the non-fallaji camp's stock 75, trophy after trophy.

    `regulars` names pilots to trophy alongside the anonymous ones, which is how
    a pilot comes to have published in the archetype before the day a reading is
    about: whether he was already around is what tells his taking a card up
    apart from his turning up at all.
    """
    return league(
        day,
        [entry(pilot, CAMP) for pilot in regulars]
        + [entry(f"{day}-trophy{i}", CAMP) for i in range(size)],
    )


# A card the archetype has never registered, against the same camp's settled
# league build. INNOVATOR is one card off that build and COPYCAT is one card off
# it too, and only one of the two cards is news.
NOVEL = "Pest Control"
FRINGE_SERIES = [
    *SETTLED,
    _stock_dump("2026-06-24"),
    _stock_dump("2026-07-01", regulars=("SOLO", "FOLLOWER1", "FOLLOWER2")),
    league(
        "2026-07-08",
        [
            entry("INNOVATOR", CAMP, {NOVEL: (1, 0)}),
            entry("COPYCAT", CAMP, {POOL_CARDS[0]: (2, 0)}),
            *[entry(f"2026-07-08-trophy{i}", CAMP) for i in range(6)],
        ],
    ),
]


def test_one_card_the_archetype_barely_plays_is_a_breakthrough_on_its_own(tmp_path):
    """Innovation-grade novelty at a delta of one, which the delta bar loses.

    Five rebuilt slots out of the pool is one kind of departure: known cards
    recombined, and it takes five of them before the list is doing something
    other than drifting through its flex slots. A card almost nobody in the
    archetype has ever registered is the other kind, and one is enough, because
    nobody arrives at it by drifting.

    COPYCAT is the control. He is exactly as far off his camp's build as
    INNOVATOR is, by one card, and the card is one a quarter of the archetype
    already plays. A delta of one is only a breakthrough when what is in it is
    novel.

    Both finished in a league, where a published list is a 5-0. That is soft
    evidence, and it is admitted here because leagues are where pilots test
    innovations first: a detector that refused them would go looking for
    breakthroughs everywhere except the stratum they start in.
    """
    raised = pilots.breakthroughs(_built(tmp_path, FRINGE_SERIES))

    assert [(flag["pilot"], flag["mode"], flag["delta"]) for flag in raised] == [
        ("INNOVATOR", "fringe", 1)
    ]
    assert raised[0]["novel"] == [[NOVEL, 1, 0]]
    assert raised[0]["camp"] == CAMP


def test_a_breakthrough_whose_fortnight_has_not_closed_is_still_being_watched(tmp_path):
    """The state a departure is in before the field has had time to answer it.

    `breakthrough` is a verdict and not a starting point: it says the fortnight
    came and went and nothing followed. A list published on the last day the
    store holds has had no fortnight, so reporting it that way would put the
    engine's verdict on a question nobody has had the chance to answer, and the
    flag would be indistinguishable from one that really did go nowhere.

    INNOVATOR trophies on the last day of this series, so what is known about
    him is that he departed and 5-0ed, and what the field made of it is not in
    yet. The hype flag draws the same line between what has been raised and what
    has matured, and for the same reason.
    """
    raised = pilots.breakthroughs(_built(tmp_path, FRINGE_SERIES))

    assert [(flag["pilot"], flag["date"], flag["state"]) for flag in raised] == [
        ("INNOVATOR", "2026-07-08", "watching")
    ]


# A card no list in the archetype has registered either, so the two lists below
# are each a departure at a delta of one card plus whatever the camps make of
# the rest of what they are.
STRAY_CARD = "Nethergoyf"

# Six cards of somebody else's deck, and the eight of the camp's own that
# INTERLOPER below drops to make room for them.
FOREIGN = {f"Foreign Card {n}": (4, 0) for n in range(6)}
ABANDONED = (
    "Ephemerate",
    "Thoughtseize",
    "Grief",
    "Unmask",
    "Fatal Push",
    "Faithful Mending",
    "Polluted Delta",
    "Marsh Flats",
)

# HYBRIDIST runs two Fallaji Archaeologist, so he is in neither camp, and runs
# the five pool cards, which is what the fallaji camp does. STRAY keeps Goryo's
# Vengeance and drops Ephemerate, so he is not in the archetype at all.
# INTERLOPER is on the watchlist for the same reason and nothing else: he keeps
# the namesake and is otherwise another deck entirely.
OUTSIDE_SERIES = [
    *SETTLED,
    challenge(
        "2026-07-04",
        [
            entry("HYBRIDIST", "hybrid", POOL | {NOVEL: (1, 0)}, points=18, placement=3),
            entry("Phryziel", CAMP, points=15, placement=6),
            entry(
                "STRAY",
                CAMP,
                {STRAY_CARD: (1, 0)},
                points=12,
                placement=9,
                dropped=("Ephemerate",),
            ),
            entry("INTERLOPER", CAMP, FOREIGN, points=6, placement=14, dropped=ABANDONED),
        ],
        event_id="12846003",
    ),
]


def test_a_hybrid_and_a_near_miss_are_read_against_the_camp_each_is_nearest_to(tmp_path):
    """The two lists that have no consensus of their own, and are the ones most
    worth reading.

    A hybrid experiment belongs to neither camp by the rule that draws them, and
    a near-miss list is not in the archetype at all. Both are exactly where a
    variant comes from, so the detector has to reach them, and neither has a
    camp to be read against.

    Each is read against every camp and keeps the smaller departure: the camp it
    is nearest to. A breakthrough has to be a departure from every settled build
    there is, so clearing the bar against the nearest camp is clearing it against
    both. Read against the far camp instead, the distance between the two camps
    would be reported as the list's own innovation, and every hybrid would look
    like a breakthrough for sitting between them.

    HYBRIDIST plays the five cards the fallaji camp plays, which is what puts him
    nearest to it: what is left of him against that camp is his Fallaji count and
    his novel card. STRAY is a non-fallaji build missing Ephemerate, so the
    non-fallaji camp is the nearer one and what is left is the card he dropped
    and the card he added.
    """
    raised = pilots.breakthroughs(_built(tmp_path, OUTSIDE_SERIES))

    assert [(flag["pilot"], flag["camp"], flag["mode"], flag["delta"]) for flag in raised] == [
        ("HYBRIDIST", "fallaji", "fringe", 1),
        ("STRAY", CAMP, "fringe", 2),
    ]
    # STRAY's delta is one card each way, so both are on the row: the camp counts
    # the staple he dropped as much as the card he added, and a departure listed
    # in one direction alone would not add up to the number beside it.
    hybridist, stray = raised
    assert ([card for card, _, _ in hybridist["novel"]], hybridist["missing"]) == ([NOVEL], [])
    assert ([card for card, _, _ in stray["novel"]], stray["missing"]) == (
        [STRAY_CARD],
        ["Ephemerate"],
    )


def test_a_watchlist_list_too_far_from_every_camp_is_another_deck_and_not_a_variant(tmp_path):
    """Where reading a list against a camp it never joined stops being a reading.

    Being read against the nearest camp is an assumption, and the assumption is
    that the list is a build of that camp. A list in a camp needs no such
    assumption: the rule that draws the camps put it there, so however far from
    its camp it is built, the distance is its own innovation and there is no
    ceiling on it.

    INTERLOPER is where the assumption fails. He mainboards the namesake, which
    is the whole of why the watchlist holds him, and is otherwise somebody
    else's deck: eight of the camp's core cards gone and six cards of his own in
    their place. Measured against the camp, that is a fourteen-card departure,
    and reported as one it would say a rival deck had innovated inside an
    archetype it is not in. STRAY, three lines above, is the case worth keeping:
    the same watchlist, one card either way, a variant of the camp arguing with
    it.
    """
    raised = pilots.breakthroughs(_built(tmp_path, OUTSIDE_SERIES))

    assert "INTERLOPER" not in [flag["pilot"] for flag in raised]


# INNOVATOR's card, taken up by two pilots who are not him, a week and a
# fortnight after he trophied with it.
FOLLOWED_SERIES = [
    *FRINGE_SERIES,
    league("2026-07-15", [entry("FOLLOWER1", CAMP, {NOVEL: (1, 0)}), entry("Dubb", CAMP)]),
    league("2026-07-22", [entry("FOLLOWER2", CAMP, {NOVEL: (1, 0)}), entry("Jonii", CAMP)]),
]


def test_a_breakthrough_the_field_took_up_graduates_to_trendsetter(tmp_path):
    """A breakthrough deck deviates and performs; a trendsetter is also copied.

    The third of those is the one the list cannot supply on its own, and it is
    what tells an innovation apart from an oddity that happened to 5-0. Only the
    fortnight after can say it, which is why graduation is a state the flag
    arrives at rather than a bar it clears when raised.

    Two other pilots, because that is what takes the configuration past the bar
    where it would still read as one pilot's pet: three pilots on a card is the
    field, and two is a preference and someone who noticed.

    The followers are counted on the configuration and not on the list, since
    what spreads is the idea rather than the 75 around it: a pilot copying the
    card into his own build has followed through, and one copying the whole list
    is the herd behaviour the engine flags separately.

    The two of them raise no flag of their own, which is the same fact read from
    the other end. INNOVATOR's camp had never registered the card, and by the
    time FOLLOWER1 sleeves it the camp has: he is the field answering a
    departure and not a pilot making one. One list introduces a card and the
    rest take it up, so the flag on the origin is the whole story, and copies of
    it standing beside it as breakthroughs of their own would report one idea as
    three.
    """
    raised = pilots.breakthroughs(_built(tmp_path, FOLLOWED_SERIES))

    assert [(flag["pilot"], flag["date"], flag["state"]) for flag in raised] == [
        ("INNOVATOR", "2026-07-08", "trendsetter"),
    ]
    graduated = raised[0]
    assert graduated["followers"] == ["FOLLOWER1", "FOLLOWER2"]
    assert graduated["adopted_card"] == NOVEL


# The same card, and the three ways a second follower fails to arrive:
# INNOVATOR sleeving it again himself the week after, NEWCOMER publishing in the
# archetype for the first time in his life, and LATE arriving three weeks later,
# a week past the fortnight the field had to answer in.
UNFOLLOWED_SERIES = [
    *FRINGE_SERIES,
    league(
        "2026-07-15",
        [
            entry("INNOVATOR", CAMP, {NOVEL: (1, 0)}),
            entry("SOLO", CAMP, {NOVEL: (1, 0)}),
            entry("NEWCOMER", CAMP, {NOVEL: (1, 0)}),
            entry("Dubb", CAMP),
        ],
    ),
    league("2026-07-29", [entry("LATE", CAMP, {NOVEL: (1, 0)}), entry("Jonii", CAMP)]),
]


def test_a_breakthrough_nobody_followed_does_not_graduate(tmp_path):
    """The three things that look like the field following and are not.

    A pilot registering his own card again is where the idea already was, so
    counting him would let anyone graduate himself by sleeving the same 75 twice
    more. And a pilot arriving three weeks later is not follow-through: the
    fortnight is how long the field takes to answer a finish, and past it the
    card has arrived by some other route than that one list.

    NEWCOMER is the third, and he is the one who looks most like a follower. He
    has never published in the archetype at all, so there is no sense in which
    this card is the thing he changed his mind about: he did not take the card
    up, he turned up. Most of the pilots a league dump ever publishes appear
    once, so counting the first-timers would make this state a reading of how
    many new names the fortnight brought rather than of what the field did with
    an idea, and a breakthrough would graduate on the strength of the game's
    turnover.

    Take all three away and one pilot picked the card up, which is a preference
    and somebody who noticed. The flag stays what it was raised as, which is the
    reading: a deviation that performed and that nothing has yet come of.

    None of them raises a flag of his own, LATE included. The camp had the card
    by the time any of them sleeved it, so none of them was standing outside it.
    They are still pilots who took the card up, which is why each is available
    to be counted as a follower and has to be ruled out on who he is or on the
    window instead.
    """
    raised = pilots.breakthroughs(_built(tmp_path, UNFOLLOWED_SERIES))

    assert [(flag["pilot"], flag["date"], flag["state"]) for flag in raised] == [
        ("INNOVATOR", "2026-07-08", "breakthrough"),
    ]
    assert raised[0]["followers"] == ["SOLO"]


# The graduating series with a card only Petter ever sleeves laid over the three
# weeks after it, so one run of the engine holds a flag of either new kind.
PETTED = "Sink into Stupor"
LEDGER_SERIES = [
    *FOLLOWED_SERIES,
    league("2026-07-29", [entry("Petter", CAMP, {PETTED: (1, 0)}), entry("St1ffler", CAMP)]),
    league("2026-08-05", [entry("Petter", CAMP, {PETTED: (1, 0)}), entry("Phryziel", CAMP)]),
    league("2026-08-12", [entry("Petter", CAMP, {PETTED: (1, 0)}), entry("Lavaridge", CAMP)]),
]


def test_the_ledger_remembers_the_pilot_flags_beside_the_time_series_ones(tmp_path):
    """One memory, whatever raised what is in it.

    The store is rebuilt from the raw cache every run and carries none, and when
    the engine first said a pilot had broken through is no more in that cache
    than when it first said a configuration was spiking. Both are the engine's
    own record of what it has told the pilot, so both are kept in the one place.

    A second run over the same store neither duplicates a flag nor re-dates one.
    A breakthrough is identified by the list that made it, and a pet by the
    configuration it is a pet of, so a run that reads the same cache reads the
    same flags and moves nothing.
    """
    db = _built(tmp_path, LEDGER_SERIES)

    recorded = ledger.record(db, today="2026-08-13")

    assert [(flag["card"], flag["pilots"]) for flag in recorded if flag["kind"] == "pet-tech"] == [
        (PETTED, ["Petter"])
    ]
    graduated = [flag for flag in recorded if flag["kind"] == "breakthrough"]
    assert ("INNOVATOR", "trendsetter") in [(flag["pilot"], flag["state"]) for flag in graduated]
    assert {flag["first_seen"] for flag in recorded} == {"2026-08-13"}

    assert ledger.record(db, today="2026-09-01") == recorded
    assert ledger.load(db) == recorded
