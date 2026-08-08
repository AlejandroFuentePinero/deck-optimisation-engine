# Postmortem: what published decklists can and cannot optimise

2026-08-08. A full audit of the engine against its own database, and a survey
of every tool that has tried to do performance analytics for Magic, to settle
one question: is the recommendation quality a defect of this system, or a
property of its data source?

Method: 10-agent review (3 repo audits, 6 landscape sweeps, 1 adversarial
cross-check). Every quoted figure was recomputed against `engine.duckdb`;
one correction from the cross-check is applied below.

## Verdict

**The audit largely vindicates the engineering and condemns the premise.**
The statistics are honest, the populations are correctly scoped, and the
instruments print their own detection floors. But every performance
instrument in the engine is running at 6-9% statistical power against
effects ten times smaller than its detection floor, on a sample conditioned
on winning. The engine is a precise adoption-measurement device pointed at a
performance question.

**This is not fixable from the current position, and it is not a failure of
imagination.** Twenty years of tooling history show that nobody has ever
produced card-level performance evidence for constructed Magic from
published decklists, that the two efforts which got real matchup data from
MTGO were both shut down by Wizards, and that the one working model (opt-in
game telemetry, HSReplay-style) is structurally unavailable for Modern and
has been declined or killed by every party able to build it.

**What remains viable is a different tool**: adoption context plus attention
routing plus the pilot's own recorded games as the only performance ground
truth available. The engine's architecture already points there; its
vocabulary oversells what the data half contributes.

## 01. Audit of the statistical layer: honest instruments, empty magazines

The dataset is 19,691 published Modern lists from 508 MTGO events
(2026-02-01 to 2026-08-08, 4,288 pilot logins), of which 837 are Goryo's,
splitting 587 non-Fallaji, 215 Fallaji, 35 hybrid. The population every
serious reading runs on, non-Fallaji challenge-class post-regime, is **177
lists from 105 pilots**. That number decides everything below.

| Instrument | What it actually measures | At current n | Verdict |
|---|---|---|---|
| Outcome contrast | P(top-16 given published top-32) with vs without a configuration | Floor 22-32pp; power 9.2% for a 5pp effect (best case), 6.4% typical. Every contrast run returned undetectable (p 0.34-1.0) | No signal |
| Performance tilt | Points-weighted minus raw adoption | Median under 0.5pp, max 4pp; suppressed below its own display floor | Correctly demoted |
| Conversion gap | League-trophy share minus challenge share | +6.7pp on SE ~5pp (z = 1.3, CI spans zero), published as "holds" with no interval | Noise labelled robust |
| Adoption deltas | Fresh-window share vs baseline share | 95% CI half-width ~20pp at n = 38 vs 75; most printed deltas (3-23pp) sit inside it; only the land-count swing (33-41pp, ~3.3 sigma) clears it | No noise floor |
| "New and climbing" | Cards appearing in the fresh window | 9 of 10 current rows are exactly one list (3% of 38), ranked "steepest first" | n = 1 as signal |
| Hype flags | Post-finish adoption spikes and their decay | 5 of 9 episodes trace to one finish; verdicts resolve on windows as small as 8 lists | Fine as caveat, thin as verdict |

Three structural notes sharpen this:

1. **Pilot clustering.** The Fisher tests assume independent lists, but 15
   pilots hold 71 of the 177 lists (40%; the top repeater alone holds 12),
   so quoted floors are ~1.3x optimistic on top of everything else. The
   conversion half caps one list per pilot (`outcome.py:169-172`); the band
   arms (`outcome.py:138-149`) do not.
2. **Dichotomisation waste.** Challenge standings publish full Swiss
   records, and a rank test on Swiss win rate instead of the binary top-16
   band would cut the floor from ~22pp toward ~16-17pp. That is the true
   ceiling of this data source, and it is still an order of magnitude above
   any plausible flex-slot effect.
3. **Survivorship is a gradient, not a wall.** Challenge-32 events publish
   essentially their whole field (29% of the contrast population, losing
   records like 2-4 included), while challenge-96 events hide two thirds of
   theirs. Softer than "winners only", still fatal for win rates.

Credit where due: the engine already knew most of this about itself.
Detection floors print beside every null, tilt was empirically demoted and
suppressed, strata are never pooled, and the land-count report explicitly
refuses to rest on win-rate evidence. The audit found the honesty real. It
also found that honesty does not create signal.

## 02. What actually fed the 75

Tracing all eight hypothesis records end to end: every `data` entry in every
record is adoption description (shares, deltas, hype caveats, one mirror
share). No performance reading has ever reached a record, because the one
instrument billed as bearing on performance, the outcome contrast, is wired
into neither the evidence layer nor the report. It exists only as a manual
CLI query. The permanent argument log a verdict is written from can
structurally contain only popularity.

The pattern completes at the decision layer. The project's single live slot
decision (v3: third Wrath of the Skies in, Pest Control out) followed a 92%
camp adoption share, with no playtest entry, while the record still reads
`status: open` and the report counts 8 of 8 unresolved. By the engine's own
vocabulary that decision is indistinguishable from herd adoption, the exact
failure mode HEURISTICS.md ranks below a lone dissenter. The safeguards
exist; the first decision under pressure bypassed them.

And the naming inflates the product. "Confidence" is the share of the camp
that registered the pilot's exact configuration: conformity, renamed. The
slot audit's column header is "Verdict" over what are popularity buckets.
"Departure lineage" is billed as the field's verdict on an idea and the
highest-powered instrument the data holds; it counts pilots copying a card,
the same signal class the hype flag exists to discount, and its own rows
show graduated trendsetters lapsing afterwards. The outputs that genuinely
match their claims are the modest ones: the playtest queue, missing-core,
and unplayed-card readings, which spend adoption data on the one thing
popularity legitimately buys, deciding where attention goes.

## 03. Six things mtgo.com structurally does not publish

| Absent | Question it makes unanswerable |
|---|---|
| Opponents / pairings | Any matchup win rate, mirror performance, strength of schedule |
| Per-round results | Opponent-adjusted performance (only aggregate Swiss W-L survives) |
| Game counts | Game win rate, pre- vs post-board performance, play/draw |
| Sideboard decisions | Whether a sideboard card is ever boarded in, or is dead weight |
| The losing field | True win rates, conversion, popular-but-losing configurations |
| Entry counts | Separating play rate from conversion (only the product is served) |

None of the six is recoverable from this source; each would require a
different data source entirely.

The ingestion architecture itself audited clean: immutable raw cache,
transactional rebuilds, committed list-grain index, printings merged at
parse time. The cache-index-rebuild pattern would carry over intact to a
richer source; the parse layer and the schema (which has no grain for
matches, opponents, or games) would not. One asset sits idle: the
`meta_snapshots` table is the project's only field-composition data, the
only thing that could say *why* a configuration moved, and nothing reads it
yet.

## 04. The landscape: nobody has done this, and the reasons are structural

The six sweeps covered roughly forty tools across Magic and adjacent games.
Compressed to what bears on this project.

### Matchup ground truth has been obtained exactly three ways, ever

1. **A developer API exposing both decklists.** Legends of Runeterra had it
   (exact matchup matrices, zero inference); it died with the game in 2024.
   Dota and League founded the pattern. Wizards has never offered it.
2. **A deterministic client log complete enough to classify the opponent.**
   Hearthstone's Power.log made HSReplay: per-card mulligan and drawn win
   rates *conditioned on archetype*, the only card-level constructed
   analytics in any card game. Arena's log deliberately omits the opponent's
   decklist, which is why Untapped.gg's matchup tables are inference-based,
   Arena-only, and paywalled. MTGO's equivalent surface does not exist at
   scale.
3. **Owning the tournament pipeline.** Limitless TCG runs the bracket,
   collects lists at submission, and matchup records fall out of pairings
   for free. The Melee.gg equivalent for Magic exists but API access is
   gated to tournament organisers.

Constructed Magic on MTGO has none of the three. That is the whole story of
why the imagined tool does not exist; it is not that nobody thought of it.

### When someone gets the data anyway, Wizards has ended it

This settles "could we ever": the constraint is policy, not engineering, and
it has been enforced repeatedly.

- **Shut down**: StarCityGames' *Too Much Information* series, real matchup
  tables from SCG's own independent circuit. Wizards asked them to stop
  publishing it.
- **Shut down**: MTGGoldfish's replay-harvested Modern matchup series (the
  "28k games" era). Wizards asked; then a client change blocked spectating
  replays of games you did not play, killing the method for everyone.
- **Shut down**: the Daybreak Census API, late 2023: every league 5-0 and
  full challenge results over REST, the richest MTGO data surface ever.
  Wizards intervened after roughly six months, "pending internal review".
  It never returned.
- **Attempted**: February 2026, publication cut to top-8/16/32 by event
  size, reversed within a week under community backlash. The stated
  rationale: MTGO data was "overrepresented versus the population size" in
  aggregators.

Meanwhile the one team with a working opt-in pipeline, 17lands, looked at
constructed and declined it in writing ("no plans... a bad return on our
time to implement"), and the scraper ecosystem this repo's ingest layer
resembles has a named succession problem: Badaro's community decklist cache,
the de facto standard, was archived the day a 2025 site change broke it, and
survives only because a second maintainer had already forked the pipeline.

### The academic route is not a shortcut either

Every deckbuilding-optimisation paper that reached simulated competitiveness
needed a fast rules engine, a competent pilot AI, and a gauntlet of real
meta decks. Magic has the rules engines (Forge, XMage) and no competent fast
pilot, which is why the Hearthstone research line has no MTG equivalent. The
single system ever validated against humans, a GA with hand-coded synergy
scores, went 0-7 at a real Standard Open. LLM deckbuilders (2025-26 state)
deliver legality and theme and, by their own authors' assessment, not
competitiveness. And the strongest AI result in Magic, draft bots at 66-68%
human-pick accuracy, exists precisely because 17lands telemetry exists.
Dense decision data in, competence out; there is no such corpus for
constructed.

## 05. The granularity ladder

Line every data source up against the resolution of question it can answer
and the postmortem writes itself. Each rung needs roughly an order of
magnitude more data than the one above it, and the sources that exist for
Modern stop at the top.

1. **Meta share: who plays what.** Published decklists answer this well. It
   is what MTGGoldfish has sold for twenty years, and what this engine
   computes correctly. Status: solved.
2. **Archetype matchup win rate: what beats what.** Needs pairings joined to
   lists. Exists thinly for Modern (mtgdecks.net, ~56k matches across the
   whole format, so single cells run on dozens of matches) and properly only
   where telemetry or tournament platforms exist (Untapped on Arena,
   Limitless for Pokemon). Status: noisy priors at best for Modern.
3. **Card-level win rate within an archetype: which card earns its slot.**
   Needs game telemetry at density. Achieved exactly once in any card game
   (HSReplay, because Hearthstone's client logs everything), refused by
   17lands for constructed, killed twice on MTGO by Wizards. Status: blocked
   by policy and platform.
4. **Flex-slot configuration within one camp: this project's question.** One
   resolution finer still: not "is Surgical good in Goryo's" but "does the
   third Wrath beat Pest Control in this 75, in this field". No dataset has
   ever reached rung 3 for Magic; the engine was aimed at rung 4 with rung 1
   data. Status: pilot ground truth only.

Everything below rung 2 is invisible to any Modern data source that exists.

## 06. Can it be overcome?

### From the current position: no, and stop trying

No code change manufactures the losing field, the pairings, or the sample
size. The honest reading of the audit is that the engine has already
extracted approximately everything rung-1 data holds, and its remaining
defects are about not overselling that. Worth fixing precisely because they
are cheap and truth-preserving:

- Cap the outcome contrast's band arms at one list per pilot (the conversion
  half already does this)
- Put a confidence interval on the conversion gap; retire the bare "holds"
  label
- Give adoption deltas a noise floor, as tilt already has; a delta under
  ~20pp at current n is weather
- Give `climbing()` the same 8-list floor `migrations()` already has
- Use Swiss records, not the binary band, in the contrast (floor ~22pp to
  ~16-17pp, the true ceiling)
- Wire the contrast and conversion gap into the hypothesis evidence layer so
  the argument log can hold them
- Rename "confidence" to what it is (camp backing), and rule on
  wrath-density so the decision practice matches the mechanism
- Read the idle `meta_snapshots` table: field composition is the one context
  that says why a slot moved

### Ever, for this deck: partially, by changing what counts as data

Two acquisitions are real, and both are already precedented by surviving
tools:

1. **The pilot's own MTGO game logs.** The client writes play-by-play
   GameLog files locally; parsing them is proven (MyMTGO,
   cderickson/MTGO-Tracker) and is the only ToS-durable MTGO telemetry there
   is. It yields exactly the evidence the hypothesis records are starving
   for: matchup results, game counts, sideboard decisions, per
   configuration. Small n, but it is *owned* n, on the actual 75, against
   the actual field, and the record architecture was built for it.
2. **Melee pairings for the paper field.** Archetype-level matchup priors
   for the tournament being prepared for, at rung-2 resolution. Noisy, but
   it bounds which matchups deserve sideboard slots, which is the decision
   the mirror-share machinery already gestures at.

Neither reaches rung 4. Nothing ever has. Rung 4 belongs to playtesting, and
the engine's correct role is to decide *which* playtests to run, which is
precisely what its best outputs (the queue, missing-core, unplayed cards)
already do.

### The general all-deck optimisation tool: not from this position, and probably not from any

The preconditions are now enumerable. A constructed optimiser at the
resolution players would pay for needs rung-3 data, which requires one of: a
Wizards API that has been built once and revoked, client telemetry Wizards
has killed twice and the capable parties have declined, or owning the
tournament layer, which for Magic means Melee's seat. The scaling worry
about per-deck heuristics turned out to be the smaller obstacle: most of
what this project captured as "heuristics" is a reusable data model of MTGO
publication, and the landscape shows archetype classification (a solvable
rules-engine problem) is the actual per-deck subsystem. The binding
constraint is that the ground truth is generated inside a client whose owner
treats its release as a format-health lever, states so publicly, and has
enforced that position for a decade. That is a policy wall. Tools do not
engineer through policy walls; they wait for them to move, or they build on
data they own.

## So: data problem or knowledge problem?

Data, three rungs deep, with a policy wall at the bottom. The knowledge that
would remain even with perfect data is small, forward-looking, and already
the pilot's: what field shows up in three weeks, and what each slot is for.
The system's real failure was never limited game knowledge; it was that
rung-1 data was dressed in rung-3 and rung-4 vocabulary ("confidence",
"verdict", "performance"). Strip the costume and a genuinely useful, honest
tool remains: a field model, an attention router for playtesting, and a
ledger where the pilot's own games are the only performance evidence,
because for this format, at this resolution, they are the only performance
evidence anyone has.

## Key sources

- Repo evidence: `engine.duckdb` queries; `deck_engine/outcome.py`,
  `movement.py`, `store.py`, `hypotheses.py`; `reports/2026-08-08.html`;
  ADR 0001; `hypotheses/*.md`. All figures recomputed by the cross-check
  pass; one correction applied (the top repeater holds 12 lists in the
  contrast population, not 16).
- 17lands constructed refusal: 17lands.com/faq. HSReplay model:
  hsreplay.net, help.hearthsim.net. Untapped constructed matchups (Arena,
  premium): mtga.untapped.gg/premium
- Policy history: mtggoldfish.com/articles/wizards-data-insanity (SCG TMI
  and replay-series shutdowns); Daybreak Census API rise and revocation:
  mtgscribe.com (2024-06-20) and MTGGoldfish Vintage 101 / This Week in
  Legacy coverage; Feb 2026 cut and reversal:
  mtgo.com/news/reversing-decklist-changes-02202026
- Modern matchup ceiling: mtgdecks.net/Modern/winrates (~56k matches).
  Melee API gating: help.melee.gg/docs/api-use
- MTGO telemetry: github.com/videre-project/MTGOSDK, mymtgo.com,
  github.com/cderickson/MTGO-Tracker. Community cache succession:
  github.com/Badaro/MTGODecklistCache to
  github.com/fbettega/mtg_decklist_scrapper
- Academic line: Garcia-Sanchez et al. CIG 2016; Q-DeckRec
  (arXiv:1806.09771); MAP-Elites GECCO 2019/2022; magique's 0-7 field test;
  UrzaGPT (arXiv:2508.08382)
