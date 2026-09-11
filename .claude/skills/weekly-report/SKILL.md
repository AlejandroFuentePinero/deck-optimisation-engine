---
name: weekly-report
description: Ingest the week's MTGO data and build a tracked deck's weekly report. Use whenever Alejandro asks for this week's report, for the Esper Blink or Goryo's report, to prepare for the team meeting, or to ingest new data and report on a tracked deck.
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
uv run deck-engine weekly --deck blink
uv run deck-engine weekly --deck goryos
```

`refresh` fetches every Modern event published since that date and rebuilds the
store. Go back two weeks rather than one: MTGO publishes on US time, a league
dump keeps gaining 5-0s through its own day, and the last few days are refetched
rather than trusted.

`weekly` freezes the closed weeks and fortnights, writes the numbers to a JSON
file, and renders the HTML. It prints where both landed. It defaults to Esper
Blink and to the last complete week; `--deck` and `--week` override. `refresh`
serves every deck at once, so it runs once and `weekly` runs per deck.

If it prints `NO SUMMARY`, that is the next step and the whole of it.

**Which lists a report reads is not a flag.** It is the report's own entry in
`config.REPORTS`: the archetype, the camp its volume and performance figures are
pooled over, the camp its build readings are taken on, the slots it watches. The
report calls a camp a **version of the deck** and names it from
`config.VERSION_NAMES` where the pilot's word is not the rule's, so the
non-fallaji camp prints as **Riddler**; the code, `flags.json` and every reading
outside this report still key it by the rule name. One report per directory under `data/tracking/`,
because a pooled row and a one-camp
row in the same `weekly.csv` would be two measurements under one column heading
and nothing in the file would say which a row was. Adding a subject is an entry
there and a first run; changing an existing subject's population invalidates
every frozen row it has, so it is Alejandro's call and not a tidy-up.

The two subjects differ in that Goryo's pools its camps and Blink does not. Its
volume and performance are the whole archetype's, which is what a metagame share
is, and its storyline, goldfishing figure and Spotlight findings are the
non-fallaji camp's. Pooled, a card at nine tenths of one camp and none of
another reads as the deck at half of it, and a camp arriving reads as the deck
changing its mind. The report labels both populations where they appear; the
summary should not contradict the labels.

## Writing the summary

Read the JSON the run named. Write `data/tracking/<deck>/summary/<week>.md` and
re-run `uv run deck-engine weekly` to render it in.

**A headline on a week a major event fell in, then six clauses in this order,
one or two sentences each. Nothing else.** The order is fixed so that a reader
comparing two weeks is comparing the deck rather than comparing two pieces of
writing.

**The headline**, and only on a week a major event fell in: an RC, a PT or a
Spotlight. Who finished, named, with their rank and record, from
`major_event.top`, and the event. One sentence, its own paragraph, above clause 1.
It leads for two reasons. A team reads a named finish at the biggest tournament
of the era before it reads a share, and everything under it is MTGO, so without
it the week's one paper result arrives in sixth place under figures that never
counted it.

1. **Volume against last week.** `challenge.lists` and `challenge.share` against
   `challenge.previous_share`. Up, down or level. **Say MTGO.** Clauses 1 to 4
   and 6 are the MTGO store and nothing else, paper being deliberately kept out
   of it, so on a week an event fell in, "43 finishes in swiss-like tournaments"
   reads as the deck's whole week when it is the online half of it.
2. **Volume against its own history.** The same figures against
   `challenge.median_lists`, the median week since the bans, which is the figure
   that stops a deflating spike reading as a collapse. `challenge.recent_median`
   is the median of the four weeks behind this one, and the two together are the
   clause: a deck can be well above its regime median and level against where it
   has just been, which is what a deck that moved to a new level looks like.
3. **Conversion.** `conversion.top8` and `conversion.top8_share` against
   `challenge.share`. When `conversion.over_converting` is true the deck is
   holding more of the top 8 than of the top 32, and that is the sentence.
4. **Innovation.** What `timeline_latest` holds, named, and the fortnight it
   covers. When it is empty, say the fortnight was stable. Never dress up a
   stable fortnight. A card climbing in one board and falling in the other is
   two rows and one decision: write it as the card changing boards.
5. **Paper**, and only on a week a major event fell in: `major_event`, which
   is there on those weeks and null on every other. The event whose week is the
   reported week, read against `major_event.against_row`, which is whatever the
   storyline said last: the paper event a week earlier where there was one, and
   the MTGO fortnight before it otherwise. Field share with its n, top 32 with
   its n, conversion, match record and win rate against the field's. This is where the
   headline's finishes get their context, so it does not repeat the names. An
   event a week outside the reported week is the comparison and never the
   subject: a report whose clauses reach past their own week cannot be read
   against the week before it.
6. **The other versions of the deck.** `versions`, one entry per version the
   report names but does not read, as bare numbers. Observability only. They get
   no verdict, and where the report's figures are pooled they are already
   counted in them. The presence figure's third panel plots the same split.

Rules for the prose:

- **Short sentences.** The summary is read aloud in a meeting off the top of the
  page. One number per sentence where the sentence can carry only one, and a
  comparison next to the figure it qualifies rather than four clauses later.
  Six numbers in one sentence is a table, and there is a table further down.
- **The words are fixed too.** A placement-publishing event is a **swiss-like
  tournament**, never "challenge-class". The history since 2026-05-18 is
  **since the Modern bans**, never "post-regime". The deck **achieves finishes
  in swiss-like tournaments**; it does not "take lists". Those are the reader's
  words. The JSON keys stay as they are (`challenge.lists` and the rest), and
  so does the engine's own vocabulary outside this report.
- **Every claim comes from the JSON.** No matchup opinions, no predictions, no
  "suggesting that". If the numbers do not say it, it does not go in.
- **Print the n beside a share.** A week can be nine lists. Where the report
  reads one camp, the paper figures are that camp's and the clause says so:
  Esper Blink took 63 lists to Dallas and the row says 61.
- **`goldfishing` is read per pilot per 60**, so its share is over
  `builds` and not over `lists`. A league publishes every 5-0, so one grinder
  can be five of a week's lists and is one of its builds.
- When `challenge.spiking` is true the report already carries a banner saying
  so. Do not contradict it, and do not repeat it either. It is true only where
  the week clears twice both medians, so a deck four weeks into a new level does
  not flag and must not be written up as spiking because the count looks large.
- No em dashes.

## Before you hand it over

- The rendered file opens and the three weekly figures are there, plus the
  major-events figure on any week a paper event is cached.
- The summary's clauses are in order and every number in it appears in the JSON.
- On a week a major event fell in, the summary opens with the headline and the
  MTGO clauses under it say MTGO.
- The paper clause names the event that fell inside the reported week, and the
  event before it only as the comparison.
- `git status` shows changes under `data/tracking/`, and `data/index.csv` moved.
  Commit those: they are the report's memory, and without them the timeline
  cannot be rebuilt.
- The rendered HTML is under `reports/` and is deliberately not committed.

## What not to do

- Do not edit a row in `timeline.csv` or `weekly.csv`. They are append-only.
  A past week's numbers can genuinely move when a league dump fills in, and the
  frozen row is what was reported.
- Do not rewrite an old summary. If one was wrong, say so in this week's.
- Do not add a card to `copy_drift` or `watch` because it moved once. Those
  tuples decide which slots earn a row for a count change, and they read the
  same slots every fortnight on purpose. `watch` is the sharper of the two and
  the more tempting: it reads a slot at ten points rather than twenty, and by
  copy count rather than by presence, so it says that two copies went to three
  in a fifth of the camp where no mean could. That bar only holds because the
  list is short and every entry on it is a question Alejandro asked. Widened by
  a scan it doubles the storyline and finds nothing: unfiltered at ten points
  this population gives 78 rows across eight fortnights against 41 at twenty,
  and 38% of them reverse in the next fortnight either way.
- Do not widen the membership rule to catch a list that looks like the deck.
  Raise it with Alejandro; it is his call, and `HEURISTICS.md` is where the
  answer goes.

## Major paper events

A Spotlight, a Pro Tour or an RC is fetched once and kept:

```bash
uv run deck-engine event-fetch
```

It reads `config.MAJOR_EVENTS`, skips every list already cached, and writes one
JSON per event to `data/raw-melee/`. A played-out event does not change, so this
is not part of the Monday run: fetch it the week the event lands and never again.
A field of nine hundred is nine hundred requests to someone else's server.

The report picks up whatever is cached and renders the major-events section from
it, under the MTGO half of the page and above the storyline. Nothing else in the
run changes.

- **Paper figures never share an axis with MTGO ones.** A Spotlight publishes
  every finisher and a challenge publishes its top 32, so the Spotlight's *field
  share* is a true metagame share with no MTGO counterpart. The only like-for-
  like number is its *top 32* column, and that is a handful of lists, so it is
  printed with its count and never as a bare percentage.
- **An event that played two formats is read at the end of its last
  constructed round**, and its `format` in `config.MAJOR_EVENTS` says which. A
  Pro Tour is six rounds of draft and ten of Modern under a single ranking and
  its top 8 is a draft pod, so the Swiss cut is the Modern standing and the
  playoff reorders the top 8 on limited results alone. Its match record is the
  constructed rounds by themselves, taken as the difference between the
  standings either side of each run. The finishing positions still carry the
  draft rounds, which no arithmetic can undo.
- **A major event is a storyline entry like any other.** It is read against
  whatever came immediately before it: the paper event played since the last
  fortnight closed, and the fortnight itself where there was none. MTGO moves
  what pilots take to a Pro Tour and a Pro Tour moves what turns up on MTGO the
  fortnight after, so it gets its own row for the focus and never because it is
  decoupled from the rows around it.
- **Its lists are never folded into a fortnight's own numbers.** Each entry is
  one room. An event week sits inside a fortnight rather than beside one, so the
  two cannot be put in a sequence: the entry after Pro Tour Amsterdam would be
  the fortnight the Pro Tour was played in. Pooled it would also be most of the
  bin, the fortnight to 6 September holding 87 MTGO lists of Goryo's against 106
  from Brisbane and Dallas, and the bin's row read against a pure MTGO bin would
  report the American field as the deck changing its mind. The MTGO response
  reaches the timeline by the calendar: the fortnight holding an event runs on
  past it, and the one after is read against that.
- **Do not put a Spotlight in the store.** The challenge-class readings are
  defined as every event class except league, so a paper event in `decklists`
  would be counted as challenge-class by default and would swamp the week.
- **A Spotlight carries no land count**, melee publishing a decklist page the
  fetch keeps the cards of and not its type headings, so the manabase reading is
  MTGO only and a paper row never mentions the land count. Recoverable, at the
  price of refetching every decklist page: the headings are on the page and
  `melee.boards` reads them to split the boards.
- **A list whose boards did not separate is counted as unread**, not classified.
  A sideboard filed under a heading the fetch does not know puts the whole 75 in
  the mainboard, and membership is a mainboard test, so such a list would join
  the deck on a parse failure. The report prints the count. If it climbs past
  the three melee has published so far, the fetch has broken and the Spotlight
  numbers are not to be reported until it is fixed.
- **A row read against a fortnight is marked cross-population** and means less
  than one against the paper event before it. Brisbane to Dallas is paper on
  both sides, a week apart: that is the stronger of the two comparisons, and a
  clause off a cross-population row says which room each side came from.
- Adding an event is adding it to `config.MAJOR_EVENTS` **and** to
  `data/events.csv`, the first for the reading and the second for the line on
  the figures. Which events count is Alejandro's call, same as `events.csv`.
  A frozen fortnight does not gain the line: `events.csv` puts a row in the bin
  an event falls in when that bin is frozen, so an event added after the fact
  reaches the storyline through its own row and not through the fortnight's.

## When something new turns up

A new major event goes in `data/events.csv` as `date,label`. It becomes a
vertical line on every figure and a timeline row in the fortnight it falls in.

If the run reports off-colour exclusions climbing, the colour rule has gone
stale: a red or green source nobody listed is letting a Mardu build in, or
turning a real list away. Name the count and ask.
