"""The pilot's own 75: the reference list, versioned, and what changed between.

A capture is the list as exported on a day, in the representation MTGO
publishes a list in: copies then card name, under a board heading. Captures are
appended and never edited, so what the 75 has done is derived from them rather
than recorded beside them, and the log cannot come to disagree with the lists.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from . import config
from .classify import camp
from .store import CHALLENGE_CLASS, adoption

BOARDS = ("mainboard", "sideboard")

# What a version file is called: the version it is, then where it came from.
# Anchored, since it both reads a version number and strips one off a filename,
# and unanchored it would strip a card's name out of the middle of one.
VERSION_RE = re.compile(r"^v(\d+)-")

# What a slot's annotation may open with to put that slot on a side of the
# core/flex partition whatever adoption says, and how it is told apart from the
# note: marked off with a colon, or standing alone. Taken from any first word
# that happened to be one of them, `core to the gameplan, never cut` would file
# the slot core, drop it out of the playtest queue, and keep the pilot's reason
# a word short.
OVERRIDE_RE = re.compile(r"(core|flex)(?::\s*|\s*$)", re.IGNORECASE)


@dataclass
class Reference:
    """One captured version of the 75, with whatever the pilot annotated on it.

    The annotations are the pilot's own knowledge about a slot: a `core:` or
    `flex:` word overriding where the camp's adoption would file it, and a note
    saying why the slot is what it is. A note is what tells a deviation the
    pilot has thought about from one nobody has looked at yet.
    """

    version: int | None
    path: Path
    mainboard: dict[str, int]
    sideboard: dict[str, int]
    overrides: dict[str, str]
    notes: dict[str, str]

    def configurations(self) -> dict[str, tuple[int, int]]:
        """The 75 as the pairs the domain reads a list in, one per card."""
        return {
            card: (self.mainboard.get(card, 0), self.sideboard.get(card, 0))
            for card in self.mainboard | self.sideboard
        }


def _annotation(text: str) -> tuple[str | None, str]:
    """A slot's annotation: an optional partition override, then the note.

    The override is a word the engine reads and the note is prose it only
    carries, so the override comes first and anything after it is the pilot's.
    """
    text = text.strip()
    marked = OVERRIDE_RE.match(text)
    if marked:
        return marked[1].lower(), text[marked.end() :].strip()
    return None, text


def read(path: Path) -> Reference:
    """A capture's 75 and its annotations.

    The capture is the export as pasted: `4 Goryo's Vengeance` under a board
    heading, with `#` on its own carrying where and when it came from and `#`
    after a slot carrying what the pilot knows about that slot.

    Printings merge here as they do on ingestion of the field's lists, since the
    reference list is only ever read against the field: keeping the two names
    apart would compare a two-of against a consensus counted on the merged one.
    """
    boards: dict[str, dict[str, int]] = {name: {} for name in BOARDS}
    board: dict[str, int] = {}
    overrides: dict[str, str] = {}
    notes: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        entry, _, annotation = line.partition("#")
        entry = entry.strip()
        if not entry:
            continue
        if entry.lower() in boards:
            board = boards[entry.lower()]
            continue
        copies, card = entry.split(" ", 1)
        card = config.CARD_ALIASES.get(card, card)
        board[card] = board.get(card, 0) + int(copies)
        override, note = _annotation(annotation)
        if override:
            overrides[card] = override
        if note:
            notes[card] = note
    numbered = VERSION_RE.match(path.name)
    return Reference(
        version=int(numbered[1]) if numbered else None,
        path=path,
        mainboard=boards["mainboard"],
        sideboard=boards["sideboard"],
        overrides=overrides,
        notes=notes,
    )


def versions(reference_dir: Path = config.REFERENCE_DIR) -> list[Reference]:
    """Every captured version, oldest first.

    A version is a numbered capture, so a file carrying no number is not one of
    them however much its name looks the part: the number is what the history is
    ordered on, and reading such a file in would leave the versions unorderable.
    """
    captured = [read(path) for path in reference_dir.glob("v*.txt") if VERSION_RE.match(path.name)]
    return sorted(captured, key=lambda version: version.version)


def current(reference_dir: Path = config.REFERENCE_DIR) -> Reference:
    """The version the 75 stands at, which is the one an audit is run on."""
    return versions(reference_dir)[-1]


def changes(before: Reference, after: Reference) -> list[dict]:
    """What moved between two versions, by card, in name order.

    The unit is the configuration and not the copy count, as it is everywhere
    else: a copy crossing into the sideboard is a change the pilot made, and a
    total would report it as nothing having happened. A card absent from a
    version has no configuration there rather than a configuration of none.
    """
    was, now = before.configurations(), after.configurations()
    return [
        {"card": card, "before": was.get(card), "after": now.get(card)}
        for card in sorted(was | now)
        if was.get(card) != now.get(card)
    ]


def history(reference_dir: Path = config.REFERENCE_DIR) -> list[dict]:
    """The change log: what each version did to the one before it.

    The first version opens the history rather than changing anything, so it has
    no entry: a log of one version is the log of a 75 that has not moved yet.
    """
    captured = versions(reference_dir)
    return [
        {
            "version": after.version,
            "from_version": before.version,
            "changes": changes(before, after),
        }
        for before, after in zip(captured, captured[1:])
    ]


def _filed(captured: Reference) -> tuple:
    """Everything a version records: the 75, and what the pilot said about it."""
    return (captured.configurations(), captured.overrides, captured.notes)


def capture(source: Path, reference_dir: Path = config.REFERENCE_DIR) -> Reference:
    """File an export as the next version of the reference list.

    The export is kept byte for byte, annotations and provenance comments
    included: what the pilot wrote about a slot is part of the version it was
    written on. Nothing already filed is touched, so a version number, once
    given out, means one 75 forever.

    Writing down why a slot is what it is therefore files a version of its own,
    and moves no configuration when it does. That is the only way to record it:
    the annotations live on the slots of a version and a version is never
    edited, so holding a capture to the configurations alone would leave the
    pilot with nowhere to say anything.

    An export that records nothing new is not a version. Re-exporting the same
    list is the easy thing to do, and an append-only history cannot drop the
    empty entry it would file.

    Nor is an export with no mainboard to it, which is what a list written under
    a heading this format does not know reads as. No mainboard is a Fallaji
    Archaeologist count of zero, so it would be filed as a non-fallaji 75 and
    audited against a camp it was never registered in, out of a version that
    cannot afterwards be edited.
    """
    exported = read(source)
    if not exported.mainboard:
        raise ValueError(f"{source} registers no mainboard: nothing here to file as a version")

    standing = versions(reference_dir)
    if standing and _filed(standing[-1]) == _filed(exported):
        raise ValueError(f"{source} is the reference list unchanged: no version to file")

    version = standing[-1].version + 1 if standing else 1
    reference_dir.mkdir(parents=True, exist_ok=True)
    path = reference_dir / f"v{version}-{VERSION_RE.sub('', source.stem)}.txt"

    # Landed whole or not at all, as every capture in this engine is: a version
    # is never rewritten, so one left half written would stay half written.
    partial = path.with_suffix(".partial")
    partial.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    partial.replace(path)
    return read(path)


def _bucket(share: float, note: str | None) -> str:
    """Where a flex slot stands against the camp that could have registered it.

    A majority of the camp is its consensus, and the pilot registering it is
    playing what the camp plays. Below that the slot is a minority position:
    supported while a real part of the camp is on it, and the pilot's own
    beneath the bar the domain calls fringe.

    A deviation the capture says nothing about is unexamined, which is the whole
    reason the audit exists: it is a slot the pilot has never had to defend.
    """
    if share >= config.CONSENSUS_ADOPTION:
        return "consensus"
    if share >= config.SUPPORTED_MINORITY:
        return "supported-minority"
    return "deliberate-deviation" if note else "unexamined-deviation"


def slots(
    captured: Reference, db_path: Path = config.DB_PATH, stratum: str = CHALLENGE_CLASS
) -> list[dict]:
    """Every slot of the reference list, partitioned and audited against its camp.

    The reading is the camp's own, in one stratum, over the fresh window. The
    camp because a configuration is only consensus within the camp that
    registered it, and this list belongs to one of them by the rule the field is
    read by. One stratum because the two publish on different terms and a share
    over both is a number no population reported; the challenge stratum by
    default, since that is where a list submitted to a tournament has to hold up.
    The fresh window because what a 75 answers to is the camp as it stands.

    Core is where the camp is near-unanimous and the pilot is with it: a slot
    that is not the place to spend playtesting on. Everything else is flex and
    carries the audit's verdict on it, together with the reading it was filed
    on, since a bucket without its population is a verdict with no evidence
    behind it.

    A card the camp never registered is a share of none and not a missing
    reading: the camp published lists, and none of them went there. A camp that
    published no lists at all is the other case entirely, and there is no audit
    to give: every slot would read as a deviation from nobody.
    """
    belongs = camp(captured.mainboard)
    registered = {
        (row["card"], row["main"], row["side"]): row
        for row in adoption(db_path)
        if (row["camp"], row["stratum"]) == (belongs, stratum)
    }
    # The camp's own fresh population, which every one of its rows carries and
    # which is zero where the camp published only into the baseline.
    population = next(iter(registered.values()), {}).get("fresh_population", 0)
    if not population:
        raise ValueError(f"no fresh {stratum} lists from the {belongs} camp to read the 75 against")

    audited = []
    for card, (main, side) in sorted(captured.configurations().items()):
        reading = registered.get((card, main, side))
        share = reading["fresh_adoption"] if reading else 0.0
        override = captured.overrides.get(card)
        core = override == "core" if override else share >= config.CORE_ADOPTION
        note = captured.notes.get(card)
        audited.append(
            {
                "camp": belongs,
                "stratum": stratum,
                "card": card,
                "main": main,
                "side": side,
                "population": population,
                "confidence": share,
                "tilt": reading["fresh_tilt"] if reading else None,
                "delta": reading["delta"] if reading else None,
                "core": core,
                "bucket": None if core else _bucket(share, note),
                "note": note,
            }
        )
    return audited


def playtest_queue(audited: list[dict]) -> list[dict]:
    """The flex slots in the order playtesting should reach them.

    Confidence is the share of the slot's own camp that registered the exact
    configuration the pilot did, and it is that share and nothing else: an index
    blending in the tilt or the delta would rank the 75 on a figure no
    population reported. Those readings ride along on the row, where they say
    what they are.

    Lowest first, and at equal confidence the slot nothing has ever been said
    about goes ahead of the one the pilot has a reason for: the camp cannot tell
    an examined deviation from an unexamined one, and the queue exists to spend
    the playtesting where no one has thought yet.
    """
    return sorted(
        (slot for slot in audited if not slot["core"]),
        key=lambda slot: (
            slot["confidence"],
            slot["bucket"] != "unexamined-deviation",
            slot["card"],
        ),
    )
