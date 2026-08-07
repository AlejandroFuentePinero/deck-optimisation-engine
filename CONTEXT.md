# Deck Optimisation Hypothesis

A system that mines published MTGO decklist data to back up, or challenge, experience-based deckbuilding decisions for a specific archetype ahead of a competitive paper tournament.

## Language

### Data source

**MTGO**:
Magic: The Gathering Online. The sole source of decklist-level data for this project.

**MTGGoldfish**:
The aggregator supplying archetype-level meta share. Never a source of decklist-level data.

**League**:
A continuous MTGO event. Only undefeated (5-0) lists are published, as trophy reports.

**Challenge**:
A scheduled MTGO tournament, often with hundreds of players. Only the top 32 lists are published.

**Event class**:
The kind of event a list was published under, kept exactly as the site publishes it: `league`, `challenge-32`, `challenge-64`, `challenge-96`, `showcase-challenge`, `showcase-qualifier`, `rc-qualifier`, `rc-super-qualifier`, `last-chance`.

**Challenge-class**:
Every event class except league: Swiss rounds, then publication of the top 32 with placement and Swiss points. The stratum that carries performance evidence.
_Avoid_: tournament (the payload's own word, which does not distinguish the strata)

**Swiss points**:
A pilot's points from the Swiss rounds of a challenge-class event, 3 per win, as published in the standings. Excludes the playoff entirely, so a winner may hold fewer Swiss points than someone who finished below them. See ADR 0001.

**Decklist**:
A single published list: mainboard plus sideboard, with pilot, date, and event attached.

**Pilot**:
The player who registered a decklist.

### Deck concepts

**Archetype**:
A family of decks recognised by its signature cards. The target archetype here is Goryo's.

**Signature card**:
A card whose presence in a list identifies its archetype.

**Goryo's**:
The Modern archetype being optimised: an Esper (WUB) list whose mainboard contains Goryo's Vengeance, Atraxa, Grand Unifier, and Psychic Frog, all three required. Green sources for casting Atraxa do not change membership.
_Avoid_: Reanimator (broader family), Grixis Reanimator (a different archetype)

**Configuration**:
For a card in a list, the pair (mainboard copies, sideboard copies). The unit at which adoption is tracked: a main↔side migration is a configuration change even when total copies are constant. Deck-level counts (e.g. lands) are configurations of the list as a whole.

**Card pool**:
The set of all distinct cards observed in the archetype's lists within the analysis history (roughly 100-120 cards for Goryo's).

**Fringe card**:
A card at under ~10% adoption across the archetype's analysis history, including cards returning to the pool after falling out. Playing one is innovation-grade novelty at a delta of one.
_Avoid_: out-of-pool (never-seen is just the extreme case)

**Variant**:
A recognised camp within the archetype, defined by a divergence card. Currently: Fallaji camp (3-4 copies) vs non-Fallaji camp (0 copies); 1-2 copies is a hybrid experiment belonging to neither consensus. Consensus builds and novelty are computed per variant, never across camps.

**Core / flex slot**:
Core is the near-universal part of the camp's 75 (default: configurations at 90%+ within-camp adoption); flex slots are the rest, where optimisation happens. Confidence is assessed per flex slot.

**Near-miss list**:
A list with mainboard Goryo's Vengeance that fails full membership. Surfaced as potential variant innovation, excluded from archetype metrics.

### Optimisation concepts

**Hypothesis**:
A falsifiable claim about deck configuration (e.g. "card X belongs in the main over card Y"), tracked across pipeline runs. Evidence may be data-derived or pilot-supplied (playtesting, judgment); both are first-class. Hypotheses also direct where playtesting energy goes.

**Reference list**:
The user's own 75 being optimised. The final output of the project is the reference list as submitted to the tournament.

**Heuristic**:
A piece of MTG expertise supplied by the user (gained from play, not derivable from data) that informs how the data is interpreted. Captured persistently so the co-intelligence improves across sessions.

### Analytical concepts

**Fresh window**:
The recent period whose lists represent the current state of the archetype and meta.

**Baseline window**:
The longer comparison period that deltas are computed against. Bounded by meta regime changes, since older lists lose relevance.

**Regime change**:
A Modern B&R change or meta-warping set release that resets the relevance of prior lists. Lists on either side of a regime boundary belong to different eras and are not directly comparable.

**Meta share**:
The fraction of published winning lists an archetype occupies over a time window. A proxy for true field share, since only the winning portion of the field is visible.

**Meta snapshot**:
One dated reading of MTGGoldfish's archetype table, transcribed by hand and kept whole. Identified by the pair (capture date, window length), which the site serves neither of and the ingest stamps on: a share read over 30 days is a different measurement from one read over 14, so a trend is read within one window and never across two. Re-ingesting a pair corrects that entry rather than adding one, and a transcription whose own stamp disagrees is refused, since a mistyped date would file a reading no screenshot was taken for. The history is committed because, unlike an event, a screenshot cannot be fetched again.

**Mirror share**:
Goryo's own meta share: how much of the field the archetype plays against itself. The join a conditional hypothesis needs, since a slot bought on mirror density is only earned while that density stands. Read as of a date, which is answered by the last snapshot taken on or before it, stale readings included and marked as such.

**Performance tilt**:
For a configuration, its points-weighted adoption minus its raw adoption within challenge lists. Positive: overrepresented among high-point finishes. Negative on a rising configuration: the herd is adopting an underperformer. Swiss points only, so no league list enters it.

**Conversion gap**:
For a camp, its share of league-trophy pilots minus its share of challenge-class pilots, over a regime-bounded window, counting each pilot once per camp. A league dump publishes trophies without their denominator: a camp's 5-0 count is its entries times its conversion, and only the product is served, so the challenge-class stratum stands in for the entries. The two strata truncate at different bars, so a camp short of 5-0s and long on challenge finishes is flatter, not worse. Hypothesis-grade evidence about outcome distribution: it routes to playtesting, never to a slot decision. Reported only beside its controls, since one grinder's trophies or a straddled regime boundary would otherwise produce it on their own. The cap either holds the gap, collapses it (leaving under half of the uncapped figure standing) or flips its sign, and the reading says which. It is applied to the reading and not to the cache, which stays as published (see ADR 0001).
_Avoid_: performance tilt (a different figure, over the challenge stratum alone, that the conversion gap never feeds)

**Top-32 truncation**:
The visibility bias: challenges publish only the top 32, leagues only 5-0s. Losing lists never appear, so all analysis is conditioned on success.

**Hype spike**:
A surge in adoption of a card combination after a visible finish. Subsequent results reflect adoption density, not card quality. Self-correcting over time, and must not be read as optimisation.

**Breakthrough deck**:
A list that deviates from the archetype norm, performs well, and sets the forward trend.

**Pilot affinity**:
A pilot's persistent preference for pet cards. Concentrated adoption is signal in both directions: it inflates apparent field adoption, but a dissenter's repeated success with it is hypothesis-grade innovation.

**Dissenter**:
A pilot repeatedly performing well with a configuration that departs from the herd's current consensus. The opposite failure mode of herd adoption.

**Herd adoption**:
Many pilots converging on a recent winner's exact list. Looks like consensus; is largely copying, and inflates belief in that configuration's optimality.
