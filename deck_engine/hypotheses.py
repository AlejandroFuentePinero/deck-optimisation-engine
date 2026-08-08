"""The tracked hypotheses: what the 75 is still arguing about, and the evidence.

A hypothesis is a falsifiable claim about deck configuration, and the point of
recording one is that the argument for it accumulates: the camp's numbers on the
day they were read, what the pilot found when he played it, and what he judged.
So a record is a claim with a dated log under it, and the log is appended to and
never rewritten.

One record per file, in Markdown, because the pilot writes the claim and reads
the argument back. What the engine acts on sits in a header of `key: value`
lines the pilot can also write; everything under a `##` heading is prose.
"""

from datetime import date
from pathlib import Path

from . import config, ledger, reference
from .classify import camp
from .store import CHALLENGE_CLASS, adoption, card_pool, land_counts, mirror_share

# Where the argument has got to. Everything but the last is unresolved: the 75
# is submitted whether or not the evidence arrived, so `decided` is the only
# status that closes a record, and an inconclusive claim is decided by carrying
# a verdict of keeping what the 75 already runs.
STATUSES = ("open", "supported", "contradicted", "inconclusive", "decided")
DECIDED = "decided"

# What a record is about, in the field's lists: a card by name, or the one
# deck-level configuration the archetype argues over.
LANDS = "lands"

# Where an entry came from. Data is the engine's reading of the store; the other
# two are the pilot's, and they are entries of the same standing.
DATA = "data"
SOURCES = (DATA, "playtest", "judgment")

# Where a claim came from. The pilot's own is what the tracked set opens on; the
# data-suggested origin is for the claims the flag layer goes on to raise.
ORIGINS = ("pilot-experience", "data-suggested")

# What a record is made of on the page: the claim it opens on, the header of
# `key: value` lines the engine acts on, then the prose sections, then the log's
# own dated entries. Every reading and every append goes through these three
# marks, so the format the pilot writes in is written down once.
CLAIM_MARK = "# "
SECTION_MARK = "## "
ENTRY_MARK = "### "

# The section the dated log lives under. It is the last section of a record, so
# an entry is appended to the file and nothing already written is disturbed.
EVIDENCE_HEADING = f"{SECTION_MARK}Evidence"

# The header keys a ruling rewrites. Everything else on a record is the pilot's
# and survives being ruled on.
RULED = ("status", "verdict")

# What a hype flag does to a share taken over the configuration it flagged. The
# adoption is real and it is not evidence about the card: what it counts is how
# many pilots copied a list after a visible finish, which the domain says
# corrects on its own within about a week of play.
HYPE_CAVEAT = "adoption density, not card quality"
HYPE = "hype"

# What a record may be conditional on. The mirror is the join the domain names:
# a slot bought on how much of the field the archetype itself is stays bought
# only while that density stands, so the reading that stood on the day goes into
# the entry beside the configurations it qualifies.
MIRROR = "mirror"


def _sections(text: str) -> tuple[str, dict[str, list[str]], dict[str, list[str]]]:
    """A record's three parts: the claim, the header, and the prose sections.

    The claim is the heading the file opens on, the header is the `key: value`
    lines under it, and everything from the first section mark is prose kept as
    the lines it was written as.

    A header key may be written more than once, which is how a record names two
    subjects: a card's name can hold a comma, so one line per subject is the
    only separator that cannot cut Teferi, Time Raveler in half.
    """
    claim, header, sections = "", {}, {}
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith(SECTION_MARK):
            current = sections.setdefault(line[len(SECTION_MARK) :].strip().lower(), [])
        elif line.startswith(CLAIM_MARK):
            claim = line[len(CLAIM_MARK) :].strip()
        elif current is not None:
            current.append(line)
        elif ":" in line:
            key, _, value = line.partition(":")
            header.setdefault(key.strip().lower(), []).append(value.strip())
    return claim, header, sections


def _prose(lines: list[str]) -> str:
    """A section as the paragraph it was written as, without its blank edges."""
    return "\n".join(lines).strip()


def _log(lines: list[str]) -> list[dict]:
    """The evidence section as the dated entries it is made of.

    An entry opens on the day it was taken and the kind of source it came from,
    and everything under that is what that source said. The three kinds are read
    back the same way, because a playtest result and a run of the numbers are
    the same sort of thing here: something that happened on a day and bears on
    the claim.
    """
    entries: list[dict] = []
    for line in lines:
        if line.startswith(ENTRY_MARK):
            on, _, source = line[len(ENTRY_MARK) :].strip().partition(" ")
            entries.append({"on": on, "source": source.strip(), "lines": []})
        elif entries and line.strip():
            entries[-1]["lines"].append(line.rstrip())
    return entries


def read(path: Path, today: str | None = None) -> dict:
    """One record, as the claim it makes and where the argument stands.

    The days remaining are what makes an unresolved record urgent: the 75 is
    handed in on a date, and a claim nobody has decided by then is a slot
    decided by default. A record already decided has none, having no clock left
    to run against.

    A record is written by hand, so the three header words the engine acts on
    are checked rather than taken. Each of them is silent when it is wrong: an
    unknown status files the claim as neither open nor decided, an unknown
    origin loses which side the claim came from, and an unknown condition makes
    a conditional record read as an unconditional one, which is the meta join
    going missing without anything saying so.
    """
    claim, header, sections = _sections(path.read_text(encoding="utf-8"))
    status = header.get("status", [""])[0]
    origin = header.get("origin", [""])[0]
    conditional_on = header.get("conditional-on", [None])[0]
    vocabularies = ((status, STATUSES), (origin, ORIGINS), (conditional_on, (None, MIRROR)))
    for word, vocabulary in vocabularies:
        if word not in vocabulary:
            raise ValueError(f"{path} reads {word!r}, which is none of {vocabulary}")

    # A claim naming nothing in the field's lists is one no run can bring
    # evidence to, and it would take data entries all the same: a log full of
    # readings that say nothing looks exactly like a claim being worked on.
    subjects = header.get("subject", [])
    if not subjects:
        raise ValueError(f"{path} names no subject: no reading can reach the claim")

    today = today or date.today().isoformat()
    return {
        "id": path.stem,
        "path": path,
        "claim": claim,
        "status": status,
        "origin": origin,
        "subjects": subjects,
        "conditional_on": conditional_on,
        "verdict": header.get("verdict", [None])[0],
        "sought": _prose(sections.get("evidence sought", [])),
        "evidence": _log(sections.get("evidence", [])),
        "days_remaining": None
        if status == DECIDED
        else (date.fromisoformat(config.SUBMISSION_DATE) - date.fromisoformat(today)).days,
    }


def standing(
    hypotheses_dir: Path = config.HYPOTHESES_DIR, today: str | None = None
) -> list[dict]:
    """Every tracked hypothesis, by id."""
    return [read(record, today) for record in sorted(hypotheses_dir.glob("*.md"))]


def record_path(hypothesis_id: str, hypotheses_dir: Path = config.HYPOTHESES_DIR) -> Path:
    """Where a record lives. A record's id is the name of its file and nothing
    else, so the two cannot come to disagree."""
    return hypotheses_dir / f"{hypothesis_id}.md"


def rule(
    hypothesis_id: str,
    status: str,
    verdict: str,
    hypotheses_dir: Path = config.HYPOTHESES_DIR,
    today: str | None = None,
) -> dict:
    """Rule on a record: how the evidence came out, and what the 75 does about it.

    The two are separate answers. The status is what the argument reached, and
    the verdict is the decision the pilot took, which every record gets whether
    or not the evidence settled anything: a claim nobody ruled on is a slot
    decided by default, and inconclusive-keep-current is a decision.

    The claim and the log are untouched. A verdict with the argument for it
    thrown away is a decision that cannot be revisited when the meta moves.
    """
    if status not in STATUSES:
        raise ValueError(f"{status!r} is none of {STATUSES}")

    ruled = record_path(hypothesis_id, hypotheses_dir)
    # The header is what the engine acts on and the sections are the pilot's, so
    # the rewrite stops at the first of them.
    head, marked, body = ruled.read_text(encoding="utf-8").partition(f"\n{SECTION_MARK}")
    kept = [
        line
        for line in head.splitlines()
        if line.partition(":")[0].strip().lower() not in RULED
    ]
    while kept and not kept[-1].strip():
        kept.pop()
    # The verdict is one header line, so it is written as one: broken over two,
    # the second half would read back as a header key nothing knows and half the
    # pilot's decision would be gone with nothing saying so.
    kept += [f"status: {status}", f"verdict: {' '.join(verdict.split())}"]
    text = "\n".join(kept) + "\n" + (marked + body if marked else "")

    partial = ruled.with_suffix(".partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(ruled)
    return read(ruled, today)


def _readings(
    subjects: list[str], db_path: Path, reference_dir: Path
) -> tuple[str, int, list[dict]]:
    """What the pilot's own camp registered of each subject, and over how many.

    The population is the reference list's camp, in the challenge stratum, over
    the fresh window, for the reason the slot audit reads the same three: a
    configuration of the 75 is only ever answerable to the camp that could have
    registered it, in the stratum a tournament list has to hold up in, as it
    stands now. A share over any other three is a number no population reported.

    Every configuration of the subject the camp is currently on gets a line,
    ordered by how much of the camp went to it, because a hypothesis about where
    a copy goes is a question about which of them the camp chose. One it has
    stopped registering is not among them: the entry says what the camp did on
    the day it was read, and the deltas beside the surviving configurations are
    where a configuration being abandoned shows up. A subject with no line at
    all is the strongest such reading, and the record says so in those words.
    """
    belongs = camp(reference.current(reference_dir).mainboard)

    def camped(rows: list[dict]) -> list[dict]:
        return [row for row in rows if (row["camp"], row["stratum"]) == (belongs, CHALLENGE_CLASS)]

    # The deck-level table is only asked for where a record argues about it: a
    # land count is read exactly as a card's configuration is, off the same
    # camp, stratum and windows, and the two differ only in what names a row.
    cards = camped(adoption(db_path))
    deck = camped(land_counts(db_path)) if LANDS in subjects else []
    population = next(iter(cards or deck), {}).get("fresh_population", 0)

    readings = []
    for subject in subjects:
        taken = (
            [(str(row["lands"]), row) for row in deck]
            if subject == LANDS
            else [(f"{row['main']}/{row['side']}", row) for row in cards if row["card"] == subject]
        )
        readings += [
            {
                "subject": subject,
                "configuration": configuration,
                "adoption": row["fresh_adoption"],
                "tilt": row["fresh_tilt"],
                "delta": row["delta"],
            }
            for configuration, row in sorted(
                (pair for pair in taken if pair[1]["fresh_adoption"]),
                key=lambda pair: (-pair[1]["fresh_adoption"], pair[0]),
            )
        ]
    return belongs, population, readings


def _flagged(subjects: list[str], belongs: str, db_path: Path) -> list[dict]:
    """What the flag layer has raised about the subjects, in the pilot's camp.

    A share is a headcount and says nothing about how the camp came to it, which
    is the whole of what the flags know: that the field arrived on a
    configuration in a fortnight behind one finish, that the card is barely in
    the pool, that the adoption is one pilot's habit. So they are appended
    beside the numbers rather than left for the reader to go and look up, and a
    hyped configuration carries the caveat that its adoption is not evidence
    about the card.

    Raised in another camp, a flag is about another population and is no
    evidence here. Matched on the card and not on the configuration, because
    what a flag says about a card bears on every count of it the camp registered.

    A breakthrough flag is a list rather than a configuration and names no card,
    so it never matches: what it says is about a 75 somebody registered, and the
    reading that belongs beside a claim about one slot is the flag layer's
    verdict on that slot. Only a hype flag carries a caveat, the others
    classifying a share rather than qualifying it.
    """
    return [
        {
            "kind": flag["kind"],
            "card": flag["card"],
            "configuration": f"{flag['main']}/{flag['side']}",
            "state": flag.get("state"),
            # When the engine first said so, which the log needs for the reason
            # the mirror reading carries its own two terms: an episode from six
            # weeks ago and one raised this week are different evidence, and a
            # permanent entry cannot say which without the day on it.
            "raised": flag["first_seen"],
            "caveat": HYPE_CAVEAT if flag["kind"] == HYPE else None,
        }
        for flag in ledger.load(db_path)
        if flag.get("card") in subjects and flag["camp"] == belongs
    ]


def _rendered(entry: dict) -> list[str]:
    """One entry as the record carries it: the day, the source, and what it said.

    A data entry names the population before its numbers, because a share whose
    camp, stratum and window are not on the page is a figure the reader cannot
    check. A pilot's entry is his note and nothing else.
    """
    lines = [f"### {entry['on']} {entry['source']}", ""]
    if entry["note"]:
        lines.append(entry["note"])
    if entry["source"] != DATA:
        return lines

    lines.append(
        f"{entry['camp']} camp, {entry['stratum']},"
        f" {entry['population']} list(s) in the fresh window."
    )
    for reading in entry["readings"]:
        tilt = "" if reading["tilt"] is None else f", tilt {reading['tilt']:+.2f}"
        delta = "" if reading["delta"] is None else f", delta {reading['delta']:+.2f}"
        lines.append(
            f"{reading['subject']} {reading['configuration']}:"
            f" {reading['adoption']:.0%} of the camp{tilt}{delta}"
        )
    for subject in entry["silent"]:
        lines.append(f"{subject}: the camp registered none in the fresh window.")
    for subject in entry["unknown"]:
        lines.append(
            f"{subject}: the archetype's history has never registered it,"
            " so it is a card outside the pool or a name typed wrong."
        )
    for flag in entry["flags"]:
        state = f" ({flag['state']})" if flag["state"] else ""
        caveat = f": {flag['caveat']}" if flag["caveat"] else ""
        lines.append(
            f"{flag['kind']} flag on {flag['card']} {flag['configuration']}{state},"
            f" raised {flag['raised']}{caveat}."
        )
    if entry["mirror"]:
        mirror = entry["mirror"]
        lines.append(
            f"mirror {mirror['share']:.1%} of the field,"
            f" read {mirror['captured_on']} over {mirror['window_days']} days."
        )
    if entry["unconditioned"]:
        lines.append(f"no {MIRROR} reading stood on this day: the condition went unread.")
    return lines


def _appended(text: str, block: list[str]) -> str:
    """A record with one entry added to the end of its log.

    The end of the log and the end of the file are not the same place. A record
    may carry sections written after the log, and an entry put past them is on
    disk and out of the log: it would not read back, would not print, and
    nothing would say it had gone. So the entry goes at the last line of the
    evidence section and the rest of the record closes over it unchanged.

    The heading is matched as a whole line, `## Evidence sought` being the
    section a record opens with and the one this is a prefix of. A record that
    has no log yet gets one opened here, which is why a fresh record carries no
    empty heading: a section with nothing under it is not a log.
    """
    lines = text.splitlines()
    if EVIDENCE_HEADING not in lines:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", EVIDENCE_HEADING]

    opened = lines.index(EVIDENCE_HEADING) + 1
    following = [i for i, line in enumerate(lines[opened:], opened) if line.startswith(SECTION_MARK)]
    end = following[0] if following else len(lines)
    while end > opened and not lines[end - 1].strip():
        end -= 1

    rest = lines[end:]
    return "\n".join([*lines[:end], "", *block, *(["", *rest] if rest else [])]) + "\n"


def evidence(
    hypothesis_id: str,
    source: str,
    note: str | None = None,
    on: str | None = None,
    db_path: Path = config.DB_PATH,
    hypotheses_dir: Path = config.HYPOTHESES_DIR,
    reference_dir: Path = config.REFERENCE_DIR,
) -> dict:
    """Append one dated entry to a record's log, and say what it says.

    The three sources are one call because they are one log: what the camp
    registered, what the pilot found playing it, and what he judged all bear on
    the same claim, and a data entry that outranked the other two would be the
    engine deciding the 75. A data entry is the run's to write, so it takes its
    numbers from the store rather than a note; the other two are the pilot's,
    and his note is the whole of what they carry.

    The 75 is read for the one thing a data entry needs of it, which is the camp
    it belongs to: a configuration is only answerable to the population that
    could have registered it.
    """
    if source not in SOURCES:
        raise ValueError(f"{source!r} is none of {SOURCES}")
    # A pilot's entry carries his note and nothing else, so without one it is a
    # dated line saying that something happened, in a log with no way to take it
    # back. A data entry has the store to speak for it.
    if source != DATA and not (note and note.strip()):
        raise ValueError(f"a {source} entry is the pilot's note: there is none here to file")

    on = on or date.today().isoformat()
    # Every reading the log joins to compares dates as text, so `2026-8-1`
    # sorting before `2026-08-07` would attach the mirror share of a week later
    # to an entry claiming the earlier day. The same hazard `meta.ingest` names.
    date.fromisoformat(on)

    logged = record_path(hypothesis_id, hypotheses_dir)
    record = read(logged)
    entry = {
        "on": on,
        "source": source,
        "note": note,
        "camp": None,
        "stratum": None,
        "population": None,
        "readings": [],
        "silent": [],
        "unknown": [],
        "flags": [],
        "mirror": None,
        "unconditioned": False,
    }
    if source == DATA:
        belongs, population, readings = _readings(record["subjects"], db_path, reference_dir)
        spoken = {reading["subject"] for reading in readings}
        # A subject with no configuration is two different readings, and the
        # pool is what tells them apart: a card the archetype plays and this
        # camp is currently off is the camp having gone elsewhere, and a name no
        # list has ever carried is not a finding at all.
        known = card_pool(db_path) | {LANDS}
        quiet = [s for s in record["subjects"] if s not in spoken]
        # The mirror is read as of the day the entry is dated, which is the
        # reading that stood when the configurations beside it were taken, and
        # it comes back whole so a stale answer can be told from a fresh one.
        # Where the history does not reach back that far there is no reading to
        # condition on, and the entry says so: a conditional claim quietly
        # served its unconditional half is the join going missing unnoticed.
        mirror = mirror_share(entry["on"], db_path) if record["conditional_on"] == MIRROR else None
        entry |= {
            "camp": belongs,
            "stratum": CHALLENGE_CLASS,
            "population": population,
            "readings": readings,
            "silent": [s for s in quiet if s in known],
            "unknown": [s for s in quiet if s not in known],
            "flags": _flagged(record["subjects"], belongs, db_path),
            "mirror": mirror,
            "unconditioned": bool(record["conditional_on"]) and mirror is None,
        }

    text = _appended(logged.read_text(encoding="utf-8"), _rendered(entry))

    # Landed whole or not at all, as every capture in this engine is: a log half
    # written is an argument with a reading missing out of the middle of it.
    partial = logged.with_suffix(".partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(logged)
    return entry
