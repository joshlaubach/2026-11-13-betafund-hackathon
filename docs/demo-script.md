# Demo script (2 minutes)

Rewritten 2026-11-13 for the 4:00 PM Pacific slot. This replaces the earlier script and is linked from the README. Target: 2:00 on camera. Left column: what you say. Right column: what you do on screen. Rehearse it twice, once with wifi off.

## Before you record

- Plugged in. `docker compose up -d --wait`, then open http://localhost:3000 and reload once.
- Open **Settings** from the top bar. Set **Where marks come from** to **Saved replay (works offline)**. Close it.
- Have `images/01-drone-mistake.jpeg` ready, unmodified.
- Rehearse once to learn the right answer to the first streak problem.
- Backup: a screen recording of one full run.

## The script

| Time | You say | You do |
|---|---|---|
| 0:00 to 0:15 | "Echo turns a handwritten calculus mistake into verified practice on the exact concept the student missed." | Show the empty page. |
| 0:15 to 0:40 | "This is a photo of a finished drone worksheet. Part (b) is wrong. The math program checked it, not the AI, and the page says so." | Drag `01-drone-mistake.jpeg` onto the dropzone. Click **Analyze worksheet**. When part (b) appears, point at **Incorrect** and **Echo verified**. |
| 0:40 to 1:05 | "The student wrote $6 - e^5$. SymPy computed $4 + e^{-5}$ and compared. Now I'll practice this exact skill." | Click **Start streak** on part (b). Point at the progress bar and the **Echo-checked** label on the first problem. |
| 1:05 to 1:20 | "Right answers fill the bar. A wrong answer resets it, but the practice keeps going." | Answer the first problem correctly and click **Check answer**; the bar moves to 1 of 5. Answer one wrong on purpose and click **Check answer**; the bar resets and a new problem appears. |
| 1:20 to 1:40 | "I'm stuck, so I'll ask the tutor. It gives me one step and a question, not the full answer." | Click **Ask the tutor** and type "Explain how to find total distance". Point at the note under the reply: offline, from Echo's verified bank examples. |
| 1:40 to 1:50 | "If I want the whole example, I can ask for it. Every step comes from a verified problem." | Click **Show a worked example**. Let the steps show. |
| 1:50 to 2:00 | "AI can misread handwriting, so every mark shows what Echo read and how sure it was, apart from the math. Echo never claims more than it checked." | Open **How this was checked** on a wrong answer, then close the recording. |

## If something fails

| Problem | What to do |
|---|---|
| Wifi or model down | Replay mode needs neither. Stay in replay. |
| Page will not load | `docker compose up -d --wait`, wait 20 seconds, reload. |
| No saved reading for the photo | You uploaded a different file. Use `01-drone-mistake.jpeg`, unmodified. |
| Everything fails | Play the backup recording and narrate it. |

## Do not claim

- Streak celebration or confetti: not on `main`.
- Math rendering fixes beyond what the page shows now: not on `main`.
- Live generation of new problems: problems are generated ahead of time and saved. The app never asks the model for a new problem during the demo.
- That every topic has Echo-checked problems. Only net change, chain rule and quotient rule do. Other topics show bank problems labeled "bank-verified, not Echo-checked".

## Questions you may get

| Question | Answer |
|---|---|
| "Is this RAG?" | The tutor searches Echo's verified bank (BM25 with topic filters) and must cite the ids of the examples it used. Marks are not RAG: SymPy computes them. |
| "Where do the new problems come from?" | A model proposes an answer, then writes a problem for it. SymPy verifies the problem, and only verified problems are saved. A human has not reviewed them. |
| "What can it not do?" | Parametric curves, graphs and prose answers are AI judgment only, and labeled that way. |
| "Is student data stored?" | Photos stay in memory and are not saved. Location data is stripped on upload. Saved replays hold only text. |
