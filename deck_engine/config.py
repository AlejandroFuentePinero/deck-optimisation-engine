"""Named configuration values. v2 repoints the engine by editing these."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = REPO_ROOT / "data" / "raw"
DB_PATH = REPO_ROOT / "data" / "engine.duckdb"

# The pilot's own client logs, copied out of the MTGO install: one binary
# Match_GameLog file per match played on this machine. Personal data with
# opponent logins in it, so the directory stays out of the repository.
GAMELOG_DIR = REPO_ROOT / "data" / "gamelogs"
MATCHES_PATH = REPO_ROOT / "data" / "matches.jsonl"
PILOT_LOGIN = "alejandrofp"

# The meta history: one dated MTGGoldfish snapshot per file. Transcribed from a
# screenshot by hand and committed, because unlike an event it cannot be
# fetched again.
META_DIR = REPO_ROOT / "data" / "meta"

# The window a meta reading is taken over, and the fresh window's own length.
# A share read over 30 days is a different measurement from one read over 14,
# so every meta query names the window it wants rather than pooling them.
META_WINDOW_DAYS = 14

FORMAT = "modern"

# Printings the site publishes as separate cards that are one card. Superior
# Spider-Man is Kavaero, Mind-Bitten with the Marvel IP on it; a list is
# published under whichever printing its pilot registered, and a pilot may
# register both. The Magic name is the canonical one, being what most of the
# history is already published under.
# Elesh Norn is the same card again: the site publishes the March of the
# Machine legend under its full name almost everywhere and under the bare one
# twice, and the pilot confirmed they are one card. Left unmerged it reads as a
# card the archetype had never played, which is exactly the finding a returning-
# card reading exists to make and exactly the wrong one.
CARD_ALIASES = {
    "Superior Spider-Man": "Kavaero, Mind-Bitten",
    "Elesh Norn": "Elesh Norn, Mother of Machines",
}

# Decks MTGGoldfish tables as separate archetypes that are one deck. Its Eldrazi
# row is the Gruul build, and Gruul Basking Broodscale Combo is the same seventy-
# five under a second name: the pilot checked the cards. The site's split reports
# one deck at two shares, so anything the field's density is read for, mirror
# volume aside, is understating it by whichever half went unread.
#
# Neither of the site's names is the canonical one here, which is where this
# parts company with the printings above. Eldrazi names a creature suite three
# other rows also field, so the merged deck under that name reads as the family
# rather than as the build, and the pilot calls the deck Broodscale after the
# card the combo is. Mono-Green Eldrazi, Eldrazi Tron and Eldrazi Ramp are those
# other shells and stay their own rows.
META_ARCHETYPE_ALIASES = {
    "Eldrazi": "Broodscale",
    "Gruul Basking Broodscale Combo": "Broodscale",
}

# How far back the analysis history reaches: two regimes' worth of events.
HISTORY_START = "2026-02-01"

# The regime boundary the history spans (see ADR 0001). Lists either side of it
# belong to different eras, so every window is bounded by it.
REGIME_BOUNDARY = "2026-05-18"

# The fresh window: how far back a published list still speaks for the archetype
# as it stands. Nothing to do with META_WINDOW_DAYS, which is the window
# MTGGoldfish took a reading over.
FRESH_WINDOW_DAYS = 14

# The baseline window: how far back the comparison reaches behind the fresh one.
# Fixed rather than running to the regime boundary, so a delta means the same
# thing on every run. Left open, the baseline lengthens by a day per day and a
# configuration that has not moved reports a shrinking delta as its denominator
# grows; two runs a fortnight apart would then disagree about a slot nothing
# happened to. It is also a comparison against the camp rather than against the
# format: a card adopted mid-regime is diluted across the weeks before it
# existed, so a long baseline reports a settled configuration as still climbing.
# The regime boundary still bounds it, since a window may never cross one.
BASELINE_WINDOW_DAYS = 28

# How long an event's publication can still change. A league dump gains 5-0s
# through its own day, and the site publishes on US time while we run on
# Australian time, so the last few days are refetched rather than trusted.
UNSETTLED_DAYS = 3

# Membership rule: every signature card, in the mainboard.
ARCHETYPE = "goryos"
# The same deck under MTGGoldfish's name for it, which is how the meta layer
# knows it: the mirror share is this archetype's own row in the field's table.
META_ARCHETYPE = "Goryo's Vengeance"
# Ephemerate is in the rule because the other three are as at home in a Grixis
# reanimator deck as in this one. It is the blink half of the Esper shell, and
# the line the two versions of the deck fall either side of.
SIGNATURE_CARDS = (
    "Goryo's Vengeance",
    "Atraxa, Grand Unifier",
    "Psychic Frog",
    "Ephemerate",
)

# Variant rule: the camps a member belongs to, by mainboard copies of the card
# the archetype forks on. No list in the history sideboards it, so the mainboard
# count is the whole commitment. A count between the camps is a hybrid
# experiment: it belongs to neither consensus.
DIVERGENCE_CARD = "Fallaji Archaeologist"
CAMPS = {"fallaji": (3, 4), "non-fallaji": (0,)}
HYBRID_CAMP = "hybrid"

# Tracked decks: archetypes the engine classifies and reports on but never
# optimises. Goryo's above is the optimised one and every reading in this
# project answers to it; these have no reference list, no hypotheses and no slot
# audit, only the weekly report. The optimised rule is tested first and these in
# turn, so a list takes the first name that claims it and is never two decks.
TRACKED_DECKS = {
    "blink": {
        # The four together are the deck. Phelia alone is not enough: a white
        # energy build and a Boros build both play her, and the Ephemerate pool
        # on its own is half Goryo's.
        "signature": (
            "Phelia, Exuberant Shepherd",
            "Flickerwisp",
            "Overlord of the Balemurk",
            "Witch Enchanter",
        ),
        # The deck is Esper or Orzhov and nothing else. A Mardu build shares all
        # four signature cards and is a different deck, so a mainboard source
        # that actually produces red or green puts a list outside the archetype.
        # Fetchlands are not colour evidence here: most of the Orzhov half
        # fetches with Flooded Strand, which produces neither.
        "off_colour": (
            "Sacred Foundry",
            "Blood Crypt",
            "Raucous Theater",
            "Elegant Parlor",
            "Mountain",
            "Snow-Covered Mountain",
            "Arena of Glory",
            "Overgrown Tomb",
            "Temple Garden",
            "Lush Portico",
        ),
        # Variant rule: the blue half against the two-colour half. Mainboard
        # Watery Grave partitions the archetype exactly, with no list between
        # the two, where a rule drawn on blue sources throws away the Orzhov
        # lists that fetch and a rule drawn on blue spells drops any Esper list
        # that cut Teferi. Presence and not a count: a variant here is which
        # colours the deck is, which one copy settles.
        "variant_card": "Watery Grave",
        "variant_with": "esper",
        "variant_without": "orzhov",
        # The cards the deck argues about the number of, and the only ones a
        # count change earns a timeline row for. Named rather than found by a
        # scan, so the timeline reads the same slots every fortnight and a card
        # arriving is a decision somebody made. All three sit at
        # near-total adoption, which is why no adoption reading sees them: the
        # whole of the disagreement is how many, and it has moved about a copy
        # since mid-June while every other slot held.
        "copy_drift": ("Flickerwisp", "Emperor of Bones", "Witch Enchanter"),
    }
}

# Tracking rule: what counts as a change worth a timeline row, read over a
# fortnight rather than a week. A week of this deck runs from nine lists to
# sixty-four, a seven-fold swing, so a threshold set as a share is measuring the
# sample size and not the deckbuilding: across every bar from five points to
# twenty-five, a weekly reading reverses in the next bin about two times in
# five, and no threshold escapes it. Over a fortnight the same bars reverse
# between fifteen and twenty-two percent of the time and fall as the bar rises,
# which is what a threshold is supposed to do. The plots stay weekly; only the
# detection is binned.
TRACK_BIN_DAYS = 14

# And the bar itself, in both units. The share is what makes a move large; the
# list count is what makes it evidence. The count does the real work, being a
# fifty-six percent swing in the thinnest fortnight and eight percent in the
# fattest, which is the right behaviour when the denominator moves that far: it
# holds the evidence constant rather than the effect size.
TRACK_ADOPTION_DELTA = 0.20
TRACK_MIN_LISTS = 5

# How far a card's mean copy count has to move to be the camp changing its mind
# rather than the week's lists differing. Read on the mean and never the mode:
# the modal count of the cards that actually move oscillates every other week
# and every oscillation reverses, because the mode is held by a plurality one
# pilot can flip.
TRACK_COPY_DELTA = 0.4

# Returning-card gates, per zone. A sideboard churns about seven times harder
# than a mainboard, so one gate cannot serve both: two thirds of the sideboard
# names this deck has ever registered appear in two weeks or fewer, and they
# carry four percent of the volume. Both sit on RETURN_ABSENCE_DAYS above, which
# a fortnight is too short for: a staple running at three to six lists a week
# misses two thin weeks on chance alone and reads as a return.
TRACK_RETURN_MAIN_LISTS = 2
TRACK_RETURN_SIDE_LISTS = 3

# A return also has to be bigger than the card has ever been, which is what
# separates a card the field has turned to from a card that was always a
# one-off and is a one-off again. Without it the gates admit both and the
# timeline cannot tell the reader which it is looking at.
TRACK_RETURN_BEATS_PEAK = True

# Spike rule: how far this week's volume has to clear the post-regime median
# before the summary says so. A deck at several times its own baseline is being
# copied, and every performance figure taken over the spike measures adoption
# density rather than the deck. The report has to say that in the week it
# happens, not in the retrospective.
TRACK_SPIKE_MULTIPLE = 2.0

# The dated events a plot marks and the timeline names, one per line as
# `date,label`. Committed and hand-maintained: what counts as a major event is
# the pilot's call, and no feed serves it.
EVENTS_PATH = REPO_ROOT / "data" / "events.csv"

# The paper Spotlights, by their melee tournament id. One-off events rather than
# a feed, so they are named here rather than discovered: a Spotlight enters the
# analysis because the pilot says it matters, the same way `events.csv` works.
# The date is the local day the event started, which is the day `events.csv`
# marks it on and the day its week is taken from; melee publishes a UTC start,
# and Brisbane's is the evening before.
SPOTLIGHTS = (
    {"id": 441441, "label": "Spotlight Brisbane", "date": "2026-08-29"},
    {"id": 405590, "label": "Spotlight Dallas", "date": "2026-09-05"},
)

# One JSON per Spotlight, fetched once and kept. The melee equivalent of RAW_DIR
# and separate from it, because a paper event and an MTGO event are not the same
# population and nothing downstream may pool them by accident.
MELEE_DIR = REPO_ROOT / "data" / "raw-melee"

# What the weekly report is built from and cannot rebuild: the frozen weekly
# figures, the frozen timeline rows, and the summary written over them. Committed
# for the reason the ingest index is, one directory per tracked deck. The
# rendered page itself is derived and stays out, like every other report.
TRACKING_DIR = REPO_ROOT / "data" / "tracking"

# Conversion gap rule: how much of the uncapped figure counting each pilot once
# has to leave standing before the gap is the camp's rather than a grinder's.
CAP_COLLAPSE = 0.5

# Hype rule: the spike a flag is raised on, read as a fortnight's adoption
# against the fortnight before it. Nothing to do with FRESH_WINDOW_DAYS, which
# is how far back a list still speaks for the archetype; this is how long the
# domain says a hype spike takes to happen in.
HYPE_WINDOW_DAYS = 14
HYPE_FLOOR = 0.10
HYPE_CEILING = 0.30

# The smallest population a spike may be read off. A camp publishes single
# figures of lists in a thin fortnight, where one pilot changing his mind clears
# any threshold, and a flag raised on that is noise wearing a verdict's clothes.
HYPE_MIN_LISTS = 8

# The finish behind a spike has to be one the field would have seen: top-16 is
# the performance cut, since the top-8 boundary is mostly tiebreakers.
HYPE_ORIGIN_PLACEMENT = 16

# Fringe rule: how little of the archetype's history a card can hold and still
# be innovation-grade novelty when it appears, and how long a card has to have
# been out of the pool for its reappearance to be a return rather than a gap.
FRINGE_ADOPTION = 0.10
RETURN_ABSENCE_DAYS = 28

# Pet tech rule: a configuration registered this many times over the post-regime
# history, by this few distinct pilots, is one pilot's preference rather than
# the field's. Enough appearances that it is a habit and not a one-off, few
# enough pilots that the share it holds is really theirs.
PET_TECH_APPEARANCES = 3
PET_TECH_PILOTS = 2

# Proven pilot rule: how many challenge-class top-16 finishes over the baseline
# window put a pilot in the tier whose dissent is worth a hypothesis. A
# challenge is a ten-hour tournament and availability caps how often anyone
# enters one, so the count stays modest. Top-16 because the top-8 boundary is
# mostly tiebreakers between identical records.
PROVEN_PILOT_FINISHES = 2
PROVEN_PILOT_PLACEMENT = 16

# Breakthrough rule: how many cards outside its camp a list has to be built on
# to be a departure rather than flex-slot drift, and how well it has to have
# finished for that departure to have performed. Top-16 as everywhere, since the
# top-8 boundary is mostly tiebreakers. A card the archetype barely plays is a
# departure at a delta of one and answers to neither figure. What counts as one
# card outside the camp is drawn once, at the bars the slot audit is read at:
# SUPPORTED_MINORITY below, for a card hardly any of the camp plays, and
# CORE_ADOPTION for one it is near-unanimous on that the list runs none of.
BREAKTHROUGH_DELTA = 5
BREAKTHROUGH_PLACEMENT = 16

# And how far outside a camp a list that was never in it may be read, above
# which it is another deck rather than a variant of that camp. Only a list the
# camp rule left out answers to this: a list in a camp is a build of it by the
# rule that put it there, however far from the consensus it is built, but a
# hybrid or a near-miss is only read against a camp on the assumption that it is
# one of that camp's, and this is where the assumption fails. A dozen cards is a
# sixth of a 75, which is past any argument about flex slots and into a list
# that shares a namesake with the archetype and not a deck.
BREAKTHROUGH_CEILING = 12

# The smallest population a camp may be read against, for the reason the hype
# floor exists: a camp a handful of lists deep has settled on nothing, and a
# share of six lists moves by a sixth when one pilot changes his mind.
BREAKTHROUGH_MIN_LISTS = 8

# Trendsetter rule: how many pilots the card was new to have to take up one of a
# breakthrough's own, and how long they have to do it in, for the departure to
# have set the trend rather than merely been one. Two is the floor, which puts
# three pilots on the card and past the bar at which it would still read as one
# pilot's pet. A fortnight, which is how long the field takes to answer a finish.
#
# The floor alone measures the format's throughput rather than the idea's spread:
# a league dump publishes tens of lists a day, so two pilots reaching for a
# playable card inside a fortnight is close to certain. So the bar is also a
# share of the pilots who published at all in that window, and the higher of the
# two has to be cleared. A twentieth of the field is a real move; two names out
# of a hundred is the turnover.
TRENDSETTER_FOLLOWERS = 2
TRENDSETTER_SHARE = 0.05
TRENDSETTER_WINDOW_DAYS = 14

# Board migration rule: the smallest population either window may hold before a
# card's copies crossing the boards is read as the camp moving it. A card three
# lists deep moves its whole share when one pilot sideboards it, and a scan over
# every card the camp registered is exactly where that arrives wearing a
# finding's clothes rather than as a figure somebody went looking for. Both
# windows, since the shift is the difference between two shares and either one
# taken off a handful of lists carries the whole reading.
MIGRATION_MIN_LISTS = 8

# Watchlist rule: a non-member mainboarding this one is a near-miss, and what it
# dropped is the rest of the trio.
WATCHLIST_CARD = "Goryo's Vengeance"

# The pilot's own 75, kept as `v1-...txt`, `v2-...txt` and so on: captures are
# appended and never edited, so the change log is derived from them.
REFERENCE_DIR = REPO_ROOT / "reference"

# The rendered runs, one file per day. Derived from the cache, the captures and
# the records, and so rebuildable: kept out of the repository like the store.
REPORT_DIR = REPO_ROOT / "reports"

# The tracked hypotheses, one record per file. Written by the pilot and appended
# to by the engine, so they are committed beside the 75 they argue about.
HYPOTHESES_DIR = REPO_ROOT / "hypotheses"

# The day the 75 is handed in: Spotlight Brisbane, paper. It is what makes an
# open hypothesis urgent rather than merely unfinished, so every unresolved
# record is read against it.
SUBMISSION_DATE = "2026-08-27"

# Core/flex rule: how much of its own camp has to have registered a
# configuration for that slot of the reference list to be core rather than one
# of the flex slots where the optimisation happens. Overridable per slot, on
# the capture itself, since a pilot still arguing with a unanimous camp is the
# case the threshold cannot see.
CORE_ADOPTION = 0.90

# Slot audit rule: where the camp stands on a flex slot. A majority of the camp
# is its consensus. Below that, a share the size of the fringe bar is still a
# minority with support behind it, and anything under that is the pilot's own
# deviation, examined or not.
CONSENSUS_ADOPTION = 0.50
SUPPORTED_MINORITY = 0.10

# Unplayed rule: how much of his own camp has to play a card the reference list
# registers none of before it is worth the pilot's attention, and how many such
# cards a reading serves. The slot audit reads the slots he took and the missing
# core reading starts at near-unanimity, so everything between the two is a
# decision a real part of the camp made that nothing surfaces. A quarter of the
# camp is the bar: below it the reading fills up with the pool, and at the core
# bar it would miss a card a third of them play. The cap is on how much of the
# tail is worth reading rather than on what qualifies, and what it dropped is
# reported rather than left silent.
UNPLAYED_FLOOR = 0.25
UNPLAYED_LIMIT = 10

# Boundary rule: how close to the bar a slot's share has to sit before the audit
# says the verdict turns on one or two pilots. Read in lists rather than in
# share, since that is what a reader can check: a camp of forty puts the core bar
# at thirty-six, and a slot at thirty-five is one registration from being filed
# the other way.
BOUNDARY_LISTS = 2

# Tilt rule: how large a performance tilt has to be before it is worth printing.
# Every published list already finished, so the Swiss points a camp's fortnight
# spreads over are bunched: across the configurations this archetype registers,
# the median tilt is under half a point and the largest is four. A column of
# figures that small reads as a performance lens and is noise, so below this the
# reading prints as nothing rather than as a number a reader would weigh. The
# figure stays on the row; what is suppressed is the display of it.
TILT_FLOOR = 0.05
