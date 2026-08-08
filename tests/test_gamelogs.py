"""The gamelog parser against synthetic logs in the client's framing."""

import struct
from datetime import datetime

from deck_engine import gamelogs

# 2025-06-01 12:00 as .NET ticks, the stamp format the client writes.
TICKS = int((datetime(2025, 6, 1, 12, 0) - datetime(1, 1, 1)).total_seconds()) * 10**7


def _log(tmp_path, events, name="Match_GameLog_00000000-0000-0000-0000-000000000001.dat"):
    """A synthetic log: framed events with a timestamp, as the client writes
    them. \\x9c is the printable-garbage byte that glues onto runs."""
    data = b"\x01\x00$00000000-0000-0000-0000-000000000001"
    for offset, text in enumerate(events):
        framed = text.encode()
        data += struct.pack("<Q", TICKS + offset * 10**7) + b"\x00" + bytes([len(framed)]) + framed
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_decided_match(tmp_path):
    path = _log(
        tmp_path,
        [
            "@Palice rolled a 3.",
            "@Pbob_the.Builder rolled a 6.",
            " @P@Palice joined the game.",
            "@Palice plays @[Flooded Strand@:108388,440:@].",
            "@Palice casts @[Thoughtseize@:100512,444:@] targeting bob_the.Builder.",
            "@Pbob_the.Builder casts @[Psychic Frog@:252834,451:@].",
            "@Palice wins the game.",
            "@Pbob_the.Builder wins the game.",
            "@Palice wins the game.",
            "@Palice wins the match 2-1",
        ],
    )
    match = gamelogs.parse_match(path)
    assert match.match_id == "00000000-0000-0000-0000-000000000001"
    assert match.start == "2025-06-01T12:00:00"
    assert match.players == ["alice", "bob_the.Builder"]
    assert match.game_wins == {"alice": 2, "bob_the.Builder": 1}
    assert match.winner == "alice"
    assert match.score == "2-1"
    assert match.cards == {
        "alice": ["Flooded Strand", "Thoughtseize"],
        "bob_the.Builder": ["Psychic Frog"],
    }


def test_abandoned_match_still_decides_on_two_game_wins(tmp_path):
    path = _log(
        tmp_path,
        [
            "@Palice rolled a 3.",
            "@Pbob rolled a 6.",
            "@Pbob wins the game.",
            "@Pbob wins the game.",
        ],
    )
    match = gamelogs.parse_match(path)
    assert match.winner == "bob"
    assert match.score is None


def test_truncated_match_has_no_winner(tmp_path):
    path = _log(tmp_path, ["@Palice rolled a 3.", "@Pbob rolled a 6.", "@Palice wins the game."])
    match = gamelogs.parse_match(path)
    assert match.winner is None
    assert match.game_wins == {"alice": 1}


def test_load_sorts_oldest_first_and_roundtrips(tmp_path):
    _log(tmp_path, ["@Palice rolled a 3.", "@Palice wins the game."])
    matches = gamelogs.load(tmp_path)
    assert [m.match_id for m in matches] == ["00000000-0000-0000-0000-000000000001"]
    landed = gamelogs.write_matches(matches, tmp_path / "matches.jsonl")
    assert landed.read_text().count("\n") == 1
