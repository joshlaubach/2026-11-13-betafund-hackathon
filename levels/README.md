# Echo Level Guesser — experimental baseline

This contribution estimates difficulty from the existing bank. It does not check
answer correctness or assign new authoritative ratings. All code, explanations,
outputs and deliverable names are English.

## What is implemented

- `LevelGuesser.estimate(topic, statement, key_latex)` returns a Level 1–4 estimate,
  five same-topic neighbor records, distances, vote counts, or an explicit abstention.
- A level needs a strict majority: at least 3 of the 5 neighbors. A 2–2–1 split
  abstains. Equal distances straddling the fifth/sixth neighbor boundary also
  abstain; this additional conservative rule avoids arbitrary ID-based decisions.
- `check_requested_level(..., requested_level)` additionally requires five usable
  reference rows at the requested level and returns `passes_requested_level`.
  Requested level never influences neighbor selection or votes.
- Exact statements and detected number variants are excluded as evidence for their
  own estimate. IDs remain scoped by topic.
- Bank eligibility reuses `scripts/audit_bank.py`; levels 5 and excluded rows are
  never references. Unsupported/oversized inputs abstain; no code or math text is
  evaluated, and no API key or AI call is needed.

## Important difference from the approved plan

**This is a baseline for review, not the completed PLAN.md level gate.** The plan
calls for expression node count, nesting, distinct functions and key size on typed
mathematical expressions. This adapter counts bounded LaTeX source tokens and
delimiter nesting as proxies. These features are affected by notation and miss
semantic mathematical complexity. Per-topic typed adapters are still needed.

The module has deliberately **not** been connected to `core.entry`, the AI drafter,
or the answer checker. This avoids silently rejecting otherwise valid problems
based on a weak experimental signal. No source bank, core checker or approved plan
has been edited. The API also does not enforce same-task/answer-type matching;
that belongs to the future per-topic adapters and existing planned pipeline.

## Run

From the Echo project root (Python 3.10+):

```sh
python scripts/evaluate_levels.py
python -m pytest tests/test_level_guesser.py -q
```

On the current Mac's Anaconda environment, the optional debugger plugin needs to
be disabled because its native readline module crashes:

```sh
.venv/bin/python -m pytest -p no:debugging tests/test_level_guesser.py -q
```

Open `levels/Echo_Level_Guesser_Evaluation.ipynb` for the executed walkthrough.
Full per-problem results and neighbor evidence are in
`build/level_guesser/evaluation.json`; predictions are also exported to CSV.

## Evaluation protocol

The feature definition and decision rules were fixed before the first evaluation;
no hyperparameters or labels were tuned against the held-out results.

Five folds are assigned by a deterministic hash of number-masked statement text.
All detected numeric variants and exact repeated statements share a fold, even
across topics. For each held-out fold, neighbors and feature standard deviations
come only from the other four folds. This blocks direct self-match and detected
number-variant leakage; undetected mathematical equivalents may still cross folds.

Both exact accuracy over **all test problems** (abstentions count as incorrect)
and exact accuracy **when an estimate is returned** are reported. Prediction
coverage and abstention reasons are separate. The comparison baseline chooses the
most common training label in each topic, breaking ties toward the lowest label.
Its performance is sensitive to the grouped split; it is not a universal chance
accuracy. A single fixed five-fold evaluation is not an independent final test.

Targets are one tutor's bank labels, not independently measured student difficulty.
No performance claim is made for new live AI drafts. Bank key size is a feature,
so a checker-verified key should be supplied; this estimator never validates it.

## Next steps for Josh

1. Review whether these simple features are useful enough before integration.
2. Add typed per-topic expression adapters and report their coverage separately.
3. Obtain additional independent difficulty ratings and a separate external test set.
4. Re-evaluate with the frozen protocol, then decide whether to gate, suggest a
   level for tutor review, or always fall back to the labeled bank.

## Recorded results for review

Evaluated 3,318 held-out bank problems across 86 topics:

- Returned an estimate for 1,459 problems (43.97% coverage).
- Correct on 746 returned estimates (51.13% exact accuracy among predictions).
- Abstained on 1,859 problems.
- Exact accuracy over all held-out problems: 22.48%.
- Within one level among returned estimates: 85.68%.

These results are too limited for a reliable automatic difficulty gate. No live
AI-generated problems were evaluated. Answer correctness is not checked here.

Reviewed snapshots:

- [Evaluation summary, confusion matrix and per-topic metrics](results/Evaluation_Summary.json)
- [Per-problem held-out predictions](results/Level_Predictions.csv)
- [Executed English notebook](Echo_Level_Guesser_Evaluation.ipynb)

The bank and audit script match the upload base `b6c400c`; the actual bank SHA-256
is retained in the summary. Rerun `python scripts/evaluate_levels.py` after any
bank change. This upload is Level Guesser only; it does not duplicate the Bank
Analysis contribution or change any core/app/server/UI/plan files.
