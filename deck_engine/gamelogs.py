"""The pilot's own match logs to match records.

MTGO writes one Match_GameLog_<uuid>.dat per match into the client's
ClickOnce data directory. The container is binary, but every event the
client showed is embedded as readable text: player references arrive
prefixed @P and card references as @[Name@:catalog,instance:@]. That is
enough to read who played, who took each game, and what both decks cast,
which is the matchup-level ground truth the published-list pipeline can
never see.
"""

import json
import re
import struct
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import config

MATCH_FILE_RE = re.compile(r"Match_GameLog_(?P<match_id>[0-9a-f\-]+)\.dat$")

# Player references embed as @P<login>. The byte before an event is framing
# and can glue printable garbage onto the run, so the @P marker is the only
# safe left edge for a login.
_LOGIN = r"@P(?P<player>[A-Za-z0-9_.\-]+)"
GAME_WIN_RE = re.compile(_LOGIN + r" wins the game")
MATCH_WIN_RE = re.compile(_LOGIN + r" wins the match (?P<score>\d+-\d+)")
ROLL_RE = re.compile(_LOGIN + r" rolled a \d")
CAST_RE = re.compile(_LOGIN + r" (?:casts|plays) @\[(?P<card>[^@]+)@:")

# Every event carries a .NET timestamp: 100ns ticks since year 1, little-
# endian. The whole 2015-2040 era shares the high byte 0x08, which is what
# makes scanning for candidates cheap.
_TICKS_EPOCH = datetime(1, 1, 1)


def _ticks(year: int) -> int:
    return int((datetime(year, 1, 1) - _TICKS_EPOCH).total_seconds()) * 10**7


_TICKS_LOW, _TICKS_HIGH = _ticks(2015), _ticks(2040)


@dataclass
class MatchLog:
    """One match as the client recorded it."""

    match_id: str
    start: str
    players: list[str]
    game_wins: dict[str, int]
    winner: str | None
    score: str | None
    cards: dict[str, list[str]]


def _start(data: bytes, path: Path) -> datetime:
    """When the match began: the earliest embedded timestamp, or the file's
    own mtime for a log too truncated to carry one.

    The scan admits impostors: any 8 framing bytes that happen to land in the
    era pass the range check. The real stamps are the hundreds clustered
    around the match, so the start is the earliest tick within a day of the
    median rather than the earliest tick outright."""
    ticks = []
    at = data.find(b"\x08", 7)
    while at != -1:
        (value,) = struct.unpack_from("<Q", data, at - 7)
        if _TICKS_LOW <= value <= _TICKS_HIGH:
            ticks.append(value)
        at = data.find(b"\x08", at + 1)
    if ticks:
        ticks.sort()
        median = ticks[len(ticks) // 2]
        day = 24 * 3600 * 10**7
        start = min(t for t in ticks if abs(t - median) < day)
        return _TICKS_EPOCH + timedelta(microseconds=start // 10)
    return datetime.fromtimestamp(path.stat().st_mtime)


def _winner(text: str, game_winners: list[str]) -> tuple[str | None, str | None]:
    """Who took the match. The explicit line when the log has one; otherwise
    the first player to two game wins, which an abandoned log still shows."""
    final = MATCH_WIN_RE.search(text)
    if final:
        return final["player"], final["score"]
    tally: dict[str, int] = {}
    for player in game_winners:
        tally[player] = tally.get(player, 0) + 1
        if tally[player] == 2:
            return player, None
    return None, None


def parse_match(path: Path) -> MatchLog:
    data = path.read_bytes()
    # latin-1 keeps every byte, so the framing bytes pass through harmlessly
    # and the regexes see the embedded text as the client wrote it.
    text = data.decode("latin-1")

    players: list[str] = []
    for roll in ROLL_RE.finditer(text):
        if roll["player"] not in players:
            players.append(roll["player"])

    game_winners = [won["player"] for won in GAME_WIN_RE.finditer(text)]
    winner, score = _winner(text, game_winners)

    cards: dict[str, list[str]] = {}
    for cast in CAST_RE.finditer(text):
        seen = cards.setdefault(cast["player"], [])
        if cast["card"] not in seen:
            seen.append(cast["card"])

    game_wins: dict[str, int] = {}
    for player in game_winners:
        game_wins[player] = game_wins.get(player, 0) + 1

    return MatchLog(
        match_id=MATCH_FILE_RE.search(path.name)["match_id"],
        start=_start(data, path).isoformat(timespec="seconds"),
        players=players,
        game_wins=game_wins,
        winner=winner,
        score=score,
        cards=cards,
    )


def load(directory: Path = None) -> list[MatchLog]:
    """Every match log in the directory, oldest first."""
    directory = directory or config.GAMELOG_DIR
    parsed = [parse_match(path) for path in directory.glob("Match_GameLog_*.dat")]
    return sorted(parsed, key=lambda match: match.start)


def write_matches(matches: list[MatchLog], path: Path = None) -> Path:
    """The parsed history as one record per line, for whatever reads it next."""
    path = path or config.MATCHES_PATH
    with path.open("w") as out:
        for match in matches:
            out.write(json.dumps(asdict(match)) + "\n")
    return path
