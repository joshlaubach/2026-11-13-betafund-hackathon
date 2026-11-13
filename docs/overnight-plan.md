# Overnight plan (Thursday 2026-11-12 night to Friday 2026-11-13)

Submission deadline: **Friday 4:00 PM Pacific**. Demos 4:00 to 4:50 PM, 3 minutes each.

## Rules for every agent

- **No pushes.** Nothing leaves the laptop until the user says so.
- **No commits by agents.** Agents leave changes in the working tree. The orchestrator reruns the checks itself, then commits.
- **No live model calls by agents.** Only the orchestrator runs live calls, and only to re-save replays after the code freeze.
- **Own your files.** Each lane edits only the files listed for it. If a change needs a file owned by another lane, stop and report.
- **Stop and report when blocked.** Do not guess around a failing check. Do not weaken a test to make it pass.
- **Honesty rules stay.** A label never claims more than the evidence. AI never overrides SymPy or the bank. The student's answer never reaches a blind solve. Unsure marks never count as verified.
- **No secrets.** Never print, copy, or commit the API key. `.env` stays ignored.

## Order

1. **Finish and verify** the two running builders (cross-check fix; photo privacy and browser downscale). Commit each after the orchestrator's own checks.
2. **Lane E (unsure reasons and clarify)** starts once the privacy builder has landed, because both change the page and server files.
3. **Lanes A, B, C** run in parallel with E where files do not overlap.
4. **Lane D (design pass)** starts after E, because E changes the page.
5. **Code freeze** when A, B and E have reported, or at 4:00 AM, whichever comes first. After the freeze nothing in `core/` changes except confirmed review fixes.
6. **After the freeze (orchestrator only):** triage review findings, delete the stale replay files, re-save the replays for the demo photos with live runs, replay each once, rebuild Docker, run the smoke test, commit.

## Lanes

| Lane | Who | Owns | Work | Done when |
|---|---|---|---|---|
| A. Checking | Claude builder | new `core/parametric.py`, new `scripts/gate_topics.py`, small hook in `core/sympy_task.py` | SymPy checks for parametric curves (dy/dx, d2y/dx2, tangent line, arc-length integral). Then the derivative-topic probe: run bank statements and keys through `check_derivative` per topic and report pass rates. | Tests pass, gate ENABLED, probe report in `build/` |
| B. Review | Codex, read-only | writes `docs/review-grading.md` only | Independent hunt for false "verified" and false "incorrect" marks in `core/sympy_task.py`, `equations.py`, `solution_sets.py`, `antiderivatives.py`, `solvers.py`, with reproducible inputs | A report the orchestrator can reproduce case by case |
| C. Docs | Codex | `README.md`, `docs/progress.md`, `docs/decisions.md`, `docs/known-issues.md` | Rewrite for the worksheet flow, the honesty rules, Docker, privacy, and known gaps | Every claim checked against code and test counts by the orchestrator |
| D. Design | Claude builder with the frontend-design skill | `ui/` styling and layout only, after E | Screenshots at laptop and phone width, critique, one focused pass. Then the "Practice what I missed" page with a print layout. | tsc clean, e2e passes, screenshots in `docs/screens/` |
| E. Reasons and clarify | Claude builder | `core/worksheet_types.py` (new field), `core/worksheet.py`, `core/sympy_task.py` (reason tagging), `server/`, `ui/` | See below | See below |

## Lane E in detail

**Step 1, reason codes.** Add `reason` to each unsure or not-marked grade: `reading` (could not read the writing), `format` (could not compare the forms), `disagreement` (independent solves disagree), `no_verdict` (a call failed or gave no answer), `rule` (a known rule such as a missing + C, a domain difference, or a rounded decimal). The page shows a short line per reason. `reading` and `no_verdict` offer an action: retake the photo, or Regrade. Only `disagreement` and `no_verdict` count as real doubt in the skill picture. Change the pinned test `test_set_crosscheck_unreadable_ai_reply_stays_unsure` so an unreadable AI reply on a solution-set part keeps SymPy's mark (a `format` case), and say so in the commit message.

**Step 2, retake one part.** A "Retake this part" action uses the single-photo reader (`/api/read-photo`) on a close-up and replaces that one row. The result is labeled as a close-up reading.

**Step 3, clarify by typing.** On a not-marked or unsure row a text box says "Tell Echo what this problem asks, or what you wrote." A cheap model turns plain words or math into LaTeX. Echo shows "Echo understood: ..." and the user must confirm before anything is graded. The mark is then labeled "Reading corrected by you". The text goes through `core/input_boundary.py` first. The call is capped, and it never changes a SymPy result. The correction shows beside the photo reading, never silently over it.

**Step 4, clarify by voice.** A microphone button fills the same text box using the browser's built-in speech recognition. It hides itself where the browser has none. Chrome sends the audio to Google, so the README must say so, and the typed box stays the fallback. Voice is the first thing cut if the night goes badly.

## Morning checklist

**The user:**
- Make the repo visible to judges.
- Record the demo video and rehearse once with wifi off, on the presenting laptop.
- Look at the page and judge the design.
- Approve any push.

**The orchestrator:**
- Report which lanes landed, which did not, and every check run.
- Replays re-saved from the final code and replayed once each.
- Docker rebuilt, smoke test passed.
- Update `docs/progress.md` at the end.

## If the night goes badly

Cut in this order: voice (E step 4), the "Practice what I missed" page, the derivative-topic probe, parametric curves. Do not cut: the cross-check fix, photo privacy and downscale, the re-saved replays, the Docker rebuild, the rehearsal.
