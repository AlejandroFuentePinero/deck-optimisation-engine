# MTG Heuristics

Pilot-supplied knowledge from long-term play, not derivable from the data.
Each entry: the heuristic, why it holds, and how it changes the analysis.
Source is Alejandro unless noted. Dates are when captured.

## Tournament structure

**Challenge participation is expensive** (2026-08-07):
A challenge is a ~10-hour tournament; availability caps how often even
dedicated pilots play. Frequency thresholds must stay modest.
*Applies*: proven pilot = 2+ challenge top-16 Goryo's finishes in the baseline
window, not more.

**A lone dissenting regular beats herd convergence as evidence** (2026-08-07):
Mass adoption of a winner's 75 inflates belief in it (goldfish copying). A
single pilot who goes against the hype with a different configuration and does
well repeatedly is stronger grounds for a hypothesis than the herd's converged
numbers.
*Applies*: pet-tech flags classify rather than discount; dissenter patterns
auto-raise hypothesis candidates.

**Top-8 is mostly tiebreakers; top-16 is the real cut** (2026-08-07):
In MTGO challenges the top-8/9-16 boundary usually separates identical 4-2
records on breakers, not performance. Top-16 vs 17-32 is the meaningful
performance stratum.
*Applies*: normalized Swiss points are the primary performance lens; when a
placement band is needed, cut at top-16 / 17-32, never top-8 / rest.

## Card evaluation

**Cards are only evaluable in deck context** (2026-08-07):
In general, a card's value depends on the whole deck structure, so raw
single-card adoption stats mislead. They are acceptable for Goryo's right now
only because the shell is heavily optimised and just a few flex slots move.
*Applies*: single-card adoption tables are valid for this archetype this
season; re-examine before reusing the pipeline on another archetype. Card-pair
co-occurrence is tracked as a cheap partial guard.

## Archetype knowledge

**Goryo's forks on Fallaji Archaeologist** (2026-08-07):
Current Goryo's builds split into a Fallaji Archaeologist camp (3-4 copies)
and a non-Fallaji camp (0 copies). These are divergent construction
directions, not flex-slot drift; the non-Fallaji build is the more stable of
the two. Lists on 1-2 copies are hybrid experiments, innovation probing in
both directions, and belong to neither consensus.
*Applies*: consensus builds, novelty deltas, and slot comparisons are computed
within-camp; hybrids are flagged as innovation, excluded from camp consensus.
The camp ratio over time is a tracked signal.

## Data interpretation

**Hype corrects in about a week, and the weekend is the judge** (2026-08-07):
One week of play is usually enough for reality to hit misconfigured or
suboptimal hyped lists, but the heaviest tournament density is on weekends, so
the correction generally requires a weekend to land.
*Applies*: time bins align to the tournament week; a hype flag cannot resolve
until at least one post-spike weekend of challenge data exists; late spikes
(after the final pre-tournament weekend) are decided by pilot judgment alone.

**League 5-0s are soft evidence** (2026-08-07):
Leagues are casual; many opponents pilot weak decks, so 5-0 is attainable with
suboptimal builds ("free wins"). Leagues still matter: they reflect the
competitive field's assumptions and are where players (often the same ones who
play challenges) test innovations first.
*Applies*: league-derived stats are never blended with challenge stats;
leagues drive novelty detection, challenges drive performance evidence.

## Proposed, awaiting pilot verdict

Heuristic candidates, held here until Alejandro rules on them. Nothing in this
section is adopted knowledge and nothing here may steer an analysis. Each entry
cites the evidence that raised it and counts the sessions it has been put to
him in. See `.claude/skills/mtg-heuristics/SKILL.md`.

_(none open)_
