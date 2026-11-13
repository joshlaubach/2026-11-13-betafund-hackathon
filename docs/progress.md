# Progress

## 2026-11-12 (Thursday evening; deadline about 24 hours after 5:31 pm)

**Done and committed**
- Plan for all of Calculus I and II, approved by Codex (SHA256 `d8268f20...77d0`). Record in `PLAN-REVIEW-LOG.md`.
- Problem bank (3,510 problems, 90 topics) and the bank audit script (`scripts/audit_bank.py`).
- Strict input reader `core/input_boundary.py` and the LaTeX reader `core/latex_reader.py` (reads 2,537 of 2,767 bank answers correctly, 0 wrongly; the rest are refused, not guessed).
- Reused checking code in `app/`, sorted into `calc1/`, `calc2/`, `shared/`, `api/` (map in `docs/app-map.md`). Not wired in yet.
- First Echo-checked topic: `power_rule`. `core/derivative_checker.py` derives the answer with SymPy and compares on 10 non-grid points. Gate (`scripts/gate_power_rule.py`): 40 of 40 supported, 120 deliberately wrong keys all rejected, `GATE: ENABLED`. Demo: `scripts/demo_wrong_key.py`.
- Labeled bank fallback `core/bank_fallback.py`: a topic is labeled Echo-checked only when `build/gate_<topic>.json` says it passed and matches a hash of the current bank. Coverage today: 88 of 90 topics have usable bank problems (3,405 problems); 1 topic is Echo-checked. Demo: `scripts/demo_fallback.py`.
- Teammate task list: `docs/partner-tasks.md`.
- A reviewer pass found a wrong-key acceptance bug (sample points on a grid); fixed, and the bug now has a test.

**Not built yet**
- AI drafting layer (needs a model service and API key from the user).
- Photo reading and topic matching, level check, chat screens, worksheet, saved replay, backup video.
- README status table and "Running it" section are out of date.

**Next**
1. Drafting layer: the AI proposes a problem and key, the checker accepts or rejects, with an offline replay mode.
2. Chat screens (teammate, fake data first), then connect.
3. README status and "Running it" (run `python scripts/gate_power_rule.py` once first, because `build/` is not committed).
4. Replay, backup video, make the repository visible to judges.

**Notes**
- Gate result files are tied to a hash of `docs/verified_problems.json`; any edit to the bank (even line endings) needs the gate rerun.
- `\sqrt[n]{x}` at negative x reads as a complex root, so those sample points are skipped. Right keys can be refused there; wrong ones are never accepted.
- The gate shows the checker reproduces the bank's keys. The bank may come from similar verifiers, so this is consistency, not independent proof.
