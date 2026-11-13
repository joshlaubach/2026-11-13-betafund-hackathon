# Known issues and gotchas

## Gotchas
- **Inline Python breaks in PowerShell.** `python -c "..."` with nested quotes gets mangled. Write a script file to the scratchpad and run `python -I script.py` instead.
- **`export` is not a PowerShell command.** Use `$env:NAME = "value"` in PowerShell; `export NAME=value` only works in Git Bash.
- **claudex-loop runner path.** The runner is at `<plugin>/skills/claudex-loop/scripts/runner.py`, not `<plugin>/skills/scripts/runner.py`.
- **Editing PLAN.md voids its approval.** The approval is bound to the plan's hash. Check it with the runner's `check` mode before relying on it.
- **Nested repo.** `echo/` sits inside the `math-problem-generator` repo, which ignores it. Run git commands from inside `echo/`, or they hit the parent repo.

## Open
- `README.md` is a placeholder (a single character, "f").
- No checker or app code exists yet. The plan's approval covers its text only.
- The plan grew during review (checker contract, bank adapter, substitution rule) and may not fit tonight's 3.5 hours. Trimming it needs a re-review.
- Bank entry C410-16 is labeled `u_substitution` but fails the plan's substitution rule, so the adapter excludes it. Others may do the same; the adapter's counts will show how many.
