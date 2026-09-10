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
from datetime import date, timedelta
from pathlib import Path

from . import config, plots, timeline, tracking

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


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
    variant: str = "esper",
    through: str | None = None,
) -> dict:
    """Compute the weeks and fortnights that have closed, and commit the new ones.

    `through` is the last week to freeze, so a run never writes a row for a week
    still gaining lists. Weeks already on file are not recomputed: what was
    reported is what stands.
    """
    through = through or last_complete_week()
    root = deck_dir(deck)
    weekly_path, timeline_path = root / "weekly.csv", root / "timeline.csv"

    held = {row["week"] for row in _read(weekly_path)}
    weeks = [
        row
        for row in tracking.weekly(db_path, deck, variant)
        if row["week"] <= through and row["week"] not in held
    ]

    held_bins = {row["start"] for row in _read(timeline_path)}
    rows = []
    for entry in timeline.findings(db_path, deck, variant):
        if entry["end"] > through or entry["start"] in held_bins:
            continue
        found = entry["found"] or [{"kind": "stable", "zone": "", "card": "", "text": ""}]
        rows.extend({**entry, **finding} for finding in found)

    return {
        "through": through,
        "weeks_added": _append(weekly_path, WEEKLY_COLUMNS, weeks),
        "timeline_added": _append(timeline_path, TIMELINE_COLUMNS, rows),
    }


def facts(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    week: str | None = None,
) -> dict:
    """Everything the summary is written from, as numbers rather than prose.

    The interface between the half of this that is computed and the half that is
    interpreted. A summary written from the rendered page would be a summary of
    whatever the writer happened to notice; written from this, it says the same
    kinds of things about the same figures every week.
    """
    week = week or last_complete_week()
    rows = _read(deck_dir(deck) / "weekly.csv")
    numbered = [{**row, **{k: float(row[k] or 0) for k in ("chal_share", "top8_share",
                                                           "trophy_share")}} for row in rows]
    this = next((row for row in numbered if row["week"] == week), None)
    if this is None:
        return {"week": week, "error": "no frozen week on file; run freeze first"}

    history = [row for row in numbered if row["week"] < week]
    previous = history[-1] if history else None
    counts = sorted(int(row["chal"]) for row in numbered)
    median = counts[len(counts) // 2]

    other = config.TRACKED_DECKS[deck]["variant_without"]
    orzhov = [row for row in tracking.weekly(db_path, deck, other) if row["week"] == week]

    frozen = _read(deck_dir(deck) / "timeline.csv")
    latest = max((row["start"] for row in frozen), default=None)
    stability = [row for row in tracking.stability(db_path, deck, variant) if row["week"] == week]

    return {
        "week": week,
        "lists": int(this["lists"]),
        "challenge": {
            "lists": int(this["chal"]),
            "share": this["chal_share"],
            "previous_share": previous["chal_share"] if previous else None,
            "median_lists": median,
            "spiking": int(this["chal"]) >= config.TRACK_SPIKE_MULTIPLE * median,
        },
        "conversion": {
            "top8": int(this["top8"]),
            "top8_share": this["top8_share"],
            "top16": int(this["top16"]),
            "over_converting": this["top8_share"] > this["chal_share"],
        },
        "leagues": {
            "trophies": int(this["trophies"]),
            "share": this["trophy_share"],
            "previous": int(previous["trophies"]) if previous else None,
        },
        "orzhov": {
            "lists": orzhov[0]["lists"] if orzhov else 0,
            "challenge": orzhov[0]["chal"] if orzhov else 0,
            "trophies": orzhov[0]["trophies"] if orzhov else 0,
        },
        "stability": stability[0] if stability else None,
        "timeline_latest": [row for row in frozen if row["start"] == latest and row["text"]],
        "excluded_off_colour": tracking.excluded(db_path, deck),
    }


_STYLE = """
:root {
  color-scheme: light;
  --surface: #fcfcfb; --panel: #ffffff; --line: #e4e3de;
  --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #86847d;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --flag: #fdf3e7; --flag-line: #eda100;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #14140f; --panel: #1a1a19; --line: #34332e;
    --ink: #f5f4ef; --ink-2: #c3c2b7; --ink-3: #8b8a80;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
    --flag: #2a2113; --flag-line: #c98500;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #14140f; --panel: #1a1a19; --line: #34332e;
  --ink: #f5f4ef; --ink-2: #c3c2b7; --ink-3: #8b8a80;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
  --flag: #2a2113; --flag-line: #c98500;
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
.tl .open { color: var(--flag-line); font-size: 11px; margin-top: 2px; }
.tag { display: inline-block; font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase;
       color: var(--ink-3); border: 1px solid var(--line); border-radius: 3px;
       padding: 1px 5px; margin-right: 7px; }
footer { margin-top: 48px; padding-top: 20px; border-top: 1px solid var(--line);
         color: var(--ink-3); font-size: 12px; }
footer code { font-size: 11px; }
"""


def _found(found: list[dict]) -> str:
    """A fortnight's findings as cells, or the sentence that says there were none."""
    marks = "".join(
        f'<div><span class="tag">{row["kind"]}</span>{row["text"]}</div>'
        for row in found
        if row.get("text")
    )
    return marks or '<span class="none">Stable against the fortnight before.</span>'


def _table(columns: list[str], rows: list[list[str]], klass: str = "") -> str:
    head = "".join(f"<th>{c}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return (
        f'<div class="scroll"><table class="{klass}"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def render(
    db_path: Path = config.DB_PATH,
    deck: str = "blink",
    variant: str = "esper",
    week: str | None = None,
) -> Path:
    """Build the week's HTML from the frozen rows, the store and the summary."""
    week = week or last_complete_week()
    root, name = deck_dir(deck), f"{variant.title()} {deck.title()}"
    weeks = [row for row in tracking.weekly(db_path, deck, variant) if row["week"] <= week]
    drift = [row for row in tracking.copy_drift(db_path, deck, variant) if row["week"] <= week]
    settled = [row for row in tracking.stability(db_path, deck, variant) if row["week"] <= week]
    marks = timeline.events()
    reading = facts(db_path, deck, variant, week)

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
            f'{reading["challenge"]["lists"]} challenge-class lists against a post-regime '
            f'median of {reading["challenge"]["median_lists"]}. Performance figures taken '
            f"over a spike measure how many pilots copied the deck, not how good it is.</p>"
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
        for entry in timeline.findings(db_path, deck, variant)
        if entry["start"] <= week and (entry["start"], entry["end"]) not in frozen
    ]
    timeline_rows = [
        [
            f"{entry['start']} to {entry['end']}<div class=\"open\">in progress</div>",
            _found(entry["found"]),
        ]
        for entry in sorted(running, key=lambda e: e["start"], reverse=True)
    ] + [
        [f"{start} to {end}", _found(found)]
        for (start, end), found in sorted(frozen.items(), reverse=True)
    ]

    body = f"""<div class="page">
<header>
  <h1>{name}</h1>
  <p class="dek">Week of {week} &middot; MTGO Modern &middot; built {date.today().isoformat()}</p>
</header>

<h2>This week</h2>
{banner}<div class="summary">{summary}</div>

<h2>Presence</h2>
<figure>{plots.presence(weeks, marks)}</figure>

<h2>Conversion</h2>
<figure>{plots.conversion(weeks, marks)}</figure>

<h2>Copies run</h2>
<figure>{plots.copy_drift(drift, marks)}</figure>

<h2>Stability</h2>
<figure>{plots.stability(settled, marks)}</figure>

<h2>What changed, fortnight by fortnight</h2>
{_table(["Fortnight", "Findings"], timeline_rows, "tl")}

<h2>The numbers</h2>
{_table(
    ["Week", "Lists", "Top 32", "of field", "Top 8", "of field", "Top 16", "Trophies", "of field"],
    [[
        row["week"], str(row["lists"]), str(row["chal"]), f'{(row["chal_share"] or 0):.1%}',
        str(row["top8"]), f'{(row["top8_share"] or 0):.1%}', str(row["top16"]),
        str(row["trophies"]), f'{(row["trophy_share"] or 0):.1%}',
    ] for row in reversed(weeks)],
)}

<footer>
<p>Membership: mainboard holds
{", ".join(config.TRACKED_DECKS[deck]["signature"])}, and no red or green source.
The {config.TRACKED_DECKS[deck]["variant_with"]} variant mainboards
{config.TRACKED_DECKS[deck]["variant_card"]}; the
{config.TRACKED_DECKS[deck]["variant_without"]} variant does not. Every reading above is the
{variant} variant alone. {reading.get("excluded_off_colour", 0)} list(s) held the signature and
were turned away on colour.</p>
<p>Challenge-class is every event that publishes a placement, pooled. League trophies are
uncapped, so one pilot's repeats count. Top 8 is shown because it is the band a team talks in;
top 16 is the band this project reads performance evidence at. Timeline findings are detected
over a fortnight, because weekly detection on this population reverses about two times in five
at any threshold. Rows are frozen once written.</p>
</footer>
</div>"""

    html = (
        f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{name}, week of {week}</title><style>{_STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORT_DIR / f"{deck}-{variant}-{week}.html"
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
