---
name: mtg-heuristics
description: Capture and maintain HEURISTICS.md. Use whenever Alejandro states MTG knowledge from play (deckbuilding, matchups, event structure, how to read the data), whenever the agent wants to propose a heuristic of its own, whenever evidence contradicts an adopted entry, and at session start to triage open candidates.
---

# MTG Heuristics

`HEURISTICS.md` holds pilot knowledge that the data cannot yield: things
Alejandro knows from playing the deck, which decide how the numbers are read.
It loads at session start, so what lands in it steers every later analysis.
That is the whole reason for the gate below being asymmetric.

Two lanes, and which lane a heuristic arrives in decides everything about how
it is written.

## Lane 1: pilot-stated. No gate.

Alejandro states it, it goes in. Now, in the session it was said, not at the
end and not after it recurs. Expert knowledge earned over years of play does
not need a recurrence gate; asking it to repeat itself is just losing it.

A statement qualifies when it is knowledge about Magic or about reading the
stream that would still be true next session. "Top-16 is the real cut" is a
heuristic. "Use 14 days for this query" is an instruction for right now.

Write it into the main body under the section it belongs to, in the file's
format. If no existing section fits, open one rather than forcing the entry
into the nearest wrong home:

```markdown
**The claim, stated as a claim** (2026-08-07):
Why it holds, in Alejandro's terms. Two or three lines.
*Applies*: what changes in the analysis because of it, concretely enough that a
future session can act on it without asking.
```

The *Applies* line is the part that does the work. A heuristic with no *Applies*
line is a note, and notes get read past. If Alejandro states the knowledge but
not its consequence, propose the *Applies* line back to him in the same breath
as confirming the capture, and let him correct it.

**Duplicates update in place.** Before writing, read the existing entries.
If one already covers this ground, sharpen that entry rather than appending a
second: fold in what is new, restate it once, and move the date to today. Two
entries saying nearly the same thing is how a file starts getting skimmed.

Say what was captured. Do not commit; leave it in the tree for Alejandro to
read as a diff.

## Lane 2: agent-proposed. Always gated.

Anything the agent works out for itself is a candidate, never adopted
knowledge, however convincing the evidence looks. The file is pilot knowledge.
An agent inference that writes itself into the main body is the engine feeding
its own guesses back to itself as expertise, which is the exact failure this
project exists to avoid.

Candidates come from three places:

- a pattern in the data that suggests a rule of thumb,
- a behaviour observed repeatedly across sessions,
- evidence that contradicts an entry already adopted (see Revision below).

They go in the `## Proposed, awaiting pilot verdict` section at the foot of the
file, and nowhere else:

```markdown
**The candidate claim** (raised 2026-08-07, surfaced 0×):
Why it might hold.
*Evidence*: the concrete observation that raised it. Named events, counts,
dates, session moments. Specific enough that Alejandro can check it himself and
that a later session can re-run it.
*Applies if adopted*: what would change downstream.
```

`surfaced` counts the later sessions in which the candidate was actually put to
Alejandro for a verdict. Raising it is not one of them, so a new candidate is
written at `0×`.

**The evidence line is the gate.** A candidate that cannot point at specifics
is the generic slop these systems fill with, confident and useless. If the
evidence cannot be named, the candidate is not raised.

Raise sparingly. Most sessions produce none. A list of five candidates means
they were generated rather than found.

## Revision, and deletion

New evidence against an adopted entry does not license editing it. Adopted
entries change only by pilot verdict, the same as adoption. Raise it as a
candidate, phrased as the revision it is:

```markdown
**Revise: "League 5-0s are soft evidence"** (raised 2026-08-07, surfaced 0×):
What the entry says, and what the evidence suggests instead.
*Evidence*: ...
*Applies if adopted*: sharpen the entry to X / drop it entirely.
```

Sharpening an entry, narrowing its scope, and deleting it outright are all
valid outcomes, and the last one is the one most likely to get skipped.
**If `HEURISTICS.md` only ever grows, this skill is failing.** A heuristic that
has been contradicted and left standing is worse than no heuristic, because it
still loads at session start and still steers the analysis.

## Triage at session start

The file loads every session, so open candidates resurface on their own. Do not
let them sit unread. When candidates exist, put them to Alejandro once,
briefly, and carry on with what the session was for. Bump each one's `surfaced`
count as you do.

A verdict from Alejandro resolves a candidate three ways, and only he can give
one:

- **Accepted, new heuristic** → write it into the main body in the adopted
  format, dated today, with the why and the *Applies* line. Delete it from the
  proposed section.
- **Accepted, revision** → apply it to the entry it names and nowhere else,
  sharpening, narrowing, or deleting that entry, and move its date to today.
  A revision never becomes a second entry. Delete it from the proposed section.
- **Rejected** → delete it. No graveyard section; git holds the history.
- **No verdict** → it stays, with its count one higher.

**Expiry.** A candidate that has been surfaced three times without a verdict is
dropped, and say so when you drop it. Alejandro not ruling on it three times
running is itself the answer. Without this the proposed section becomes the
second place things go to be ignored.

## Report

Say what was captured, what was raised, what a verdict moved or deleted, and
what expired. Or that none of it happened, which is the common case.
