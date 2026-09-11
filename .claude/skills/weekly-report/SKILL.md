---
name: weekly-report
description: Ingest the week's MTGO data and build the tracked deck's weekly report. Use whenever Alejandro asks for this week's report, for the Esper Blink report, to prepare for the team meeting, or to ingest new data and report on a tracked deck.
---

# The weekly tracked-deck report

Runs Monday, for the week that closed on Sunday, ahead of the Tuesday team
meeting. Everything numeric is computed by the CLI and frozen. The one thing
written by hand is the summary at the top, and the whole point of this file is
that it gets written the same way every week.

**The numbers are not yours to adjust.** If a figure looks wrong, say so and
stop. Do not filter a week out, re-bin anything, or reach past the CLI into the
store to get a better number. A report whose method moves week to week is worse
than no report, because nobody can tell a change in the deck from a change in
how it was measured.

## The run

```bash
uv run deck-engine refresh --since <the Monday two weeks back>
uv run deck-engine weekly
```

`refresh` fetches every Modern event published since that date and rebuilds the
store. Go back two weeks rather than one: MTGO publishes on US time, a league
dump keeps gaining 5-0s through its own day, and the last few days are refetched
rather than trusted.

`weekly` freezes the closed weeks and fortnights, writes the numbers to a JSON
file, and renders the HTML. It prints where both landed. It defaults to Esper
Blink and to the last complete week; `--deck`, `--variant` and `--week` override.

If it prints `NO SUMMARY`, that is the next step and the whole of it.

## Writing the summary

Read the JSON the run named. Write `data/tracking/<deck>/summary/<week>.md` and
re-run `uv run deck-engine weekly` to render it in.

**Five clauses, this order, one or two sentences each. Nothing else.** The
order is fixed so that a reader comparing two weeks is comparing the deck rather
than comparing two pieces of writing.

1. **Volume against last week.** `challenge.lists` and `challenge.share` against
   `challenge.previous_share`. Up, down or level.
2. **Volume against its own history.** The same figures against
   `challenge.median_lists`. This is the clause that stops a deflating spike
   reading as a collapse.
3. **Conversion.** `conversion.top8` and `conversion.top8_share` against
   `challenge.share`. When `conversion.over_converting` is true the deck is
   holding more of the top 8 than of the top 32, and that is the sentence.
4. **Innovation.** What `timeline_latest` holds, named. When it is empty, say
   the fortnight was stable. Never dress up a stable fortnight.
5. **Orzhov.** `orzhov.lists`, `orzhov.challenge`, `orzhov.trophies`, as bare
   numbers. Observability only. It is not in any plot and it does not get a
   verdict.

Rules for the prose:

- **The words are fixed too.** A placement-publishing event is a **swiss-like
  tournament**, never "challenge-class". The history since 2026-05-18 is
  **since the Modern bans**, never "post-regime". The deck **achieves finishes
  in swiss-like tournaments**; it does not "take lists". Those are the reader's
  words. The JSON keys stay as they are (`challenge.lists` and the rest), and
  so does the engine's own vocabulary outside this report.
- **Every claim comes from the JSON.** No matchup opinions, no predictions, no
  "suggesting that". If the numbers do not say it, it does not go in.
- **Print the n beside a share.** A week can be nine lists.
- When `challenge.spiking` is true the report already carries a banner saying
  so. Do not contradict it, and do not repeat it either.
- No em dashes.

## Before you hand it over

- The rendered file opens and the three weekly figures are there, plus the
  Spotlights figure on any week a paper event is cached.
- The summary's five clauses are in order and every number in it appears in the
  JSON.
- `git status` shows changes under `data/tracking/`, and `data/index.csv` moved.
  Commit those: they are the report's memory, and without them the timeline
  cannot be rebuilt.
- The rendered HTML is under `reports/` and is deliberately not committed.

## What not to do

- Do not edit a row in `timeline.csv` or `weekly.csv`. They are append-only.
  A past week's numbers can genuinely move when a league dump fills in, and the
  frozen row is what was reported.
- Do not rewrite an old summary. If one was wrong, say so in this week's.
- Do not add a card to `copy_drift` in config because it moved once. That tuple
  decides which slots a count change earns a timeline row for, and it reads the
  same slots every fortnight on purpose.
- Do not widen the membership rule to catch a list that looks like the deck.
  Raise it with Alejandro; it is his call, and `HEURISTICS.md` is where the
  answer goes.

## Paper Spotlights

A Spotlight is fetched once and kept:

```bash
uv run deck-engine spotlight-fetch
```

It reads `config.SPOTLIGHTS`, skips every list already cached, and writes one
JSON per event to `data/raw-melee/`. A played-out event does not change, so this
is not part of the Monday run: fetch it the week the event lands and never again.
A field of nine hundred is nine hundred requests to someone else's server.

The report picks up whatever is cached and renders the Spotlights section from
it. Nothing else in the run changes.

- **Paper figures never share an axis with MTGO ones.** A Spotlight publishes
  every finisher and a challenge publishes its top 32, so the Spotlight's *field
  share* is a true metagame share with no MTGO counterpart. The only like-for-
  like number is its *top 32* column, and that is a handful of lists, so it is
  printed with its count and never as a bare percentage.
- **Do not put a Spotlight in the store.** The challenge-class readings are
  defined as every event class except league, so a paper event in `decklists`
  would be counted as challenge-class by default and would swamp the week.
- **A Spotlight row against MTGO is marked cross-population** and means less
  than one against the Spotlight before it. Brisbane to Dallas is paper on both
  sides, a week apart: that is the comparison to write a clause about.
- Adding a Spotlight is adding it to `config.SPOTLIGHTS` **and** to
  `data/events.csv`, the first for the reading and the second for the line on
  the figures. Which events count is Alejandro's call, same as `events.csv`.

## When something new turns up

A new major event goes in `data/events.csv` as `date,label`. It becomes a
vertical line on every figure and a timeline row in the fortnight it falls in.

If the run reports off-colour exclusions climbing, the colour rule has gone
stale: a red or green source nobody listed is letting a Mardu build in, or
turning a real list away. Name the count and ask.
