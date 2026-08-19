"""Weekly average copies per card, in the two Riddler/Fallaji builds.

A split the project's own camp rule does not draw. The adopted camps fork on
Fallaji Archaeologist at 3-4 against 0, with 1-2 a hybrid experiment; this
reads the field as two builds instead, one carrying the Riddler package with
almost no Fallaji and one carrying Fallaji, and it is the pilot's cut rather
than the engine's. Nothing here writes to the store or the ledger.

Challenge-class only, per the adopted heuristic that league-derived stats are
never blended with challenge stats.
"""

import argparse
import csv
import glob
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from deck_engine import config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RIDDLER, FALLAJI = "Riddler Goryo's", "Fallaji Goryo's"

# The palette validates for line charts at eight slots and no further, so this
# is the cap on how many cards may carry a colour. Past it the reader is being
# asked to tell hues apart that nobody can.
PALETTE_SLOTS = 8


def land_names() -> set[str]:
    """Every card the site itself types as a land, read off the raw cache.

    The store keeps a deck-level land count but no per-card type, so the types
    come from the payloads. Taken from the site rather than a hardcoded list so
    a new land needs no edit here.

    One caveat rides along, the same one `parse.py` carries: the payload types
    the front face, so a modal double-faced card with a land back is typed by
    its spell half. Sink into Stupor is the one this archetype plays and it
    counts as a non-land here.
    """
    names = set()
    for path in glob.glob(str(config.RAW_DIR / "*.json")):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        for deck in payload.get("decklists", []):
            for entry in deck.get("main_deck", []) + deck.get("sideboard_deck", []):
                attrs = entry["card_attributes"]
                if (attrs.get("card_type") or "").strip() == "LAND":
                    name = attrs["card_name"]
                    names.add(config.CARD_ALIASES.get(name, name))
    return names


def week_end(day: str) -> str:
    """The Sunday closing the tournament week a day falls in.

    Bins align to the tournament week because that is how play is distributed
    and where the week's verdict lands, which is the convention `flags.py`
    already reads windows on.
    """
    parsed = date.fromisoformat(day)
    return (parsed + timedelta(days=6 - parsed.weekday())).isoformat()


def panel_of(cards: dict[str, tuple[int, int]]) -> str | None:
    """Which build a list belongs to, on mainboard copies.

    The two are disjoint on the Fallaji count and very nearly exhaust the
    archetype; a list on 0-1 Fallaji that is not also on 3-4 Riddler belongs to
    neither and is dropped rather than forced into one.
    """
    fallaji = cards.get("Fallaji Archaeologist", (0, 0))[0]
    riddler = cards.get("Quantum Riddler", (0, 0))[0]
    if fallaji <= 1 and 3 <= riddler <= 4:
        return RIDDLER
    if 2 <= fallaji <= 4:
        return FALLAJI
    return None


def collect(since: str, db_path: Path) -> tuple[dict, list[str]]:
    """Every challenge-class list of the archetype since `since`, in week bins.

    The week the cache stops partway through is dropped: an average over the
    two days a week has so far is not the same measurement as one over seven,
    and plotted as the last point it reads as a collapse.
    """
    connection = duckdb.connect(str(db_path), read_only=True)
    rows = connection.execute(
        """
        SELECT d.list_id, d.date, c.card, c.main, c.side
        FROM decklists d JOIN configurations c USING (list_id)
        WHERE d.archetype = 'goryos' AND d.event_class <> 'league' AND d.date >= ?
        """,
        [since],
    ).fetchall()
    connection.close()

    lists: dict[int, dict] = {}
    for list_id, day, card, main, side in rows:
        entry = lists.setdefault(list_id, {"day": day, "cards": {}})
        entry["cards"][card] = (main, side)

    last_day = date.fromisoformat(max(entry["day"] for entry in lists.values()))
    # The last Sunday the cache has reached: a week is complete only once its
    # own Sunday has been played and published.
    settled = (last_day - timedelta(days=(last_day.weekday() + 1) % 7)).isoformat()

    binned: dict[tuple[str, str], list[dict]] = defaultdict(list)
    dropped: Counter = Counter()
    for entry in lists.values():
        panel, week = panel_of(entry["cards"]), week_end(entry["day"])
        if week > settled:
            dropped["incomplete final week"] += 1
        elif panel is None:
            dropped["neither build"] += 1
        else:
            binned[(panel, week)].append(entry["cards"])
    return binned, dropped


def weekly_averages(binned: dict, lands: set[str]) -> tuple[list[dict], list[str]]:
    """Average copies per card, per build, per board, per week.

    The denominator is every list in that build-week, not only the ones playing
    the card, so a card nobody registered is an average of zero rather than a
    gap: the reading is what the build runs on average, and a card falling out
    is exactly the movement this plot exists to show.
    """
    weeks = sorted({week for _, week in binned})
    totals: dict[tuple[str, str, str, str], float] = defaultdict(float)
    for (panel, week), lists in binned.items():
        for cards in lists:
            for card, (main, side) in cards.items():
                if card in lands:
                    continue
                totals[(panel, "mainboard", card, week)] += main
                totals[(panel, "sideboard", card, week)] += side
    sizes = {key: len(value) for key, value in binned.items()}

    records = []
    for (panel, board, card, week), copies in totals.items():
        records.append(
            {
                "week": week,
                "panel": panel,
                "board": board,
                "card": card,
                "avg_copies": copies / sizes[(panel, week)],
                "lists": sizes[(panel, week)],
            }
        )
    return records, weeks, sizes


def densify(records: list[dict], kept: list[str], weeks: list[str], sizes: dict) -> list[dict]:
    """Every non-land card over every week, carrying an explicit zero where absent.

    A week the card was in nobody's 75 is a reading of zero, not a gap. Left as
    a gap the line breaks and a card the build picked up mid-season draws as a
    stub hanging in mid-air, which is the one movement this plot is for.

    The whole pool is written, not only the cards that moved, so the settled
    part of the 75 is on the plot as the shape the movement happens against.
    Only `kept` carries a colour: the palette holds eight series and the pool
    runs to eighty, so the rest are drawn as context and the flag says which is
    which. Every card is in the table either way.
    """
    held = {(r["panel"], r["board"], r["card"], r["week"]): r["avg_copies"] for r in records}
    pool = sorted({row["card"] for row in records})
    # Coloured cards first, so the CSV's order is the palette's order.
    ordered = kept + [card for card in pool if card not in kept]
    panels = sorted({panel for panel, _ in sizes})
    return [
        {
            "week": week,
            "panel": panel,
            "board": board,
            "card": card,
            "avg_copies": held.get((panel, board, card, week), 0.0),
            "lists": sizes[(panel, week)],
            "highlight": card in kept,
        }
        for panel in panels
        for board in ("mainboard", "sideboard")
        for card in ordered
        for week in weeks
        if (panel, week) in sizes
    ]


def movers(records: list[dict], weeks: list[str], threshold: float) -> list[str]:
    """The cards whose weekly average actually moved, largest swing first.

    A card is kept on its widest swing in any one of the four series, so a card
    the Fallaji build dropped while the Riddler build held it is kept: the
    movement is the finding. The zeros matter here, which is why a week the card
    is absent from counts as zero rather than being skipped.
    """
    series: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in records:
        series[(row["panel"], row["board"], row["card"])][row["week"]] = row["avg_copies"]

    swing: dict[str, float] = defaultdict(float)
    for (_, _, card), points in series.items():
        values = [points.get(week, 0.0) for week in weeks]
        swing[card] = max(swing[card], max(values) - min(values))
    kept = [card for card, value in swing.items() if value >= threshold]
    return sorted(kept, key=lambda card: -swing[card])


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2026-05-18", help="YYYY-MM-DD, the first week's Monday")
    parser.add_argument(
        "--move",
        type=float,
        help="keep a card whose weekly average swings at least this many copies",
    )
    parser.add_argument(
        "--layout",
        choices=("builds", "cards"),
        default="builds",
        help="builds: a panel per build and board, colour per card, which warns past 8."
        " cards: a panel per card, colour per build, which has no such limit",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        help="plot these cards instead, in this order; pins the colours across runs",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "reports", help="where the CSV and PNG land")
    parser.add_argument("--no-plot", action="store_true", help="write the CSV and stop")
    args = parser.parse_args(argv)

    # The colour cap is the whole reason the builds layout has to be picky: eight
    # series is what a categorical palette carries, so the threshold has to cut
    # the pool down to eight. Faceting by card puts the two builds on the colour
    # instead, which is two series however many cards are drawn, so the cut goes
    # back to being about what moved rather than about what fits.
    if args.move is None:
        args.move = 1.0 if args.layout == "builds" else 0.5

    lands = land_names()
    binned, dropped = collect(args.since, config.DB_PATH)
    records, weeks, sizes = weekly_averages(binned, lands)
    # Colour is assigned in the order the cards come back, so which cards are on
    # the plot decides which slot each one gets. That is fine within a run and
    # wrong across runs: next week's data admits a new mover and every line is
    # repainted. Naming the cards is how a series keeps its colour week to week.
    kept = args.cards or movers(records, weeks, args.move)

    args.out.mkdir(parents=True, exist_ok=True)
    stem = "weekly-copies" if args.layout == "builds" else "weekly-copies-by-card"
    csv_path = args.out / f"{stem}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["week", "panel", "board", "card", "avg_copies", "lists", "highlight"])
        writer.writeheader()
        writer.writerows(densify(records, kept, weeks, sizes))

    print(f"{len(weeks)} week(s), {weeks[0]} to {weeks[-1]}, challenge-class only")
    for reason, count in dropped.items():
        print(f"  dropped {count} list(s): {reason}")
    for panel in (RIDDLER, FALLAJI):
        sizes = [len(binned[(panel, week)]) for week in weeks if (panel, week) in binned]
        print(f"  {panel:<17} {sum(sizes)} list(s), {min(sizes)}-{max(sizes)} per week")
    if args.cards:
        seen = {row["card"] for row in records}
        print(f"{len(kept)} card(s) named on the command line:")
        for card in kept:
            print(f"  {card}" + ("" if card in seen else "   NOT FOUND in these lists"))
    else:
        print(f"{len(kept)} card(s) swinging at least {args.move} copies, widest first:")
        for card in kept:
            print(f"  {card}")
        print("  (pass --cards to pin this set, and its colours, across weekly runs)")
    pool = len({row["card"] for row in records})
    print(f"{pool - len(kept)} further non-land card(s) left off the plot, in the table only")
    if args.layout == "builds" and len(kept) > PALETTE_SLOTS:
        print(
            f"  WARNING: {len(kept)} series against {PALETTE_SLOTS} distinguishable colours."
            f" Raise --move, or use --layout cards, which has no cap."
        )
    print(f"table at {csv_path}")

    if args.no_plot:
        return
    png_path = args.out / f"{stem}.png"
    subprocess.run(
        ["Rscript", str(Path(__file__).with_suffix(".R")), str(csv_path), str(png_path), "" if args.cards else str(args.move), args.layout],
        check=True,
    )
    print(f"plot at {png_path}")


if __name__ == "__main__":
    main()
