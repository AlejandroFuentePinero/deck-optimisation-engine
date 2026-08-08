"""Named configuration values. v2 repoints the engine by editing these."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = REPO_ROOT / "data" / "raw"
DB_PATH = REPO_ROOT / "data" / "engine.duckdb"

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
CARD_ALIASES = {"Superior Spider-Man": "Kavaero, Mind-Bitten"}

# How far back the analysis history reaches: two regimes' worth of events.
HISTORY_START = "2026-02-01"

# The regime boundary the history spans (see ADR 0001). Lists either side of it
# belong to different eras, so every window is bounded by it.
REGIME_BOUNDARY = "2026-05-18"

# The fresh window: how far back a published list still speaks for the archetype
# as it stands. The baseline is what is left of the regime behind it, which is
# why only this length is named. Nothing to do with META_WINDOW_DAYS, which is
# the window MTGGoldfish took a reading over.
FRESH_WINDOW_DAYS = 14

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
# have set the trend rather than merely been one. Two, which puts three pilots
# on the card and past the bar at which it would still read as one pilot's pet.
# A fortnight, which is how long the field takes to answer a finish.
TRENDSETTER_FOLLOWERS = 2
TRENDSETTER_WINDOW_DAYS = 14

# Watchlist rule: a non-member mainboarding this one is a near-miss, and what it
# dropped is the rest of the trio.
WATCHLIST_CARD = "Goryo's Vengeance"

# The pilot's own 75, kept as `v1-...txt`, `v2-...txt` and so on: captures are
# appended and never edited, so the change log is derived from them.
REFERENCE_DIR = REPO_ROOT / "reference"

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
