# Progress

Submission deadline: Friday 2026-11-13, 4:00 PM Pacific.

## 2026-11-13 midday — tutor layout, Socratic tutoring, verification vs correctness

**Built** (commit `c7334ab`)

- **Tutor clipping fixed at the cause.** The docked tutor column was `100dvh` tall but started below the masthead, so its bottom and the composer hung off-screen at scroll 0. On desktop the masthead now lives inside the worksheet column and the tutor column spans the full viewport height. Phones get `interactive-widget=resizes-content`, a `visualViewport` keyboard inset (`--kb-inset`) and safe-area handling.
- **`core/evidence.py` is the one boundary between grading and tutoring.** `verification_of` (verified, unverified, unavailable), `stance_of` (confirmed, likely, or not known), `help_level` (ask, hint, step, solution) and `leaks_internals`. `Grade.verification` is a derived field, so saved grades gain it without a migration. Stored verdicts are unchanged.
- **Ask Echo and the tutor tutor from a stance, not the grading record.** The model no longer receives the record's explanation, reason or label. A mark that was not verified is never described as wrong. The first reply is a question, help gets more specific each round, and the full solution comes on request or after five rounds. A reply that uses grading vocabulary, or is empty or malformed, is replaced by guided questions. A service failure shows a plain message with Retry, and the technical cause goes to the log.
- **Regression caught and fixed before the demo.** The first version answered "Show me a worked example" and "Explain this topic" with another question. Explicit requests for an example, a solution or an explanation now get one.

**Verified** (2026-11-13, final code): backend `pytest` 1544 passed, 9 skipped, 0 failed (was 1468 passed, 9 skipped); browser `npx playwright test` 112 passed, 0 failed (was 104). The 8 new layout tests fail on the old layout (tutor bottom at 978px in a 900px viewport) and pass on the fix. Not verified: the new tutor against the real model (every test used a fake), and a real phone keyboard.

**Next:** rebuild the Docker images (the running copy is the old build), try the tutor in Live mode, update the demo script's tutor beat (it still describes the old behavior), rehearse twice with wifi off, record the backup video, make the repo visible to judges before 4:00 PM Pacific. Known limits are in `docs/known-issues.md` under "Tutor and verification".

## 2026-11-13 morning — learning loop, tutor, redesign

**Built**

- Practice workspace: type an answer, check it (SymPy compares with the bank's verified key at 10 sample points; numeric, not symbolic), reveal the bank's worked steps one at a time as hints, or the full solution. The key stays hidden until solved. Each check shows who checked, evidence, time, and limits. Routes `/api/practice/steps`, `/api/practice/check`.
- Echo tutor (`/api/tutor/chat`): BM25 retrieval over eligible bank problems with topic filters (24/26 relevance eval), context from the active problem, attempts, hints and worksheet tally; live replies must cite retrieved ids and are `grounded` only when they do; scripted no-AI replies in replay and fake. Validated structured actions (similar, harder, easier, practice set, hint, next step, solution, check, explain, worked example) drive real page operations.
- Ask Echo per row (read-only explanation of a mark), with plain-language method names.
- Redesign: Geist and Instrument Serif, the requested dark palette plus a light theme, theme toggle with no flash, docked resizable tutor on desktop and Worksheet/Tutor tabs on phones, drag-and-drop upload, preview with zoom/rotate/full screen, honest two-step analysis progress, statuses Echo verified / Bank confirmed / AI-graded, unverified / Unable to verify with glyphs, reading confidence shown apart from the math check, shared motion tokens with reduced-motion support. Difficulty levels are never shown.

**Fixed after review or real-page testing**

- Tutor: tag-stripping bypass, forged history lines, replies claiming verification, untruthful `grounded`, total-distance questions retrieving net-change examples, vague requests finding no example, inline "Step 1: … Step 2: …" now one step per line.
- Internal method ids no longer reach model prompts; snake_case words no longer render as math.

**Verified:** backend 1468 passed, 9 skipped; browser suite 104 of 104; four user journeys scripted against the Docker app at 1440, 820 and 390 px in light and dark, no console errors, no overflow.

**Known limits:** one difficulty dimension (the bank has one expert level); no streaming; only power_rule generates Echo verified problems; about a third of bank answers cannot be read by the checker (shown as Unable to verify); no axe/Lighthouse audit or real-device test; the worksheet column does not animate its width when the tutor opens.

## 2026-11-12 — current worksheet flow

**Built**

- The browser page accepts a finished worksheet photo. A live vision read returns questions, final answers, and shared setup. Replay uses a saved reading for the same photo. Fake mode uses scripted data.
- The grading route tries an eligible bank match, then SymPy computation, then blind AI solves or AI judgment. Low-confidence reads are not marked in live and fake grading. Each mark has a method label.
- SymPy routes cover supported derivatives, limits, values, definite and indefinite integrals, tangent lines, equations, and solution sets. A blind AI cross-check can confirm a computed mark or make it unsure.
- The page shows marks, a per-topic skill picture, ranked recommendations, practice problems, and a Regrade button. Live Regrade makes a fresh AI solve for AI marks. Replay and fake mode keep the mark.
- The `power_rule` gate is built into the API image. It is the only Echo-checked generated practice topic. Other usable topics serve labeled bank problems.
- Uploads pass through metadata stripping before reading. Echo's own code keeps image bytes in memory; replay files contain readings and grades. The API checks local Host and write Origin headers and caps request bodies. Compose publishes ports 8000 and 3000 on `127.0.0.1`.

**Next**

1. Add a way to correct an unclear reading before marking it. Typed correction is planned; voice is optional.
2. Check the final demo photos in live and replay mode. A replay needs a saved reading for that photo and saved grades to reproduce AI marks.
3. Rebuild and smoke-check the Docker demo, then rehearse before the submission deadline.

## 2026-11-12 — earlier foundation

- The Calculus I and II bank, bank audit, strict reader, and `power_rule` practice checker were already in place. The gate enables the checker only when it matches the current bank hash.
- The drafting entry point supports live, replay, fake, and bank sources. Bank problems carry the label “bank-verified, not Echo-checked.”
- The checking code in `app/` was reused from the author's earlier math tutor. The worksheet marking routes use `core/` instead.

## 2026-11-13 (overnight)

- **Built:** reason codes for unsure marks (reading, format, disagreement, no_verdict, rule); clarify by typing or voice with a confirm step; photo metadata stripped on upload and large photos downscaled in the browser (live reads only); a banner when nothing on a photo can be marked.
- **Grading fixes from an independent Codex review** (`docs/review-grading.md`): a restricted definition ("for x>0") no longer grades by SymPy, a second ask after "and state" is no longer dropped, a contradictory chain of equal signs is unsure, a decimal where "exact" was asked is unsure, and a non-real interval endpoint no longer crashes.
- **Regression found and fixed on the real page:** replay needs the photo's original bytes, so the browser only re-encodes photos in live mode. A writing ask that mentions math ("Write a sentence explaining v(0)") is still stripped.
- **Replays saved** for five demo photos (`replay/`), each replayed once with no model calls.
- **Probe:** `scripts/gate_topics.py` shows `chain_rule` (95%) and `quotient_rule` (90%) would meet the `power_rule` bar; nothing has been enabled.
- **Next:** design pass, demo script and backup video, rehearsal with wifi off, make the repo visible to judges before 4:00 PM Pacific.

## 2026-11-13 — Bank analysis contribution

- Added the executed English `analysis/Echo_Bank_Analysis.ipynb`, `scripts/analyze_bank.py`, offline report renderer/templates, tests, and reviewed snapshot results under `analysis/results/`.
- Reuses existing bank-audit eligibility; no edits to bank keys, difficulty ratings, core checker, UI, server or approved plan. Level guesser is not included.
- Results reconcile to the existing audit: 3,510 rows; 3,450 in levels 1–4; 3,405 eligible; 45 excluded; 60 level-5 rows out of scope. 88 topics have eligible rows; 78 have at least three at every level; 19 topic-level cells are empty.
- Repeated statement text: 11 groups / 22 rows (one within-topic: `strategy::ST12/ST16`; ten cross-topic). Review candidates only, no deletions. 250 reused ID values involve 500 rows; no duplicate `(topic,id)` keys. All 190 absent SymPy strings belong to enum-answer rows.
- Power-rule consistency tests: 40/40 bank keys accepted and 120/120 constructed wrong keys rejected using the existing three mutations. Not independent proof or all-calculus accuracy.
- Validation: 92 relevant tests passed; 8 English notebook code cells executed. Browser report search/filter verified. The analyzed bank and audit/checker dependencies are unchanged at base `482b966`.

## 2026-11-13 — Experimental level-guesser contribution

- Added standalone `levels/guesser.py`, English README and executed notebook, `scripts/evaluate_levels.py`, 10 behavior tests, and recorded summary/prediction snapshots under `levels/results/`.
- Five nearest same-topic references, strict 3/5 majority, and explicit abstention for ambiguous votes, tied neighbor cutoffs, unsupported input or insufficient reference pools. Requested level never selects the winning label.
- Evaluation: fixed five-fold number-masked-statement-family holdout; scales and neighbors use training-fold references only. Tested 3,318 bank problems in 86 topics. Returned 1,459 estimates (43.97%); 746 correct (51.13% among returned estimates; 22.48% over all test problems); 1,859 abstentions. Targets are existing one-tutor ratings, not independent difficulty truth. No live AI-generated problems tested.
- Plan gap: bounded LaTeX source-token size/nesting are proxies, not the final typed semantic expression features. Typed per-topic and task/answer-type adapters remain to be built. Do not treat this as the completed PLAN.md level gate.
- Validation: 10 targeted tests passed; five notebook code cells executed. Source bank and audit script unchanged at upload base `b6c400c`.
- No changes to bank keys/ratings, core checker, drafting, UI/server or approved plan; no production integration. Bank Analysis is a separate contribution.
