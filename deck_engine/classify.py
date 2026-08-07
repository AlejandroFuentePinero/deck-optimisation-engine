"""Archetype membership: the mainboard trio rule."""

from pathlib import Path

from . import config
from .parse import Decklist, parse_cache


def archetype(decklist: Decklist) -> str | None:
    """`config.ARCHETYPE` when the mainboard holds every signature card."""
    if all(card in decklist.mainboard for card in config.SIGNATURE_CARDS):
        return config.ARCHETYPE
    return None


def classify_cache(raw_dir: Path) -> list[Decklist]:
    """The seam harness: cached payloads through parse and classify."""
    lists = parse_cache(raw_dir)
    for decklist in lists:
        decklist.archetype = archetype(decklist)
    return lists
