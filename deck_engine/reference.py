"""The pilot's own 75: the reference list as captured from a deckbuilding site."""

from pathlib import Path


def read(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """A capture's mainboard and sideboard, by card.

    The capture is the export as pasted: `4 Goryo's Vengeance` under a board
    heading, with `#` comments carrying where and when it came from.
    """
    boards = {"mainboard": {}, "sideboard": {}}
    board: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() in boards:
            board = boards[line.lower()]
            continue
        copies, card = line.split(" ", 1)
        board[card] = board.get(card, 0) + int(copies)
    return boards["mainboard"], boards["sideboard"]
