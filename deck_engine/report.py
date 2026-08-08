"""The daily surface: one run, one self-contained HTML file.

Every reading the engine takes already has a terminal command behind it. What
none of them answers is the question a morning actually opens on, which is what
changed and what to test next, and the answer to that is all of them at once and
in one place. So this renders the run rather than computing anything: what is on
the page is what the metric, flag, audit and record layers said, laid out so
that two minutes of skimming reaches the work.

The file carries no asset it does not contain. A report is read on a plane, off
a phone, out of an email a fortnight after the run that wrote it, and one that
fetched a stylesheet would render as whatever the network felt like that day.
"""

from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import config, flags, hypotheses, ledger, reference, store


def _days_between(first: str, second: str) -> int:
    return (date.fromisoformat(second) - date.fromisoformat(first)).days


def _facts(rows: list[tuple[str, str]]) -> str:
    """A block of named values: what each one is, and what it says.

    Not the domain's readings, which are shares of a population over a window
    and arrive in tables carrying their terms. These are the dates, the counts
    and the standings a section is framed by.
    """
    return "<dl>" + "".join(
        f"<dt>{escape(name)}</dt><dd>{escape(value)}</dd>" for name, value in rows
    ) + "</dl>"


def _section(anchor: str, title: str, lead: str, body: str) -> str:
    """One section of the report, under the anchor it is linked by.

    The lead is not decoration: every figure below it is a share of one
    population over one window, and a section that opened straight onto its
    numbers would leave the reader to guess which.
    """
    return (
        f'<section id="{anchor}">'
        f"<h2>{escape(title)}</h2><p class=lead>{escape(lead)}</p>{body}</section>"
    )


def _run(read: dict, today: str) -> str:
    """What this run was taken over, before anything it found.

    The windows hang off the last day the cache holds a list for rather than off
    the clock, so both dates are here: a report read on a quiet Monday covers a
    fortnight ending on the Wednesday before it, and one date alone would date
    that fortnight as today's. The clock is the third reading, since what is left
    before the 75 is handed in is what makes an open question a piece of work.
    """
    return _section(
        "run",
        "This run",
        f"Read on {today}, over the cache as it stood.",
        _facts(
            [
                ("Fresh window", f"{read['fresh_start']} to {read['fresh_end']}"),
                ("Baseline window", f"{read['baseline_start']} to {read['baseline_end']}"),
                (
                    "Last published list",
                    f"{read['as_of']}, {_days_between(read['as_of'], today)} day(s) back",
                ),
                (
                    "Submission",
                    f"{config.SUBMISSION_DATE}, {_days_between(today, config.SUBMISSION_DATE)}"
                    " day(s) to go",
                ),
            ]
        ),
    )


def _record(record: dict) -> str:
    """One tracked claim, where the argument on it stands, and its log.

    The days remaining ride with the status because that pairing is the whole
    reading: a claim nobody has ruled on by submission day is a slot decided by
    default, and a decided record has no clock left to run.

    The verdict prints wherever there is one and not only where the record
    closed, the two answers being separate: the status is how the evidence came
    out, the verdict is what the 75 does about it.

    The log runs newest first. This is the surface a run is read off, so what a
    run added is what a reader has come for; the entries behind it are the
    argument so far and keep their place under it.
    """
    standing = (
        record["status"]
        if record["days_remaining"] is None
        else f"{record['status']}, {record['days_remaining']} day(s) to submission"
    )
    lines = [f"<h3>{escape(record['id'])}</h3>", f"<p class=claim>{escape(record['claim'])}</p>"]
    facts = [("Standing", standing)]
    if record["verdict"]:
        facts.append(("The 75", record["verdict"]))
    if record["conditional_on"]:
        facts.append(("Conditional on", f"the {record['conditional_on']}"))
    lines.append(_facts(facts))
    # Each entry under the day and the source it came from: a share and a
    # playtest result are only comparable when the reader can see which is which.
    lines += [
        f"<p class=entry><b>{escape(entry['on'])} {escape(entry['source'])}</b><br>"
        + "<br>".join(escape(line.strip()) for line in entry["lines"])
        + "</p>"
        for entry in reversed(record["evidence"])
    ]
    return "".join(lines)


def _hypotheses(hypotheses_dir: Path, today: str) -> str:
    """Every record the project is tracking, least clock left first.

    Unresolved ahead of decided, because what is still open is the work: a
    record the pilot has ruled on is on the page as the argument it settled,
    not as something a reader has to do anything about.
    """
    records = hypotheses.standing(hypotheses_dir, today)
    ordered = sorted(records, key=lambda record: (record["days_remaining"] is None, record["id"]))
    unresolved = sum(record["status"] != hypotheses.DECIDED for record in records)
    return _section(
        "hypotheses",
        "Hypotheses",
        f"{unresolved} of {len(records)} record(s) unresolved,"
        f" {_days_between(today, config.SUBMISSION_DATE)} day(s) to submission.",
        "".join(_record(record) for record in ordered),
    )


def _share(value: float | None) -> str:
    """A share as the percentage it is, or nothing where no population reported
    one: a blank cell is a reading that was not taken, and 0% is one that was."""
    return "" if value is None else f"{value:.0%}"


def _signed(value: float | None) -> str:
    """A delta or a tilt, which are movements and so carry their direction."""
    return "" if value is None else f"{value:+.2f}"


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    return (
        "<table><tr>"
        + "".join(f"<th>{escape(head)}</th>" for head in headers)
        + "</tr>"
        + "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in rows
        )
        + "</table>"
    )


def _slot_row(slot: dict) -> tuple[str, ...]:
    """One slot of the queue: what the pilot registered, and what backs it.

    A missing core slot rides in the same row as the slots the pilot took, since
    it is one piece of work and not two, and says the two things that are
    different about it. It has no bucket, because the four are verdicts on a
    slot the pilot took and a fifth word there would make this the fifth of
    them; what the camp does instead stands in that column. And its delta and
    tilt are the camp's leading configuration's rather than the pilot's, whose
    no copies is a configuration adoption never reported and so has neither.
    """
    if slot["missing"]:
        stands = (
            f"{_share(slot['camp_playing'])} of the camp plays it,"
            f" {_share(slot['camp_adoption'])} on {slot['camp_main']}/{slot['camp_side']}"
        )
        return (
            _share(slot["confidence"]),
            f"{slot['card']} -",
            stands,
            _signed(slot["camp_delta"]),
            _signed(slot["camp_tilt"]),
            slot["note"] or "",
        )
    return (
        _share(slot["confidence"]),
        f"{slot['card']} {slot['main']}/{slot['side']}",
        slot["bucket"],
        _signed(slot["delta"]),
        _signed(slot["tilt"]),
        slot["note"] or "",
    )


def _audit(db_path: Path, reference_dir: Path) -> str:
    """The 75 against its own camp, in the order playtesting should reach it.

    The queue is the answer to what to test next, so the section is the queue:
    the audited flex slots and the camp's staples the 75 runs none of, ranked
    together on the one confidence. The core slots the pilot is with his camp on
    are counted and not listed, being the part of the 75 that is not in question.
    """
    captured = reference.current(reference_dir)
    audited = reference.slots(captured, db_path)
    missing = reference.missing_core(captured, db_path)
    queue = reference.playtest_queue(audited + missing)
    cores = sum(row["core"] for row in audited)
    return _section(
        "audit",
        f"Slot audit, v{captured.version}",
        f"The {audited[0]['camp']} camp, {audited[0]['stratum']},"
        f" {audited[0]['population']} list(s) in the fresh window."
        f" {cores} core, {len(audited) - cores} flex,"
        f" {len(missing)} missing core slot(s), least backed first.",
        _table(
            ("Confidence", "Slot", "Where the camp is", "Delta", "Tilt", "The pilot's note"),
            [_slot_row(slot) for slot in queue],
        ),
    )


def _finish(row: dict) -> str:
    """How a list finished, in the terms its own stratum published it under: a
    challenge ranks its top 32, and a league dump publishes 5-0s and no order."""
    return f"#{row['placement']}" if row["placement"] else row.get("record") or "5-0"


def _near_miss(db_path: Path) -> str:
    """The watchlist: lists that mainboarded the namesake and are not the deck.

    What each one dropped is the whole reason to look at it, the drop being the
    construction direction it proposes, so both halves are on the row. None of
    these is a member, and no figure anywhere else in this report counts them.
    """
    watched = [
        row for row in store.near_miss_lists(db_path) if row["date"] >= config.REGIME_BOUNDARY
    ]
    return _section(
        "near-miss",
        "Near misses",
        f"{len(watched)} list(s) mainboarding {config.WATCHLIST_CARD} that miss membership,"
        f" most recent first, back to the {config.REGIME_BOUNDARY} regime boundary."
        " Watched as variant innovation, counted in nothing.",
        _table(
            ("Published", "Pilot", "Event", "Finish", "Kept", "Dropped"),
            [
                (
                    row["date"],
                    row["pilot"],
                    row["event"],
                    _finish(row),
                    ", ".join(row["kept"]),
                    ", ".join(row["dropped"]),
                )
                for row in watched
            ],
        ),
    )


def _answerable_on(flag: dict) -> str | None:
    """The first day the field could answer an open flag, or None where it has
    already answered it.

    The two kinds of flag wait on different data and each names its own. A hype
    flag waits on a weekend of challenge data inside the fortnight it is judged
    over, that being where tournament density is and so where the correction to
    a copied list lands; the midweek challenges after a spike are too thin a
    slice to resolve on. A breakthrough waits on the fortnight the field is
    given to take the departure up, since a departure that went nowhere is a
    verdict the field has to have had the time to reach.

    A flag whose state is a verdict has no clock left to run, which is what
    keeps a resolved episode from carrying a caveat about evidence still coming.
    """
    if flag["kind"] == "hype" and flag["state"] == "raised":
        spike = date.fromisoformat(flag["raised_on"])
        judged = (spike + timedelta(days=days) for days in range(1, config.HYPE_WINDOW_DAYS + 1))
        return next((day.isoformat() for day in judged if day.weekday() in flags.WEEKEND), None)
    if flag["kind"] == "breakthrough" and flag["state"] == "watching":
        closes = date.fromisoformat(flag["date"]) + timedelta(
            days=config.TRENDSETTER_WINDOW_DAYS
        )
        return closes.isoformat()
    return None


def _clock(flag: dict) -> str:
    """What is left to come on an open flag, and whether the 75 will see it.

    A flag the data cannot answer before submission day is the pilot's to
    decide, per the heuristic that a late spike is judged by judgment alone. The
    state without that beside it would read as a verdict still on its way, and
    the pilot would wait out a fortnight that ends after the deck is registered.

    A matured episode has had its weekend and got nothing from it, the fortnight
    after the spike having published too few challenge lists to read a share
    off. There is no day that answers it, so it carries what it is waiting on
    instead: beside `established` and `decayed` the bare word would read as the
    third verdict rather than as the absence of one.
    """
    if flag["kind"] == "hype" and flag["state"] == "matured":
        return "; waiting on a challenge fortnight thick enough to read a share off"
    answerable = _answerable_on(flag)
    if answerable is None:
        return ""
    if answerable > config.SUBMISSION_DATE:
        return f"; not answerable until {answerable}, past submission: pilot judgment alone"
    return f"; answerable {answerable}"


def _hype(recorded: list[dict]) -> str:
    """The hype watchlist: what the field copied, and what the challenges said.

    Every share on the row says which stratum it came from. The spike is the
    league's, that being where copying shows first and hardest, and the state is
    the challenge stratum's verdict on it; unlabelled beside one another the two
    would read as one figure moving, which is the blend the strata are kept
    apart to prevent. The finish is the third reading, since a configuration
    that climbed after nothing visible is drift rather than an episode.
    """
    episodes = [flag for flag in recorded if flag["kind"] == "hype"]
    return _section(
        "hype",
        "Hype watchlist",
        f"{len(episodes)} episode(s), newest spike first. The spike is read in the league"
        " stratum, the state is the challenge stratum's verdict on it.",
        _table(
            (
                "Spiked",
                "Configuration",
                "Camp",
                "League share",
                "Challenge says",
                "Tilt while climbing",
                "The finish it followed",
            ),
            [
                (
                    flag["raised_on"],
                    f"{flag['card']} {flag['main']}/{flag['side']}",
                    flag["camp"],
                    f"{_share(flag['from_adoption'])} -> {_share(flag['to_adoption'])}"
                    f" of {flag['population']} list(s)",
                    flag["state"] + _clock(flag),
                    _signed(flag["tilt"]),
                    f"{flag['origin_pilot']} #{flag['origin_placement']}"
                    f", {flag['origin_event']} {flag['origin_date']}",
                )
                for flag in sorted(episodes, key=lambda flag: flag["raised_on"], reverse=True)
            ],
        ),
    )


def _breakthrough(recorded: list[dict]) -> str:
    """The lists that left their camp's build behind and finished.

    Both directions of the departure print, because the delta counts both: the
    cards hardly any of the camp registered that this list did, and the camp's
    near-unanimous cards it ran none of. Listing only the first, the figure
    beside it would contradict itself.

    The camp named is the one the departure was measured against, which for a
    hybrid or a near-miss is the camp it came out nearest to rather than one it
    was ever registered in. What the field did next is a later and separate
    reading, so it rides beside the departure rather than inside it.
    """
    departures = [flag for flag in recorded if flag["kind"] == "breakthrough"]
    return _section(
        "breakthrough",
        "Breakthroughs",
        f"{len(departures)} departure(s) that performed, newest first. A watched flag is one"
        " the field has not had its fortnight to answer yet.",
        _table(
            ("Published", "Pilot", "Camp read against", "Finish", "Delta", "Departure", "Since"),
            [
                (
                    flag["date"],
                    f"{flag['pilot']}, {flag['event']}",
                    flag["camp"],
                    _finish(flag),
                    f"{flag['delta']} ({flag['mode']})",
                    ", ".join(
                        [f"+{card}" for card, _, _ in flag["novel"]]
                        + [f"-{card}" for card in flag["missing"]]
                    ),
                    (
                        f"{flag['state']}: {', '.join(flag['followers'])} on"
                        f" {flag['adopted_card']}"
                        if flag["followers"]
                        else flag["state"]
                    )
                    + _clock(flag),
                )
                for flag in sorted(departures, key=lambda flag: flag["date"], reverse=True)
            ],
        ),
    )


def _camps(db_path: Path) -> str:
    """How the archetype splits between its camps, newest day first.

    Composition and nothing about performance: it counts who registered what,
    over a population that is only ever the published winners of either stratum.
    The two strata get their own rows, because a league dump publishes an order
    of magnitude more lists than a challenge does and a pooled share would swing
    with which events happened to run that day.

    A day's shares are the whole split on one line, hybrids included: a camp
    losing ground to the experiment is the same news as it losing ground to the
    other camp, and a row per camp would leave the reader adding them up.
    """
    split: dict[tuple[str, str], list[str]] = {}
    for row in store.camp_ratio(db_path):
        if row["date"] < config.REGIME_BOUNDARY:
            continue
        split.setdefault((row["date"], row["stratum"]), []).append(
            f"{row['camp']} {_share(row['share'])} ({row['lists']})"
        )
    return _section(
        "camps",
        "Camp ratio",
        f"The {config.DIVERGENCE_CARD} split per published day, newest first, back to the"
        f" {config.REGIME_BOUNDARY} regime boundary. Per stratum and never pooled across"
        " them. Lists in brackets.",
        _table(
            ("Published", "Stratum", "The split"),
            [
                (day, stratum, ", ".join(camps))
                for (day, stratum), camps in sorted(split.items(), reverse=True)
            ],
        ),
    )


def _meta(db_path: Path) -> str:
    """The archetype's own share of the field, which is the mirror density.

    Read within one window and never across two: a share over 30 days is a
    different measurement from one over 14, so each row carries the terms it was
    taken on. A slot bought on mirror density stays bought only while that
    density stands, which is what a conditional record joins against.
    """
    snapshots = store.meta_trend(config.META_ARCHETYPE, db_path)
    return _section(
        "meta",
        "Meta trend",
        f"{config.META_ARCHETYPE} on MTGGoldfish, over a {config.META_WINDOW_DAYS}-day window,"
        f" oldest snapshot first. {len(snapshots)} reading(s) transcribed by hand.",
        _table(
            ("Captured", "Window", "Share of the field", "Decks in the table"),
            [
                (
                    row["captured_on"],
                    f"{row['window_days']} days",
                    f"{row['share']:.1%}",
                    str(row["deck_count"]),
                )
                for row in snapshots
            ],
        ),
    )


STYLE = """
body { font: 15px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 60rem; padding: 2rem; }
h1 { margin-bottom: 0; }
h2 { border-bottom: 1px solid #ccc; margin-top: 2.5rem; padding-bottom: .2rem; }
p.lead { color: #555; margin-top: .3rem; }
dl { display: grid; gap: .2rem 1rem; grid-template-columns: max-content 1fr; margin: 0; }
dt { color: #555; }
"""


def render(
    db_path: Path = config.DB_PATH,
    reference_dir: Path = config.REFERENCE_DIR,
    hypotheses_dir: Path = config.HYPOTHESES_DIR,
    today: str | None = None,
) -> str:
    """One run's report, whole, as a document that depends on nothing else.

    A cache with nothing published in it is declined rather than rendered, the
    way the slot audit declines a camp that published nothing and for the same
    reason: there are no windows to read over and no camp to read the 75
    against, and a document that rendered anyway would carry sections reporting
    that the archetype plays nothing, which is a claim no population made.
    """
    today = today or date.today().isoformat()
    read = store.windows(db_path)
    if read is None:
        raise ValueError(f"{db_path} holds no published list: there is no run to report")
    recorded = ledger.load(db_path)
    body = (
        _run(read, today)
        + _hypotheses(hypotheses_dir, today)
        + _audit(db_path, reference_dir)
        + _breakthrough(recorded)
        + _hype(recorded)
        + _near_miss(db_path)
        + _camps(db_path)
        + _meta(db_path)
    )
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        f"<title>Goryo's, {escape(today)}</title><style>{STYLE}</style></head>"
        f"<body><h1>Goryo's</h1><p class=lead>Run of {escape(today)}.</p>{body}</body></html>"
    )


def write(
    report_dir: Path = config.REPORT_DIR,
    db_path: Path = config.DB_PATH,
    reference_dir: Path = config.REFERENCE_DIR,
    hypotheses_dir: Path = config.HYPOTHESES_DIR,
    today: str | None = None,
) -> Path:
    """Render the run and land it as the day's report.

    The file is named for the day it read the cache on, so a run does not
    overwrite the evidence of the ones before it. A second run of the same day
    does replace its own file: what a report says is what the cache said when it
    was written, and the later read of one day is the truer one.

    Landed whole or not at all, as every capture in this engine is: a document
    half written by a run that died would still open, and would read as a report
    whose later sections found nothing.
    """
    today = today or date.today().isoformat()
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{today}.html"
    partial = path.with_suffix(".partial")
    partial.write_text(
        render(db_path, reference_dir, hypotheses_dir, today), encoding="utf-8"
    )
    partial.replace(path)
    return path
