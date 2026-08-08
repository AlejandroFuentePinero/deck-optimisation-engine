"""Who registered what: the readings that are about pilots rather than shares.

Adoption counts lists, which is the right unit for asking what a camp plays and
the wrong one for asking whether a camp plays it. Three appearances of a card
are three pilots agreeing or one pilot repeating himself, and the share reports
the same number either way. These readings put the pilot back in.
"""

from datetime import date, timedelta
from itertools import groupby
from pathlib import Path

from . import config
from .flags import novelty, ordered_by_day
from .store import CHALLENGE_CLASS, LEAGUE, near_miss_series, series


def _baseline_end(published: list[dict]) -> str:
    """The last day of the baseline window: where the fresh window starts.

    Anchored on the last day the store holds a list for rather than on the
    clock, as every window in this engine is, so a quiet week shortens none of
    them.
    """
    last = max(row["date"] for row in published)
    return (date.fromisoformat(last) - timedelta(days=config.FRESH_WINDOW_DAYS)).isoformat()


def proven_pilots(db_path: Path = config.DB_PATH) -> dict[str, int]:
    """The pilots the baseline window saw finish, and how often, above the cut.

    The tier exists to tell a dissenter from an unknown: a pilot going against
    the herd is only evidence if he is someone whose results say he can play the
    deck. It is read over the baseline window alone, because it has to say who
    was already proven when a fresh list turned up, and a pilot proven by the
    same fortnight as the list would be proven by the news itself.

    Challenge-class only. A league dump publishes 5-0s and no standings, so
    there is no placement there to make a cut at, and the trophies of a pilot
    who grinds leagues are not the finishes this asks about.
    """
    published = series(db_path, config.REGIME_BOUNDARY)
    if not published:
        return {}

    baseline_end = _baseline_end(published)
    finishes: dict[str, int] = {}
    for row in published:
        if (
            row["stratum"] == CHALLENGE_CLASS
            and row["date"] <= baseline_end
            and row["placement"]
            and row["placement"] <= config.PROVEN_PILOT_PLACEMENT
        ):
            finishes[row["pilot"]] = finishes.get(row["pilot"], 0) + 1
    return {
        pilot: count
        for pilot, count in finishes.items()
        if count >= config.PROVEN_PILOT_FINISHES
    }


def pet_tech(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every configuration the post-regime history saw from one or two pilots
    often enough for it to be theirs, earliest appearance first.

    Adoption counts lists, so three appearances read the same whether three
    pilots converged on a configuration or one pilot registered it three times.
    The flag says which, and it classifies rather than discounts: the same
    concentration that inflates apparent field adoption is what makes a
    dissenter's repeated success with it worth a hypothesis.

    Read per camp, as every share it qualifies is: a configuration means one
    thing inside the camp that registered it and nothing outside it. Both strata
    count towards the appearances, because what is being counted is a pilot
    reaching for the card and not how a list finished; a league dump is where a
    pet shows most, being published without dedup.

    A list in no camp is read against no camp, as `_fold` does with the same
    lists. The hybrid bucket is the residue of the rule that draws the two camps
    rather than a camp of its own, and it is thin by construction, so nearly
    everything in it is one or two pilots' by the only measure this has: a
    single hybridist publishing his stock 75 three times would come out holding
    a pet in every slot of it, the divergence card included.

    Whose pet it is decides what the flag is worth, so the tier is composed onto
    it here. A dissenter is a proven pilot who has performed *with this
    configuration*, and both halves are load-bearing. Being proven says he can
    play the deck, which is what makes his going against the herd worth reading
    at all; having finished on the card is the claim itself, and without it the
    flag would raise a hypothesis out of a good player's untested preference.
    A lone dissenting regular beats herd convergence as evidence, so that pairing
    raises a hypothesis candidate: a claim about the 75 that playtesting is owed.
    An unknown's pet is one player's preference and there is nothing to learn
    from it yet.

    The finishes counted are challenge-class top-16 ones, as the tier's are: a
    league dump publishes no standings, so a pet that only ever appears in
    trophies has no finish behind it to have performed with. There have to be as
    many of them as the tier itself asks for, and for the tier's own reason: a
    proven pilot is one who finishes, so his finishing once with a card in the
    75 is what he was going to do anyway. Repeated success is the claim, and one
    result is not repetition.
    """
    published = series(db_path, config.REGIME_BOUNDARY)
    proven = proven_pilots(db_path)

    seen: dict[tuple, dict] = {}
    for row in ordered_by_day(published):
        if row["camp"] not in config.CAMPS:
            continue
        performed = (
            row["pilot"] in proven
            and row["stratum"] == CHALLENGE_CLASS
            and row["placement"]
            and row["placement"] <= config.PROVEN_PILOT_PLACEMENT
        )
        for configuration in row["configurations"]:
            registered = seen.setdefault(
                (row["camp"], *configuration),
                {"appearances": 0, "pilots": {}, "on": row["date"], "dissenters": {}},
            )
            registered["appearances"] += 1
            registered["pilots"].setdefault(row["pilot"], row["date"])
            if performed:
                registered["dissenters"][row["pilot"]] = (
                    registered["dissenters"].get(row["pilot"], 0) + 1
                )

    return [
        {
            "kind": "pet-tech",
            "camp": camp,
            "card": card,
            "main": main,
            "side": side,
            "appearances": registered["appearances"],
            "pilots": sorted(registered["pilots"]),
            "appeared_on": registered["on"],
            # How often each dissenter finished above the cut registering this,
            # which is the claim: the tier that qualified him is only why it
            # counts, and the row carrying it instead would report a pilot's
            # record where it means to report what the card did.
            "dissenters": dict(sorted(registered["dissenters"].items())),
            "hypothesis_candidate": any(
                finishes >= config.PROVEN_PILOT_FINISHES
                for finishes in registered["dissenters"].values()
            ),
        }
        for (camp, card, main, side), registered in sorted(
            seen.items(), key=lambda item: (item[1]["on"], item[0])
        )
        if registered["appearances"] >= config.PET_TECH_APPEARANCES
        and len(registered["pilots"]) <= config.PET_TECH_PILOTS
    ]


def _fold(standing: dict, row: dict) -> None:
    """Fold one published list into the tally its camp is read off.

    Kept per camp and per stratum, which is the population every share in this
    engine is taken over, and accumulated rather than recomputed so a list is
    read against what its camp was playing before it was published.

    A list in no camp is folded into none of them. A hybrid experiment belongs
    to neither consensus by the rule that draws the camps, and a near-miss list
    is not in the archetype at all, so letting either into a tally would put a
    build the camp never registered into what the camp is held to have settled on.
    """
    if row["camp"] not in config.CAMPS:
        return
    tally = standing.setdefault((row["camp"], row["stratum"]), {"lists": 0, "plays": {}})
    tally["lists"] += 1
    for card, _, _ in row["configurations"]:
        tally["plays"][card] = tally["plays"].get(card, 0) + 1


def _departure(tally: dict, registered: list[tuple]) -> tuple[list, list]:
    """How far outside its camp a list is built: the configurations it
    registered that almost none of that camp did, and the cards the camp is
    near-unanimous on that it registered none of.

    A departure is not a disagreement with the camp's majority. Most of a 75 is
    flex slots, where the camp has no majority to disagree with, so counting
    every slot the camp is split over would make the ordinary list a departure
    of a dozen cards and the measure would say nothing.

    Nor is it a count. Read at the configuration, a pilot on four Flooded Strand
    where his camp runs three is standing outside a camp that is unanimous with
    him about the card, and a list is eight such deviations deep before it has
    done anything at all. That is the reading `missing_core` refuses on the same
    grounds: a camp that agrees on a card and argues about how many is agreed on
    the card, and only a list running none of it stands outside all of them.

    So the unit here is the card, and both directions of it count. A card under
    `SUPPORTED_MINORITY` is one hardly any of the camp plays, which is the slot
    audit's deviation; a card at `CORE_ADOPTION` that the list runs none of is
    its missing core slot. A staple left out is as much of a departure as a card
    nobody plays. The count the list registered rides along on the row, because
    that is what a reader wants to see, and it decides nothing.
    """
    lists = tally["lists"]
    held = {card: (main, side) for card, main, side in registered}
    novel = [
        [card, main, side]
        for card, (main, side) in sorted(held.items())
        if tally["plays"].get(card, 0) / lists < config.SUPPORTED_MINORITY
    ]
    missing = sorted(
        card
        for card, plays in tally["plays"].items()
        if card not in held and plays / lists >= config.CORE_ADOPTION
    )
    return novel, missing


def _finished(row: dict) -> bool:
    """Whether the list performed well enough for its deviation to be evidence.

    Top-16 in the challenge stratum, the cut being where performance rather than
    tiebreakers separates finishes. Every published league list is a 5-0, which
    is soft evidence and counted anyway: leagues are where pilots test
    innovations first, so refusing them would look for breakthroughs everywhere
    except the stratum they start in.
    """
    return row["stratum"] == LEAGUE or bool(
        row["placement"] and row["placement"] <= config.BREAKTHROUGH_PLACEMENT
    )


def _read_against(camp: str | None) -> tuple[str, ...]:
    """The camps a list's deviation is measured against.

    A list registered in a camp answers to that camp and no other. A hybrid
    experiment belongs to neither consensus, and a near-miss list is not in the
    archetype at all, so each is read against every camp and keeps the smallest
    departure: the camp it is nearest to. A breakthrough has to be a departure
    from every settled build there is, and reading a hybrid against the far camp
    alone would report the distance between the two camps as its innovation.
    """
    return (camp,) if camp in config.CAMPS else tuple(config.CAMPS)


def _mode(delta: int, novel: list, fringe: dict[str, dict], tally: dict) -> str | None:
    """Which kind of departure this is, or none that the detector reads.

    A card the archetype barely plays is a departure at a delta of one, since
    nobody arrives at it by drifting through their flex slots. Known cards
    recombined take five, which is the bar between a rebuilt list and the
    ordinary movement of a camp's flex slots.

    The card has to be one the tally had never seen, and not merely one it is
    under the minority bar on. A share is the wrong instrument for this: the bar
    is a tenth of the camp, so in a camp of three hundred lists a card stays
    novel for its first thirty-odd registrations, and every pilot who takes it
    up in that stretch is read as having departed. That is the field answering a
    departure, which is what the trendsetter state is for. One list introduces a
    card and the rest follow it, so the departure is the first sight of it and
    the flag belongs to the list that brought it.

    First sight is the camp's and the stratum's together, that being the
    population every share here is taken over, so a card can be a departure once
    in the leagues and again in the challenges. That is the right reading rather
    than a duplicate: the strata are kept apart because they answer different
    questions, and a card the leagues have been passing around for a fortnight
    is still the first of its kind to turn up where finishes are measured.
    """
    if any(card in fringe and not tally["plays"].get(card) for card, _, _ in novel):
        return "fringe"
    return "in-pool" if delta >= config.BREAKTHROUGH_DELTA else None


def _candidate(row: dict, standing: dict, fringe: dict[str, dict]) -> dict | None:
    """What the list did against the camp it answers to, if it did enough to be
    a breakthrough candidate.

    Which camp that is, is `_read_against`'s to say and not this reading's: a
    list registered in a camp answers to that one, and a hybrid or a near-miss
    is read against every camp and keeps the smallest departure it comes out at.

    A list borrowing a camp that way is also held to a ceiling, which one in its
    own camp is not. Reading it against the nearest camp assumes it is a build
    of that camp, and past the ceiling the assumption has failed rather than the
    list having innovated: a watchlist list is on the watchlist for mainboarding
    one card, and most of them are simply other decks.
    """
    if not _finished(row):
        return None

    borrowed = row["camp"] not in config.CAMPS
    readings = []
    for camp in _read_against(row["camp"]):
        settled = standing.get((camp, row["stratum"]))
        if settled is None:
            continue
        novel, missing = _departure(settled, row["configurations"])
        readings.append((len(novel) + len(missing), camp, novel, missing, settled))
    if not readings:
        return None

    delta, camp, novel, missing, settled = min(readings)
    if borrowed and delta > config.BREAKTHROUGH_CEILING:
        return None
    mode = _mode(delta, novel, fringe, settled)
    if not mode:
        return None
    return {
        "kind": "breakthrough",
        "camp": camp,
        "pilot": row["pilot"],
        "event": row["event"],
        "date": row["date"],
        "placement": row["placement"],
        "mode": mode,
        "delta": delta,
        "novel": novel,
        "missing": missing,
    }


def _followed(
    flag: dict, adopters: dict[str, list[tuple[str, str]]], debut: dict[str, str], last: str
) -> dict:
    """What the field did with the list's own configurations in the fortnight
    after it, and whether that was enough to have set the trend.

    Follow-through is counted on a card rather than on the list, since what
    spreads is the idea and not the 75 around it: a pilot taking the card into
    his own build has followed through, and one registering the whole list is
    the herd behaviour the hype flag is for. The card that carried the most of
    the field is the one the row names, so a rebuilt list is read on the slot
    that caught on rather than on all of it or none.

    A departure made only of staples the list dropped has nothing here to catch
    on, and so cannot graduate. That is the reading rather than a gap in it: the
    field takes up a card, and there is no card in an omission for it to take up.

    A follower is a pilot the card is new to and the archetype is not. Anyone
    already on the card did not follow it, and counting him would graduate a
    breakthrough on the strength of the people it departed from in the first
    place. That rules the pilot himself out with everyone else: he registered
    the card on the day, so it is not new to him either.

    A pilot who had never published in the archetype did not take the card up
    either, whatever he registered afterwards: he turned up. Most of the names a
    league dump publishes appear once and never again, so counting first-timers
    would make this a reading of how many of them a fortnight brought rather
    than of what the field did with an idea, and a departure would graduate on
    the game's turnover.

    Until the fortnight is up the flag is being watched rather than answered.
    `breakthrough` is a verdict, that the field had its fortnight and did
    nothing, and a list published yesterday has had no fortnight to have been
    ignored in. Enough followers ends it early, since a departure two pilots
    have already taken up has set the trend whatever the rest of the fortnight
    brings, but nothing short of that is decided yet.
    """
    closes = (
        date.fromisoformat(flag["date"]) + timedelta(days=config.TRENDSETTER_WINDOW_DAYS)
    ).isoformat()
    taken_up: list[tuple[str | None, list[str]]] = []
    for card, _, _ in flag["novel"]:
        registered = adopters.get(card, [])
        already = {pilot for day, pilot in registered if day <= flag["date"]}
        followers = sorted(
            {
                pilot
                for day, pilot in registered
                if flag["date"] < day <= closes
                and pilot not in already
                and debut[pilot] <= flag["date"]
            }
        )
        taken_up.append((card, followers))

    card, followers = max(taken_up, key=lambda taken: len(taken[1]), default=(None, []))
    if len(followers) >= config.TRENDSETTER_FOLLOWERS:
        state = "trendsetter"
    else:
        state = "watching" if closes > last else "breakthrough"
    return {"state": state, "followers": followers, "adopted_card": card}


def breakthroughs(db_path: Path = config.DB_PATH) -> list[dict]:
    """Every list the post-regime history holds that departed from its camp and
    finished, oldest first.

    The camp is accumulated day by day rather than read over a window, so a list
    is measured against what its camp was playing the day before it was
    published. Measured against the camp as it stands now, a list the field went
    on to copy would be read against its own influence and report itself as
    ordinary, which is exactly backwards for a reading about what set the trend.

    A card's fringeness is read over the whole analysis history, which reaches
    back past the regime boundary: how much of the deck's life a card has been
    part of does not reset when the format does, and the departures read here
    are only the ones the current regime holds.

    The watchlist is walked beside the archetype's own lists, since a near-miss
    build is where a variant comes from and a detector that could not see one
    would be looking for innovation everywhere except the place it is filed.
    """
    history = series(db_path, config.HISTORY_START) + near_miss_series(
        db_path, config.HISTORY_START
    )
    # A first run that reached nothing has no last day to close a window against.
    if not history:
        return []
    novel_cards = novelty(history)
    published = [row for row in history if row["date"] >= config.REGIME_BOUNDARY]

    tallies: dict[tuple, dict] = {}
    raised = []
    for _, published_today in groupby(ordered_by_day(published), key=lambda row: row["date"]):
        published_today = list(published_today)
        # A camp too thin to have settled on anything is read against by
        # nobody, by the floor a hype spike is held to and for its reason: a
        # share of six lists is one pilot changing his mind.
        standing = {
            where: tally
            for where, tally in tallies.items()
            if tally["lists"] >= config.BREAKTHROUGH_MIN_LISTS
        }
        for row in published_today:
            flag = _candidate(row, standing, novel_cards.get(row["list_id"], {}))
            if flag:
                raised.append(flag)
        for row in published_today:
            _fold(tallies, row)

    # Taken over the whole analysis history and not the post-regime part of it,
    # since what this decides is whether the card was new to a pilot: someone
    # who played it before the boundary and came back to it after a finish did
    # not follow that finish, and a history starting at the boundary would have
    # no way to know so.
    adopters: dict[str, list[tuple[str, str]]] = {}
    debut: dict[str, str] = {}
    for row in history:
        debut[row["pilot"]] = min(debut.get(row["pilot"], row["date"]), row["date"])
        for card, _, _ in row["configurations"]:
            adopters.setdefault(card, []).append((row["date"], row["pilot"]))
    last = max(row["date"] for row in history)
    return [flag | _followed(flag, adopters, debut, last) for flag in raised]
