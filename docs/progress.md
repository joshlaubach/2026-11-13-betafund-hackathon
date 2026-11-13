# Progress

## 2026-11-12 (Thursday evening; deadline about 24 hours after 5:31 pm)

**Done and committed (pushed to GitHub through `1f6b890`)**
- Plan for all of Calculus I and II, approved by Codex (SHA256 `d8268f20...77d0`). Record in `PLAN-REVIEW-LOG.md`.
- Problem bank (3,510 problems, 90 topics) and the bank audit script (`scripts/audit_bank.py`). 3,405 problems at levels 1 to 4 are usable; 88 of 90 topics have at least one.
- Strict input reader `core/input_boundary.py` and the LaTeX reader `core/latex_reader.py` (reads 2,537 of 2,767 bank answers correctly, 0 wrongly; the other 230 are refused, not guessed).
- Reused checking code in `app/`, sorted into `calc1/`, `calc2/`, `shared/`, `api/` (map in `docs/app-map.md`). Not wired in yet.
- First Echo-checked topic: `power_rule`. `core/derivative_checker.py` derives the answer with SymPy and compares on 10 non-grid points (needs 6 usable). Gate (`scripts/gate_power_rule.py`): 40 of 40 supported, 120 deliberately wrong keys all rejected, `GATE: ENABLED`. Demo: `scripts/demo_wrong_key.py`.
- Labeled bank fallback `core/bank_fallback.py`. A topic counts as Echo-checked only when `build/gate_<topic>.json` says it passed and matches a hash of the current bank. Demo: `scripts/demo_fallback.py`.
- AI drafting layer `core/drafter.py` with live, replay and fake (scripted) sources. Live path used once with `claude-sonnet-5-5`: 5 drafts, 3 accepted, all hand-checked. Saved as `replay/power_rule_L2.json` (live) and `replay/power_rule_L2_fake.json` (scripted).
- Single entry point `core/entry.py`: `request_problems(topic, level, mode)`. Checker-accepted drafts first, any shortfall filled from the bank with the bank label, "unsupported" notice when nothing is usable, source failures fall back with a note. Demo: `scripts/demo_entry.py`. 560 tests pass, 9 skipped.
- `.env.example` added; `.env` (holds the real key) is git-ignored.
- Teammate task list: `docs/partner-tasks.md`.
- README status table and "Running it" brought up to date.
- `requirements.txt` (runtime) and `requirements-dev.txt` (adds pytest), pinned. Checked in a fresh virtual environment: 560 passed, 9 skipped. `app/api` needs `fastapi` and `sqlalchemy`, but Echo does not use that folder, so they are left out.

**Not built yet**
- Photo reading and topic matching, level check, chat screens, worksheet, backup video.
- Checkers for any topic other than `power_rule` (next candidates: limits `algebraic`, `u_substitution`).

**Next**
1. Chat screens (teammate, fake data first, built on `request_problems`). Teammate must be added as a repo collaborator.
2. One `python-reviewer` pass on `core/drafter.py` and `core/entry.py` (skipped so far to save rate limit).
3. A second Echo-checked topic, if time allows.
4. Backup video; make the repository visible to judges before the deadline; confirm the exact deadline time.

**Notes**
- Gate result files are tied to a hash of `docs/verified_problems.json`; any edit to the bank (even line endings) needs the gate rerun. `build/` is not committed, so run `python scripts/gate_power_rule.py` before any demo.
- `\sqrt[n]{x}` at negative x reads as a complex root, so those sample points are skipped. Right keys can be refused there; wrong ones are never accepted.
- The gate shows the checker reproduces the bank's keys and rejects corrupted ones. The bank may come from similar verifiers, so this is consistency, not independent proof.
- The live run produced three correct drafts, so the "wrong key rejected" moment in demos comes from the scripted fake run or from `demo_wrong_key.py`'s deliberately corrupted keys. Say so when presenting.
- The server-side refusal fallback for the model call is not enabled; the saved replay is the outage plan.
- The API key was pasted into a local `.env` during this session. Rotate it after the hackathon.
