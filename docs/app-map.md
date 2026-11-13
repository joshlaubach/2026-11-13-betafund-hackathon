# Map of `app/`

## Orientation

- `app/` holds the checking code: the per-topic verifiers, the safe math reader, the sandbox that runs the checks in a child process, and the offline problem sources.
- The top level of `app/` holds the shared engine. `shared/` holds helpers used across topics, `calc1/` holds Calculus I topics, `calc2/` holds Calculus II topics, and `api/` holds a web layer that Echo does not use.
- The code is reused from the author's existing AI math tutor. A reorganizing script moved the files into these folders.
- Echo's own new code lives in `core/`, `scripts/`, and `tests/`, outside `app/`.
- File suffixes: `_checks.py` is an independent numeric re-check, `_samples.py` is an offline problem source, `_core.py` holds helpers shared by a family of topics, and `__init__.py` is an empty package marker.

## `app/` top level

| File | Role |
|---|---|
| `app/__init__.py` | Empty package marker. |
| `app/config.py` | Settings from the environment or `.env`: model, concurrency, engine, timeout, database. |
| `app/offline.py` | Offline engine: builds a verified problem with no model call, using the `SAMPLERS` registry. |
| `app/safe_parse.py` | Reads model-written math text into SymPy without `eval`, by rejecting bad input before parsing. |
| `app/sandbox.py` | Runs SymPy work in a child process that is killed when it runs past the timeout. |
| `app/worker.py` | Child-process entry point: reads one JSON job on stdin and runs the named task from `TASKS`. |

## `app/shared/`

| File | Role |
|---|---|
| `app/shared/__init__.py` | Empty package marker. |
| `app/shared/calculus_core.py` | Helpers for derivative and application verifiers: result format, numeric check, answer rule. |
| `app/shared/clean_answer.py` | No-calculator answer rule: the final answer must be a short exact form. |
| `app/shared/difficulty.py` | Provisional difficulty score (a guess, version v0) from the raw measures a verifier returns. |
| `app/shared/figure_labels.py` | Generated outlines (SVG path data) of the LaTeX labels used on figures. Do not edit by hand. |
| `app/shared/figures.py` | Builds figures for graph-reading problems from one JSON spec; the server alone makes the SVG. |
| `app/shared/function_pool.py` | Pool of elementary functions, each with its rule text, domain note and complexity weight. |
| `app/shared/graph_problems.py` | Graph-reading problems: the student gets a picture, not a formula. |
| `app/shared/integral_core.py` | Integration helpers: parsing, derivative check, definite and improper evaluation, hashing. |
| `app/shared/integral_finish.py` | Shared ending for integration topics after u-substitution: bounds, answer rule, `finish`. |
| `app/shared/wordproblem.py` | Word-problem pipeline: model writes the statement, server derives and checks the answer. |

## `app/calc1/` (Calculus I)

| File | Role |
|---|---|
| `app/calc1/__init__.py` | Empty package marker. |
| `app/calc1/applications.py` | Verifiers for graph-shape topics: critical numbers, extrema, monotonicity, concavity, sketching. |
| `app/calc1/applications_b.py` | Verifiers for modelling topics: linear approximation, L'Hopital, Newton's method, motion, marginal. |
| `app/calc1/applications_b_samples.py` | Offline problem source for the modelling topics in `applications_b.py`. |
| `app/calc1/applications_samples.py` | Offline problem source for the graph-shape topics in `applications.py`. |
| `app/calc1/derivative_advanced.py` | Verifiers for implicit, logarithmic, inverse-function and higher-order derivatives. |
| `app/calc1/derivative_advanced_samples.py` | Offline problem source for the topics in `derivative_advanced.py`. |
| `app/calc1/derivative_rules.py` | Verifiers for product, quotient and chain rules, and tangent and normal lines. |
| `app/calc1/derivative_rules_samples.py` | Offline problem source for the topics in `derivative_rules.py`. |
| `app/calc1/derivatives.py` | Verifiers for basic derivative topics; one entry point, `verify(stem, ...)`, run in the sandbox. |
| `app/calc1/derivatives_samples.py` | Offline problem source for the basic derivative topics. |
| `app/calc1/integral_applications.py` | Area and volume applications, derived and checked inside the sandbox. |
| `app/calc1/integral_applications_checks.py` | Independent numeric re-checks for area and volume problems. |
| `app/calc1/integral_applications_samples.py` | Offline structures for area and volume problems. |
| `app/calc1/integration_basics.py` | Verifiers for integration basics; called only by the sandbox worker. |
| `app/calc1/integration_basics_checks.py` | Independent numeric re-checks for integration-basics problems. |
| `app/calc1/integration_basics_samples.py` | Seeded offline replies for integration basics. |
| `app/calc1/limits.py` | Verifiers for limits and continuity; one entry point, `verify(stem, ...)`, run in the sandbox. |
| `app/calc1/limits_samples.py` | Offline problem source for limits and continuity. |
| `app/calc1/rates_optimization.py` | Related rates and optimization methods for the word-problem pipeline. |
| `app/calc1/rates_optimization_samples.py` | Offline related-rates and optimization word problems, written from templates. |
| `app/calc1/usub.py` | Verifies a u-substitution candidate (g, R, bounds) and derives the statement, answer and steps. |
| `app/calc1/usub_samples.py` | Offline u-substitution source for the calibration packet only; not registered in `app/offline.py`. |

## `app/calc2/` (Calculus II)

| File | Role |
|---|---|
| `app/calc2/__init__.py` | Empty package marker. |
| `app/calc2/arc_length.py` | Cartesian arc length for bounded, server-defined curve families. |
| `app/calc2/arc_length_checks.py` | Independent re-check of the generated Cartesian curve for arc length. |
| `app/calc2/arc_length_samples.py` | Offline structures for Cartesian arc length. |
| `app/calc2/by_parts.py` | Verifies an integration-by-parts candidate and derives what the student sees. |
| `app/calc2/by_parts_samples.py` | Offline by-parts problem source: tries model-style replies in a seeded order until one verifies. |
| `app/calc2/error_bounds.py` | Verifies a numerical-integration error-bound candidate and derives what is shown. |
| `app/calc2/improper.py` | Verifies an improper-integral candidate and derives what the student sees. |
| `app/calc2/improper_samples.py` | Offline improper-integral problem source, built from tables of integrands. |
| `app/calc2/parametric.py` | Parametric-curve topics: tangents, second derivatives, area, arc length, surface area. |
| `app/calc2/parametric_polar.py` | Verified parametric and polar problems; called only by the sandbox worker. |
| `app/calc2/parametric_polar_checks.py` | Packet audit for parametric and polar topics, using mpmath numerics instead of SymPy derivations. |
| `app/calc2/parametric_polar_samples.py` | Seeded offline pools for parametric and polar topics. |
| `app/calc2/partial_fractions.py` | Verifies a partial-fractions decomposition and derives what the student sees. |
| `app/calc2/partial_samples.py` | Offline partial-fractions problem source, built from the assigned axes. |
| `app/calc2/polar.py` | Polar-curve topics: slopes, area and arc length. |
| `app/calc2/power_series.py` | Verified power-series problems; called only by the sandbox worker. |
| `app/calc2/power_series_b.py` | Taylor, binomial, remainder and Euler-formula topics; dispatched by `power_series.py`. |
| `app/calc2/power_series_checks.py` | Independent numeric checks for power-series verifiers (mpmath only). |
| `app/calc2/power_series_core.py` | Exact power-series arithmetic: known series as fraction lists, and a matcher for functions of x. |
| `app/calc2/power_series_samples.py` | Seeded offline pools for power-series topics. |
| `app/calc2/pp_core.py` | Shared helpers for the parametric and polar verifiers; called only by the sandbox worker. |
| `app/calc2/rules.py` | Verifies a midpoint, trapezoid or Simpson candidate and derives what is shown. |
| `app/calc2/rules_samples.py` | Offline problem source for midpoint, trapezoid, Simpson and error-bound problems. |
| `app/calc2/sequences_series.py` | Verified sequence and first series-test problems; called only by the sandbox worker. |
| `app/calc2/sequences_series_checks.py` | Independent numeric checks for sequence and series verifiers. |
| `app/calc2/sequences_series_samples.py` | Seeded offline pools for sequences and first series tests. |
| `app/calc2/series_tests.py` | Verified series convergence-test problems; called only by the sandbox worker. |
| `app/calc2/series_tests_checks.py` | Independent numeric checks for series-test verifiers (mpmath only). |
| `app/calc2/series_tests_core.py` | Convergence-test derivations shared by the series-test verifiers and the radius of convergence. |
| `app/calc2/series_tests_samples.py` | Seeded offline pools for series-test topics. |
| `app/calc2/strategy.py` | Mixed integration: the model names the technique, and the server runs that technique's verifier. |
| `app/calc2/strategy_samples.py` | Offline mixed-strategy problem source. |
| `app/calc2/trig_samples.py` | Offline problem source for trig and hyperbolic integrals. |
| `app/calc2/trig_sub_samples.py` | Offline problem source for trig-substitution problems. |
| `app/calc2/trig_substitution.py` | Verifies a trig-substitution candidate and derives the worked solution. |
| `app/calc2/trigfam.py` | Trig and hyperbolic integrals: one engine, two function sets. |

## `app/api/` (not used by Echo)

Not used by Echo (accounts, database, web server; `app/api/main.py` and `app/api/pipeline.py` do not import because `catalog`, `verify`, `llm`, and `strategies` are missing).

| File | Role |
|---|---|
| `app/api/__init__.py` | Empty package marker. |
| `app/api/auth.py` | Invite codes, a daily quota per code, and a global daily spend cap. |
| `app/api/db.py` | Generation log (no user data); tables created at startup. |
| `app/api/keys.py` | Command-line tool to create, list and revoke invite codes. |
| `app/api/main.py` | FastAPI web app entry point. No module docstring; see the file. |
| `app/api/pipeline.py` | Request orchestration (catalog, slots, logging). Does not import yet; see Known gaps. |
| `app/api/schemas.py` | Request and response models for the web layer. No module docstring; see the file. |

## How the checkers are called

- **Sandbox.** `app/sandbox.py` runs each job in a new child process, `python -m app.worker`. The job goes in as JSON on stdin and the result comes back as JSON on stdout. The child is killed when it runs past `settings.sandbox_timeout_s`, which is 10 seconds by default in `app/config.py`.
- **Task registry.** `app/worker.py` builds the `TASKS` dict: 100 task names mapped to functions. Examples: `verify_usub`, `verify_by_parts`, `verify_limits_algebraic`, `verify_derivatives_product_rule`, and `verify_power_series_euler_formula`. Most verifier tasks are built from a topic module's `verify(stem, ...)` entry point, and the `audit_*` tasks call the `audit` function of a topic's `_checks.py` module.
- **Offline samplers.** `app/offline.py` builds the `SAMPLERS` dict, with 87 topics. A sampler proposes replies a good model would give, and each reply goes through the same verifier as a model reply, so the offline engine's output is checked the same way. u-substitution has no sampler and is LLM-only.

## Known gaps

Copied in substance from `docs/known-issues.md`:

- `app/` does not match the approved plan's input limits. Parsing uses SymPy's `parse_expr` behind a character whitelist, although the plan says never to use eval-based parsing. It allows 2,000 characters and depth 40 (the plan: 200 and 20), skips the memory cap on Windows (the plan: 512 MB), and its audit checks use a 1e-7 tolerance (the plan: 1e-9 relative).
- Probed: hostile input is rejected, and `9^9^9^9` is killed by the sandbox timeout. `docs/known-issues.md` says 5 seconds; `app/config.py` defaults to 10 seconds. Never call `safe_parse` on hang-prone input outside the sandbox.
- `app/api/pipeline.py` and `app/api/main.py` do not import. They need `catalog`, `verify`, `llm`, and `strategies`, which are not in the folder. The verifiers and samplers import fine.
- The bank may come from these same verifiers, so a gate "positive" test shows self-consistency, not independence.
- Bank entry C410-16 is labeled `u_substitution` but fails the plan's substitution rule, so the bank adapter excludes it. Other entries may do the same.
