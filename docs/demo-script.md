# Demo script (3 minutes)

Drafted 2026-11-13 for the 4:00 PM Pacific demo slot. Rehearse it twice, once with wifi off.

## Before you walk up

- Laptop plugged in, `docker compose up -d --wait`, page open at http://localhost:3000, light or dark theme as you prefer.
- Open **Marks come from** under the Analyze button and pick **Saved replay (works offline)**. Say out loud that it is a saved run of a real photo; the page labels it too.
- Have `images/01-drone-mistake.jpeg` and `images/04-edge-cases-clear.jpeg` ready in a folder.
- Backup: a screen recording of one full run, and the screenshots in `docs/screens/`.

## The script: one learning loop

**0:00 to 0:15. The line.**
"Echo turns a student's handwritten mistakes into verified, personalized practice, so they master the exact concept they missed."

**0:15 to 0:55. Read the photo and find the mistake (drone photo).**
- Drag `01-drone-mistake.jpeg` onto the dropzone. Zoom in once on the preview. Click **Analyze worksheet**; the two steps tick only when the server finishes each.
- Part (b): the student wrote $6 - e^5$; SymPy computed $4 + e^{-5}$. Badge **Echo verified**. Open **How this was checked**: the reading confidence is listed separately from the math check. "No human marked this and the AI did not decide it. A math program computed the answer and compared."

**0:55 to 1:30. Explain the misconception (tutor).**
- Under **What to work on**, click **Practice this topic** (Net change and total distance). On the first problem click **Ask the tutor**.
- Type "Explain how to find total distance". The tutor answers from a real worked example in Echo's bank, cites its id, and the steps add absolute values, not signed displacements. Point at the line under the reply: offline tutor, bank confirmed, no AI.

**1:30 to 2:15. Targeted practice, checked.**
- Type a wrong answer (for example `5`) and click **Check answer**: **Not yet**, with who checked it (SymPy against the bank's verified answer), the evidence, the time, and what the check does not prove. The key stays hidden.
- Click **Hint**: the first verified step appears. Ask the tutor "Why is my answer wrong?" and click **Try an easier problem**: a new set loads for the same topic. "The suggestion is an action, not a chat message: it calls Echo's problem service with a validated topic and level."

**2:15 to 2:45. The honest cases (edge-case sheet, optional if time).**
- Upload `04-edge-cases-clear.jpeg`. Part (g) `3 ln x + C` is **Unable to verify**: it only holds for $x > 0$. Part (f) is **AI-graded, unverified**. Open **Fix what Echo read** on a part to show typed or spoken correction.

**2:45 to 3:00. Close.**
"AI can misread handwriting, so every part shows what Echo read and how sure it was, apart from the math. Echo's promise is not that it is always right. It is that it never claims more than it checked."

## If something fails

- **Wifi or model down:** replay mode needs neither. Stay in replay.
- **Page will not load:** `docker compose up -d --wait`, wait 20 seconds, reload.
- **Replay says no saved reading:** you uploaded a different file. Use the two files above, unmodified.
- **Mic button missing:** the browser has no speech recognition. Type instead.
- **Everything fails:** play the backup recording and narrate it.

## Questions you may get

- **"Is this RAG?"** The tutor is: it retrieves worked examples from Echo's bank (BM25 with topic filters) and must cite the ids it used; "grounded" is true only when a cited id was retrieved. Marks are not RAG: SymPy computes them.
- **"Two difficulty dimensions?"** No. The bank has one expert level per problem; harder and easier move that level. Echo does not invent a second dimension.
- **"What can it not do?"** Parametric curves, two-sided limits, graphs, and prose answers are AI judgment only and labeled that way. The `docs/review-grading.md` report lists what an independent review found.
- **"Is student data stored?"** Photos are never written to disk, and location data is stripped on upload. Saved replays hold only text and a hash.
