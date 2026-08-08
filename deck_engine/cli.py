"""Terminal entry points: refresh a day, then ask what Goryo's did."""

import argparse
from pathlib import Path

from . import config, hypotheses, ledger, meta, reference
from .refresh import refresh
from .store import build, goryos_lists, meta_trend


def _breakthrough_line(flag: dict) -> str:
    """One list that departed from its camp's build and finished, and what the
    field then did about it.

    The camp named is the one the departure was measured against, which for a
    hybrid experiment or a near-miss list is the camp it came out nearest to
    rather than one it was ever registered in. The delta and the mode go beside
    it because the two modes are not the same claim: five known cards recombined
    and one card nobody plays are different kinds of news at different bars.
    """
    finish = f"#{flag['placement']}" if flag["placement"] else "5-0"
    where = f"{flag['camp']:<12} {flag['pilot']} {finish}"
    followed = (
        f"  {flag['state']}: {len(flag['followers'])} new pilot(s) on {flag['adopted_card']}"
        if flag["followers"]
        else f"  {flag['state']}"
    )
    # Both directions of the departure print, because the delta counts both: the
    # cards hardly any of the camp plays and the camp's own staples the list ran
    # none of. Only the first of them listed, the figure would contradict itself.
    departed = [f"+{card}" for card, _, _ in flag["novel"]] + [
        f"-{card}" for card in flag["missing"]
    ]
    return (
        f"{flag['date']}  break   {where:<44}"
        f" delta {flag['delta']} ({flag['mode']}): {', '.join(departed)}{followed}"
    )


def _flag_line(flag: dict) -> str:
    """One flag as a line, saying which reading raised it and where that leaves it.

    A hype flag's two shares are the league stratum's and its state is the
    challenge stratum's verdict, so the line names the stratum each came from:
    unlabelled beside one another they would read as one figure moving, which is
    the blend the two strata are kept apart to prevent.
    """
    if flag["kind"] == "breakthrough":
        return _breakthrough_line(flag)

    where = f"{flag['camp']:<12} {flag['card']} {flag['main']}/{flag['side']}"
    if flag["kind"] == "pet-tech":
        # Whose the configuration is, then what that makes of it. The pilots are
        # named rather than counted, since a flag whose whole subject is that the
        # adoption belongs to somebody has to say to whom.
        # The dissenter's finishes are the ones he took registering this, not his
        # record: what raises the hypothesis is what the card did for him.
        dissent = (
            "  hypothesis candidate: "
            + ", ".join(f"{pilot} top-16ed x{n} on it" for pilot, n in flag["dissenters"].items())
            if flag["hypothesis_candidate"]
            else ""
        )
        return (
            f"{flag['appeared_on']}  pet     {where:<44}"
            f" {flag['appearances']} list(s) from {', '.join(flag['pilots'])}{dissent}"
        )

    if flag["kind"] == "hype":
        tilt = "" if flag["tilt"] is None else f" tilt {flag['tilt']:+.3f}"
        return (
            f"{flag['raised_on']}  hype    {where:<44}"
            f" league {flag['from_adoption']:>4.0%} -> {flag['to_adoption']:>4.0%}"
            f"{tilt}  challenge says {flag['state']}"
            f"  after {flag['origin_pilot']} #{flag['origin_placement']}"
            f" {flag['origin_event']} {flag['origin_date']}"
        )
    back = f" back after {flag['absent_days']}d" if flag["returning"] else ""
    return (
        f"{flag['appeared_on']}  fringe  {where:<44}"
        f" {flag['historical_adoption']:>4.0%} of the history{back}  {flag['pilot']}"
    )


def _configuration(pair: tuple[int, int] | None) -> str:
    """A card's copies as the pair the domain reads, or a dash where the version
    does not run the card at all: absent is absent, not a configuration of none."""
    return "-" if pair is None else f"{pair[0]}/{pair[1]}"


def _slot_line(slot: dict) -> str:
    """One audited flex slot: what the camp did with it, and what the pilot said.

    The bucket is a verdict and the share is the evidence, so the two are never
    printed apart. The delta and the tilt sit beside them as the readings they
    are, and neither is folded into the confidence the queue is ordered on.
    """
    delta = "" if slot["delta"] is None else f" delta {slot['delta']:+.2f}"
    tilt = "" if slot["tilt"] is None else f" tilt {slot['tilt']:+.2f}"
    note = f"  {slot['note']}" if slot["note"] else ""
    where = f"{slot['card']} {_configuration((slot['main'], slot['side']))}"
    return f"  {slot['confidence']:>4.0%}  {where:<40} {slot['bucket']:<20}{delta}{tilt}{note}"


def _missing_line(slot: dict) -> str:
    """One camp-core slot the 75 registers no copies of, in the queue beside the
    audited ones and ranked on the same confidence they are.

    No bucket goes in the bucket column, because the four are verdicts on a slot
    the pilot took and a fifth word there would make this the fifth of them.
    What the camp runs goes there instead, and the delta and the tilt follow it
    rather than standing in an audited slot's columns: they are the camp's
    leading configuration's, and the pilot's `0/0` has neither. The note prints
    last, where an audited slot's does, being his reason for leaving the card out.

    Two camp shares print, because the confidence answers to the first of them.
    A camp split over how many can be unanimous on the card while no count of it
    is near-unanimous, and the leading count alone beside a confidence of none
    would read as a figure contradicting itself rather than as a camp agreeing
    on the card and arguing about the number.
    """
    delta = "" if slot["camp_delta"] is None else f" delta {slot['camp_delta']:+.2f}"
    tilt = "" if slot["camp_tilt"] is None else f" tilt {slot['camp_tilt']:+.2f}"
    note = f"  {slot['note']}" if slot["note"] else ""
    where = f"{slot['card']} {_configuration(None)}"
    camp = (
        f"{slot['camp_playing']:.0%} of the camp plays it,"
        f" {slot['camp_adoption']:.0%} on {slot['camp_main']}/{slot['camp_side']}"
    )
    return f"  {slot['confidence']:>4.0%}  {where:<40} {'':<20}{camp}{delta}{tilt}{note}"


def _hypothesis_lines(record: dict) -> list[str]:
    """One record as its claim, where the argument stands, and the log so far.

    The days remaining print beside the status because that is what makes an
    unresolved record a piece of work rather than a note: the 75 is handed in on
    a date, and a claim nobody has ruled on by then is a slot decided by
    default. A decided one has no clock left to run.

    The verdict prints wherever there is one, and not only where the record is
    closed. The two answers are separate: the status is how the evidence came
    out and the verdict is what the 75 does, so a claim the data supported and
    the pilot has already acted on would otherwise sit here saying only that it
    was supported.
    """
    standing = (
        hypotheses.DECIDED
        if record["status"] == hypotheses.DECIDED
        else f"{record['status']}, {record['days_remaining']}d to submission"
    )
    lines = [f"{record['id']:<24} {standing}", f"  {record['claim']}"]
    if record["verdict"]:
        lines.append(f"  the 75: {record['verdict']}")
    if record["conditional_on"]:
        lines.append(f"  conditional on the {record['conditional_on']}")
    # The log's own lines, indented under the day and the source they came from,
    # since a share and a playtest result are only comparable when the reader
    # can see which is which.
    for entry in record["evidence"]:
        lines.append(f"  {entry['on']}  {entry['source']}")
        lines += [f"    {line}" for line in entry["lines"]]
    return lines


def _reference_log() -> None:
    """The change log: what each version of the 75 did to the one before it."""
    for entry in reference.history():
        print(f"v{entry['from_version']} -> v{entry['version']}")
        for change in entry["changes"]:
            print(
                f"  {change['card']:<40} {_configuration(change['before'])}"
                f" -> {_configuration(change['after'])}"
            )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="deck-engine", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("refresh", help="cache published events and rebuild the store")
    fetch.add_argument("--since", default=config.HISTORY_START, help="YYYY-MM-DD")
    fetch.add_argument("--until", help="YYYY-MM-DD, defaults to today")

    query = commands.add_parser("goryos", help="show the archetype's published lists")
    query.add_argument("--date", help="restrict to one day (YYYY-MM-DD)")

    # Both terms are asked for outright: they are what the site does not serve,
    # and a screenshot stamped with the wrong window cannot be captured again.
    ingest = commands.add_parser("meta-ingest", help="record a dated MTGGoldfish meta snapshot")
    ingest.add_argument("source", type=Path, help="transcribed archetype, meta_pct, deck_count")
    ingest.add_argument("--captured-on", required=True, help="YYYY-MM-DD the table was read")
    ingest.add_argument("--window-days", type=int, required=True, help="the window it reads")

    trend = commands.add_parser("meta-trend", help="an archetype's share across the history")
    trend.add_argument("archetype", nargs="?", default=config.META_ARCHETYPE)
    trend.add_argument("--window-days", type=int, default=config.META_WINDOW_DAYS)

    commands.add_parser("flags", help="the ledger: hype, fringe, pet tech and breakthroughs")

    commands.add_parser("reference", help="audit the reference list against its camp")

    filed = commands.add_parser("reference-capture", help="file an export as the next version")
    filed.add_argument("source", type=Path, help="the exported 75, in the published format")

    commands.add_parser("hypotheses", help="the tracked claims, their evidence and their clock")

    logged = commands.add_parser("hypothesis-evidence", help="append an entry to a record's log")
    logged.add_argument("hypothesis", help="the record's id")
    logged.add_argument("--source", choices=hypotheses.SOURCES, required=True)
    logged.add_argument("--note", help="what the pilot found; a data entry takes its own reading")
    logged.add_argument("--on", help="YYYY-MM-DD the entry is dated, defaults to today")

    ruled = commands.add_parser("hypothesis-rule", help="close a record with a decision for the 75")
    ruled.add_argument("hypothesis", help="the record's id")
    ruled.add_argument("--status", choices=hypotheses.STATUSES, required=True)
    ruled.add_argument("--verdict", required=True, help="what the 75 does about it")

    args = parser.parse_args(argv)
    if args.command == "refresh":
        refresh(args.since, args.until)
        print(f"since {args.since}: raw cache in {config.RAW_DIR}, store at {config.DB_PATH}")
        return

    if args.command == "meta-ingest":
        path = meta.ingest(args.source, args.captured_on, args.window_days)
        build()
        print(f"{args.window_days}-day meta of {args.captured_on} at {path}, store rebuilt")
        return

    if args.command == "meta-trend":
        snapshots = meta_trend(args.archetype, window_days=args.window_days)
        for row in snapshots:
            print(f"{row['captured_on']}  {row['share']:>6.1%}  {row['deck_count']:>4} decks")
        print(f"{len(snapshots)} {args.window_days}-day snapshot(s) of {args.archetype}")
        return

    if args.command == "flags":
        recorded = ledger.load()
        for flag in recorded:
            print(_flag_line(flag))
        print(f"{len(recorded)} flag(s); run refresh to bring them up to date")
        return

    if args.command == "reference-capture":
        captured = reference.capture(args.source)
        print(f"reference list v{captured.version} at {captured.path}")
        _reference_log()
        return

    if args.command == "hypotheses":
        records = hypotheses.standing()
        for record in records:
            print("\n".join(_hypothesis_lines(record)))
        unresolved = [r for r in records if r["status"] != hypotheses.DECIDED]
        print(
            f"{len(unresolved)} of {len(records)} hypothesis(es) unresolved,"
            f" {config.SUBMISSION_DATE} to submit"
        )
        return

    if args.command == "hypothesis-evidence":
        hypotheses.evidence(args.hypothesis, args.source, note=args.note, on=args.on)
        print("\n".join(_hypothesis_lines(hypotheses.read(hypotheses.record_path(args.hypothesis)))))
        return

    if args.command == "hypothesis-rule":
        ruled = hypotheses.rule(args.hypothesis, args.status, args.verdict)
        print("\n".join(_hypothesis_lines(ruled)))
        return

    if args.command == "reference":
        captured = reference.current()
        audited = reference.slots(captured)
        missing = reference.missing_core(captured)
        queue = reference.playtest_queue(audited + missing)
        print(f"reference list v{captured.version}, {captured.path.name}")
        _reference_log()
        # The reading names its own terms: a share of a camp, in a stratum, over
        # a window is a different number from a share of any other three.
        print(
            f"{audited[0]['camp']} camp, {audited[0]['stratum']},"
            f" {audited[0]['population']} list(s) in the fresh window"
        )
        cores = sum(row["core"] for row in audited)
        print(
            f"{cores} core, {len(audited) - cores} flex,"
            f" {len(missing)} missing core slot(s), least backed first"
        )
        # One line per slot, missing ones among the rest: they are ranked on the
        # confidence every other line is ranked on, and printing them again in a
        # block of their own would report one slot as two pieces of work.
        for slot in queue:
            print(_missing_line(slot) if slot["missing"] else _slot_line(slot))
        return

    rows = goryos_lists(day=args.date)
    for row in rows:
        finish = f"#{row['placement']}" if row["placement"] else row["record"]
        swiss = f"{row['swiss_points']:>3}pts" if row["swiss_points"] is not None else " " * 6
        print(f"{row['date']}  {row['event']:<22} {finish:>5} {swiss}  {row['pilot']}")
    print(f"{len(rows)} Goryo's list(s)")
