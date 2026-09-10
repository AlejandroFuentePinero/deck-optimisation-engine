"""Archetype membership: the mainboard signature rules, then the camp within one."""

from pathlib import Path

from . import config
from .parse import Decklist, parse_cache


def archetype(decklist: Decklist) -> str | None:
    """The first archetype whose rule the mainboard answers to, or none.

    The optimised archetype is tested before the tracked ones, so a list takes
    one name and never two. A tracked rule is its signature cards plus the
    colours the deck comes in: a build sharing the signature and splashing
    outside them is a different deck, not a variant of this one.
    """
    if all(card in decklist.mainboard for card in config.SIGNATURE_CARDS):
        return config.ARCHETYPE
    for name, rule in config.TRACKED_DECKS.items():
        if all(card in decklist.mainboard for card in rule["signature"]) and not any(
            card in decklist.mainboard for card in rule["off_colour"]
        ):
            return name
    return None


def camp(mainboard: dict[str, int]) -> str:
    """The variant camp a mainboard's divergence-card count commits it to.

    Takes the mainboard rather than a list so the reference list, which has no
    event to have been published at, is read by the same rule as the field.
    """
    copies = mainboard.get(config.DIVERGENCE_CARD, 0)
    for name, counts in config.CAMPS.items():
        if copies in counts:
            return name
    return config.HYBRID_CAMP


def variant(name: str, mainboard: dict[str, int]) -> str:
    """The camp a member of `name` belongs to, by that archetype's own rule.

    The optimised archetype forks on how many copies of one card a list runs;
    a tracked deck forks on whether it runs the card at all, which is what a
    colour split is. Both read the mainboard alone.
    """
    if name == config.ARCHETYPE:
        return camp(mainboard)
    rule = config.TRACKED_DECKS[name]
    if mainboard.get(rule["variant_card"], 0):
        return rule["variant_with"]
    return rule["variant_without"]


def classify_cache(raw_dir: Path) -> list[Decklist]:
    """The seam harness: cached payloads through parse and classify."""
    lists = parse_cache(raw_dir)
    for decklist in lists:
        decklist.archetype = archetype(decklist)
        if decklist.archetype:
            decklist.camp = variant(decklist.archetype, decklist.mainboard)
    return lists
