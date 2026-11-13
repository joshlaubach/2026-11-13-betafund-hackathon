# Echo bank analysis — teammate contribution

This adds analysis alongside Josh's existing code. It does not change the bank,
the approved plan, the math checker, or the existing app. No LLM or API key is used.

## Files, in plain English

- `scripts/analyze_bank.py`: reads the bank, reuses the current audit rules, and
  measures topic/level coverage, metadata, repeated statements and ID collisions.
  It also builds and actually runs negative tests for `power_rule` using the
  existing checker and corruptor.
- `analysis/Echo_Bank_Analysis.ipynb`: a fully English, step-by-step, executed notebook explaining the
  analysis. Open it in Cursor's notebook viewer, Jupyter or VS Code. Rerunning
  cells regenerates the data; the saved notebook already includes results.
- `analysis/render_report.py`: turns the measured JSON results into an offline,
  interactive HTML report with English explanations by default, searchable topic coverage,
  exclusions, duplicate candidates and a real negative-test example.
- `tests/test_bank_analysis.py`: checks the interpretation of zero-count cells,
  topic-scoped IDs, duplicates, enum metadata and the read-only CLI.

## Run from the Echo project root

Requires Python 3.10+. The existing pinned requirements are sufficient for the
analysis scripts. Notebook display additionally needs Jupyter/IPython; the
scripts themselves do not.

```sh
python -m pip install -r requirements-dev.txt
python scripts/analyze_bank.py
python analysis/render_report.py
python analysis/render_report.py --lang zh
python -m pytest tests/test_bank_analysis.py tests/test_audit_bank.py -q
```

Open `build/bank_analysis/report.html` (Chinese) or `build/bank_analysis/Echo_Bank_Analysis_Report.html` (English) in your browser. It works offline; all
report data is embedded, with no CDN or external AI calls. CSV and JSON links
work when their files stay beside the report. No web server is required.

For counts and metadata without installing the math dependencies:

```sh
python scripts/analyze_bank.py --skip-negative-tests
```

On this Mac, Anaconda Python 3.13's `readline` crashed when pytest loaded its
optional debugger. The tested workaround is to disable just that pytest plugin:

```sh
.venv/bin/python -m pytest -p no:debugging tests/test_bank_analysis.py tests/test_audit_bank.py -q
```

## Reproducibility and provenance

Analysis source snapshot: `joshlaubach/2026-11-13-betafund-hackathon` at
`bc58c8aef0daf55e566176436895ee707197e7bf`. The bank, audit and checker dependencies
are unchanged at the upload base `482b96613e68057bf46623a8dbb2c93af4c50451`.
This contribution is applied on top of that newer upstream commit, preserving
Josh's newer UI, server and grading changes. It includes bank analysis only.

The report records the SHA-256 of the actual bank bytes. Run again after any bank
change. Generated results live in the ignored `build/` folder. The executed
notebook and `analysis/results/` retain the reviewed snapshot results. Regenerate
outputs into `build/` after changing the bank; the checked-in results are not live. None of the
analysis edits `PLAN.md`, `CLAUDE.md`, `app/`, `core/` or the source bank.

## Interpretation limits

1. **Eligible is not fully verified.** Eligibility is exactly the heuristic in
   `scripts/audit_bank.py`. We reconciled counts to that script, but did not prove
   every question self-contained or every answer correct.
2. **Coverage is per topic AND level.** An empty level can coexist with a large
   total topic pool. A three-row pool is only a quantity threshold; it can still
   include duplicate tasks or the wrong confirmed answer type.
3. **Exact duplicates are textual.** Whitespace-normalized matching does not find
   every mathematically equivalent problem. Cross-topic reuse can be intentional.
   Different written answers may be equivalent; neither is automatically removed.
4. **Number-masked templates are review candidates.** Many intentionally share the
   same structure with different numbers. We do not count them as confirmed
   duplicates or exclude them from eligible counts.
5. **IDs must be scoped.** Use `(topic, id)`; a reused ID in two topics is not a
   duplicate key. Both metrics are measured separately.
6. **190 absent symbolic strings are enum answers in this snapshot.** They are
   informational metadata findings, not evidence of missing answer keys.
7. **Negative tests are narrow.** The 120 constructed wrong keys only exercise
   three existing mutations on 40 power-rule problems. This measures consistency
   and these error detections, not an error rate for new AI drafts or all calculus.
8. **Difficulty is inherited.** Levels were rated by one tutor. We do not train a
   predictor or independently validate those ratings.

## Suggested conversation with Josh

“I reused your existing audit and added topic-by-level coverage, duplicate review
candidates and an exported negative-test dataset. I did not edit your bank or
checker. Can we review the empty topic-level cells and `strategy::ST12/ST16` before
we choose how to handle insufficient pools in the interface?”

## Language versions

The primary `Echo_Bank_Analysis.ipynb` is fully English, including explanations and
executed output. The Chinese notebook is retained locally and is not part of this upload.
Python analysis code, comments and documentation are English. HTML presentation
strings live in separate `analysis/templates/report.en.html` and
`analysis/templates/report.zh.html` resources. The renderer defaults to English.

## Reviewed results included in this branch

- [Executed English notebook](Echo_Bank_Analysis.ipynb)
- [English HTML report](results/Echo_Bank_Analysis_Report.html): download and open
  locally; GitHub displays HTML source rather than executing the report.
- [Full analysis JSON](results/report.json)
- [Topic and level counts](results/topic_coverage.csv)
- [Coverage gaps](results/coverage_gaps.csv)
- [Repeated statement groups](results/exact_statement_groups.csv)
- [Constructed negative tests](results/negative_test_cases.csv)

Headline results: 3,510 total rows; 3,405 audit-eligible level 1–4 rows; 19 empty
topic-level cells; 11 repeated-statement groups (one within-topic, ten cross-topic).
Power-rule consistency tests: 40/40 original keys accepted, 120/120 constructed
wrong keys rejected. These are not proof of all-calculus correctness.
