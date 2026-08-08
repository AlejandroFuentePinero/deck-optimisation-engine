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

**Printing**:
One of the names the site publishes a single card under. Superior Spider-Man is the Marvel printing of Kavaero, Mind-Bitten, mechanically the same card, and a list is published under whichever its pilot registered. Printings merge to one card at ingestion and their copies are summed, before anything counts a configuration: a pilot registering both is playing a two-of, not two one-ofs.

**Goryo's**:
The Modern archetype being optimised: an Esper (WUB) list whose mainboard contains Goryo's Vengeance, Atraxa, Grand Unifier, Psychic Frog and Ephemerate, all four required. Ephemerate is in the rule because the other three are as at home in a Grixis reanimator deck as in this one: it is the blink half of the Esper shell, and the line the two versions fall either side of. Green sources for casting Atraxa do not change membership.
_Avoid_: Reanimator (broader family), Grixis Reanimator (a different archetype, and what the rule without Ephemerate lets in)

**Configuration**:
For a card in a list, the pair (mainboard copies, sideboard copies). The unit at which adoption is tracked: a main↔side migration is a configuration change even when total copies are constant. Deck-level counts (e.g. lands) are configurations of the list as a whole.

**Card pool**:
The set of all distinct cards observed in the archetype's lists within the analysis history (roughly 100-120 cards for Goryo's).

**Fringe card**:
A card at under ~10% adoption across the archetype's analysis history, including cards returning to the pool after falling out. Playing one is innovation-grade novelty at a delta of one. The share is read as of the day the card turns up, over the history behind it: counting the appearance itself would let a card the camp piles onto the week it arrives price itself out of being fringe, losing the one card everybody has suddenly started playing.
_Avoid_: out-of-pool (never-seen is just the extreme case)

**Variant**:
A recognised camp within the archetype, defined by a divergence card. Currently: Fallaji camp (3-4 copies) vs non-Fallaji camp (0 copies); 1-2 copies is a hybrid experiment belonging to neither consensus. Consensus builds and novelty are computed per variant, never across camps.

**Core / flex slot**:
Core is the near-universal part of the camp's 75 (default: configurations at 90%+ within-camp adoption, overridable per slot by a slot annotation); flex slots are the rest, where optimisation happens. Confidence is assessed per flex slot. Read of the reference list, core is a slot the pilot took and is with his camp on; read of the camp alone, it is a configuration the camp is near-unanimous on whether or not the reference list has it, which is what a missing core slot is missing.

**Near-miss list**:
A list with mainboard Goryo's Vengeance that fails full membership. Surfaced as potential variant innovation, excluded from archetype metrics.

### Optimisation concepts

**Hypothesis**:
A falsifiable claim about deck configuration (e.g. "card X belongs in the main over card Y"), tracked across pipeline runs. Evidence may be data-derived or pilot-supplied (playtesting, judgment); both are first-class. Hypotheses also direct where playtesting energy goes.

**Reference list**:
The user's own 75 being optimised. The final output of the project is the reference list as submitted to the tournament.

**Reference list version**:
One capture of the reference list, kept in the representation MTGO publishes a list in. Versions are appended and never edited, so the change log is derived from the captures rather than recorded beside them and cannot come to disagree with them. A capture that changed nothing is not a version: an append-only history cannot drop the empty entry it would file.

**Slot annotation**:
What the pilot knows about one slot, written on the line that slot is registered on: a `core:` or `flex:` word overriding where adoption would file it, and a note saying why the slot is what it is. The override is marked off with a colon rather than read out of whatever word the annotation opens on, since `core to the gameplan` is the pilot writing a note and filing the slot on its first word would drop the slot out of the playtest queue. Adoption cannot see either, since both are the pilot's, and the note is the whole of what tells a deviation that has been thought about from one nobody has looked at. A slot may be registered at no copies purely to carry one: that is how the pilot writes down a card he knows about and has left out, which otherwise has no line in the 75 to be written on. The override is the audit's and does nothing there, a slot at no copies not being one the audit reads.

**Slot audit**:
Every flex slot of the reference list read against its own camp, in one stratum, over the fresh window, and filed in one of four buckets. Consensus where a majority of the camp registered the same configuration, supported minority where a real part of it did, deliberate deviation where almost none did and the slot carries a note, unexamined deviation where almost none did and nothing says why. Core slots are not audited: they are not where optimisation happens. Every slot it reads is one the pilot took, so what his camp is near-unanimous on and his 75 never registered leaves no slot behind for it to bucket: that is the missing core slot's reading, not the audit's.

**Missing core slot**:
A card the reference list's own camp is near-unanimous on that the reference list registers no copies of. Read of the card and not the configuration, on both sides: a card the pilot plays at a count of his own is a slot he took and the slot audit has it, so only a card absent from the 75 entirely is missing; and the camp counts as near-unanimous when near all of it plays the card, over every count it registered the card at, rather than when any one of those counts clears the bar on its own. A camp agreeing on the card and arguing about how many leaves nobody on no copies at all, which is the strictest case for playing it and the one a per-configuration reading drops, since the split puts every count under the bar. The count most of the camp went to is carried beside the finding as what it mostly did, never as the whole of what it did. Where the audit's buckets are verdicts on a slot the pilot took, this is one he never had, so it is its own reading and never a fifth bucket. Core is read here off raw adoption, as it is everywhere: near-unanimity is a headcount, and the points-weighted share is for telling contested configurations apart. A capture registering the slot at no copies to say why the card was left out is still running none of it, so it stays in the reading and carries the pilot's note: what he wrote down is his reason, not a slot he has taken.
_Avoid_: fringe card (a card the archetype barely plays, which is the opposite reading)

**Confidence**:
For a flex slot, the share of the pilot's own camp that registered the exact configuration the pilot did, and only that. An index folding in the delta or the performance tilt would rank the 75 on a figure no population reported; those readings are carried beside it instead. Running no copies is a configuration like any other, so a missing core slot has a confidence too: the share of the camp registering none of the card, which is what is left once every count the camp does register it at is taken out.

**Playtest queue**:
The slots in the order playtesting should reach them: lowest confidence first, and at equal confidence the slot nothing has been said about ahead of the slot carrying a note, since the camp cannot tell them apart and only one of them has had the thinking done. The note is what breaks the tie, not the bucket it puts a slot in: a staple the pilot has written a reason for cutting has no bucket to be read off, the four being verdicts on slots he took. The flex slots and the missing core slots both, ranked on the one confidence and nothing added for a slot being the camp's core: a camp near-unanimous on a card leaves the pilot who runs none of it at most the remainder of the core bar, so the share puts a missing staple near the front on its own. Core slots the pilot took are not in it at all.

**Heuristic**:
A piece of MTG expertise supplied by the user (gained from play, not derivable from data) that informs how the data is interpreted. Captured persistently so the co-intelligence improves across sessions.

**Heuristic candidate**:
A heuristic the agent inferred rather than the user stating it, including one raised against an adopted heuristic the evidence now contradicts. Staged with the evidence that raised it and never treated as knowledge; it becomes a heuristic only on an explicit verdict from the user, and expires unratified.
_Avoid_: candidate on its own (a hypothesis candidate is a different thing: a claim about deck configuration)

### Analytical concepts

**Fresh window**:
The recent period whose lists represent the current state of the archetype and meta. Fourteen days, ending on the last day the store holds a published list for rather than on today, so a quiet week shortens no window.

**Baseline window**:
The longer comparison period that deltas are computed against. Bounded by meta regime changes, since older lists lose relevance, and it stops where the fresh window starts: the two are disjoint, so a delta is movement and not a fortnight compared against a period containing it.

**Regime change**:
A Modern B&R change or meta-warping set release that resets the relevance of prior lists. Lists on either side of a regime boundary belong to different eras and are not directly comparable.

**Meta share**:
The fraction of published winning lists an archetype occupies over a time window. A proxy for true field share, since only the winning portion of the field is visible.

**Meta snapshot**:
One dated reading of MTGGoldfish's archetype table, transcribed by hand and kept whole. Identified by the pair (capture date, window length), which the site serves neither of and the ingest stamps on: a share read over 30 days is a different measurement from one read over 14, so a trend is read within one window and never across two. Re-ingesting a pair corrects that entry rather than adding one, and a transcription whose own stamp disagrees is refused, since a mistyped date would file a reading no screenshot was taken for. The history is committed because, unlike an event, a screenshot cannot be fetched again.

**Mirror share**:
Goryo's own meta share: how much of the field the archetype plays against itself. The join a conditional hypothesis needs, since a slot bought on mirror density is only earned while that density stands. Read as of a date, which is answered by the last snapshot taken on or before it, stale readings included and marked as such.

**Adoption**:
For a configuration, the share of a population's lists that registered it. The population is one camp, in one stratum, over one window, and never a blend of them: the same configuration reads differently in each, and a share over two of anything is a number no population reported. Deck-level configurations, such as the land count, are read the same way.

**Points-weighted adoption**:
The same share with each list weighted by its Swiss points over the best Swiss total its own event published. The per-event normalisation puts a long challenge on the same scale as a short one, so a configuration cannot climb on having been registered at the events that ran more rounds. Challenge-class only: a league publishes no standings to weigh a list by. Always read beside raw adoption, since their difference is performance tilt.

**Performance tilt**:
For a configuration, its points-weighted adoption minus its raw adoption within challenge lists. Positive: overrepresented among high-point finishes. Negative on a rising configuration: the herd is adopting an underperformer. Swiss points only, so no league list enters it.

**Conversion gap**:
For a camp, its share of league-trophy pilots minus its share of challenge-class pilots, over a regime-bounded window, counting each pilot once per camp. A league dump publishes trophies without their denominator: a camp's 5-0 count is its entries times its conversion, and only the product is served, so the challenge-class stratum stands in for the entries. The two strata truncate at different bars, so a camp short of 5-0s and long on challenge finishes is flatter, not worse. Hypothesis-grade evidence about outcome distribution: it routes to playtesting, never to a slot decision. Reported only beside its controls, since one grinder's trophies or a straddled regime boundary would otherwise produce it on their own. The cap either holds the gap, collapses it (leaving under half of the uncapped figure standing) or flips its sign, and the reading says which. It is applied to the reading and not to the cache, which stays as published (see ADR 0001).
_Avoid_: performance tilt (a different figure, over the challenge stratum alone, that the conversion gap never feeds)

**Top-32 truncation**:
The visibility bias: challenges publish only the top 32, leagues only 5-0s. Losing lists never appear, so all analysis is conditioned on success.

**Hype spike**:
A surge in adoption of a card combination after a visible finish. Subsequent results reflect adoption density, not card quality. Self-correcting over time, and must not be read as optimisation.

**Departure**:
How far outside its camp a list is built: the cards hardly any of that camp registered that it did, plus the camp's near-unanimous cards it registered none of. Counted at the card and not the configuration, so a pilot on four copies of a land his camp runs three of has not departed from anything: a camp that agrees on a card and argues about the number is agreed on the card. Measured against the camp and stratum as they stood the day before publication, never as they stand now, since a list the field went on to copy would otherwise be read against its own influence. Two kinds clear the bar, and the reading says which. A card the archetype has barely played that the tally had never seen is a departure on its own, nobody arriving at such a card by drifting through flex slots; known cards recombined take five.

**Breakthrough deck**:
A list that departs from what its camp had settled on, and performs. Whether the field then followed it is a later reading and a separate word, for which see trendsetter. A list registered in a camp answers to that camp however far from it the list is built; one the camp rule left out, a hybrid experiment or a near-miss list, is read against the camp it comes out nearest to and only up to a ceiling, past which it is another deck rather than a variant of that camp.
_Avoid_: using this for a list the field took up (that is a trendsetter)

**Trendsetter**:
A breakthrough deck the field then took up: pilots the card was new to, and the archetype was not, registering it inside the fortnight after. Counted on the card and not on the list, since what spreads is the idea rather than the 75 around it, and a pilot registering the whole list is herd adoption instead. A first-time publisher is not one of these pilots: most of the names a league dump carries appear once, so counting them would read the game's turnover as follow-through. Until the fortnight closes the flag is being watched rather than answered, a departure that went nowhere being a verdict the field has to have had the time to reach.

**Pilot affinity**:
A pilot's persistent preference for pet cards. Concentrated adoption is signal in both directions: it inflates apparent field adoption, but a dissenter's repeated success with it is hypothesis-grade innovation.

**Pet tech**:
A configuration the post-regime history saw often enough to be a habit rather than a one-off, from one or two pilots only. Adoption counts lists, so it reports the same share whether several pilots converged or one repeated himself; the flag says which, and classifies rather than discounts. Read within a camp, as every share is. The hybrid bucket is not one: being the residue of the rule that draws the two camps, it is thin by construction, so nearly anything registered in it is one or two pilots' by default.

**Proven pilot**:
A pilot the baseline window saw finish above the cut more than once, challenge-class only, a league dump publishing no standings to make a cut at. The tier that tells a dissenter from an unknown. Read over the baseline window alone, so that it says who was already proven when a fresh list turned up rather than who the news itself proved.

**Hypothesis candidate**:
A claim about deck configuration that playtesting is owed, raised where a proven pilot's pet tech is also what he repeatedly finished on. Both halves carry weight: the tier is why his going against the herd is worth reading, and the finishes on that configuration are the claim.
_Avoid_: heuristic candidate (a different thing: a claim about how the numbers are read)

**Dissenter**:
A pilot repeatedly performing well with a configuration that departs from the herd's current consensus. The opposite failure mode of herd adoption.

**Herd adoption**:
Many pilots converging on a recent winner's exact list. Looks like consensus; is largely copying, and inflates belief in that configuration's optimality.
