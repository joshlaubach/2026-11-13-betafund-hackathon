# Teammate tasks (updated 2026-11-13, demo day)

Written so anyone can follow it, with technical words explained where they first appear. Submission deadline: **4:00 PM Pacific today**. Demos run 4:00 to 4:50 PM, 3 minutes each. Do the tasks in order: each one makes the next safer.

## Where Echo stands this morning

Echo reads a photo of a finished calculus worksheet, marks each answer, shows which topics are weak, and then coaches the student through new practice problems with a built-in tutor. Every mark says how it was checked.

- **Works now:** photo upload, reading, marking, the skill picture, recommendations, practice problems you can answer and check, hints, the tutor, and "Ask Echo" on each marked part. The page and the API both run in Docker. All automated tests pass: 1,544 backend and 112 browser.
- **Changed this morning:**
  - The tutor panel used to be cut off at the bottom of the screen, hiding the box you type in. Fixed on laptop, tablet and phone sizes.
  - The tutor now asks a question first, then gives a hint, then the next step, then the full solution. Asking for a solution or an example still gets it straight away.
  - The tutor and Ask Echo no longer tell a student their answer is wrong unless a math program confirmed it. If they cannot tell, they say so and ask the student to check a step. (The marks table is unchanged: an AI-only mark still shows as Incorrect, labeled "AI-graded, not verified.")
  - If the AI service fails, the student sees a plain "could not answer just now" message with a Retry button, not a technical error.
- **Not done yet:** the Docker copy on the demo laptop has not been rebuilt with this morning's changes, the new tutor has not been tried against the real AI yet (the orchestrator does both), the demo script still describes the old tutor, there is no backup video, and nobody has tried the page on a real phone.
- **What Echo does not claim:** only one topic, the power rule, has Echo-checked generated problems. Every other topic shows bank problems labeled "bank-verified, not Echo-checked." AI marks can be wrong, and a misread photo gives a wrong mark. Parametric curves cannot be checked by a math program, so Echo shows those marks as AI-only.
- **Run it:** `docker compose up -d --wait`, then open http://localhost:3000. To work on the page without the API, run `cd ui && NEXT_PUBLIC_FIXTURES=1 npm run dev` (fake data, no key needed). The page offers three sources for marks: Live AI (needs internet and a key), Saved replay (no internet), and Scripted demo data.
- **Demo photos:** `images/` holds the demo photos with their location data removed. The script uses `01-drone-mistake.jpeg` and `04-edge-cases-clear.jpeg`.

## Words used below

| Word | Plain meaning |
|---|---|
| **Fixture mode** | The page showing made-up sample results, so you can work on how it looks without the API or a key. |
| **Replay** | A saved run of a real photo, played back with no internet. The page labels it "Saved replay." Only works for the exact photo it was saved from. |
| **Echo-checked / verified** | A mark whose answer a math program (SymPy) computed or compared with a verified key. |
| **Not verified** | An AI gave or judged the answer and no program confirmed it. The page says so on the mark. |
| **Socratic** | Teaching by asking a focused question first, instead of giving the answer. |
| **Edge case** | A photo built to trip Echo up (smudges, crossed-out answers, a non-math page). |
| **Done when** | A check anyone can run to see whether the task is finished. |

## Tasks for today

### 1. Fix the demo script's tutor beat, then rehearse it twice

- **In plain words:** `docs/demo-script.md` was written before this morning's tutor changes. The 0:55 to 1:30 beat and the "Why is my answer wrong?" line no longer behave the way the script says.
- **What is different now (in Saved replay, which the demo uses):**
  - Typing "Explain how to find total distance" gets one step of a similar example plus a question, not the whole worked example. To show the full example, click **Show a worked example** or type "show me a worked example".
  - The tutor will not say an answer is wrong unless a check confirmed it. After a wrong answer and **Check answer** says "Not yet", the tutor knows it was checked. Without a check it asks "what was your first step?" Reword the "Why is my answer wrong?" line so the demo shows the check first.
- **What to do:** run the script as written, note every place the page does something different, fix the script, then rehearse it twice with a timer. Do one rehearsal in Saved replay with wifi off.
- **Done when:** `docs/demo-script.md` matches what the page does, and the end of the file lists two timed run-throughs, each under 3:00, one with wifi off.

### 2. Record the backup video

- **In plain words:** if the live demo fails, we play a recording.
- **What to do:** after task 1, record one clean run on screen in Saved replay with wifi off.
- **Done when:** a video file that plays without internet, saved where the orchestrator can find it (not in `images/`, and not in git if it is large).

### 3. Check the page on a real phone

- **In plain words:** the tutor was tested at phone-sized windows on a laptop, but not on a real phone with its on-screen keyboard.
- **What to do:** on the laptop run `cd ui && NEXT_PUBLIC_FIXTURES=1 npm run dev -- -H 0.0.0.0`, then open `http://<the laptop's address>:3000` on a phone on the same wifi. Fixture mode only shows made-up data and never calls the API, so this is safe. Stop it afterward. Do not open the real API to the network: it has no login.
- **Check:** open the Tutor tab; tap the box and confirm the box and **Send** stay visible above the keyboard; send a few messages; rotate the phone; confirm there is no sideways scrolling.
- **Done when:** a short note to the orchestrator: phone model, browser, and pass or fail for each check.

### 4. Try to break the tutor and Ask Echo with real photos

- **In plain words:** photograph your own worksheet with planted mistakes, run it in live mode, then use **Ask Echo** and the tutor on the parts. Write down what Echo got right and wrong.
- **What to look for:** does it call an answer wrong when the mark says "not verified"? Does it mention SymPy, "the record", "AI judge" or similar without being asked? Does it repeat the same question? Does it give the full solution when asked? Ideas for photos: a crossed-out answer with a correction beside it, a right answer with wrong working, an answer in an unusual but equal form, a graph or table, a parametric curve, a very large phone photo.
- **Done when:** a short table in `docs/edge-case-results.md`: the photo, what you wrote, what Echo marked, what the tutor said, and whether that is right. Wrong marks and odd tutor replies are findings, not failures. Send them to the orchestrator rather than fixing the grading code.

### 5. Read the README like a stranger

- **In plain words:** `README.md` was rewritten this morning. Read it cold and note anything you could not follow, anything that is wrong, and anything a judge would ask about that it does not answer.
- **Done when:** a list of the places you got stuck, sent to the orchestrator.

### 6. Stretch: topic coverage notes

- **In plain words:** only one topic has Echo-checked generated problems. A notebook that counts the bank's problems per topic and level shows which topics could be added next.
- **Done when:** a notebook that runs from a clean copy and prints counts per topic and level. They match the bank audit script's totals (3,510 problems, 3,405 eligible, 88 of 90 topics usable).

## Tasks to keep with the orchestrator and workers

- **Rebuild the Docker copy and try the tutor against the real AI.** Both must happen before anyone rehearses on the demo laptop.
- **The grading code and the gate** (`core/`, `scripts/gate_power_rule.py`). This is the heart of the claim "a math program checked this." A small mistake there quietly breaks the main promise, so changes go through a written brief and a review.
- **`core/evidence.py`.** The one place that decides how sure the tutor may sound about an answer. It is what stops Echo from calling an unverified answer wrong. Changes need a brief and a review.
- **`core/input_boundary.py`.** The strict reader that turns text into math safely. It is security-sensitive.
- **Submission.** Making the repository visible to judges and completing the submission form before 4:00 PM.

## Working together

- **Separate folders.** Work in `ui/` and `docs/`. Two people should not edit the same file at once.
- **Do not push to `main`.** Push a branch and tell the orchestrator. Pushes to `main` are approved one at a time.
- **Never commit a key.** The API key lives in `.env`, which is ignored by git. Do not paste it into a file, a message, or a screenshot.
- **Photos.** Strip location data before adding any photo to the repo. Ask for the script.
