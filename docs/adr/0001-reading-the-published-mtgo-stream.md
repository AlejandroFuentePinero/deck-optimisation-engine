# ADR 0001: Reading the published MTGO stream

Status: accepted (2026-08-07)

## Context

The backfill of every published Modern event from 2026-02-01 to 2026-08-07 gave
the first full look at the source: 505 events, 19,551 lists, every day of the
range covered, spanning the 2026-05-18 regime boundary. Four properties of that
stream were verified from the data rather than assumed, because each one decides
how the numbers downstream may be read.

**The points column is Swiss-only.** Challenge-class standings publish a `score`
of 3 per Swiss win (every total observed is a multiple of 3; no drawn rounds
appear in the range). The playoff never touches it: in 210 of the 318
challenge-class events the winner holds fewer points than someone who finished
below them. The 2026-08-05 challenge `12850696` is the plain case, won by
BowBloBiw on 15 points over JustAnotherGuy83 on 18.

**League dumps are published without dedup.** Across 188 dumps and 254,269
within-dump pairs, 649 pairs share an identical mainboard inside the same dump:
502 from different pilots, 147 from a pilot who went 5-0 twice that day. Another
335 pairs differ by one or two cards. Nothing is collapsed before publication.

**An event is sometimes listed under a second, wrongly dated slug.** Four events
appeared twice, e.g. the 2026-07-08 challenge also listed as 2026-07-24. Both
slugs serve the same payload, and that payload's `site_name` names the event it
really is. The duplicates were later withdrawn from the index, having already
been fetched.

**A league dump grows through its own day.** The 2026-08-07 dump held 7 lists
when first captured and 10 lists an hour later, while the completed 2026-08-06
dump stayed at 58 across the same interval. Its 5-0s are published as they
finish, so a day captured while it is still running is a partial capture. The
site also publishes on US time while this runs on Australian time, which puts
the local date up to a day ahead of the site's. It catches up within the local
day: the 08-07 dump was already serving 12 lists at 15:18 local on 2026-08-07.
Every one of the seven months backfilled publishes an event dated its first, so
a new month's index is populated before local time leaves the first.

**The site intermittently serves a 200 whose content is missing:** a month index
listing no events, or an event page whose payload holds metadata and no lists.
Ten such stubs were cached before this was caught. Which pages stub moves around
and does not always clear inside five attempts: one run found the 08-04, 08-05
and 08-06 league dumps all stubbed, and minutes later 08-04 and 08-05 served
their 62 and 41 lists while 08-06 and 08-07 had begun stubbing instead.

## Decision

- Swiss points are the performance lens for challenge-class evidence, and are
  named as Swiss points everywhere. Points-weighted adoption measures Swiss
  performance only; the playoff is visible in `placement` and nowhere else.
- League lists load exactly as published. The pipeline never dedups a dump, so a
  configuration's league count is a publication count, in which repeat 5-0s by
  one pilot are real observations of pilot affinity rather than noise to remove.
- An event's identity is the `site_name` its payload publishes, never the slug it
  was fetched under. The raw cache keeps both slugs, since it records what the
  site served; the store loads the event once.
- A fetch is complete only when the page carries what was asked for: an index
  listing events, an event payload holding lists. Anything else is retried, and
  a refresh that cannot reach an event caches the rest and then fails naming the
  gap, so an incomplete run is never mistaken for a complete one.
- A month beginning today or later is one the site has not opened yet, so its
  index failing to serve is not a failure. Local time turns the month over some
  fourteen hours before MTGO does, which puts a run on the local first ahead of
  the site's first event of the month. Every month already open is held to the
  rule above, since there an absent index cannot be told apart from a stub.
- A capture lands whole or not at all: the payload is written beside its slug and
  moved into place. The cache is immutable and keyed on the file being there, so
  a payload half written by a run that died would be kept for good and would
  break every rebuild from then on.
- A gap is an event with nothing on disk. An unsettled day the site will not
  serve keeps the capture it already has and does not fail the run: that refetch
  was for what the day may have gained, not because the capture was wrong, so
  losing it costs nothing. Failing on it would instead fail most daily runs,
  which teaches the reader to ignore the one failure that means something.
- An event is settled, and cached for good, once it is older than
  `config.UNSETTLED_DAYS` (3) days before **today**, not before the end of the
  range asked for. Inside that window it is refetched and overwritten on every
  run, because it may still be growing. A re-run therefore refetches the handful
  of unsettled days and nothing else. A range running past today ends today,
  since the site cannot publish the future.
- `event_class` stays as published (`league`, `challenge-32/64/96`,
  `showcase-challenge`, `showcase-qualifier`, `rc-qualifier`,
  `rc-super-qualifier`, `last-chance`) rather than collapsed into two buckets,
  and challenge-class means every class except `league`.

## Consequences

- Performance tilt and every points-weighted figure carry a Swiss-only caveat
  that the report must state; a playoff run is worth nothing in the points column.
- League adoption over-weights prolific pilots by construction. That is the
  intended reading, and pet-tech and pilot-affinity flags interpret it.
- Counting the raw cache by file over-counts events by four. Count the store.
- The published counts are the site's current ones: the 2026-08-06 league dump
  holds 58 lists today against the 55 recorded when issue #3 was written.
- The freshest days in the store are provisional until they settle, and the last
  three days cost a handful of refetches per run. If MTGO ever publishes a 5-0
  more than three days late, that list is lost; nothing observed suggests it
  does, and the window is a config value.
- An index that lists no events cannot be told apart from a stub, so the
  rollover tolerance is drawn on the calendar and closes at the end of the local
  first. The stream above says that is the whole of the window: the month's
  index is populated before local time leaves the first. Widening the tolerance
  to any month that lists no events would instead let a stub drop a month.
- A `.partial` file is left behind by a run that died mid-write. Nothing reads
  it, since the cache loads `*.json`, and the next run overwrites it.
