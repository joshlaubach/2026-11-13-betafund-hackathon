# Known issues and gotchas

## Gotchas
- **Inline Python breaks in PowerShell.** `python -c "..."` with nested quotes gets mangled. Write a script file to the scratchpad and run `python -I script.py` instead.
- **`export` is not a PowerShell command.** Use `$env:NAME = "value"` in PowerShell; `export NAME=value` only works in Git Bash.
- **claudex-loop runner path.** The runner is at `<plugin>/skills/claudex-loop/scripts/runner.py`, not `<plugin>/skills/scripts/runner.py`.
- **Editing PLAN.md voids its approval.** The approval is bound to the plan's hash. Check it with the runner's `check` mode before relying on it.
- **Nested repo.** `echo/` sits inside the `math-problem-generator` repo, which ignores it. Run git commands from inside `echo/`, or they hit the parent repo.

- **Bank ids are not unique.** 250 of the 3,510 problems share an id with a problem in another topic (for example `AE01` is both an `absolute_extrema` and an `alternating_error` problem). Every `(topic, id)` pair is unique, so key anything per problem on `(topic, id)`, never on `id` alone. `PLAN.md` quotes ids such as `MV01` and `C410-16` as examples; read them as ids within their named topic. Found by the audit-script build.
- **pytest prints hundreds of `pytest_asyncio` DeprecationWarnings.** They come from the installed environment, not from our code. Ignore them.

- **`app/` does not match the approved plan's input limits.** It parses with SymPy's `parse_expr` behind a character whitelist (the plan says never eval-based parsing), allows 2,000 characters and depth 40 (plan: 200 and 20), skips the memory cap on Windows (plan: 512 MB), and its audit checks use a 1e-7 tolerance (plan: 1e-9 relative). Probed: hostile input is rejected and `9^9^9^9` is killed by the 5-second sandbox timeout. Never call `safe_parse` on hang-prone input outside the sandbox.
- **`app/pipeline.py` and `app/main.py` do not import.** They need `catalog`, `verify`, `llm`, and `strategies`, which are not in the folder. The verifiers and samplers import fine.
- **The bank may come from these same verifiers**, so a gate "positive" test shows self-consistency, not independence.

## Open
- `README.md` is a placeholder (a single character, "f").
- No checker or app code exists yet. The plan's approval covers its text only.
- The plan grew during review (checker contract, bank adapter, substitution rule) and may not fit tonight's 3.5 hours. Trimming it needs a re-review.
- Bank entry C410-16 is labeled `u_substitution` but fails the plan's substitution rule, so the adapter excludes it. Others may do the same; the adapter's counts will show how many.
