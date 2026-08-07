# deck-optimisation-hypothesis

## Session start

Read `CONTEXT.md` and `HEURISTICS.md` before the first analysis of a session. The glossary fixes the vocabulary every answer uses; the heuristics file carries the pilot knowledge that decides how the numbers are read. If its `Proposed, awaiting pilot verdict` section holds anything, run `mtg-heuristics` and triage through it before getting on with the session.

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues on `AlejandroFuentePinero/deck-optimisation-engine`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Heuristics capture

`HEURISTICS.md` at the repo root, maintained by the `mtg-heuristics` skill. See `.claude/skills/mtg-heuristics/SKILL.md`.
