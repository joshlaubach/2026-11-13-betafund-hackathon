# Demo script (3 minutes)

Drafted 2026-11-13 for the 4:00 PM Pacific demo slot. Rehearse it twice, once with wifi off.

## Before you walk up

- Laptop plugged in, `docker compose up -d --wait`, page open at http://localhost:3000.
- Pick **Saved replay (works offline)** in the dropdown. Say out loud that it is a saved run of a real photo; the page labels it too.
- Have `images/01-drone-mistake.jpeg` and `images/04-edge-cases-clear.jpeg` ready in a folder.
- Backup: a screen recording of one full run, and the screenshots in `docs/screens/`.

## The script

**0:00 to 0:20. What it is.**
"A teacher or student photographs a finished calculus worksheet. Echo reads it, marks every answer, shows which topics need work, and writes practice. The point is that every mark says exactly how it was checked."

**0:20 to 1:10. A worksheet with a planted mistake (drone photo).**
- Upload `01-drone-mistake.jpeg`, click **Read and mark worksheet**.
- Point at part (a): correct, **Verified mark**, "Marked by Echo's checker: SymPy computed the answer itself."
- Part (b): the student wrote 6 minus e to the 5. SymPy computed 4 plus e to the minus 5. Incorrect, and verified.
- "No human marked this, and the AI did not decide it. A math program computed the true answer and compared."

**1:10 to 1:55. The honest cases (edge-case sheet).**
- Upload `04-edge-cases-clear.jpeg`.
- Part (e): the student wrote "0 > x" and "x > 2" as two answers. Echo reads them as one set and marks it correct.
- Part (g): `3 ln x + C` is **Unsure**. "Echo says why: it only holds for x greater than 0; the answer should use the absolute value. It would rather say unsure than guess."
- Part (f), the limit: labeled **AI-graded, not verified by Echo**. "Where SymPy cannot check, Echo says so."

**1:55 to 2:25. Telling Echo what it could not read (second input type).**
- On part (g), type or speak: "three x times open paren x minus two close paren" or "derivative of x squared times e to the x".
- Show **Echo understood:**, then **Use this**. The part is graded and tagged **Corrected by you**.
- "Echo never grades a guess at what you meant. You confirm first. Voice uses the browser's speech recognition, so typing is the fallback."

**2:25 to 2:50. From marks to practice.**
- Scroll to **What to work on**: weakest topics first, in course order.
- Click **Make level 2 problems** on Power rule: "Echo-checked." Then one bank topic: "Problems come from the verified bank, not Echo-checked."
- "We only call a topic Echo-checked after it passes a gate: every genuine bank key accepted and every deliberately wrong key rejected. Today that is one topic, with two more that pass the same bar in a test."

**2:50 to 3:00. Close.**
"AI can misread handwriting, so every part shows what Echo read beside the photo. Echo's promise is not that it is always right. It is that it never claims more than it checked."

## If something fails

- **Wifi or model down:** replay mode needs neither. Stay in replay.
- **Page will not load:** `docker compose up -d --wait`, wait 20 seconds, reload.
- **Replay says no saved reading:** you uploaded a different file. Use the two files above, unmodified.
- **Mic button missing:** the browser has no speech recognition. Type instead.
- **Everything fails:** play the backup recording and narrate it.

## Questions you may get

- **"Is this RAG?"** No. Answers come from computing with SymPy, not from retrieving text. Echo looks up bank problems by exact match.
- **"What can it not do?"** Parametric curves, two-sided limits, graphs, and prose answers are AI judgment only and labeled that way. The `docs/review-grading.md` report lists what an independent review found.
- **"Is student data stored?"** Photos are never written to disk, and location data is stripped on upload. Saved replays hold only text and a hash.
