"""Archetype membership: the mainboard trio rule, then the camp within it."""

from pathlib import Path

from . import config
from .parse import Decklist, parse_cache


def archetype(decklist: Decklist) -> str | None:
    """`config.ARCHETYPE` when the mainboard holds every signature card."""
    if all(card in decklist.mainboard for card in config.SIGNATURE_CARDS):
        return config.ARCHETYPE
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


def classify_cache(raw_dir: Path) -> list[Decklist]:
    """The seam harness: cached payloads through parse and classify."""
    lists = parse_cache(raw_dir)
    for decklist in lists:
        decklist.archetype = archetype(decklist)
        if decklist.archetype:
            decklist.camp = camp(decklist.mainboard)
    return lists
