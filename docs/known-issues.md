# Known issues and gotchas

## Gotchas
- **Inline Python breaks in PowerShell.** `python -c "..."` with nested quotes gets mangled. Write a script file to the scratchpad and run `python -I script.py` instead.
- **`python -I -c` cannot import repo folders** (`core`, `scripts`, `app`) from the current directory. Add `sys.path.insert(0, <repo root>)` first, or test through pytest, which does it for you.
- **`export` is not a PowerShell command.** Use `$env:NAME = "value"` in PowerShell; `export NAME=value` only works in Git Bash.
- **claudex-loop runner path.** The runner is at `<plugin>/skills/claudex-loop/scripts/runner.py`, not `<plugin>/skills/scripts/runner.py`.
- **Editing PLAN.md voids its approval.** The approval is bound to the plan's hash. Check it with the runner's `check` mode before relying on it.
- **Nested repo.** `echo/` sits inside the `math-problem-generator` repo, which ignores it. Run git commands from inside `echo/`, or they hit the parent repo.
- **Bank ids are not unique.** 250 of the 3,510 problems share an id with a problem in another topic (for example `AE01` is both an `absolute_extrema` and an `alternating_error` problem). Every `(topic, id)` pair is unique, so key anything per problem on `(topic, id)`, never on `id` alone. `PLAN.md` quotes ids such as `MV01` and `C410-16` as examples; read them as ids within their named topic.
- **pytest prints hundreds of `pytest_asyncio` DeprecationWarnings.** They come from the installed environment, not from our code. Ignore them.
- **Test a migration's apply path, not just its dry run.** The first `--apply` of `scripts/reorg_app.py` crashed on a missing folder because only the dry run and the text rewriting had tests. It is now covered by an end-to-end test in a throwaway git repo. The rewrite also missed a path inside a longer string (`prog="python -m app.keys"`), so search for leftovers with a plain-text scan, not only structural checks.
- **Never call `safe_parse` (or any SymPy parse of hang-prone input like `9^9^9^9`) outside the sandbox.** It hangs the process. Use `app/sandbox.py`, which kills the child at the timeout.
- **git line endings.** `core.autocrlf` is on, so most working files are CRLF and the repository stores LF. A few files are LF in the working tree. Scripts that rewrite files must preserve each file's own style; `scripts/reorg_app.py` does.

## `app/` (code reused from the author's existing AI math tutor)
- **It does not match the approved plan's input limits.** It parses with SymPy's `parse_expr` behind a character whitelist (the plan says never eval-based parsing), allows 2,000 characters and depth 40 (plan: 200 and 20), skips the memory cap on Windows (plan: 512 MB), uses a 10-second sandbox timeout by default (`app/config.py`, plan: 5 seconds), and its audit checks use a 1e-7 tolerance (plan: 1e-9 relative). Probed: hostile input is rejected and `9^9^9^9` is killed by the sandbox timeout.
- **`core/input_boundary.py` is the plan-conformant reader, but it is not wired into `app/` yet.** The future drafting layer must call it on every AI draft and tutor edit before anything reaches `app/`.
- **`app/api/pipeline.py` and `app/api/main.py` do not import.** They need `catalog`, `verify`, `llm`, and `strategies`, which are not in the folder. The verifiers and samplers import fine. Echo has to build the drafting layer itself.
- **`app/templates/` and `app/llm/prompts/` do not exist** in the working tree or in git. The web UI (`app/api/main.py`) and the "blind solve" path in `app/shared/wordproblem.py` would fail at runtime if used. This predates the reorganization.
- **`app/calc2/parametric_polar.py` has leftovers:** a comment pointing at the missing `app/catalog/__init__.py` and a `VERIFIER` dict of old `"calc.<name>"` strings that nothing reads.
- **Verifier calling conventions trip scripts.** `verify_derivatives_power_rule` needs `at="x"` (not `None`) for the derivative function. Verifiers return `{"ok": False, "cause": ..., "reason": ...}` instead of raising, so always check `ok`. Limits and derivatives tasks get `stem` from `_topic_task`; do not pass it again.
- **The bank may come from these same verifiers**, so a gate "positive" test shows self-consistency, not independence.

## Open
- The gate script is not built. The audit script, the input boundary, and the reorganized `app/` are done; the next step is a gate pilot on three topics (`u_substitution`, one limits topic, one derivatives topic) behind a shared LaTeX-to-SymPy reader. Substitution is the hard one: its verifier needs the pair `g`, `R`, which the bank does not store.
- `README.md` is written for graders, but its status table and the "Running it" section still need to be brought up to date before submission.
- The plan's Friday schedule still treats coding as onsite work; retitling it needs a plan re-review, so batch it with any other plan change.
- Bank entry `C410-16` is labeled `u_substitution` but fails the plan's substitution rule, so the adapter excludes it. Others may do the same; the adapter's counts will show how many.
- Confirm with the organizer that "written beforehand" covers reusing code from an existing product (see `docs/decisions.md`).
