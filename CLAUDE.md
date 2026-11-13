# Echo

Echo turns a photo of a calculus problem a student missed into up to three fresh practice problems of the same kind. Every AI-written problem is checked by a math program (SymPy) before a tutor sees it; where no checker exists yet, Echo shows verified bank problems labeled as not Echo-checked, or an unsupported notice when none are usable. Scope: all of Calculus I and II (90 bank topics, levels 1 to 4). Each topic gets its own verifier; a topic is labeled Echo-checked only after its verifier passes a gate against the problem bank, and every other topic serves bank problems labeled "bank-verified, not Echo-checked" when usable ones exist, and otherwise shows an unsupported notice. Integration by substitution is the first and deepest verifier. Built for the 2026-11-13 BetaFund hackathon.

The build plan is `PLAN.md`. The all-calculus version was approved by Codex (review 6, round 3), bound to SHA256 `d8268f20...77d0` (see `PLAN-REVIEW-LOG.md`). Any edit to `PLAN.md` voids the approval and needs a re-review. The earlier substitution-only version is superseded.

## Roles

- **The main session is the orchestrator.** It plans, writes briefs, and checks results. It does not do bulk work itself when a worker can do it.
- **Workers are subagents on Haiku**: `builder` (writes code to a brief) and `reviewer` (checks a diff against a brief), defined in `.claude/agents/`.

## Briefs

Every brief to a worker states:
1. **Goal:** one or two sentences.
2. **Files to read:** exact paths, including the relevant `PLAN.md` section.
3. **Done when:** a check that can be run or seen, such as a command and its expected output, a test name that must pass, or a file that must exist with given content.

A brief without a runnable or visible "Done when" is not ready to send.

## Accepting work

- Before accepting any worker's output, the orchestrator runs the worker's "Done when" check itself.
- If the check fails, send the work back to the worker with the exact failure output.
- Never pass a worker's report to the user unchecked. Report what the orchestrator itself ran and saw.

## Session routine

**Start of every session:** read `CLAUDE.md`, `docs/progress.md`, `docs/decisions.md`, and `docs/known-issues.md`.

**End of every session:**
1. Update `docs/progress.md`.
2. Add new decisions to `docs/decisions.md` and new gotchas to `docs/known-issues.md`.
3. Run the `reflect` skill: propose skill or `CLAUDE.md` edits with evidence from this session. The user approves each one before it is applied.

## Folder map

| Path | What it is |
|---|---|
| `CLAUDE.md` | This file: project summary, rules, folder map |
| `PLAN.md` | Build plan for all of Calculus I and II (approved; hash-bound; edits need re-review) |
| `PLAN-REVIEW-LOG.md` | Append-only Codex plan-review transcript |
| `README.md` | Public README (placeholder; written Friday 2:00 to 3:00) |
| `docs/verified_problems.json` | Pre-built bank of 3,510 verified problems in 90 topics; Echo uses the levels 1 to 4 problems that pass the audit (see `PLAN.md`) |
| `docs/progress.md` | What's done, in progress, and next |
| `docs/decisions.md` | Decisions with date and reason |
| `docs/known-issues.md` | Gotchas and open problems |
| `.claude/agents/builder.md` | Haiku worker: writes code to a brief, runs the check |
| `.claude/agents/reviewer.md` | Haiku worker: lists where a diff fails its brief |
| `.claude/skills/reflect/SKILL.md` | End-of-session reflection skill |
