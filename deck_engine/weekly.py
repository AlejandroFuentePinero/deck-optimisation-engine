"""The weekly report on a tracked deck: freeze the numbers, then render them.

Two halves, and the split is the point. Everything numeric is computed here and
committed, so the same week reports the same figures however often it is rebuilt
and a number that moves shows up as a diff rather than as a quiet correction.
The summary at the top is the other half: it is written once a week over the
numbers, in a fixed clause order, and committed beside them.

Rows are appended and never edited. A timeline row written six weeks ago
describes what the engine saw six weeks ago, and a rebuild that would rephrase
it is a rebuild rewriting history. The store can change under a past week for a
real reason, a league dump gaining trophies through its own day being the usual
one, so the frozen row is what the report renders and the store is only ever
asked about weeks that have no row yet.
"""

import csv
import json
import statistics
from datetime import date, timedelta
from math import ceil
from pathlib import Path

from . import config, plots, spotlight, timeline, tracking

WEEKLY_COLUMNS = (
    "week", "lists", "chal", "chal_field", "chal_share", "top8", "top8_field",
    "top8_share", "top16", "trophies", "league_field", "trophy_share",
)
TIMELINE_COLUMNS = ("start", "end", "lists", "kind", "zone", "card", "text")


def deck_dir(deck: str = "blink") -> Path:
    return config.TRACKING_DIR / deck


def last_complete_week(today: str | None = None) -> str:
    """The Monday of the last week that has fully closed.

    The report is generated on a Monday for the week behind it, because MTGO's
    tournament density is on the weekend: a week read before its Sunday is a
    week missing the days that carry most of its evidence.
    """
    day = date.fromisoformat(today) if today else date.today()
    monday = day - timedelta(days=day.weekday())
    return (monday - timedelta(days=7)).isoformat()


def week_label(monday: str) -> str:
    """A week named by the Sunday it closed on.

    Keyed by its Monday everywhere it is stored, that being the bucket the store
    groups on and the name every frozen row and summary file is written under.
    Shown by its Sunday, because a week labelled with the day it opened reads as
    the day the data stops, and the report then looks a week behind itself.
    """
    return (date.fromisoformat(monday) + timedelta(days=6)).isoformat()


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


_COUNTS = ("lists", "chal", "chal_field", "top8", "top8_field", "top16", "trophies", "league_field")
_SHARES = ("chal_share", "top8_share", "trophy_share")


def _numbers(row: dict) -> dict:
    """A frozen weekly row read back as the numbers it froze.

    The file holds text, and everything downstream of it plots, compares and
    formats. Done once here rather than at each reader, so the figures and the
    facts cannot come to disagree about what an empty share means.
    """
    return {**row, **{k: int(row[k]) for k in _COUNTS}, **{k: float(row[k] or 0) for k in _SHARES}}


def weeks_through(db_path: Path, deck: str, report: dict, week: str) -> list[dict]:
    """The weekly rows a report renders: the frozen ones, and the store only for
    a week no run has frozen yet.

    The split this module opens on is only half kept while the plots and the
    table are computed live: the summary is then written from the frozen file
    and printed above figures drawn from the store, and a league dump filling in
    behind a past week moves one and not the other with no diff to show for it.
    A run whose weeks are all frozen reads nothing from the store at all.
    """
    frozen = {row["week"]: _numbers(row) for row in _read(deck_dir(deck) / "weekly.csv")}
    return [
        frozen.get(row["week"], row)
        for row in tracking.weekly(db_path, report["archetype"], report["camp"])
        if row["week"] <= week
    ]


def _append(path: Path, columns: tuple[str, ...], rows: list[dict]) -> int:
    """Add rows the file does not hold yet, leaving the ones it does alone."""
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if fresh:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return len(rows)


def freeze(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    through: str | None = None,
) -> dict:
    """Compute the weeks and fortnights that have closed, and commit the new ones.

    `through` is the last week to freeze, so a run never writes a row for a week
    still gaining lists. Weeks already on file are not recomputed: what was
    reported is what stands.

    One report per directory, which is why the population is the subject's and
    never an argument: a pooled row and a one-camp row in the same `weekly.csv`
    would be two measurements under one column heading, and nothing in the file
    would say which a row was.
    """
    through = through or last_complete_week()
    report = config.REPORTS[deck]
    root = deck_dir(deck)
    weekly_path, timeline_path = root / "weekly.csv", root / "timeline.csv"

    held = {row["week"] for row in _read(weekly_path)}
    weeks = [
        row
        for row in tracking.weekly(db_path, report["archetype"], report["camp"])
        if row["week"] <= through and row["week"] not in held
    ]

    held_bins = {row["start"] for row in _read(timeline_path)}
    rows = []
    # Against the week's Sunday and not its Monday key. A fortnight closing on
    # the reported week's own last day has closed, and compared against the key
    # it reads as still filling: the report would then show the fortnight it is
    # reporting on as in progress, and freeze it a week late under a later run's
    # phrasing.
    closed = week_label(through)
    for entry in timeline.findings(db_path, report):
        if entry["end"] > closed or entry["start"] in held_bins:
            continue
        found = entry["found"] or [{"kind": "stable", "zone": "", "card": "", "text": ""}]
        rows.extend({**entry, **finding} for finding in found)

    return {
        "through": through,
        "weeks_added": _append(weekly_path, WEEKLY_COLUMNS, weeks),
        "timeline_added": _append(timeline_path, TIMELINE_COLUMNS, rows),
    }


def _paper(entries: list[dict], week: str) -> dict | None:
    """The major event that fell in the reported week, with the row it reads against.

    The paper clause was the one clause whose figures were not in this file, so
    it was the one clause written off the rendered page, which is the thing
    `facts` exists to prevent. Nothing in the JSON even said an event had fallen
    in the week, so whether the report got a paper paragraph at all depended on
    the writer remembering.

    The comparison row rides along with its own numbers rather than its label
    alone: the clause quotes both sides, and a label would send the writer back
    to the page for the other half. `placings` is dropped from both, being the
    positional plot's series and no sentence.
    """
    entry = next((row for row in entries if row["week"] == week), None)
    if entry is None:
        return None
    earlier = entries[: entries.index(entry)]
    before = earlier[-1] if earlier else None
    return {
        **{key: value for key, value in entry.items() if key != "placings"},
        "against_row": (
            {key: value for key, value in before.items() if key not in ("placings", "found")}
            if before
            else None
        ),
    }


def facts(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    week: str | None = None,
) -> dict:
    """Everything the summary is written from, as numbers rather than prose.

    The interface between the half of this that is computed and the half that is
    interpreted. A summary written from the rendered page would be a summary of
    whatever the writer happened to notice; written from this, it says the same
    kinds of things about the same figures every week.
    """
    week = week or last_complete_week()
    report = config.REPORTS[deck]
    numbered = [_numbers(row) for row in _read(deck_dir(deck) / "weekly.csv")]
    this = next((row for row in numbered if row["week"] == week), None)
    if this is None:
        return {"week": week, "error": "no frozen week on file; run freeze first"}

    history = sorted((row for row in numbered if row["week"] < week), key=lambda r: r["week"])
    previous = history[-1] if history else None
    # The deck's own history to the reported week and never past it. Taken over
    # the whole file, a week re-rendered in October quotes a baseline that did
    # not exist when it was reported, and clause 2 of a past summary stops being
    # checkable against the report it was written from: Goryo's week of 8 June
    # was written against a median of 13 and the file now says 31.
    median = statistics.median(sorted(row["chal"] for row in history + [this]))
    # The spike is read against the level the deck was just at instead, for the
    # reason `config.TRACK_SPIKE_WEEKS` gives.
    recent = [row["chal"] for row in history[-config.TRACK_SPIKE_WEEKS :]]
    recent_median = statistics.median(recent) if recent else median

    # The versions of the deck the report names but does not read: observability,
    # and already counted in the figures above wherever the population is pooled.
    observed = {}
    for name in report["observe"]:
        rows_ = tracking.weekly(db_path, report["archetype"], name)
        row = next((r for r in rows_ if r["week"] == week), None)
        observed[config.version_name(name)] = {
            "lists": row["lists"] if row else 0,
            "challenge": row["chal"] if row else 0,
            "trophies": row["trophies"] if row else 0,
        }

    frozen = _read(deck_dir(deck) / "timeline.csv")
    latest = max((row["start"] for row in frozen), default=None)
    copying = [row for row in tracking.goldfishing(db_path, report["archetype"],
                                                   report["build_camp"])
               if row["week"] == week]
    played = spotlights_through(week)
    paper = _paper(spotlight.chain(db_path, report, played), week) if played else None

    return {
        "week": week,
        "week_ending": week_label(week),
        "lists": this["lists"],
        "challenge": {
            "lists": this["chal"],
            "share": this["chal_share"],
            "previous_share": previous["chal_share"] if previous else None,
            "median_lists": median,
            "recent_median": recent_median,
            "spiking": this["chal"] >= config.TRACK_SPIKE_MULTIPLE * max(median, recent_median),
        },
        "conversion": {
            "top8": this["top8"],
            "top8_share": this["top8_share"],
            "top16": this["top16"],
            "over_converting": this["top8_share"] > this["chal_share"],
        },
        "leagues": {
            "trophies": this["trophies"],
            "share": this["trophy_share"],
            "previous": previous["trophies"] if previous else None,
        },
        "versions": observed,
        "goldfishing": copying[0] if copying else None,
        "timeline_latest": [row for row in frozen if row["start"] == latest and row["text"]],
        "major_event": paper,
        "excluded_off_colour": tracking.excluded(db_path, report["archetype"]),
    }


_STYLE = """
:root {
  color-scheme: light;
  --surface: #fcfcfb; --panel: #ffffff; --line: #e4e3de;
  --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #86847d;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --flag: #fdf3e7; --flag-line: #eda100;
  --major: #c2410c;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #14140f; --panel: #1a1a19; --line: #34332e;
    --ink: #f5f4ef; --ink-2: #c3c2b7; --ink-3: #8b8a80;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
    --flag: #2a2113; --flag-line: #c98500;
    --major: #f97316;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #14140f; --panel: #1a1a19; --line: #34332e;
  --ink: #f5f4ef; --ink-2: #c3c2b7; --ink-3: #8b8a80;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
  --flag: #2a2113; --flag-line: #c98500;
  --major: #f97316;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--surface); color: var(--ink);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 940px; margin: 0 auto; padding: 40px 24px 72px; }
header { border-bottom: 1px solid var(--line); padding-bottom: 20px; margin-bottom: 28px; }
h1 { font-size: 26px; letter-spacing: -0.02em; margin: 0 0 4px; }
.dek { color: var(--ink-3); font-size: 13px; margin: 0; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em;
     color: var(--ink-3); font-weight: 600; margin: 40px 0 14px; }
.summary { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
           padding: 20px 22px; font-size: 16px; line-height: 1.6; }
.summary p { margin: 0 0 10px; } .summary p:last-child { margin: 0; }
.summary .pending { color: var(--ink-3); font-style: italic; }
.flag { background: var(--flag); border-left: 3px solid var(--flag-line);
        border-radius: 4px; padding: 12px 16px; margin: 0 0 18px; font-size: 14px; }
figure { margin: 0 0 8px; overflow-x: auto; }
figure svg { width: 100%; height: auto; display: block; min-width: 520px; }
table { border-collapse: collapse; width: 100%; font-size: 13px;
        font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--line); }
th:first-child, td:first-child { text-align: left; }
thead th { color: var(--ink-3); font-weight: 600; font-size: 11px;
           text-transform: uppercase; letter-spacing: 0.05em; }
tbody tr:hover { background: var(--panel); }
.scroll { overflow-x: auto; }
.tl td { vertical-align: top; }
.tl td:last-child { text-align: left; }
.tl .none { color: var(--ink-3); }
/* A major event's storyline row, set apart from the fortnights around it. */
.tl .major { color: var(--major); font-weight: 650; }
.open { color: var(--flag-line); font-size: 11px; margin-top: 2px; }
.note { color: var(--ink-3); font-size: 12px; line-height: 1.55; margin: 12px 0 0; }
.tag { display: inline-block; font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase;
       color: var(--ink-3); border: 1px solid var(--line); border-radius: 3px;
       padding: 1px 5px; margin-right: 7px; }
"""


def _found(found: list[dict], stable: str = "Stable against the fortnight before.") -> str:
    """A fortnight's findings as cells, or the sentence that says there were none."""
    marks = "".join(
        f'<div><span class="tag">{row["kind"]}</span>{row["text"]}</div>'
        for row in found
        if row.get("text")
    )
    return marks or f'<span class="none">{stable}</span>'


def _stable(entry: dict) -> str:
    """Why a paper row is empty, which at these populations is usually the sample.

    A bare "stable" on an eight-list event reads as a fetch that failed. The row
    is empty because nothing cleared the bar, and at eight lists the bar is most
    of the event: the gate wants the move to be worth `TRACK_MIN_LISTS` in the
    smaller population, and the adoption share to move `TRACK_ADOPTION_DELTA`,
    whichever of the two asks for more lists. Esper Blink at Amsterdam is eight
    lists against a fortnight of twenty-seven, so five of those eight have to
    change their mind about one card, and its largest move was three.
    """
    floor = min(entry["build_lists"], entry["baseline_lists"])
    needed = max(config.TRACK_MIN_LISTS, ceil(floor * config.TRACK_ADOPTION_DELTA))
    return (
        f"Nothing moved against {entry['against']}: at {floor} lists, the smaller "
        f"of the two, a row needs a shift worth {needed} of them."
    )


def spotlights_through(week: str) -> tuple[dict, ...]:
    """The Spotlights a given week's report may show: played by then, and fetched.

    Cut off at the week for the reason the weekly rows and the timeline are.
    A Spotlight cache is the one input that arrives for every event at once, so
    rebuilt in October without this, the report for the week before Brisbane
    would carry Dallas, an event a fortnight in its own future. A report whose
    past changes under it is a report nobody can cite.

    Fetched, because the report is the week's and has to render on a machine
    that has never pulled a paper event.
    """
    return tuple(
        entry
        for entry in config.MAJOR_EVENTS
        if spotlight.week(entry) <= week and spotlight.cached(entry).exists()
    )


def _spotlights(entries: list[dict], camp: str | None = None, build: str = "") -> str:
    """The paper section: where the deck finished, and the numbers behind it.

    Its own section and its own axis, never the weekly one. A major paper event
    publishes every finisher where a challenge publishes its top 32, so a share
    of its field is a true metagame share and a share of a challenge is already a
    share of a cut. Only `of top 32` is the same quantity the weekly figures
    carry, and it is printed with its own count because thirty-two slots is a
    handful of lists.
    """
    if not entries:
        return ""
    # Which lists the counts are over, said whether or not the report splits its
    # populations. A report reading one version publishes that version's field
    # share under the deck's name, and unsaid it reads as the whole archetype's:
    # Esper Blink took 63 lists to Dallas and the row says 61, the two Orzhov
    # lists being outside the population and nowhere on the page.
    said = " The lists counted here are " + (
        "every version of the archetype"
        if camp is None
        else f"the {config.version_name(camp)} version"
    )
    said += "."
    if build and build != camp:
        said += (
            f" The paper rows in the storyline below are the {config.version_name(build)} "
            f"version's build readings, "
            f"{entries[-1]['build_lists']} of the {entries[-1]['lists']} at the latest event."
        )
    unread = sum(entry["unread"] for entry in entries)
    if unread:
        said += (
            f" {unread} published list(s) could not be read: melee grouped the 75 under a"
            f" heading the fetch does not know, so the boards did not separate and membership"
            f" could not be tested."
        )
    rows = [
        [
            f"{entry['label']}<div class=\"open\">week ending {week_label(entry['week'])}</div>",
            f"{entry['field']:,}",
            str(entry["lists"]),
            f"{entry['field_share']:.1%}",
            f"{entry['cut_lists']}/32" if entry["lists"] else "-",
            "-" if entry["conversion"] is None else f"{entry['conversion']:.2f}x",
            f"#{entry['best']}" if entry["best"] else "-",
            f"{entry['wins']}-{entry['losses']}-{entry['draws']}",
            "-" if entry["win_rate"] is None else f"{entry['win_rate']:.1%}",
            "-" if entry["field_win_rate"] is None else f"{entry['field_win_rate']:.1%}",
        ]
        for entry in entries
    ]
    return f"""<h2>Major competitive events (paper)</h2>
<figure>{plots.spotlight_finishes(entries)}</figure>
{_table(
    ["Event", "Field", "Lists", "of field", "Top 32", "Conversion", "Best",
     "Match record", "Win rate", "Field win rate"],
    rows,
)}
<p class="note"><em>Conversion</em> is the deck's share of the top 32 over its share of the whole
field, so above 1.00 it held more of the cut than of the room. Win rate counts
match wins and losses as played, the top cut included, because points stop
accruing at the cut and would score the event's winner below the Swiss leader.{said}</p>"""


def _table(columns: list[str], rows: list[list[str]], klass: str = "") -> str:
    head = "".join(f"<th>{c}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return (
        f'<div class="scroll"><table class="{klass}"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _population(build: str, built: list[dict]) -> str:
    """Which version a build reading was taken on, said where the reader is looking.

    Empty where the report reads one population throughout, which is every
    report whose pooled figures and build figures are the same lists. Where they
    differ the note is not optional: the figures above a storyline row would
    otherwise put a list count beside it that the row was never read against.
    """
    if not build:
        return ""
    return (
        f'<p class="note">Read on the {config.version_name(build)} version alone, '
        f"{sum(row['lists'] for row in built)} lists since the Modern bans, where the volume "
        f"and performance figures are the whole archetype's. Pooled, a card at nine tenths of "
        f"one version and none of another would read as the deck at half of it, and a version "
        f"arriving would read as the deck changing its mind.</p>"
    )


def render(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    week: str | None = None,
) -> Path:
    """Build the week's HTML from the frozen rows, the store and the summary."""
    week = week or last_complete_week()
    report = config.REPORTS[deck]
    archetype, camp, build = report["archetype"], report["camp"], report["build_camp"]
    root, name = deck_dir(deck), report["name"]
    weeks = weeks_through(db_path, deck, report, week)
    copying = [
        row for row in tracking.goldfishing(db_path, archetype, build) if row["week"] <= week
    ]
    marks = timeline.events()
    # Every version of the deck the subject names: the one its figures are read
    # on, where it reads one, and the ones it only observes. Split out for the
    # presence figure and nowhere else, no reading in the report being taken
    # over a version the subject does not name.
    versions = [
        (config.version_name(name),
         [row for row in tracking.weekly(db_path, archetype, name) if row["week"] <= week])
        for name in ((camp, *report["observe"]) if camp else report["observe"])
    ]
    reading = facts(db_path, deck, week)
    played = spotlights_through(week)
    spotlights = spotlight.chain(db_path, report, played) if played else []
    # Named only where the two differ, which is where a reader would otherwise
    # have to guess which population a figure was taken over.
    split = build if camp != build else ""

    summary_path = root / "summary" / f"{week}.md"
    summary = (
        "".join(f"<p>{line}</p>" for line in summary_path.read_text(encoding="utf-8").split("\n\n"))
        if summary_path.exists()
        else '<p class="pending">No summary written for this week yet.</p>'
    )
    banner = ""
    if reading.get("challenge", {}).get("spiking"):
        banner = (
            f'<p class="flag"><strong>Volume is elevated.</strong> '
            f'{reading["challenge"]["lists"]} finishes in swiss-like tournaments against a '
            f'median of {reading["challenge"]["recent_median"]:g} over the '
            f"{config.TRACK_SPIKE_WEEKS} weeks behind it and "
            f'{reading["challenge"]["median_lists"]:g} since the Modern bans. Performance '
            f"figures taken over a spike measure how many pilots copied the deck, not how "
            f"good it is.</p>"
        )

    frozen: dict[tuple[str, str], list[dict]] = {}
    for row in _read(root / "timeline.csv"):
        frozen.setdefault((row["start"], row["end"]), []).append(row)
    # The fortnight the reported week sits in has usually not closed, so it has
    # no frozen row and would leave the meeting looking at a timeline up to a
    # fortnight behind the plots. It is shown from the store instead, marked for
    # what it is: a reading that can still move, unlike every row above it.
    running = [
        entry
        for entry in timeline.findings(db_path, report)
        if entry["start"] <= week and (entry["start"], entry["end"]) not in frozen
    ]
    # Fortnights and Spotlights in one sequence, ordered by the day each closed.
    # A Spotlight is a week rather than a fortnight and is read against the entry
    # before it rather than against the bin it falls inside, so it enters the
    # storyline as its own row instead of being folded into one.
    # Ordered on the day each period closed, then on the day it opened, so a
    # Spotlight week and the fortnight it falls inside sort by their own dates
    # rather than by however their labels happen to compare.
    entries = [
        (entry["end"], entry["start"],
         f"{entry['start']} to {entry['end']}<div class=\"open\">in progress</div>",
         _found(entry["found"]))
        for entry in running
    ] + [
        (end, start, f"{start} to {end}", _found(found)) for (start, end), found in frozen.items()
    ] + [
        (
            week_label(entry["week"]),
            entry["week"],
            f'<span class="major">{entry["label"]}</span>',
            _found(entry["found"], _stable(entry)),
        )
        for entry in spotlights
    ]
    timeline_rows = [
        [period, found]
        for _, _, period, found in sorted(entries, key=lambda row: row[:2], reverse=True)
    ]

    body = f"""<div class="page">
<header>
  <h1>{name}</h1>
  <p class="dek">Week ending {week_label(week)} &middot; built {date.today().isoformat()}</p>
</header>

<h2>This week</h2>
{banner}<div class="summary">{summary}</div>

<h2>Presence</h2>
<figure>{plots.presence(weeks, marks, versions)}</figure>

<h2>Conversion</h2>
<figure>{plots.conversion(weeks, marks)}</figure>

<h2>Goldfishing</h2>
<figure>{plots.goldfishing(copying, marks)}</figure>
{_population(split, copying)}

<h2>The numbers (MTGO)</h2>
{_table(
    ["Week ending", "Lists", "Top 32", "of field", "Top 8", "of field",
     "Top 16", "Trophies", "of field"],
    [[
        week_label(row["week"]), str(row["lists"]), str(row["chal"]), f'{(row["chal_share"] or 0):.1%}',
        str(row["top8"]), f'{(row["top8_share"] or 0):.1%}', str(row["top16"]),
        str(row["trophies"]), f'{(row["trophy_share"] or 0):.1%}',
    ] for row in reversed(weeks)],
)}
{_spotlights(spotlights, camp, build)}
<h2>What changed</h2>
{_table(["Period", "Findings"], timeline_rows, "tl")}
{_population(split, copying)}

</div>"""

    html = (
        f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{name}, week ending {week_label(week)}</title><style>{_STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORT_DIR / f"{deck}-{week}.html"
    partial = out.with_suffix(".partial")
    partial.write_text(html, encoding="utf-8")
    partial.replace(out)
    return out


def write_facts(reading: dict, deck: str = "blink") -> Path:
    """The week's numbers on disk, for the summary to be written from."""
    path = config.REPORT_DIR / f"{deck}-facts-{reading['week']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reading, indent=2, default=str), encoding="utf-8")
    return path
