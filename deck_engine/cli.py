"""Terminal entry points: refresh a day, then ask what Goryo's did."""

import argparse
from pathlib import Path

from . import config, gamelogs, hypotheses, index, ledger, meta, movement, outcome, reference, report
from .classify import camp as camp_of
from .refresh import refresh
from .store import CHALLENGE_CLASS, adoption, arrivals, build, goryos_lists, meta_trend


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
        tilt = _tilt(flag["tilt"], 3)
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


def _resolved(card: str) -> str:
    """A card asked for by name, under the name the store holds it by.

    The site publishes two printings of one card and the store was built with
    them merged, as every reading of the field is. Asked for under the other
    printing, an unresolved name matches nothing and each reading comes back
    empty: a confident null about a card a third of the camp plays, which is
    worse than an error for reading as an answer.
    """
    return config.CARD_ALIASES.get(card, card)


def _tilt(value: float | None, places: int = 2) -> str:
    """A performance tilt, and nothing at all where it is under the floor.

    Every published list already finished, so the Swiss points a camp's
    fortnight spreads over are bunched and the tilt across this archetype's
    configurations runs to a point or two. A column of figures that size reads
    as a performance lens while carrying none, so what the domain says about it
    is that below the floor it is not displayed. The figure stays on the row;
    what is suppressed is the display of it.
    """
    if value is None or abs(value) < config.TILT_FLOOR:
        return ""
    return f" tilt {value:+.{places}f}"


def _backing(slot: dict) -> str:
    """A slot's share as the count a reader can check it against.

    A verdict taken off forty lists is one a couple of them could reverse and a
    bare percentage reads as a fact, so the count is printed beside every share.
    """
    return f"{slot['lists']}/{slot['population']} ({slot['confidence']:>4.0%})"


def _stands(slot: dict) -> str:
    """What the camp did about the card, beside what it did about the count.

    The reading the exact-configuration share cannot carry, and the terminal was
    printing the share without it. A slot at 8% is two opposite findings and
    only this tells them apart: a card the camp barely plays, or a card it is
    unanimous on where the pilot is a copy light. The second is the actionable
    one and the share alone buries it.
    """
    if slot["camp_main"] is None:
        return "the camp registered none of it"
    return (
        f"{slot['camp_playing']:.0%} play it,"
        f" {slot['camp_adoption']:.0%} on {slot['camp_main']}/{slot['camp_side']}"
    )


def _slot_line(slot: dict) -> str:
    """One audited flex slot: what the camp did with it, and what the pilot said.

    The bucket is a verdict and the share is the evidence, so the two are never
    printed apart, and what the camp did about the card goes beside what it did
    about the count: a deviation from a card the camp barely plays and a copy
    short of one it is unanimous on are the same share and opposite findings.

    A slot whose bucket a list or two would refile says so, since a bucket is a
    categorical claim taken off forty-odd lists and the share alone hides how
    close the call was. The delta and the tilt sit beside them as the readings
    they are, and neither is folded into the confidence the queue is ordered on.
    """
    delta = "" if slot["delta"] is None else f" delta {slot['delta']:+.2f}"
    turns = f"  turns on {slot['boundary']}" if slot["boundary"] else ""
    note = f"  {slot['note']}" if slot["note"] else ""
    where = f"{slot['card']} {_configuration((slot['main'], slot['side']))}"
    return (
        f"  {_backing(slot):<12}  {where:<40} {slot['bucket']:<20}"
        f" {_stands(slot)}{delta}{_tilt(slot['tilt'])}{turns}{note}"
    )


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
    note = f"  {slot['note']}" if slot["note"] else ""
    where = f"{slot['card']} {_configuration(None)}"
    camp = (
        f"{slot['camp_playing']:.0%} of the camp plays it,"
        f" {slot['camp_adoption']:.0%} on {slot['camp_main']}/{slot['camp_side']}"
    )
    return (
        f"  {_backing(slot):<12}  {where:<40} {'':<20}"
        f" {camp}{delta}{_tilt(slot['camp_tilt'])}{note}"
    )


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


# How many of the archetype's arrivals are named before the rest become a count.
# A run against a standing index brings in a day or two and never reaches this;
# the run that does is the first one, whose index was empty and whose arrivals
# are therefore the whole history. That is not news and must not be printed as
# though it were, but it is not nothing either, so what was dropped is counted
# rather than left silent.
NAMED_ARRIVALS = 20


def _ingest_lines(change: index.Change, ours: list[dict]) -> list[str]:
    """What the run brought in: the field as a count, the archetype by name.

    The count is of lists and not of events, because the days hardest to speak
    about are the ones already cached: an unsettled league dump gains 5-0s
    through its own day, so a run reporting events alone would say nothing
    arrived on exactly the day something did. The event count goes beside it
    rather than instead of it, a fresh day and a day that grew being different
    news.
    """
    if not change.added and not change.withdrawn:
        return ["  no list published since the last run"]
    events = {row.event_id for row in change.added}
    lines = [
        f"  {len(change.added)} new list(s) across {len(events)} event(s),"
        f" {len(ours)} of them Goryo's"
    ]
    for row in ours[:NAMED_ARRIVALS]:
        finish = f"#{row['placement']}" if row["placement"] else "5-0"
        lines.append(
            f"    {row['date']}  {row['event']:<26} {finish:<5}"
            f" {row['camp']:<12} {row['pilot']}"
        )
    if len(ours) > NAMED_ARRIVALS:
        lines.append(f"    and {len(ours) - NAMED_ARRIVALS} more, further back")
    if change.withdrawn:
        # Not a gap and not an error: the site republishes an event under a
        # wrongly dated slug and later takes one of them down. Said out loud
        # because lists leaving the history quietly is the same failure as
        # lists arriving quietly, which is what the index exists to stop.
        lines.append(f"  {len(change.withdrawn)} list(s) the site no longer publishes")
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


# The two boards, under the names the store's columns carry rather than the
# names a capture's headings do: this narrows an outcome arm to a column.
BOARDS = ("main", "side")


def _share(value) -> str:
    """A share as the page prints one, or a dash where no population reported it."""
    return "-" if value is None else f"{value:.0%}"


def _signed(value) -> str:
    return "-" if value is None else f"{value:+.2f}"


def _card_lines(card: str, camp: str, main, side, board) -> list[str]:
    """Everything the engine knows about one card in one camp, in one place.

    The question this answers is the one asked most and served worst: a pilot has
    a reason to play something and wants what the field did about it. Four
    readings bear on that and they live in four modules, so a reader assembling
    them by hand gets a share here, a flag there, and no way to see that the two
    are about the same fortnight. They are printed together and each says which
    reading it is.
    """
    lines = [f"{card}, {camp} camp"]

    configured = [
        row
        for row in adoption()
        if row["card"] == card
        and row["camp"] == camp
        and row["stratum"] == CHALLENGE_CLASS
        and (row["fresh_lists"] or row["baseline_lists"])
    ]
    if not configured:
        return lines + ["  the camp has registered no copies of it in either window"]

    lines.append("  what the camp registered, challenge-class:")
    for row in sorted(configured, key=lambda row: -(row["fresh_adoption"] or 0)):
        lines.append(
            f"    {row['main']}/{row['side']}  fresh {row['fresh_lists']:>3}"
            f"/{row['fresh_population']} ({_share(row['fresh_adoption'])})"
            f"  baseline {row['baseline_lists']:>3}/{row['baseline_population']}"
            f" ({_share(row['baseline_adoption'])})  delta {_signed(row['delta'])}"
        )

    moved = movement.migration(card, camp=camp)
    if moved and moved["shift"] is not None:
        lines.append(
            f"  boards: {moved['baseline']['main_copies']} main /"
            f" {moved['baseline']['side_copies']} side"
            f" -> {moved['fresh']['main_copies']} main / {moved['fresh']['side_copies']} side,"
            f" {moved['shift']:+.0%} of copies, {moved['direction']}"
        )

    raised = [
        flag
        for flag in ledger.load()
        if flag.get("card") == card and flag.get("camp") == camp
    ]
    for flag in raised:
        state = f" {flag['state']}" if flag.get("state") else ""
        standing = f", now {flag['standing']}" if flag.get("standing") else ""
        lines.append(
            f"  {flag['kind']} flag on {flag['main']}/{flag['side']}{state}{standing},"
            f" first seen {flag['first_seen']}"
        )

    read = outcome.contrast(card, main, side, board, camp=camp)
    if read["difference"] is None:
        lines.append(f"  outcome ({read['configuration']}): one arm is empty, no contrast to take")
    else:
        lines.append(
            f"  outcome ({read['configuration']}), post-regime challenge-class:"
            f" {read['with_made_band']}/{read['with_lists']}"
            f" ({_share(read['with_rate'])}) top-{read['band']} with it,"
            f" {read['without_made_band']}/{read['without_lists']}"
            f" ({_share(read['without_rate'])}) without"
        )
        # The floor is not decoration. A null under a floor this wide says the
        # camp did not separate by that much, never that the card is neutral.
        lines.append(
            f"    difference {read['difference']:+.1%}, p={read['p']:.3f},"
            f" {read['state']} below a floor of {_share(read['floor'])}"
        )
    conversion = read["conversion"]
    if conversion["gap"] is not None:
        lines.append(
            f"    league conversion gap {conversion['gap']:+.1%}"
            f" (uncapped {conversion['uncapped']:+.1%}, the cap {conversion['cap_effect']})"
        )
    return lines


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

    rendered = commands.add_parser("report", help="render the run as one self-contained HTML file")
    rendered.add_argument("--on", help="YYYY-MM-DD the run is dated, defaults to today")

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

    # The camp every one of these reads against defaults to the reference list's,
    # since a share belongs to one camp and this pilot is in one of them.
    def camped(name, help_text):
        added = commands.add_parser(name, help=help_text)
        added.add_argument("--camp", default=None, help="defaults to the reference list's camp")
        return added

    asked = camped("card", "everything the engine knows about one card in one camp")
    asked.add_argument("card", help="the card, under the name the archetype publishes it")
    asked.add_argument("--main", type=int, help="narrow the outcome arm to one configuration")
    asked.add_argument("--side", type=int)
    asked.add_argument("--board", choices=BOARDS, help="or to a board, for a migration question")

    traded = camped("substitution", "what the camp's lists that went elsewhere played instead")
    traded.add_argument("card")
    traded.add_argument("--main", type=int, required=True)
    traded.add_argument("--side", type=int, required=True)

    camped("migrations", "the cards the camp is moving between the boards")

    camped("climbing", "the cards new to the pool the camp is still taking up")
    camped("lineage", "departures traced through to what the field did with them")
    commands.add_parser("unplayed", help="what a real part of the camp plays that the 75 does not")

    commands.add_parser("gamelogs", help="parse the pilot's own MTGO match logs into records")

    args = parser.parse_args(argv)
    if args.command == "gamelogs":
        matches = gamelogs.load()
        if not matches:
            print(f"no Match_GameLog files under {config.GAMELOG_DIR}")
            return
        landed = gamelogs.write_matches(matches)
        decided = [m for m in matches if m.winner and config.PILOT_LOGIN in m.players]
        won = sum(1 for m in decided if m.winner == config.PILOT_LOGIN)
        print(f"{len(matches)} match log(s), {matches[0].start[:10]} to {matches[-1].start[:10]}")
        print(f"{won}-{len(decided) - won} for {config.PILOT_LOGIN} where the log decides a winner")
        print(f"records at {landed}")
        return

    if args.command == "refresh":
        change = refresh(args.since, args.until)
        print(f"since {args.since}: raw cache in {config.RAW_DIR}, store at {config.DB_PATH}")
        print(f"index at {index.path()}, commit it to keep the run comparable")
        print("\n".join(_ingest_lines(change, arrivals(change.added))))
        return

    if args.command == "meta-ingest":
        path = meta.ingest(args.source, args.captured_on, args.window_days)
        build()
        print(f"{args.window_days}-day meta of {args.captured_on} at {path}, store rebuilt")
        return

    if args.command == "meta-trend":
        # Under the name the store holds the deck by, for the reason `_resolved`
        # gives about printings: the site tables one deck as two archetypes, and
        # asked for under the other name the trend comes back empty rather than
        # wrong, which reads as the field never having played it.
        archetype = config.META_ARCHETYPE_ALIASES.get(args.archetype, args.archetype)
        snapshots = meta_trend(archetype, window_days=args.window_days)
        for row in snapshots:
            print(f"{row['captured_on']}  {row['share']:>6.1%}  {row['deck_count']:>4} decks")
        print(f"{len(snapshots)} {args.window_days}-day snapshot(s) of {archetype}")
        return

    if args.command == "flags":
        recorded = ledger.load()
        for flag in recorded:
            print(_flag_line(flag))
        print(f"{len(recorded)} flag(s); run refresh to bring them up to date")
        return

    if args.command == "report":
        landed = report.write(today=args.on)
        print(f"report at {landed}")
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

    if args.command in ("card", "substitution", "migrations", "climbing", "lineage"):
        camp = args.camp or camp_of(reference.current().mainboard)

    if args.command in ("card", "substitution"):
        args.card = _resolved(args.card)

    if args.command == "card":
        print("\n".join(_card_lines(args.card, camp, args.main, args.side, args.board)))
        return

    if args.command == "substitution":
        rows = movement.substitution(args.card, args.main, args.side, camp=camp)
        if not rows:
            print(f"{args.card} {args.main}/{args.side}: the camp is all on one side of it")
            return
        first = rows[0]
        print(
            f"{args.card} {args.main}/{args.side}, {camp} camp: {first['on_it_lists']} list(s)"
            f" on it, {first['elsewhere_lists']} elsewhere, fresh window"
        )
        # Both ends, because a trade has two: what the lists that went elsewhere
        # reached for, and what they gave up to do it.
        for label, ordered in (("instead", rows[:8]), ("gave up", rows[-8:][::-1])):
            print(f"  {label}:")
            for row in ordered:
                print(
                    f"    {row['card']:<34} {_share(row['on_it'])} on it,"
                    f" {_share(row['elsewhere'])} elsewhere  {row['difference']:+.0%}"
                )
        return

    if args.command == "migrations":
        rows = movement.migrations(camp=camp)
        for row in rows:
            print(
                f"{row['card']:<34} {row['shift']:+.0%} of copies, {row['direction']}"
                f"  {row['baseline']['main_copies']} main /"
                f" {row['baseline']['side_copies']} side"
                f" -> {row['fresh']['main_copies']} main / {row['fresh']['side_copies']} side"
                f"  {row['fresh']['lists']} fresh list(s)"
            )
        print(
            f"{len(rows)} card(s) crossing at least {movement.BOARD_SHIFT:.0%} of their copies"
            f" in the {camp} camp, off {config.MIGRATION_MIN_LISTS}+ lists in both windows"
        )
        return

    if args.command == "climbing":
        rows = movement.climbing(camp=camp)
        for row in rows:
            print(
                f"{row['card']:<34} {row['main']}/{row['side']}"
                f"  {_share(row['adoption'])} of {row['population']} list(s)"
                f"  delta {row['delta']:+.2f}"
            )
        print(f"{len(rows)} card(s) new to the pool and still climbing in the {camp} camp")
        return

    if args.command == "unplayed":
        captured = reference.current()
        rows = movement.unplayed(captured.configurations())
        for row in rows:
            print(
                f"{row['card']:<34} {_share(row['camp_playing'])} of the camp play it,"
                f" {_share(row['camp_adoption'])} on {row['camp_main']}/{row['camp_side']},"
                f" delta {_signed(row['camp_delta'])}"
            )
        dropped = rows[0]["dropped"] if rows else 0
        print(
            f"{len(rows)} card(s) at or above {config.UNPLAYED_FLOOR:.0%} of the"
            f" {rows[0]['camp'] if rows else 'reference'} camp that v{captured.version} runs none of"
            + (f"; {dropped} more below these" if dropped else "")
        )
        return

    if args.command == "lineage":
        for row in ledger.lineage(camp=camp):
            spread = (
                f" -> {row['spread_card']} spiked {row['spiked_on']},"
                f" {row['resolved']}, now {row['standing']}"
                if row["spiked_on"]
                else " -> the field never piled in"
            )
            print(
                f"{row['date']}  {row['pilot']:<18} {row['stratum']:<15}"
                f" delta {row['delta']} ({row['mode']}), {row['followed']}"
                f" {len(row['followers'])}/{row['needed']}{spread}"
            )
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
