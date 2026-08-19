# Deck Optimisation Engine

Mines published MTGO decklists to inform deckbuilding decisions for one Modern
archetype ahead of a paper tournament. It caches every published Modern event,
rebuilds a DuckDB store from that cache, and answers a fixed set of questions
about what the archetype's camps are registering: what they play, what they have
moved off, who is going against the herd, and where the pilot's own 75 stands
against its camp.

It is a working research tool built for one pilot and one deck, not a product.
It is public because the honest parts of it (the domain model, the statistics,
and the audit of what this data source cannot do) are more useful shared than
sitting in a private repo.

## Read this before you trust a number

This engine is a precise adoption-measurement device, and adoption is not
performance. Published decklists are conditioned on winning: challenges publish
only the top 32, leagues only 5-0s, and losing lists never appear at all.

A full audit of the engine against its own database, alongside a survey of
twenty years of Magic analytics tooling, is in
[`docs/postmortem-2026-08-08.md`](docs/postmortem-2026-08-08.md). Its verdict:

> The audit largely vindicates the engineering and condemns the premise. The
> statistics are honest, the populations are correctly scoped, and the
> instruments print their own detection floors. But every performance instrument
> in the engine is running at 6-9% statistical power against effects ten times
> smaller than its detection floor, on a sample conditioned on winning.

So the readings that hold up are the adoption ones: what a camp registers, how
that moved between two windows, which cards are climbing, who plays what, and
where a reference list deviates from its camp. Every reading that claims to be
about performance (outcome contrast, performance tilt, conversion gap) prints
its own detection floor, and at these populations the floor is usually wider
than any effect a flex slot could produce. Read those as disconfirmation
instruments: they can rule out a large effect, and they will almost never
confirm that something helps.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/AlejandroFuentePinero/deck-optimisation-engine.git
cd deck-optimisation-engine
uv sync
```

## Quickstart

The store and the raw cache are not committed, so a fresh clone builds them:

```bash
# Fetch every published Modern event since HISTORY_START and rebuild the store.
# The first run is a six-month backfill: hundreds of events, expect it to be slow.
uv run deck-engine refresh

# What the archetype published, and what the engine flagged about it.
uv run deck-engine goryos
uv run deck-engine flags

# The pilot's own 75, audited against its camp, least-backed slot first.
uv run deck-engine reference

# All of the above as one self-contained HTML file under reports/.
uv run deck-engine report
```

Later runs are cheap: `refresh` refetches only the unsettled window (the last
few days, which are still gaining lists) plus anything new.

## Commands

Every reading names the population it was taken over: one camp, in one stratum,
over one window. A share across two of anything is a number no population
reported, and the engine will not print one.

### Ingest

| Command | What it does |
| --- | --- |
| `refresh [--since D] [--until D]` | Cache published events into `data/raw/`, rebuild the store, update the ingest index |
| `meta-ingest FILE --captured-on D --window-days N` | Record a hand-transcribed MTGGoldfish meta snapshot |
| `reference-capture FILE` | File an exported 75 as the next reference list version |
| `gamelogs` | Parse the pilot's own MTGO `Match_GameLog` files into match records |

### Reading the field

| Command | What it does |
| --- | --- |
| `goryos [--date D]` | The archetype's published lists |
| `card NAME [--main N --side N --board B]` | Everything the engine knows about one card in one camp |
| `substitution NAME --main N --side N` | What the camp's lists that went elsewhere on that slot played instead |
| `migrations` | Cards the camp is moving between mainboard and sideboard |
| `climbing` | Cards new to the pool that the camp is still taking up |
| `flags` | The ledger: hype spikes, fringe cards, pet tech, breakthroughs |
| `lineage` | Departures traced through to what the field then did with them |
| `meta-trend [ARCHETYPE] [--window-days N]` | An archetype's meta share across the snapshot history |

### Reading the 75

| Command | What it does |
| --- | --- |
| `reference` | Audit every flex slot against its camp, plus missing core slots, as a playtest queue |
| `unplayed` | Cards a real part of the camp plays that the reference list runs none of |
| `hypotheses` | Tracked claims, their evidence log, and the clock to submission |
| `hypothesis-evidence ID --source S [--note ...]` | Append a dated entry to a record's log |
| `hypothesis-rule ID --status S --verdict ...` | Close a record with a decision for the 75 |
| `report [--on D]` | Render the whole run as one self-contained HTML file |

`--camp` defaults to the reference list's camp on every command that takes it.

## Documentation

| File | What it holds |
| --- | --- |
| [`CONTEXT.md`](CONTEXT.md) | The glossary. Every term the code and the output use, defined once. Read this first |
| [`HEURISTICS.md`](HEURISTICS.md) | Pilot knowledge from play that decides how the numbers are read, and which is not derivable from the data |
| [`docs/adr/`](docs/adr/) | Architecture decisions. ADR 0001 is what four days of backfill established about the MTGO stream |
| [`docs/postmortem-2026-08-08.md`](docs/postmortem-2026-08-08.md) | The audit of what published decklists can and cannot optimise |
| [`docs/agents/`](docs/agents/) | Conventions for the coding agents that work on this repo |
| [`hypotheses/`](hypotheses/) | One file per tracked claim about the 75: the claim, the evidence log, the verdict |

`CONTEXT.md` is not optional reading. The vocabulary is load-bearing: "adoption"
and "performance tilt" and "camp" and "fresh window" all mean one specific thing
here, and several terms carry an explicit `_Avoid_` line naming the near-synonym
that would blur a real distinction.

## Layout

```
deck_engine/        the package
  mtgo.py           network: discover and fetch event payloads
  parse.py          payloads to decklist records
  refresh.py        cache a range of days, then rebuild the store
  store.py          the DuckDB store, rebuilt from the cache every run
  classify.py       archetype membership, then camp within it
  flags.py          hype, fringe, pet tech, breakthroughs
  ledger.py         what the engine has raised, and when it first said so
  index.py          the committed record of what the cache holds
  movement.py       migrations, substitutions, climbing cards
  outcome.py        outcome contrast and its detection floor
  pilots.py         the readings that are about pilots rather than shares
  meta.py           dated MTGGoldfish snapshots
  reference.py      the pilot's own 75, versioned
  hypotheses.py     the tracked claims and their evidence logs
  gamelogs.py       the pilot's own MTGO match logs to match records
  report.py         one run as one self-contained HTML file
  config.py         every named threshold, in one file
data/               index.csv and meta/ are committed; the cache and store are not
reference/          the pilot's 75, one append-only capture per version
hypotheses/         one Markdown record per tracked claim
scripts/            one-off analyses that write to nothing
tests/              163 tests over committed MTGO payload fixtures
```

## Data

**Committed:** the ingest index (`data/index.csv`, one row per published list the
cache holds), the flag ledger (`data/flags.json`), the hand-transcribed meta
snapshots (`data/meta/`), the reference list captures, and the hypothesis
records. Each of these is either the engine's own memory, which no cache can
rebuild, or a transcription that cannot be fetched again.

**Not committed:** the raw payload cache (`data/raw/`, hundreds of megabytes),
the DuckDB store, and the rendered reports. All three are derived and
rebuildable from `refresh`.

**Deliberately excluded:** the pilot's own MTGO client logs (`data/gamelogs/`)
and what parses out of them. Those contain opponent logins, which is other
people's data, and they are restorable from the MTGO client machine.

The committed index and ledger do carry MTGO pilot logins, because a list
without the pilot who registered it cannot support any of the pilot-level
readings. Those logins are exactly as MTGO publishes them on its own public
decklist pages.

### Fetching etiquette

`refresh` reads public event pages from `mtgo.com` and parses the JSON payload
each page embeds. There is no API and no key. It retries a page up to five times
with lengthening backoff, because the site intermittently serves a 200 whose
content is missing, and a stub taken at face value silently drops published
lists from the cache. It is a sequential scraper with no parallelism, so a
backfill is slow by construction. Please keep it that way.

## Repointing it at another archetype

Every threshold and every rule is named in
[`deck_engine/config.py`](deck_engine/config.py), which is the file to edit:
signature cards and the membership rule, the divergence card the camps fork on,
the window lengths, the regime boundary, and the bar each flag is raised at.

Two caveats before you do. The heuristic that single-card adoption is readable
at all is specific to this archetype: it holds because the shell is heavily
optimised and only a few flex slots move (see `HEURISTICS.md`). And every
population bar in `config.py` was drawn against a camp of forty-odd lists, so an
archetype with a different publication volume needs them redrawn rather than
inherited.

## Tests

```bash
uv run pytest
```

163 tests over committed MTGO payload fixtures. The network layer is excluded
from the test seam by design and is verified by spot-checking fetched counts
against the live site; the calendar rule deciding which month may legitimately
have no index yet is not network, and is tested.

## Licence

[MIT](LICENSE).

Not affiliated with or endorsed by Wizards of the Coast. Magic: The Gathering
and MTGO are trademarks of Wizards of the Coast LLC. Card names and decklist
data are the property of their respective owners.
