# Teammate tasks (updated 2026-11-12, for demo day Friday 2026-11-13)

Written so anyone can follow it, with technical words explained where they first appear. Submission deadline: **4:00 PM Pacific**. Demos run 4:00 to 4:50 PM, 3 minutes each.

## Where Echo stands

Echo reads a photo of a finished calculus worksheet, marks each answer, shows which topics are weak, and writes new practice problems. Every mark says how it was checked.

- **Works now:** photo upload, reading, marking, the skill picture, recommendations, and practice problems, in a browser page backed by an API. Both run in Docker. About 1,050 automated tests pass.
- **How marks are made:** a math program (SymPy) computes the true answer for derivatives, limits, integrals, tangent lines, solution sets and more. The mark then says "Marked by Echo's checker." Anything SymPy cannot check is labeled "AI judgment only." Smudged or low-confidence readings are shown as "Not marked."
- **What Echo does not claim:** only one topic, the power rule, has Echo-checked generated problems. Every other topic shows bank problems labeled "bank-verified, not Echo-checked." AI marks can be wrong, and a misread photo gives a wrong mark.
- **Run it:** `docker compose up -d --wait`, then open http://localhost:3000. To work on the page without the API, run `cd ui && NEXT_PUBLIC_FIXTURES=1 npm run dev` (fake data, no key needed). The Docker defaults to replay mode: saved runs, no internet.
- **Demo photos:** `images/` holds nine photos with their location data removed (the drone sheet, an implicit-curve sheet, an edge-case sheet in clear, glare and dark light, a parametric sheet with stray work, a Greek exam that is not math, and a tiny photo).

## Words used below

| Word | Plain meaning |
|---|---|
| **Fixture mode** | The page showing made-up sample results, so you can work on how it looks without the API or a key. |
| **Replay** | A saved run of a real photo, played back with no internet. The page labels it "Saved replay." |
| **Verified mark** | A mark whose answer SymPy computed itself. The page says so on the mark. |
| **Edge case** | A photo built to trip Echo up (smudges, crossed-out answers, a non-math page). |
| **Brief** | A short written assignment saying what to build and how we will check it is done. |
| **"Done when"** | A check anyone can run to see whether the task is finished. |

## Tasks for tomorrow

### 1. Make the page look and feel right (most valuable)

- **In plain words:** the page works but has not had a design pass. The demo is judged on how it looks and how clear it is.
- **What to do:** open the page in fixture mode and look at it at laptop width and phone width. Fix what is unclear or cramped. Look at: the first screen, how verified marks differ from AI-only marks, the "Not marked" banner, and the practice problems. One focused pass, not a redesign.
- **Where:** `ui/app/page.tsx`, `ui/components/`, `ui/app/globals.css`. Colors and fonts are tokens at the top of `globals.css`.
- **Done when:** `cd ui && npx tsc --noEmit` is clean, `npx playwright test` passes (10 tests), and the page looks right at 375 pixels wide with no sideways scrolling.

### 2. Try to break it with real photos

- **In plain words:** photograph your own worksheet with planted mistakes, then run it through the page in live mode. Write down what Echo got right and wrong.
- **Ideas:** a crossed-out answer with a correction beside it, a right answer with wrong working, an answer in an unusual but equal form, a graph or table, two columns, a very large phone photo.
- **Done when:** a short table in `docs/edge-case-results.md`: the photo, what you wrote, what Echo marked, and whether that is right. Wrong marks are findings, not failures. Send them to the orchestrator rather than fixing the grading code.

### 3. Demo script and backup video

- **In plain words:** judges see a 3-minute live demo. We need a script and a recording in case the live run fails.
- **What to do:** run the demo from a saved replay with wifi off, at least twice. Write the script: start with one clean photo that gets verified marks, then show the honest case (a `3 ln x + C` answer marked "unsure", and a non-math photo producing the "could not mark anything" banner), then the practice problems. Record a screen video of one good run.
- **Done when:** a one-page script in `docs/demo-script.md` and a video file that plays without internet.

### 4. Read the README like a stranger

- **In plain words:** we are rewriting `README.md` tonight. Read it cold and note anything you could not follow.
- **Done when:** a list of the places you got stuck, sent to the orchestrator.

### 5. Stretch: topic coverage notes

- **In plain words:** only one topic has Echo-checked generated problems. A notebook that counts the bank's problems per topic and level shows which topics could be added next.
- **Done when:** a notebook that runs from a clean copy and prints counts per topic and level. They match the bank audit script's totals (3,510 problems, 3,405 eligible, 88 of 90 topics usable).

## Tasks to keep with the orchestrator and workers

- **The grading code and the gate** (`core/`, `scripts/gate_power_rule.py`). This is the heart of the claim "a math program checked this." A small mistake there quietly breaks the main promise, so changes go through a written brief and a review.
- **`core/input_boundary.py`.** The strict reader that turns text into math safely. It is security-sensitive.

## Working together

- **Separate folders.** Work in `ui/` and `docs/`. Two people should not edit the same file at once.
- **Do not push to `main`.** Push a branch and tell the orchestrator. Pushes to `main` are approved one at a time.
- **Never commit a key.** The API key lives in `.env`, which is ignored by git. Do not paste it into a file, a message, or a screenshot.
- **Photos.** Strip location data before adding any photo to the repo. Ask for the script.
