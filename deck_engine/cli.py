"""Terminal entry points: refresh a day, then ask what Goryo's did."""

import argparse

from . import config
from .refresh import refresh
from .store import goryos_lists


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="deck-engine", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("refresh", help="cache a day's events and rebuild the store")
    fetch.add_argument("day", help="YYYY-MM-DD")

    query = commands.add_parser("goryos", help="show the archetype's published lists")
    query.add_argument("--date", help="restrict to one day (YYYY-MM-DD)")

    args = parser.parse_args(argv)
    if args.command == "refresh":
        refresh(args.day)
        print(f"{args.day}: raw cache in {config.RAW_DIR}, store at {config.DB_PATH}")
        return

    rows = goryos_lists(day=args.date)
    for row in rows:
        finish = f"#{row['placement']}" if row["placement"] else row["record"]
        print(f"{row['date']}  {row['event']:<22} {finish:>5}  {row['pilot']}")
    print(f"{len(rows)} Goryo's list(s)")
