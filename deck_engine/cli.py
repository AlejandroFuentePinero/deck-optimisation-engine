"""Terminal entry points: refresh a day, then ask what Goryo's did."""

import argparse
from pathlib import Path

from . import config, flags, meta, reference
from .refresh import refresh
from .store import build, goryos_lists, meta_trend


def _flag_line(flag: dict) -> str:
    """One flag as a line, saying which reading raised it and where that leaves it.

    A hype flag's two shares are the league stratum's and its state is the
    challenge stratum's verdict, so the line names the stratum each came from:
    unlabelled beside one another they would read as one figure moving, which is
    the blend the two strata are kept apart to prevent.
    """
    where = f"{flag['camp']:<12} {flag['card']} {flag['main']}/{flag['side']}"
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

    commands.add_parser("flags", help="the hype watchlist and the fringe appearances")

    commands.add_parser("reference", help="audit the reference list against its camp")

    filed = commands.add_parser("reference-capture", help="file an export as the next version")
    filed.add_argument("source", type=Path, help="the exported 75, in the published format")

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
        ledger = flags.load()
        for flag in ledger:
            print(_flag_line(flag))
        print(f"{len(ledger)} flag(s); run refresh to bring them up to date")
        return

    if args.command == "reference-capture":
        captured = reference.capture(args.source)
        print(f"reference list v{captured.version} at {captured.path}")
        _reference_log()
        return

    if args.command == "reference":
        captured = reference.current()
        audited = reference.slots(captured)
        queue = reference.playtest_queue(audited)
        print(f"reference list v{captured.version}, {captured.path.name}")
        _reference_log()
        # The reading names its own terms: a share of a camp, in a stratum, over
        # a window is a different number from a share of any other three.
        print(
            f"{audited[0]['camp']} camp, {audited[0]['stratum']},"
            f" {audited[0]['population']} list(s) in the fresh window"
        )
        print(f"{sum(row['core'] for row in audited)} core, {len(queue)} flex, least backed first")
        for slot in queue:
            print(_slot_line(slot))
        return

    rows = goryos_lists(day=args.date)
    for row in rows:
        finish = f"#{row['placement']}" if row["placement"] else row["record"]
        swiss = f"{row['swiss_points']:>3}pts" if row["swiss_points"] is not None else " " * 6
        print(f"{row['date']}  {row['event']:<22} {finish:>5} {swiss}  {row['pilot']}")
    print(f"{len(rows)} Goryo's list(s)")
