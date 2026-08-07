"""Flags: what the archetype's time series is doing, as verdicts rather than rows.

Adoption answers what a camp plays now against what it played before. A flag
answers the question behind that: whether a configuration climbing is the field
optimising or the field copying, and whether a card appearing is novelty worth
looking at. Both are readings over a series of days rather than over the two
windows, since an episode has a shape and a shape needs more than two points.

They read different histories, and each says why: a spike stops at the regime
boundary, a card's fringeness is its share of the whole analysis history.
"""

import json
from datetime import date, timedelta
from itertools import groupby
from pathlib import Path

from . import config
from .store import CHALLENGE_CLASS, LEAGUE, series

# The last two days of the tournament week, which is when the field's verdict
# lands: a flag matures on a weekend of challenge data and on nothing else. A
# window ends on the Sunday, so the week it bins is the week that has been played.
SATURDAY, SUNDAY = 5, 6
WEEKEND = (SATURDAY, SUNDAY)

# The ledger, which lives beside the store rather than at a path of its own:
# it is that store's memory, and a run reading one has to be reading the other.
LEDGER = "flags.json"


def _tally(published: list[dict], window: tuple[str, str]) -> tuple[dict, dict]:
    """One window's populations and per-configuration counts, by camp and stratum.

    Both come back as lists and weight together, because a share and its
    points-weighted twin are the same tally read two ways and have to be counted
    once. A league carries no weight, which is what keeps it out of every
    weighted figure.
    """
    start, end = window
    population: dict[tuple, dict] = {}
    taken: dict[tuple, dict] = {}
    for row in published:
        if not start <= row["date"] <= end:
            continue
        weight = row["weight"] or 0.0
        where = (row["camp"], row["stratum"])
        counted = population.setdefault(where, {"lists": 0, "weight": 0.0})
        counted["lists"] += 1
        counted["weight"] += weight
        for configuration in row["configurations"]:
            counted = taken.setdefault((*where, *configuration), {"lists": 0, "weight": 0.0})
            counted["lists"] += 1
            counted["weight"] += weight
    return population, taken


def _adoption(population: dict, taken: dict, key: tuple) -> float | None:
    """A configuration's share of the population that could have registered it.

    None where the camp published nothing in that stratum and window: a camp
    that did not show up has no share, which is a different claim from 0%.
    """
    size = population.get(key[:2])
    return taken.get(key, {"lists": 0})["lists"] / size["lists"] if size else None


def _tilt(population: dict, taken: dict, key: tuple) -> float | None:
    """Points-weighted adoption less raw adoption, in the challenge stratum alone.

    A league publishes 5-0s and no standings, so there is no finish there to
    weigh a list by; a challenge window whose lists all scored nothing has no
    performance to distribute either.
    """
    size = population.get(key[:2])
    if key[1] != CHALLENGE_CLASS or not size or not size["weight"]:
        return None
    weighted = taken.get(key, {"weight": 0.0})["weight"] / size["weight"]
    return weighted - _adoption(population, taken, key)


def _week_ends(first: str, last: str) -> list[str]:
    """The days a window may end on: every Sunday of the range, and only those.

    Bins align to the tournament week because that is how play is distributed,
    and the week's verdict lands on the weekend. The week the cache stops partway
    through is not one of them: the day an episode is dated at is what tells it
    from the same configuration spiking again later, so a window ending wherever
    the last capture happened to land would re-date one climb every day the field
    publishes, and the ledger would keep every one of those datings.
    """
    day, final = date.fromisoformat(first), date.fromisoformat(last)
    ends = []
    while day <= final:
        if day.weekday() == SUNDAY:
            ends.append(day.isoformat())
        day += timedelta(days=1)
    return ends


def _days_between(first: str, second: str) -> int:
    return (date.fromisoformat(second) - date.fromisoformat(first)).days


def _fortnight(end: str, back: int = 0) -> tuple[str, str]:
    """The `back`-th fortnight ending on `end`: 0 is the window, 1 the one before."""
    last = date.fromisoformat(end) - timedelta(days=back * config.HYPE_WINDOW_DAYS)
    return ((last - timedelta(days=config.HYPE_WINDOW_DAYS - 1)).isoformat(), last.isoformat())


def _origin_finish(published: list[dict], key: tuple, window: tuple[str, str]) -> dict | None:
    """The visible finish the copying followed: the best challenge-class top-16
    finish in the camp registering this configuration, over the spike and the
    fortnight before it.

    A finish inside the spike window counts, because a Tuesday winner is copied
    for the rest of that fortnight. Ties go to the earlier finish, which is the
    one the field saw first. No such finish means the climb followed nothing
    visible, and a configuration drifting upward is not a hype episode.
    """
    camp, _, card, main, side = key
    start, end = window
    seen = [
        row
        for row in published
        if row["camp"] == camp
        and row["stratum"] == CHALLENGE_CLASS
        and start <= row["date"] <= end
        and row["placement"]
        and row["placement"] <= config.HYPE_ORIGIN_PLACEMENT
        and (card, main, side) in row["configurations"]
    ]
    if not seen:
        return None
    best = min(seen, key=lambda row: (row["placement"], row["date"]))
    return {
        "origin_pilot": best["pilot"],
        "origin_event": best["event"],
        "origin_date": best["date"],
        "origin_placement": best["placement"],
    }


def fringe(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every fringe card appearing in the fresh window, earliest appearance first.

    Fringe is a share of the archetype's whole analysis history, not of a camp's
    fortnight: a card almost nobody has ever played is innovation-grade novelty
    wherever it turns up, and the camp it turned up in is on the row rather than
    in the denominator. The history reaches back past the regime boundary here,
    unlike the spike reading, because how much of the deck's life a card has been
    part of does not reset when the format does.

    A card returning to the pool after falling out of it is fringe on the same
    grounds and whatever its history says. Something that was a staple and then
    was gone for weeks is a decision when it comes back, and its historical
    share, which counts the era it was a staple in, would file it as consensus.

    One flag per card per camp, carrying the appearance that raised it: the
    reason to look is the list, and the percentage is only how it got noticed.
    """
    published = series(db_path, config.HISTORY_START)
    if not published:
        return []

    last = max(row["date"] for row in published)
    fresh = (date.fromisoformat(last) - timedelta(days=config.FRESH_WINDOW_DAYS)).isoformat()

    # The history is accumulated day by day rather than totalled up front, so an
    # appearance is read against what stood before it. Totalled, a card the camp
    # piles onto the week it arrives would carry its own adoption into its own
    # denominator, and the harder it broke out the less fringe it would look.
    # Days are walked whole: lists published on one day are one day's news, and
    # which of them the store happens to serve first decides nothing.
    lists = 0
    plays: dict[str, int] = {}
    seen_on: dict[str, str] = {}
    raised: dict[tuple, dict] = {}
    ordered = sorted(published, key=lambda row: (row["date"], row["pilot"], row["list_id"]))
    for day, published_today in groupby(ordered, key=lambda row: row["date"]):
        published_today = list(published_today)
        for row in published_today if day > fresh else []:
            for card, main, side in row["configurations"]:
                if (card, row["camp"]) in raised:
                    continue
                absent = _days_between(seen_on[card], day) if card in seen_on else None
                returning = absent is not None and absent >= config.RETURN_ABSENCE_DAYS
                historical = plays.get(card, 0) / lists if lists else 0.0
                if not returning and historical >= config.FRINGE_ADOPTION:
                    continue
                raised[(card, row["camp"])] = {
                    "kind": "fringe",
                    "camp": row["camp"],
                    "card": card,
                    "main": main,
                    "side": side,
                    "appeared_on": day,
                    "pilot": row["pilot"],
                    "event": row["event"],
                    "placement": row["placement"],
                    "historical_adoption": historical,
                    "returning": returning,
                    "absent_days": absent if returning else None,
                }
        for row in published_today:
            lists += 1
            for card, _, _ in row["configurations"]:
                plays[card] = plays.get(card, 0) + 1
                seen_on[card] = day
    return list(raised.values())


def _after(end: str, last: str) -> tuple[str, str]:
    """The fortnight a spike is judged over: the days following it, and no more
    than a fortnight of them.

    Nothing outside this window is evidence about the episode, which is the whole
    reason maturity is decided over exactly the same days: a weekend past the end
    of it would mature a flag that then resolved on the midweek data alone.
    """
    spike = date.fromisoformat(end)
    return (
        (spike + timedelta(days=1)).isoformat(),
        min((spike + timedelta(days=config.HYPE_WINDOW_DAYS)).isoformat(), last),
    )


def _matured(published: list[dict], window: tuple[str, str]) -> bool:
    """Whether a weekend of challenge data has landed inside the judging window.

    Hype corrects in about a week, and the weekend is what corrects it: that is
    where tournament density is, so it is the field's verdict on a copied list.
    The midweek challenges after a spike are too thin a slice to resolve on, and
    a flag that resolved on them would call the episode before the data that
    decides it exists.
    """
    start, finish = window
    return any(
        row["stratum"] == CHALLENGE_CLASS
        and start <= row["date"] <= finish
        and date.fromisoformat(row["date"]).weekday() in WEEKEND
        for row in published
    )


def _resolve(published: list[dict], key: tuple, window: tuple[str, str], before: float | None) -> dict:
    """What the fortnight after the spike did to the configuration.

    Read in the challenge stratum, because a hype flag asks whether a copied
    configuration performs and only that stratum publishes standings. The league
    reading comes back beside it rather than instead of it: the decay signature
    is league adoption holding while challenge presence and tilt fall away, and
    neither half says it alone.

    A window too thin to read resolves nothing, by the same floor the raise is
    held to and for the same reason: a camp publishing single figures of
    challenge lists in a fortnight is one where a single pilot swings the share
    past any bar. The flag has matured and is waiting on evidence, which is a
    different thing from evidence that the configuration failed.
    """
    camp, _, card, main, side = key
    finish = window[1]
    population, taken = _tally(published, window)
    challenge_key = (camp, CHALLENGE_CLASS, card, main, side)
    size = population.get(challenge_key[:2])
    if not size or size["lists"] < config.HYPE_MIN_LISTS:
        return {
            "state": "matured",
            "league_after": _adoption(population, taken, (camp, LEAGUE, card, main, side)),
            "challenge_after": None,
            "tilt_after": None,
            "resolved_on": finish,
        }
    after = _adoption(population, taken, challenge_key)
    return {
        "state": "matured" if after is None else _verdict(before, after),
        "league_after": _adoption(population, taken, (camp, LEAGUE, card, main, side)),
        "challenge_after": after,
        "tilt_after": _tilt(population, taken, challenge_key),
        "resolved_on": finish,
    }


def _verdict(before: float | None, after: float) -> str:
    """Established where the herd's move held in the stratum that judges it.

    Held means one of two things. It kept the ground it had while the copying was
    happening, which is a comparison within the challenge stratum and against the
    only figure that stratum ever said about it; or it reached the bar the spike
    was raised on, which it has arrived at whatever it climbed from.

    The first of those is why the bar alone will not do. `HYPE_CEILING` is
    calibrated on how hard copying shows in league dumps, and challenge shares
    live at different heights: measuring one against the other would report a
    configuration the challenges were picking up as one they dropped.

    Anything else is decay: a configuration the copying carried past the spike
    and the challenges then dropped is the episode the flag exists to catch.
    """
    held = after >= before if before is not None else False
    return "established" if held or after >= config.HYPE_CEILING else "decayed"


def hype(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every hype episode the post-regime history holds, oldest spike first.

    The spike is read in the league stratum. That is where copying shows first
    and hardest, per the pilot heuristic that leagues drive novelty detection
    while challenges drive performance evidence, and it is the only stratum
    publishing enough lists a fortnight for a camp's share to mean anything.

    The finish behind it, and everything the flag later resolves on, is read in
    the challenge stratum, since that is the evidence a copied list has to
    survive. The challenge reading at the spike comes back on the row too, as
    the share and the tilt the fortnight was climbing through: what the herd was
    adopting is on record from the raise, a fortnight before the flag may
    resolve. It is a figure and not a verdict, because at the magnitudes
    observed the sign of a tilt is not on its own evidence of anything.
    """
    published = series(db_path, config.REGIME_BOUNDARY)
    if not published:
        return []

    last = max(row["date"] for row in published)
    raised: list[dict] = []
    # A fortnight window slides, so one climb is visible from several week ends.
    # The episode is dated at the first of them and the rest are that same
    # episode seen again, which is why a configuration is deaf to a new spike
    # until the window that raised it has passed out of view.
    episodes: dict[tuple, str] = {}
    for end in _week_ends(config.REGIME_BOUNDARY, last):
        window, before = _fortnight(end), _fortnight(end, back=1)
        now, taken = _tally(published, window)
        then, taken_then = _tally(published, before)
        for key in taken:
            if key[1] != LEAGUE:
                continue
            size, size_then = now.get(key[:2]), then.get(key[:2])
            if not size or not size_then:
                continue
            if min(size["lists"], size_then["lists"]) < config.HYPE_MIN_LISTS:
                continue
            to_adoption = _adoption(now, taken, key)
            from_adoption = _adoption(then, taken_then, key)
            if to_adoption < config.HYPE_CEILING or from_adoption >= config.HYPE_FLOOR:
                continue
            seen = episodes.get(key)
            if seen and _days_between(seen, end) <= config.HYPE_WINDOW_DAYS:
                continue
            origin = _origin_finish(published, key, (before[0], window[1]))
            if not origin:
                continue
            episodes[key] = end
            camp, _, card, main, side = key
            challenge_key = (camp, CHALLENGE_CLASS, card, main, side)
            challenge_before = _adoption(now, taken, challenge_key)
            judged = _after(end, last)
            unresolved = {
                "state": "raised",
                "league_after": None,
                "challenge_after": None,
                "tilt_after": None,
                "resolved_on": None,
            }
            raised.append(
                {
                    "kind": "hype",
                    "camp": camp,
                    "card": card,
                    "main": main,
                    "side": side,
                    "raised_on": end,
                    "from_adoption": from_adoption,
                    "to_adoption": to_adoption,
                    "population": size["lists"],
                    **origin,
                    "tilt": _tilt(now, taken, challenge_key),
                    "challenge_before": challenge_before,
                    **(
                        _resolve(published, key, judged, challenge_before)
                        if _matured(published, judged)
                        else unresolved
                    ),
                }
            )
    return raised


def detect(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every flag the store's series holds right now, hype episodes first."""
    return hype(db_path) + fringe(db_path)


def _identity(flag: dict) -> tuple:
    """What makes two readings the same flag.

    A hype flag is an episode, so the day the field moved is part of it: the
    same configuration spiking again months later is a second episode and gets
    its own record. A fringe flag is a card coming back into view, so the
    configuration it came back in is not: a pilot sideboarding what used to be
    a maindeck card is the same piece of news.
    """
    if flag["kind"] == "hype":
        return (flag["kind"], flag["camp"], flag["card"], flag["main"], flag["side"],
                flag["raised_on"])
    return (flag["kind"], flag["camp"], flag["card"])


def load(db_path: Path = config.DB_PATH) -> list[dict]:
    """The ledger as it stands, or nothing where no run has written one yet."""
    path = db_path.with_name(LEDGER)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def record(db_path: Path = config.DB_PATH, today: str | None = None) -> list[dict]:
    """Merge what the store says now into the ledger, and say what it holds.

    Detection is a reading of the cache and the ledger is the engine's memory of
    what it has raised, so the merge keeps both: a flag's state is whatever this
    run makes of it, and `first_seen` stays the run that first said so.

    A flag the run no longer detects is kept rather than dropped. A fringe flag
    fires on an appearance, which is a moment, and the appearance leaves the
    fresh window a fortnight later; dropping it then would make the engine's
    memory exactly as long as its fresh window.
    """
    kept = {_identity(flag): flag for flag in load(db_path)}
    today = today or date.today().isoformat()
    for flag in detect(db_path):
        seen = kept.get(_identity(flag), {}).get("first_seen", today)
        kept[_identity(flag)] = flag | {"first_seen": seen}
    ledger = sorted(kept.values(), key=lambda flag: (flag["first_seen"], _identity(flag)))

    # Landed whole or not at all, as every capture here is: the ledger is what
    # a run remembers, and half of one is a memory with flags missing from it.
    path = db_path.with_name(LEDGER)
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    partial.replace(path)
    return ledger
