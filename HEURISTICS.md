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

**One deck per pilot in a challenge; a league day can trophy the same pilot
twice** (2026-08-08):
A challenge-class event is one entry per player, so a pilot appears in its
standings once and his list is his whole showing. A league is continuous: a
pilot can run it repeatedly in a day and publish a 5-0 each time, so a league
dump can carry several lists from one name, and they may not be the same 75.
*Applies*: in the challenge stratum (event, pilot) identifies a list, so counting
lists is counting pilots and no de-duplication is owed. In the league stratum it
does not, so anything counting lists there is counting a grinder's session: keep
the per-pilot cap on league readings, and read a league share as lists published
rather than pilots holding a configuration. It is also why the ingest index
diffs as a multiset: two identical league rows are two lists, not one filed
twice.

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

**Ephemerate is part of what makes the deck Esper** (2026-08-07):
The trio alone (Goryo's Vengeance, Atraxa, Psychic Frog) admits Grixis
reanimator builds, which are a different deck with a different manabase, a
different gameplan and no bearing on this 75. Ephemerate is the blink half of
the Esper shell and the line the two versions fall either side of.
*Applies*: Ephemerate joins the mainboard signature cards, so membership is the
four and not the three. Grixis lists leave the archetype's population entirely;
those that keep Goryo's Vengeance land on the near-miss watchlist, which is
where a different construction direction belongs.

## Data interpretation

**Kavaero, Mind-Bitten and Superior Spider-Man are one card** (2026-08-07):
Superior Spider-Man is the Marvel printing of Kavaero; mechanically they are
the same card, and the IP is the whole of the difference. MTGO publishes each
list under whichever printing the pilot registered, and a pilot may register
both.
*Applies*: the two names merge at ingestion and their copies are summed, before
anything counts a configuration. Eight lists in the history register both, and
without the merge each reads as two separate one-ofs rather than the two-of it
is, splitting one card's adoption history down the middle.

**MTGGoldfish's Eldrazi and Gruul Basking Broodscale rows are one deck**
(2026-08-14):
The site's Eldrazi row is the Gruul build, and Gruul Basking Broodscale Combo is
the same 75 tabled a second time; Alejandro checked the cards. The site's own
split reports one deck at two shares, so the field's second-largest deck reads
as two mid-sized ones. Mono-Green Eldrazi, Eldrazi Tron and Eldrazi Ramp are
different shells that share a creature suite and stay their own rows.
*Applies*: the two names merge into one archetype, `Broodscale`, on the way out
of the transcriptions and across the whole snapshot history, so every reading
already taken is corrected too. Neither of the site's names survives the merge,
since a deck left at both would be counted twice by anything summing the field.
The committed transcriptions stay exactly what the screenshots showed. The
merged share sums two figures the site rounded to a tenth each, so it can sit a
tenth off; the deck counts are exact.

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

**A card can spread challenge-first, and league-only hype detection is blind to
it** (raised 2026-08-19, surfaced 0×):
Hype is read in the league stratum on the premise that copying shows there
first and hardest. Clarion Conqueror did the opposite in the camp that matters
to this 75: it saturated the challenge stratum while the league share stayed
under the bar, so the reading that exists to catch a copied configuration never
saw the largest one this regime has produced.
*Evidence*: non-fallaji challenge-class adoption of Clarion Conqueror 0/2 went
1/80 (1%) in the baseline window to 20/40 (50%) fresh, delta +0.49, the largest
single-configuration move in the post-regime history. In the same camp's league
stratum the fortnight ending 2026-08-16 reads 24% off 25 lists, against 0% in
every fortnight before it: under `HYPE_CEILING` of 30%, so no hype flag was
raised in non-fallaji at all. The fallaji camp cleared the bar on 8 league lists,
exactly `HYPE_MIN_LISTS`, 0% to 37.5%, flag raised 2026-08-16 off eswaff #1
Modern Challenge 64 2026-08-13. The consequence lands on lineage, which joins a
departure to a hype episode on the same card in the same camp: Rvng's 2026-08-11
Clarion departure in fallaji reads "Clarion Conqueror spiked 2026-08-16, raised,
now holding", while Ivan_Draw_Go's and DskBayWolf's same-day, same-card
departures in non-fallaji both read "the field never piled in", each on a
trendsetter flag counting 17 new pilots. The camp at 50% reports the non-event;
the camp at 65% off a thinner base reports the episode.
*Applies if adopted*: a spike is read in whichever stratum the configuration
moved in, not in the league stratum by rule, and lineage joins a departure to an
episode in either. Until then a challenge-first climb has to be caught by hand
off the adoption delta, and a lineage row saying the field never piled in is not
evidence that it did not.
